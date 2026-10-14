import type { ReactNode } from "react";
import { cx } from "./cx";

export interface KeyValueRowProps {
  label: ReactNode;
  value: ReactNode;
  /** accent-100 fill edge-to-edge (bleeds by --kv-bleed; 18px inside .stage-col). */
  risk?: boolean;
  /** Value in body type / neutral-700 instead of an 800 numeral (e.g. "09:30 sent"). */
  plainValue?: boolean;
  className?: string;
}

export function KeyValueRow({ label, value, risk, plainValue, className }: KeyValueRowProps) {
  return (
    <div className={cx("kv-row", className)} data-risk={risk || undefined}>
      <span className="kv-row-label">{label}</span>
      <span className="kv-row-value" data-plain={plainValue || undefined}>
        {value}
      </span>
    </div>
  );
}
