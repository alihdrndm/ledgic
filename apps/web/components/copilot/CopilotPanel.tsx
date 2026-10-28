"use client";

import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useOptionalShell } from "@/components/shell/ShellContext";
import { MarkdownLite } from "./markdown";
import { CitationChip, type Citation } from "./CitationChip";
import "./copilot.css";

/** Pre-seeded questions (core copilot_cache is seeded with these exact strings). */
export const SUGGESTED_QUESTIONS = [
  "Why is PS-88214 on hold?",
  "What does clause 4.2 of the Protein Supplier agreement say about shrimp?",
  "What is our price-variance tolerance?",
  "Which exceptions are blocking payments right now?",
  "How is the touchless rate calculated?",
] as const;

const BYOK_KEY = "ledgic.copilot.byok";

interface Turn {
  id: number;
  question: string;
  answer: string;
  citations: Citation[];
  status: string | null;
  mode: "live" | "cached" | "retrieval_only" | null;
  model: string | null;
  error: string | null;
  done: boolean;
}

interface CopilotApi {
  open: (question?: string) => void;
  close: () => void;
  isOpen: boolean;
}

const CopilotContext = createContext<CopilotApi | null>(null);

export function useCopilot(): CopilotApi | null {
  return useContext(CopilotContext);
}

export interface CopilotProviderProps {
  /** Grounds answers on the current screen's record. */
  context?: { invoice_id?: string; exception_id?: string };
  children: ReactNode;
}

/**
 * Mounts the Ask Ledgic drawer for a screen and registers the ⌘K palette's "Ask Ledgic: <query>" row
 * (useShell().setAskAction) while mounted.
 */
export function CopilotProvider({ context, children }: CopilotProviderProps) {
  const shell = useOptionalShell();
  const [isOpen, setOpen] = useState(false);
  const [pending, setPending] = useState<{ q: string; seq: number } | null>(null);
  const seq = useRef(0);

  const open = useCallback((question?: string) => {
    setOpen(true);
    if (question && question.trim()) {
      seq.current += 1;
      setPending({ q: question.trim(), seq: seq.current });
    }
  }, []);
  const close = useCallback(() => setOpen(false), []);

  const setAskAction = shell?.setAskAction;
  useEffect(() => {
    if (!setAskAction) return;
    setAskAction({ label: "Ask Ledgic", onSelect: (q) => open(q) });
    return () => setAskAction(null);
  }, [setAskAction, open]);

  const api = useMemo(() => ({ open, close, isOpen }), [open, close, isOpen]);
  return (
    <CopilotContext.Provider value={api}>
      {children}
      <CopilotPanel open={isOpen} onClose={close} pending={pending} context={context} />
    </CopilotContext.Provider>
  );
}

/** Top-bar button that opens the drawer. */
export function AskLedgicButton() {
  const cp = useCopilot();
  if (!cp) return null;
  return (
    <button type="button" className="cp-ask-btn" onClick={() => cp.open()} aria-haspopup="dialog" aria-expanded={cp.isOpen}>
      <Sparkles size={14} strokeWidth={2} aria-hidden="true" />
      Ask Ledgic
    </button>
  );
}

function readByok(): string {
  try {
    return sessionStorage.getItem(BYOK_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeByok(v: string) {
  try {
    if (v) sessionStorage.setItem(BYOK_KEY, v);
    else sessionStorage.removeItem(BYOK_KEY);
  } catch {
    // storage unavailable — key stays in memory for this panel only
  }
}

const STEP_LABEL: Record<string, string> = {
  retrieving: "Searching contracts and policy…",
  calling_tool: "Looking up Ledgic data…",
  answering: "Writing the answer…",
};

function CopilotPanel({
  open,
  onClose,
  pending,
  context,
}: {
  open: boolean;
  onClose: () => void;
  pending: { q: string; seq: number } | null;
  context?: { invoice_id?: string; exception_id?: string };
}) {
  const shell = useOptionalShell();
  const titleId = useId();
  const inputId = useId();
  const byokId = useId();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [byok, setByok] = useState("");
  const [showByok, setShowByok] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const lastPending = useRef<number>(0);
  const turnSeq = useRef(0);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- sessionStorage is only readable after hydration
  useEffect(() => setByok(readByok()), []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const patch = useCallback((id: number, fn: (t: Turn) => Turn) => {
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const q = question.trim().slice(0, 500);
      if (!q || !shell) return;
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      turnSeq.current += 1;
      const id = turnSeq.current;
      setTurns((ts) => [
        ...ts,
        { id, question: q, answer: "", citations: [], status: "retrieving", mode: null, model: null, error: null, done: false },
      ]);
      setInput("");
      setBusy(true);
      try {
        const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "text/event-stream" };
        const key = readByok();
        if (key) headers["X-OpenAI-Key"] = key;
        const res = await fetch("/api/copilot", {
          method: "POST",
          headers,
          body: JSON.stringify({ org: shell.org.slug, question: q, context }),
          signal: ctrl.signal,
        });
        if (!res.body) throw new Error("No response body");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let finished = false;
        while (!finished) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx: number;
          while ((idx = buf.search(/\r?\n\r?\n/)) >= 0) {
            const raw = buf.slice(0, idx);
            buf = buf.slice(idx).replace(/^\r?\n\r?\n/, "");
            const ev = parseEvent(raw);
            if (!ev) continue;
            finished = handleEvent(id, ev, patch) || finished;
          }
        }
        if (buf.trim()) {
          const ev = parseEvent(buf);
          if (ev) handleEvent(id, ev, patch);
        }
        patch(id, (t) => ({ ...t, done: true, status: null }));
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        patch(id, (t) => ({ ...t, done: true, status: null, error: "Ask Ledgic couldn't be reached. Try again in a moment." }));
      } finally {
        if (abortRef.current === ctrl) setBusy(false);
      }
    },
    [shell, context, patch],
  );

  useEffect(() => {
    if (pending && pending.seq !== lastPending.current) {
      lastPending.current = pending.seq;
      void ask(pending.q);
    }
  }, [pending, ask]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [turns]);

  function submit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  if (!open) return null;
  return (
    <aside className="cp-drawer" role="dialog" aria-modal="false" aria-labelledby={titleId}>
      <header className="cp-head">
        <h2 id={titleId} className="section-label section-header-title">
          Ask Ledgic
        </h2>
        <span className="meta">Answers cite contracts, policy and Ledgic data</span>
        <button type="button" className="cp-close" aria-label="Close Ask Ledgic" onClick={onClose}>
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </header>

      <div className="cp-body" ref={bodyRef} aria-live="polite">
        {turns.length === 0 ? (
          <div className="cp-suggest">
            <div className="field-label">Suggested questions</div>
            <ul>
              {SUGGESTED_QUESTIONS.map((q) => (
                <li key={q}>
                  <button type="button" onClick={() => void ask(q)} disabled={busy}>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {turns.map((t) => (
          <article key={t.id} className="cp-turn">
            <p className="cp-q">{t.question}</p>
            {t.mode === "retrieval_only" ? (
              <p className="cp-notice" role="note">
                Retrieval only — AI budget reached. Showing the most relevant passages instead of a written answer.
              </p>
            ) : null}
            {t.answer ? <MarkdownLite text={t.answer} citations={t.citations} /> : null}
            {t.status && !t.done ? (
              <p className="cp-status" role="status">
                <span className="cp-status-bar" aria-hidden="true" />
                {STEP_LABEL[t.status] ?? t.status}
              </p>
            ) : null}
            {t.error ? (
              <p className="cp-error" role="alert">
                {t.error}
              </p>
            ) : null}
            {t.citations.length > 0 ? (
              <div className="cp-sources">
                <span className="field-label">Sources</span>
                <div className="cp-source-list">
                  {t.citations.map((c, i) => (
                    <CitationChip key={`${c.chunk_id ?? i}`} citation={{ ...c, n: c.n ?? i + 1 }} showTitle />
                  ))}
                </div>
              </div>
            ) : null}
            {t.done && t.mode ? (
              <p className="cp-mode meta">
                {t.mode === "live" ? `Answered live${t.model ? ` · ${t.model}` : ""}` : t.mode === "cached" ? "Cached answer" : "Retrieval only"}
              </p>
            ) : null}
          </article>
        ))}
      </div>

      <form className="cp-form" onSubmit={submit}>
        <label htmlFor={inputId} className="sr-only">
          Question
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          className="input cp-input"
          placeholder="Ask about an invoice, a contract clause or a policy"
          value={input}
          maxLength={500}
          rows={2}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void ask(input);
            }
          }}
        />
        <div className="cp-form-row">
          <button type="button" className="cp-link" aria-expanded={showByok} aria-controls={byokId} onClick={() => setShowByok((s) => !s)}>
            {byok ? "Using your OpenAI key" : "Use your own OpenAI key"}
          </button>
          <Button variant="ink" size="sm" type="submit" loading={busy} disabled={!input.trim()}>
            Ask
          </Button>
        </div>
        {showByok ? (
          <div id={byokId} className="cp-byok">
            <label htmlFor={`${byokId}-in`} className="field-label">
              OpenAI API key (kept in this tab only)
            </label>
            <input
              id={`${byokId}-in`}
              type="password"
              className="input"
              autoComplete="off"
              spellCheck={false}
              placeholder="sk-…"
              value={byok}
              onChange={(e) => {
                setByok(e.target.value.trim());
                writeByok(e.target.value.trim());
              }}
            />
            <p className="meta">
              Sent with your questions as a header, used for that request only and never stored on the server. It bypasses the shared daily AI budget.
            </p>
          </div>
        ) : null}
      </form>
    </aside>
  );
}

interface SseEvent {
  event: string;
  data: unknown;
}

function parseEvent(raw: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return { event, data: data.join("\n") };
  }
}

/** Applies one SSE event to a turn. Returns true when the stream is finished. */
function handleEvent(id: number, ev: SseEvent, patch: (id: number, fn: (t: Turn) => Turn) => void): boolean {
  const d = (ev.data ?? {}) as Record<string, unknown>;
  switch (ev.event) {
    case "status":
      patch(id, (t) => ({ ...t, status: String(d.step ?? "answering") }));
      return false;
    case "token":
      patch(id, (t) => ({ ...t, answer: t.answer + String(d.text ?? ""), status: "answering" }));
      return false;
    case "citation":
      patch(id, (t) => (t.citations.some((c) => c.n === d.n) ? t : { ...t, citations: [...t.citations, d as Citation] }));
      return false;
    case "done": {
      const answer = typeof d.answer_md === "string" ? d.answer_md : null;
      const cites = Array.isArray(d.citations) ? (d.citations as Citation[]) : null;
      patch(id, (t) => ({
        ...t,
        answer: answer ?? t.answer,
        citations: cites && cites.length ? cites : t.citations,
        mode: (d.mode as Turn["mode"]) ?? null,
        model: typeof d.model === "string" ? d.model : null,
        status: null,
        done: true,
      }));
      return true;
    }
    case "error":
      patch(id, (t) => ({ ...t, error: String(d.message ?? "Ask Ledgic couldn't answer."), status: null, done: true }));
      return true;
    default:
      return false;
  }
}
