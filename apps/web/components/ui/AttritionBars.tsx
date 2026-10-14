"use client";

import { useEffect, useState } from "react";
import { count as fmtCount } from "@/lib/format";

export interface AttritionItem {
  /** Lower-case label under the bar, e.g. "received". */
  label: string;
  value: number;
  /** "routed to people": accent numeral, bar and label. */
  risk?: boolean;
}

export interface AttritionBarsProps {
  items: AttritionItem[];
  /** Bar heights are value / max; defaults to the largest value. */
  max?: number;
  /** Accessible summary label. */
  label?: string;
}

/** Five-column attrition ledger: numeral M over a 44px track, bars bottom-aligned, 200ms height transition. */
export function AttritionBars({ items, max, label = "Volume through the pipeline" }: AttritionBarsProps) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  // Grow from zero on first paint; CSS disables the transition under prefers-reduced-motion.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <ol className="attrition attrition-cols" aria-label={label} style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}>
      {items.map((item) => {
        const h = top > 0 ? Math.max(0, Math.min(100, (item.value / top) * 100)) : 0;
        return (
          <li key={item.label} className="attrition-col" data-risk={item.risk || undefined}>
            <span className="attrition-num">{fmtCount(item.value)}</span>
            <span className="attrition-track" aria-hidden="true">
              <span className="attrition-bar" style={{ height: `${mounted ? h : 0}%` }} />
            </span>
            <span className="attrition-label">{item.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
