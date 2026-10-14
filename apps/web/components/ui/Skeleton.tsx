"use client";

import { useEffect, useState } from "react";
import { cx } from "./cx";

export interface SkeletonProps {
  rows?: number;
  /** Relative widths (flex units) of the blocks in each row, mirroring the real layout. */
  columns?: number[];
  label?: string;
  className?: string;
}

/** 1px-ruled rows with neutral-200 blocks. Static; pulses (1 → 0.6) only after 300ms. */
export function Skeleton({ rows = 6, columns = [2, 3, 2, 2, 1], label = "Loading", className }: SkeletonProps) {
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setPulse(true), 300);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className={cx("skeleton", className)} data-pulse={pulse || undefined} role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: rows }, (_, r) => (
        <div className="skeleton-row" key={r}>
          {columns.map((w, c) => (
            <div key={c} className="skeleton-block" style={{ flex: w }} />
          ))}
        </div>
      ))}
    </div>
  );
}
