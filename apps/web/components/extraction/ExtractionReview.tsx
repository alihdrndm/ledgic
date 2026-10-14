"use client";

import Decimal from "decimal.js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as RKeyboardEvent, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button, Chip, RiskCallout, StatCell, StatRow, useToast } from "@/components/ui";
import { Screen, needsRole, useShell } from "@/components/shell";
import { AskLedgicButton, CopilotProvider } from "@/components/copilot";
import { RealtimeRefresh } from "@/lib/realtime";
import { conf as fmtConf, duration, money, pct, time } from "@/lib/format";
import { confirmExtraction, type ConfirmFieldInput } from "@/lib/actions/extraction";
import type { BBox, ExtractionStats, InvoiceDetail } from "@/lib/queries/extraction";
import { SourceViewer, type SourceViewerHandle, type ViewerBox } from "./SourceViewer";
import "./extraction.css";

export interface ExtractionReviewProps {
  orgSlug: string;
  invoice: InvoiceDetail;
  queue: { invoice_id: string; queue_position: number }[];
  stats: ExtractionStats;
  imageUrl: string | null;
  imageKind: "image" | "pdf" | null;
  /** False when the invoice is no longer waiting for review (already confirmed). */
  inQueue: boolean;
  /** The referenced PO exists in the org's purchase orders (before enrichment links it). */
  poExists?: boolean;
}

type LineKey = "qty" | "unit_price" | "amount" | "description";
type EditKind = "text" | "money" | "unit" | "qty" | "date";

interface Flag {
  id: string; // "h:<field>" | "l:<lineId>:<key>"
  label: string;
  conf: Decimal;
  bbox: BBox | null;
  lineId?: string;
  key?: LineKey;
  field?: string;
}

const CHANNEL_LABEL: Record<string, string> = {
  photo: "dock photo",
  email: "emailed PDF",
  upload: "upload",
  portal: "vendor portal",
  edi: "EDI 810",
};

const FIELD_LABEL: Record<string, string> = {
  vendor_name: "vendor",
  vendor: "vendor",
  invoice_number: "invoice number",
  invoice_date: "invoice date",
  due_date: "due date",
  terms: "terms",
  po_reference: "PO reference",
  po_ref: "PO reference",
  subtotal: "subtotal",
  tax: "tax",
  freight: "freight",
  total: "total",
};

const LINE_LABEL: Record<LineKey, string> = { qty: "quantity", unit_price: "unit price", amount: "extended amount", description: "description" };
const CHIP_LABEL: Record<LineKey, string> = { qty: "Qty unclear", unit_price: "Price unclear", amount: "Amount unclear", description: "Text unclear" };
const EDIT_KIND: Record<string, EditKind> = {
  total: "money",
  subtotal: "money",
  tax: "money",
  freight: "money",
  invoice_date: "date",
  due_date: "date",
  qty: "qty",
  unit_price: "unit",
  amount: "money",
};

function dec(v: unknown): Decimal | null {
  if (v === null || v === undefined || v === "") return null;
  try {
    const d = new Decimal(String(v).replace(/[$,\s]/g, ""));
    return d.isFinite() ? d : null;
  } catch {
    return null;
  }
}

function plainNum(v: unknown): string {
  const d = dec(v);
  return d ? d.toDecimalPlaces(3).toFixed() : "—";
}

/** Unit prices keep up to 4 decimals ("$31.25", "$3.6825"). */
function unitMoney(v: unknown): string {
  const d = dec(v);
  if (!d) return "—";
  const t = d.toDecimalPlaces(4);
  return money(t, { decimals: Math.max(2, t.decimalPlaces()) });
}

function oneDp(d: Decimal): string {
  const q = d.toDecimalPlaces(3);
  return q.decimalPlaces() <= 1 ? q.toFixed(1) : q.toFixed();
}

function validate(kind: EditKind, raw: string): { value: string } | { error: string } {
  const s = raw.trim();
  if (!s) return { error: "Enter a value." };
  if (kind === "text") return { value: s };
  if (kind === "date") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s) || Number.isNaN(Date.parse(`${s}T00:00:00Z`))) return { error: "Use YYYY-MM-DD." };
    return { value: s };
  }
  const n = s.replace(/[$,\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(n)) return { error: "Numbers only." };
  const d = new Decimal(n);
  if (d.lte(0)) return { error: "Must be greater than 0." };
  const dp = kind === "money" ? 2 : kind === "unit" ? 4 : 3;
  if (d.decimalPlaces() > dp) return { error: kind === "money" ? "Money takes 2 decimals." : `At most ${dp} decimals.` };
  return { value: kind === "money" ? d.toFixed(2) : n };
}

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric" }).format(d);
}

function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable || Boolean(el.closest("dialog[open]"));
}

export function ExtractionReview(props: ExtractionReviewProps) {
  return (
    <CopilotProvider context={{ invoice_id: props.invoice.invoice_id }}>
      <ExtractionReviewInner {...props} />
    </CopilotProvider>
  );
}

function ExtractionReviewInner({ orgSlug, invoice: inv, queue, stats, imageUrl, imageKind, inQueue, poExists = false }: ExtractionReviewProps) {
  const { org, role } = useShell();
  const router = useRouter();
  const { toast } = useToast();
  const viewer = useRef<SourceViewerHandle>(null);
  const openedAt = useRef<number>(Date.now());
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const floor = useMemo(() => dec(stats.fieldFloor) ?? new Decimal("0.75"), [stats.fieldFloor]);
  const gate = dec(stats.confidenceGate) ?? new Decimal("0.90");
  const fields = useMemo(() => inv.fields ?? {}, [inv.fields]);
  const lines = useMemo(() => inv.lines ?? [], [inv.lines]);
  const disabledReason = !inQueue ? "Already confirmed" : needsRole(role, "ap_clerk");

  const base = `/o/${orgSlug}/extraction`;
  const idx = queue.findIndex((q) => q.invoice_id === inv.invoice_id);
  const nextId = idx >= 0 ? queue[idx + 1]?.invoice_id : queue[0]?.invoice_id;
  const prevId = idx > 0 ? queue[idx - 1]?.invoice_id : undefined;
  const afterConfirmId = idx >= 0 ? (queue[idx + 1]?.invoice_id ?? queue[idx - 1]?.invoice_id) : queue[0]?.invoice_id;

  useEffect(() => {
    openedAt.current = Date.now();
    setEdits({});
    setEditing(null);
    setFocus(null);
    setError(null);
  }, [inv.invoice_id]);

  /* ---- values ------------------------------------------------------------------------------ */
  const fieldName = useCallback((names: string[]) => names.find((n) => fields[n]) ?? names[0]!, [fields]);
  const headerValue = useCallback(
    (name: string, fallback: unknown): string | null => {
      const e = edits[`h:${name}`];
      if (e !== undefined) return e;
      const v = fields[name]?.value;
      if (v !== null && v !== undefined && v !== "") return String(v);
      return fallback === null || fallback === undefined ? null : String(fallback);
    },
    [edits, fields],
  );
  const lineValue = useCallback(
    (lineId: string, key: LineKey, original: unknown): string | null => {
      const e = edits[`l:${lineId}:${key}`];
      if (e !== undefined) return e;
      return original === null || original === undefined ? null : String(original);
    },
    [edits],
  );

  /* ---- flagged fields (< field floor) ------------------------------------------------------- */
  const flags: Flag[] = useMemo(() => {
    const out: Flag[] = [];
    for (const [name, f] of Object.entries(fields)) {
      const c = dec(f.confidence);
      // An optional field absent from the document (e.g. no freight line) has no value to confirm.
      const absent = f.value === null || f.value === undefined || f.value === "";
      if (c && c.lt(floor) && f.source !== "human" && !absent) {
        out.push({ id: `h:${name}`, label: FIELD_LABEL[name] ?? name.replace(/_/g, " "), conf: c, bbox: f.bbox ?? null, field: name });
      }
    }
    for (const l of lines) {
      for (const key of ["description", "qty", "unit_price", "amount"] as LineKey[]) {
        const c = dec(l.confidences?.[key]);
        if (c && c.lt(floor)) {
          out.push({
            id: `l:${l.id}:${key}`,
            label: `${LINE_LABEL[key]}, line ${l.line_no}`,
            conf: c,
            bbox: l.bboxes?.[key] ?? null,
            lineId: l.id,
            key,
          });
        }
      }
    }
    return out;
  }, [fields, lines, floor]);
  const flagIds = useMemo(() => new Set(flags.map((f) => f.id)), [flags]);

  /* ---- arithmetic -------------------------------------------------------------------------- */
  const lineSum = useMemo(() => {
    let s = new Decimal(0);
    for (const l of lines) s = s.plus(dec(lineValue(l.id, "amount", l.amount)) ?? 0);
    return s;
  }, [lines, lineValue]);
  const totalVal = dec(headerValue("total", inv.total));
  const sums =
    totalVal !== null &&
    lineSum
      .plus(dec(headerValue("tax", inv.tax)) ?? 0)
      .plus(dec(headerValue("freight", inv.freight)) ?? 0)
      .minus(totalVal)
      .abs()
      .lte("0.02");

  function crossCheck(f: Flag): ReactNode {
    const photo = inv.channel === "photo";
    const agreeTail = photo ? "so the arithmetic agrees with the smudged digit." : "so the arithmetic agrees with the value read.";
    const disagreeTail = "which doesn't agree with the value read — check the document before confirming.";
    const original = f.lineId
      ? lines.find((l) => l.id === f.lineId)?.[f.key as LineKey]
      : fields[f.field ?? ""]?.value;
    const edited = edits[f.id] !== undefined;
    const lead = edited ? (
      <>
        You entered <strong>{plainNum(edits[f.id]) !== "—" ? plainNum(edits[f.id]) : edits[f.id]}</strong> (model read {plainNum(original)} at confidence {fmtConf(f.conf)}).
      </>
    ) : (
      <>
        Model read <strong>{f.key === "description" || (f.field && EDIT_KIND[f.field] === undefined) ? String(original ?? "—") : plainNum(original)}</strong> at confidence{" "}
        {fmtConf(f.conf)}.
      </>
    );
    if (f.lineId && f.key && f.key !== "description") {
      const l = lines.find((x) => x.id === f.lineId);
      if (!l) return lead;
      const qty = dec(lineValue(l.id, "qty", l.qty));
      const unit = dec(lineValue(l.id, "unit_price", l.unit_price));
      const amt = dec(lineValue(l.id, "amount", l.amount));
      if (f.key === "qty" && unit && amt && !unit.isZero()) {
        const q = amt.div(unit);
        const ok = qty !== null && q.minus(qty).abs().lte("0.001");
        return (
          <>
            {lead} Cross-check: {money(amt)} ÷ {unitMoney(unit)} unit = <strong>{oneDp(q)}</strong>,{" "}
            {ok ? agreeTail : disagreeTail}
          </>
        );
      }
      if (f.key === "unit_price" && qty && amt && !qty.isZero()) {
        const u = amt.div(qty);
        const ok = unit !== null && u.minus(unit).abs().lte("0.005");
        return (
          <>
            {lead} Cross-check: {money(amt)} ÷ {plainNum(qty)} = <strong>{money(u)}</strong> per unit, {ok ? agreeTail : disagreeTail}
          </>
        );
      }
      if (f.key === "amount" && qty && unit) {
        const a = qty.times(unit).toDecimalPlaces(2);
        const ok = amt !== null && a.minus(amt).abs().lte("0.01");
        return (
          <>
            {lead} Cross-check: {plainNum(qty)} × {unitMoney(unit)} = <strong>{money(a)}</strong>, {ok ? agreeTail : disagreeTail}
          </>
        );
      }
    }
    if (f.field === "total") {
      return (
        <>
          {lead} Cross-check: lines {money(lineSum)} plus tax and freight {sums ? "equal the total, " + agreeTail : "don't equal the total — check the document before confirming."}
        </>
      );
    }
    return lead;
  }

  /* ---- editing ----------------------------------------------------------------------------- */
  function editKindOf(id: string): EditKind {
    if (id.startsWith("l:")) return EDIT_KIND[id.split(":")[2] ?? ""] ?? "text";
    return EDIT_KIND[id.slice(2)] ?? "text";
  }
  function currentValueOf(id: string): string {
    if (id.startsWith("l:")) {
      const [, lineId, key] = id.split(":") as [string, string, LineKey];
      const l = lines.find((x) => x.id === lineId);
      return lineValue(lineId, key, l?.[key]) ?? "";
    }
    const name = id.slice(2);
    return headerValue(name, (inv as unknown as Record<string, unknown>)[name]) ?? "";
  }
  function startEdit(ids: string[]) {
    if (disabledReason) return;
    const d: Record<string, string> = {};
    for (const id of ids) {
      const v = currentValueOf(id);
      const kind = editKindOf(id);
      d[id] = kind === "qty" || kind === "unit" ? plainNum(v) === "—" ? v : plainNum(v) : v;
    }
    setDraft(d);
    setEditing(ids.join("|"));
    setEditError(null);
  }
  function saveEdit() {
    if (!editing) return;
    const next: Record<string, string> = {};
    for (const id of editing.split("|")) {
      const res = validate(editKindOf(id), draft[id] ?? "");
      if ("error" in res) {
        setEditError(res.error);
        return;
      }
      if (res.value !== currentValueOf(id)) next[id] = res.value;
    }
    setEdits((e) => ({ ...e, ...next }));
    setEditing(null);
    setEditError(null);
  }
  function cancelEdit() {
    setEditing(null);
    setEditError(null);
  }
  function editorKeys(e: RKeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      saveEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  }
  function renderEditor(id: string, ariaLabel: string) {
    const kind = editKindOf(id);
    return (
      <input
        key={id}
        className="input"
        aria-label={ariaLabel}
        aria-invalid={Boolean(editError) || undefined}
        inputMode={kind === "text" || kind === "date" ? undefined : "decimal"}
        placeholder={kind === "date" ? "YYYY-MM-DD" : undefined}
        value={draft[id] ?? ""}
        autoFocus={editing?.split("|")[0] === id}
        onChange={(e) => setDraft((d) => ({ ...d, [id]: e.target.value }))}
        onKeyDown={editorKeys}
        onBlur={(e) => {
          // Save when focus leaves the editor group entirely.
          const to = e.relatedTarget as HTMLElement | null;
          if (!to || !to.closest("[data-editor]")) saveEdit();
        }}
      />
    );
  }

  /* ---- focus / zoom ------------------------------------------------------------------------ */
  function focusOn(id: string, bbox: BBox | null | undefined) {
    setFocus(id);
    if (bbox) viewer.current?.zoomTo(bbox);
  }

  const boxes: ViewerBox[] = useMemo(() => {
    const out: ViewerBox[] = [];
    for (const f of flags) if (f.bbox && (f.bbox.page ?? 1) === 1) out.push({ key: f.id, ...f.bbox, tone: "flag", label: f.label });
    if (focus && !flagIds.has(focus)) {
      let b: BBox | null | undefined = null;
      if (focus.startsWith("l:")) {
        const [, lineId, key] = focus.split(":");
        b = lines.find((l) => l.id === lineId)?.bboxes?.[key ?? ""];
      } else b = fields[focus.slice(2)]?.bbox;
      if (b && (b.page ?? 1) === 1) out.push({ key: focus, ...b, tone: "focus", label: "Selected field" });
    }
    return out;
  }, [flags, flagIds, focus, lines, fields]);

  /* ---- confirm ----------------------------------------------------------------------------- */
  const confirm = useCallback(async () => {
    if (busy || disabledReason) return;
    if (editing) saveEdit();
    setBusy(true);
    setError(null);
    const payload = new Map<string, ConfirmFieldInput>();
    const ids = new Set<string>([...flags.map((f) => f.id), ...Object.keys(edits)]);
    for (const id of ids) {
      const value = currentValueOf(id);
      if (!value) continue;
      if (id.startsWith("l:")) {
        const [, lineId, key] = id.split(":") as [string, string, LineKey];
        payload.set(id, { lineId, key, value });
      } else payload.set(id, { field: id.slice(2), value });
    }
    const seconds = (Date.now() - openedAt.current) / 1000;
    const res = await confirmExtraction({ orgSlug, invoiceId: inv.invoice_id, fields: [...payload.values()], timeSpent: Math.min(1800, seconds) });
    setBusy(false);
    if (!res.ok) {
      setError(res.message);
      if (res.code === "CONFLICT") router.refresh();
      return;
    }
    const changed = res.data.changed;
    toast(
      `Confirmed ${inv.invoice_number ?? "invoice"}${changed ? ` · ${changed} correction${changed === 1 ? "" : "s"} logged` : ""} · sent on to enrichment`,
    );
    router.push(afterConfirmId && afterConfirmId !== inv.invoice_id ? `${base}/${afterConfirmId}` : base);
    router.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, disabledReason, editing, flags, edits, inv.invoice_id, inv.invoice_number, orgSlug, afterConfirmId, base]);

  /* ---- keyboard: Enter confirm · E edit · J/K next/prev ------------------------------------ */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      if (document.querySelector(".cp-drawer") && (e.target as HTMLElement | null)?.closest?.(".cp-drawer")) return;
      const k = e.key.toLowerCase();
      if (e.key === "Enter" && !(e.target as HTMLElement | null)?.closest?.("button, a")) {
        e.preventDefault();
        void confirm();
      } else if (k === "e") {
        const first = flags[0];
        if (first) {
          e.preventDefault();
          startEdit([first.id]);
          focusOn(first.id, first.bbox);
        }
      } else if (k === "j" && nextId) {
        e.preventDefault();
        router.push(`${base}/${nextId}`);
      } else if (k === "k" && prevId) {
        e.preventDefault();
        router.push(`${base}/${prevId}`);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirm, flags, nextId, prevId, base, router]);

  /* ---- render ------------------------------------------------------------------------------ */
  const docConf = dec(inv.doc_confidence);
  const belowGate = docConf ? docConf.lt(gate) : false;
  const queueSize = queue.length;
  const received = stats.received;
  const fileBase = (inv.original_filename ?? "").replace(/\.[a-z0-9]+$/i, "");
  const skew = dec(inv.preprocessing?.skew_deg);

  const vendorName = fieldName(["vendor_name", "vendor"]);
  const poName = fieldName(["po_reference", "po_ref"]);
  const headerCells: Array<{ label: string; ids: string[]; display: ReactNode; conf: Decimal | null; note?: string; bbox?: BBox | null }> = [
    {
      label: "Vendor",
      ids: [`h:${vendorName}`],
      display: headerValue(vendorName, inv.vendor_name) ?? "—",
      conf: dec(fields[vendorName]?.confidence),
      bbox: fields[vendorName]?.bbox,
    },
    {
      label: "Invoice",
      ids: ["h:invoice_number"],
      display: headerValue("invoice_number", inv.invoice_number) ?? "—",
      conf: dec(fields.invoice_number?.confidence),
      bbox: fields.invoice_number?.bbox,
    },
    {
      label: "Date · terms",
      ids: ["h:invoice_date", "h:terms"],
      display: `${shortDate(headerValue("invoice_date", inv.invoice_date))} · ${headerValue("terms", inv.terms) ?? "—"}`,
      conf: Decimal.min(dec(fields.invoice_date?.confidence) ?? 1, dec(fields.terms?.confidence) ?? 1),
      bbox: fields.invoice_date?.bbox,
    },
    {
      label: "PO reference",
      ids: [`h:${poName}`],
      display: headerValue(poName, inv.po_number) ?? "—",
      conf: dec(fields[poName]?.confidence),
      note: inv.po_id || poExists ? "exists" : "not found",
      bbox: fields[poName]?.bbox,
    },
    {
      label: "Total",
      ids: ["h:total"],
      display: money(headerValue("total", inv.total)),
      conf: dec(fields.total?.confidence),
      note: sums ? "sums" : "doesn't sum",
      bbox: fields.total?.bbox,
    },
  ];
  const shownIds = new Set(headerCells.flatMap((c) => c.ids));
  for (const l of lines) for (const k of ["description", "qty", "unit_price", "amount"]) shownIds.add(`l:${l.id}:${k}`);

  const single = flags.length === 1 ? flags[0]! : null;
  let confirmLabel = "Confirm all";
  if (single) {
    if (single.key === "qty" && single.lineId) {
      const l = lines.find((x) => x.id === single.lineId);
      confirmLabel = `Confirm ${plainNum(lineValue(single.lineId, "qty", l?.qty))} × ${unitMoney(lineValue(single.lineId, "unit_price", l?.unit_price))}`;
    } else {
      const v = currentValueOf(single.id);
      const kind = editKindOf(single.id);
      confirmLabel = `Confirm ${kind === "money" ? money(v) : kind === "qty" ? plainNum(v) : v}`;
    }
  } else if (flags.length === 0) confirmLabel = Object.keys(edits).length ? "Confirm corrections" : "Confirm fields";

  const editBtn = (
    <Button
      variant="outline"
      disabledReason={disabledReason}
      kbd="E"
      onClick={() => {
        const f = flags[0];
        if (f) {
          startEdit([f.id]);
          focusOn(f.id, f.bbox);
        }
      }}
      disabled={flags.length === 0}
    >
      Edit value
    </Button>
  );
  const confirmBtn = (
    <Button variant="ink" onClick={() => void confirm()} loading={busy} disabledReason={disabledReason} kbd="↵">
      {confirmLabel}
    </Button>
  );

  const pos = idx >= 0 ? idx + 1 : null;

  return (
    <Screen
      title="Extraction review"
      context={`${queueSize} of ${received ?? "—"} documents need a person today`}
      riskChip={<AskLedgicButton />}
      degraded={stats.degraded}
      statusItems={[
        { key: "autosave", text: `Autosaved ${stats.lastAutosaveAt ? time(stats.lastAutosaveAt, org.timezone) : "—"}` },
        { key: "queue", text: `${queueSize} document${queueSize === 1 ? "" : "s"} in queue` },
      ]}
      version={stats.workflowVersion ?? undefined}
    >
      <RealtimeRefresh tables={["exceptions"]} orgId={org.id} />
      <StatRow>
        <StatCell label="Field accuracy, sampled" value={pct(stats.accuracy)} />
        <StatCell label="Auto-passed today" value={`${stats.autoPassed ?? "—"} / ${received ?? "—"}`} />
        <StatCell label="Median extraction" value={duration(stats.medianSeconds, { precise: true })} />
        <StatCell
          label="Queue position"
          value={pos ? `${pos} of ${queueSize}` : inQueue ? "—" : "Confirmed"}
          aside={
            <div className="ex-queue-nav">
              <button
                type="button"
                className="btn-square"
                aria-label="Previous document (K)"
                aria-keyshortcuts="K"
                disabled={!prevId}
                onClick={() => prevId && router.push(`${base}/${prevId}`)}
              >
                <ChevronLeft size={16} strokeWidth={2} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="btn-square"
                aria-label="Next document (J)"
                aria-keyshortcuts="J"
                disabled={!nextId}
                onClick={() => nextId && router.push(`${base}/${nextId}`)}
              >
                <ChevronRight size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          }
        />
      </StatRow>

      <div className="ex-body">
        <section className="ex-source" aria-label="Source document">
          <div className="ex-source-head">
            <span className="field-label">Source · {CHANNEL_LABEL[inv.channel] ?? inv.channel}</span>
            <span className="field-label">
              {[fileBase || null, inv.location_name, inv.received_at ? time(inv.received_at, org.timezone) : null].filter(Boolean).join(" · ")}
            </span>
          </div>
          <SourceViewer ref={viewer} src={imageUrl} kind={imageKind} boxes={boxes} alt={`Source document for ${inv.invoice_number ?? "invoice"}`} />
          <div className="ex-source-foot">
            <span>
              {skew && !skew.isZero() ? `Skew corrected ${skew.gt(0) ? "+" : "−"}${skew.abs().toFixed(1)}°, perspective normalized. ` : ""}
              {flags.length ? "The outlined region is the field awaiting confirmation." : "Every field cleared the confidence floor."}
            </span>
          </div>
        </section>

        <section className="ex-fields" aria-label="Extracted fields">
          <div className="ex-fields-head">
            <span className="section-label">Extracted fields</span>
            <span className="ex-doc-conf" data-ok={!belowGate || undefined}>
              Document confidence {fmtConf(docConf)}
              {belowGate ? ` — below the ${fmtConf(gate)} gate` : ` — above the ${fmtConf(gate)} gate`}
            </span>
          </div>

          <div className="ex-header-grid" role="group" aria-label="Header fields">
            {headerCells.map((c) => {
              const flagged = c.ids.some((id) => flagIds.has(id));
              const isEditing = editing !== null && editing === c.ids.join("|");
              const edited = c.ids.some((id) => edits[id] !== undefined);
              return (
                <div key={c.label} className="ex-cell" data-flag={flagged || undefined} data-editor={isEditing || undefined}>
                  <div className="field-label">{c.label}</div>
                  {isEditing ? (
                    <>
                      {c.ids.map((id) => renderEditor(id, `${c.label}: ${FIELD_LABEL[id.slice(2)] ?? id.slice(2)}`))}
                      {editError ? <div className="ex-cell-error" role="alert">{editError}</div> : null}
                    </>
                  ) : (
                    <button
                      type="button"
                      className="ex-cell-value"
                      title={disabledReason ?? "Click to edit"}
                      onClick={() => {
                        focusOn(c.ids[0]!, c.bbox);
                        startEdit(c.ids);
                      }}
                    >
                      {c.display}
                      {edited ? <span className="ex-edited">edited</span> : null}
                    </button>
                  )}
                  <div className="ex-cell-conf">
                    {edited ? "you" : `conf ${fmtConf(c.conf)}`}
                    {c.note ? ` · ${c.note}` : ""}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="ex-lines">
            <table>
              <caption className="sr-only">Line items</caption>
              <thead>
                <tr>
                  <th scope="col">Line item</th>
                  <th scope="col" className="is-num">Qty</th>
                  <th scope="col" className="is-num">Unit</th>
                  <th scope="col" className="is-num">Extended</th>
                  <th scope="col" className="is-num">Conf</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => {
                  const lineFlags = flags.filter((f) => f.lineId === l.id);
                  const risk = lineFlags.length > 0;
                  const confs = (["description", "qty", "unit_price", "amount"] as LineKey[])
                    .map((k) => dec(l.confidences?.[k]))
                    .filter((x): x is Decimal => x !== null);
                  const minConf = confs.length ? Decimal.min(...confs) : null;
                  const cell = (key: LineKey, display: string, numeric: boolean) => {
                    const id = `l:${l.id}:${key}`;
                    const flagged = flagIds.has(id);
                    if (editing === id)
                      return (
                        <span data-editor>
                          {renderEditor(id, `${LINE_LABEL[key]}, line ${l.line_no}`)}
                          {editError ? <span className="ex-cell-error" role="alert">{editError}</span> : null}
                        </span>
                      );
                    return (
                      <button
                        type="button"
                        className={`ex-cell-btn${flagged ? " ex-risk-val" : ""}`}
                        title={disabledReason ?? "Click to edit"}
                        onClick={() => {
                          focusOn(id, l.bboxes?.[key]);
                          startEdit([id]);
                        }}
                      >
                        {display}
                        {flagged && numeric && edits[id] === undefined ? " ?" : ""}
                        {edits[id] !== undefined ? <span className="ex-edited">edited</span> : null}
                      </button>
                    );
                  };
                  return (
                    <tr key={l.id} data-risk={risk || undefined} data-focus={focus?.startsWith(`l:${l.id}:`) || undefined}>
                      <td>
                        {cell("description", lineValue(l.id, "description", l.description) ?? "—", false)}
                        {lineFlags
                          .filter((f) => f.key)
                          .map((f) => (
                            <Chip key={f.id} variant="risk-outline" size="sm" style={{ marginLeft: 10 }}>
                              {CHIP_LABEL[f.key as LineKey]}
                            </Chip>
                          ))}
                      </td>
                      <td className="is-num">{cell("qty", plainNum(lineValue(l.id, "qty", l.qty)), true)}</td>
                      <td className="is-num">{cell("unit_price", unitMoney(lineValue(l.id, "unit_price", l.unit_price)), true)}</td>
                      <td className="is-num">{cell("amount", money(lineValue(l.id, "amount", l.amount)), true)}</td>
                      <td className={`is-num${risk ? " ex-risk-val" : ""}`}>{fmtConf(minConf)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {error ? (
            <RiskCallout tone="neutral" title="Not confirmed" live className="ex-callout">
              {error}
            </RiskCallout>
          ) : null}

          {!inQueue ? (
            <RiskCallout
              tone="neutral"
              title="This document is no longer waiting for review"
              className="ex-callout"
              actions={
                queue[0] ? (
                  <Link className="btn btn-ink ledgic-btn ledgic-btn-md" href={`${base}/${queue[0].invoice_id}`}>
                    Open next in queue
                  </Link>
                ) : undefined
              }
            >
              Its fields were confirmed and the run moved on. Corrections are in the invoice&apos;s audit trail.
            </RiskCallout>
          ) : flags.length > 0 ? (
            <RiskCallout
              className="ex-callout"
              title={single ? `One field needs confirmation — ${single.label}` : `${flags.length} fields need confirmation`}
              actions={
                <>
                  {confirmBtn}
                  {editBtn}
                </>
              }
            >
              {single ? (
                <p style={{ margin: 0 }}>{crossCheck(single)}</p>
              ) : (
                <ul className="ex-callout-rows">
                  {flags.map((f) => (
                    <li key={f.id}>
                      <button type="button" className="ex-cell-btn" onClick={() => focusOn(f.id, f.bbox)}>
                        <strong>{f.label[0]?.toUpperCase() + f.label.slice(1)}:</strong>
                      </button>{" "}
                      {crossCheck(f)}
                      {editing === f.id && !shownIds.has(f.id) ? <span data-editor>{renderEditor(f.id, f.label)}</span> : null}
                    </li>
                  ))}
                </ul>
              )}
            </RiskCallout>
          ) : (
            <RiskCallout tone="neutral" className="ex-callout" title="No field is below the confidence floor" actions={confirmBtn}>
              The document as a whole is under the gate, so it still needs a person to confirm before it moves on.
            </RiskCallout>
          )}

          <div className="ex-spacer" />
          <div className="ex-footer">
            <span>
              On confirm: re-scored, enriched, then matched against {inv.po_number ?? headerValue(poName, null) ?? "the purchase order"}
            </span>
            <span>Every correction is logged with actor and timestamp</span>
          </div>
        </section>
      </div>
    </Screen>
  );
}
