"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/ui";
import { age, money } from "@/lib/format";
import type { ExceptionQueueRow } from "@/lib/queries/exceptions";
import { flatOrder, groupQueue, type QueueSort } from "./sort";
import "./exceptions.css";

const PER_GROUP = 3;

export interface ExceptionQueueProps {
  orgSlug: string;
  rows: ExceptionQueueRow[];
  selectedId: string | null;
  sort: QueueSort;
}

function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable || Boolean(el.closest("dialog[open], .cp-drawer"));
}

/** 412px triage queue: groups by type with counts, 3 per group + "<n> more", J/K navigation. */
export function ExceptionQueue({ orgSlug, rows, selectedId, sort }: ExceptionQueueProps) {
  const router = useRouter();
  const groups = useMemo(() => groupQueue(rows, sort), [rows, sort]);
  const order = useMemo(() => flatOrder(groups), [groups]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const base = `/o/${orgSlug}/exceptions`;
  const q = sort === "impact" ? "?sort=impact" : "";

  // Keep the selected item visible even when it is past the first three of its group.
  useEffect(() => {
    if (!selectedId) return;
    const g = groups.find((x) => x.items.some((i) => i.exception_id === selectedId));
    if (g && g.items.findIndex((i) => i.exception_id === selectedId) >= PER_GROUP) setExpanded((e) => ({ ...e, [g.type]: true }));
  }, [groups, selectedId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      const k = e.key.toLowerCase();
      if (k !== "j" && k !== "k") return;
      if (order.length === 0) return;
      e.preventDefault();
      const i = selectedId ? order.indexOf(selectedId) : -1;
      const next = k === "j" ? order[Math.min(order.length - 1, i + 1)] : order[Math.max(0, i - 1)];
      if (next && next !== selectedId) router.push(`${base}/${next}${q}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [order, selectedId, router, base, q]);

  const now = Date.now();
  return (
    <section className="xq" aria-label="Exception queue">
      <header className="xq-head">
        <h2 className="section-label section-header-title">Queue</h2>
        <button
          type="button"
          className="xq-sort section-label"
          aria-label={`Sorted ${sort === "impact" ? "by largest impact" : "oldest first"}. Switch sort`}
          onClick={() => {
            const next = sort === "impact" ? "" : "?sort=impact";
            router.replace(`${selectedId ? `${base}/${selectedId}` : base}${next}`, { scroll: false });
          }}
        >
          {sort === "impact" ? "Largest impact" : "Oldest first"}
        </button>
      </header>
      <div className="xq-body">
        {groups.length === 0 ? (
          <EmptyState title="Queue clear">Nothing is waiting for a person right now.</EmptyState>
        ) : (
          groups.map((g) => {
            const open = expanded[g.type] ?? false;
            const shown = open ? g.items : g.items.slice(0, PER_GROUP);
            const hidden = g.items.length - shown.length;
            return (
              <div key={g.type} role="group" aria-label={`${g.label}, ${g.items.length}`}>
                <div className="xq-group" data-risk={g.risk || undefined}>
                  <span>{g.label}</span>
                  <span>{g.items.length}</span>
                </div>
                <ul className="xq-list">
                  {shown.map((r) => {
                    const sel = r.exception_id === selectedId;
                    const dup = r.type === "duplicate" ? " ×2" : "";
                    return (
                      <li key={r.exception_id}>
                        <Link
                          href={`${base}/${r.exception_id}${q}`}
                          className="xq-item"
                          aria-current={sel ? "true" : undefined}
                          scroll={false}
                        >
                          <span className="xq-line1">
                            <span className={sel ? "xq-title xq-title-sel" : "xq-title"}>
                              {r.vendor_name ?? "Unknown vendor"} · {r.invoice_number ?? "—"}
                              {dup}
                            </span>
                            <span className="xq-amt">{money(r.amount_at_risk)}</span>
                          </span>
                          <span className="xq-line2">
                            {[r.location_name, age(r.opened_at, now), r.reason].filter(Boolean).join(" · ")}
                            {r.escalated ? " · escalated" : ""}
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
                {hidden > 0 ? (
                  <button type="button" className="xq-more" onClick={() => setExpanded((e) => ({ ...e, [g.type]: true }))}>
                    {hidden} more
                  </button>
                ) : null}
              </div>
            );
          })
        )}
      </div>
      <footer className="xq-foot">Anything untouched for 24 hours escalates to the controller.</footer>
    </section>
  );
}
