import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

/**
 * ink = status fill ("Touchless") · outline = 1px ink ("Computed") · neutral = 1px divider ("16s end to end")
 * risk = solid accent-700 ("Price variance") · risk-outline = 1px accent ("Qty unclear").
 * Red variants are for exceptions / money at risk only.
 */
export type ChipVariant = "ink" | "outline" | "neutral" | "risk" | "risk-outline";

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: ChipVariant;
  size?: "md" | "sm";
  children: ReactNode;
}

export function Chip({ variant = "neutral", size = "md", className, children, ...rest }: ChipProps) {
  return (
    <span className={cx("chip", `chip-${variant}`, size === "sm" && "chip-sm", className)} {...rest}>
      {children}
    </span>
  );
}

/** "Demo · sample data" — render only when org.is_demo, and only in the top bar (TopBar does this). */
export function DemoBadge({ className }: { className?: string }) {
  return <span className={cx("demo-badge", className)}>Demo · sample data</span>;
}
