"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Search, Sparkles } from "lucide-react";

export interface PaletteItem {
  id: string;
  title: string;
  /** Right-aligned meta, e.g. "$2,847.60 · Riverside". */
  meta?: string;
  /** Navigates here on select. */
  href?: string;
  /** Custom action on select (runs instead of navigation when given). */
  onSelect?: () => void;
}

export interface PaletteGroup {
  /** "Invoices" | "Vendors" | "Exceptions" | … */
  label: string;
  items: PaletteItem[];
}

export type PaletteSearch = (query: string, signal: AbortSignal) => Promise<PaletteGroup[]>;

export interface PaletteAskAction {
  /** Row label prefix, default "Ask Ledgic". */
  label?: string;
  /** Receives the typed query (palette closes first). */
  onSelect: (query: string) => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  search: PaletteSearch;
  /** Optional "Ask Ledgic" row shown first whenever the query is non-empty. */
  askAction?: PaletteAskAction | null;
  placeholder?: string;
  /** Debounce for search calls (default 150ms). */
  debounceMs?: number;
}

interface FlatRow {
  key: string;
  group: string | null;
  title: string;
  meta?: string;
  run: () => void;
  ask?: boolean;
}

/** Registers ⌘K / Ctrl+K to toggle the palette. */
export function useCommandPaletteHotkey(setOpen: (fn: (open: boolean) => boolean) => void): void {
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);
}

/** 640px command palette with grouped results (Invoices, Vendors, Exceptions) and arrow-key navigation. */
export function CommandPalette({
  open,
  onOpenChange,
  search,
  askAction,
  placeholder = "Search invoices, vendors, exceptions",
  debounceMs = 150,
}: CommandPaletteProps) {
  const router = useRouter();
  const ref = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const [groups, setGroups] = useState<PaletteGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      setLoading(true);
      setError(false);
      search(query.trim(), ctrl.signal)
        .then((g) => {
          if (!ctrl.signal.aborted) {
            setGroups(g.filter((x) => x.items.length > 0));
            setActive(0);
          }
        })
        .catch(() => {
          if (!ctrl.signal.aborted) {
            setGroups([]);
            setError(true);
          }
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, debounceMs);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [query, open, search, debounceMs]);

  const close = () => onOpenChange(false);

  const rows: FlatRow[] = useMemo(() => {
    const out: FlatRow[] = [];
    const q = query.trim();
    if (askAction && q) {
      out.push({
        key: "__ask",
        group: null,
        ask: true,
        title: `${askAction.label ?? "Ask Ledgic"}: “${q}”`,
        run: () => askAction.onSelect(q),
      });
    }
    for (const g of groups) {
      for (const it of g.items) {
        out.push({
          key: `${g.label}:${it.id}`,
          group: g.label,
          title: it.title,
          meta: it.meta,
          run: () => {
            if (it.onSelect) it.onSelect();
            else if (it.href) router.push(it.href);
          },
        });
      }
    }
    return out;
  }, [groups, askAction, query, router]);

  const choose = (row: FlatRow | undefined) => {
    if (!row) return;
    close();
    row.run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a + 1) % rows.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a - 1 + rows.length) % rows.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(rows[active]);
    }
  };

  const optionId = (i: number) => `${listId}-opt-${i}`;
  let lastGroup: string | null | undefined;

  return (
    <dialog
      ref={ref}
      className="palette"
      aria-label="Command palette"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === ref.current) close(); // backdrop click
      }}
    >
      {open ? (
        <>
          <div className="palette-input-row">
            <Search size={16} strokeWidth={2} aria-hidden="true" />
            <input
              ref={inputRef}
              className="input"
              type="text"
              role="combobox"
              aria-expanded={rows.length > 0}
              aria-controls={listId}
              aria-activedescendant={rows.length ? optionId(active) : undefined}
              aria-autocomplete="list"
              aria-label="Search"
              placeholder={placeholder}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <ul id={listId} className="palette-results" role="listbox" aria-label="Results" aria-busy={loading || undefined}>
            {rows.map((row, i) => {
              const header =
                row.group !== lastGroup && row.group ? (
                  <li key={`h-${row.group}`} role="presentation" className="palette-group-label section-label">
                    {row.group}
                  </li>
                ) : null;
              lastGroup = row.group;
              return [
                header,
                <li
                  key={row.key}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  className="palette-item"
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(row)}
                >
                  {row.ask ? <Sparkles size={14} strokeWidth={2} aria-hidden="true" /> : null}
                  <span>{row.title}</span>
                  {row.meta ? <span className="palette-item-meta">{row.meta}</span> : null}
                </li>,
              ];
            })}
          </ul>
          {!loading && rows.length === 0 ? (
            <div className="palette-empty" role="status">
              {error ? "Search is unavailable right now." : query.trim() ? "No matches." : "Type to search invoices, vendors and exceptions."}
            </div>
          ) : null}
          <div className="palette-foot" aria-hidden="true">
            <span>↑↓ move</span>
            <span>↵ open</span>
            <span>esc close</span>
          </div>
        </>
      ) : null}
    </dialog>
  );
}
