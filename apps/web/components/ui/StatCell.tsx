"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Info } from "lucide-react";
import { cx } from "./cx";

export interface StatCellProps {
  label: ReactNode;
  /** Numeral M (22px 800). */
  value: ReactNode;
  /** Extra content beside the numeral (e.g. prev/next square buttons). */
  aside?: ReactNode;
  risk?: boolean;
  className?: string;
}

/** Stats-row cell: field label + numeral M, padding 14px 24px. Place inside <StatRow>. */
export function StatCell({ label, value, aside, risk, className }: StatCellProps) {
  return (
    <div className={cx("stat-cell", className)}>
      <div className="field-label">{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className={cx("numeral-m", risk && "numeral-risk")}>{value}</div>
        {aside}
      </div>
    </div>
  );
}

/** Row of equal StatCells / MetricCells with a 2px bottom rule. */
export function StatRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("stat-row", className)}>{children}</div>;
}

export interface MetricCellProps {
  label: ReactNode;
  /** Numeral XL (46px 800). */
  value: ReactNode;
  meta?: ReactNode;
  /** Accent variant ("Held back this quarter"). */
  risk?: boolean;
  /** Info popover content (formula, assumptions). Adds an info button beside the label. */
  info?: ReactNode;
  infoLabel?: string;
  className?: string;
}

export function MetricCell({ label, value, meta, risk, info, infoLabel = "How this is computed", className }: MetricCellProps) {
  const [open, setOpen] = useState(false);
  const popId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cx("metric-cell", className)} data-risk={risk || undefined}>
      <div className="metric-cell-label">
        <span className="field-label">{label}</span>
        {info ? (
          <button
            type="button"
            className="info-btn"
            aria-label={infoLabel}
            aria-expanded={open}
            aria-controls={popId}
            onClick={() => setOpen((o) => !o)}
          >
            <Info size={13} strokeWidth={2} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      <div className="numeral-xl">{value}</div>
      {meta ? <div className="metric-cell-meta">{meta}</div> : null}
      {info && open ? (
        <div id={popId} role="note" aria-label={infoLabel} className="popover">
          {info}
        </div>
      ) : null}
    </div>
  );
}
