import type { ReactNode } from "react";
import { cx } from "./cx";

export interface SectionHeaderProps {
  /** Section label (rendered uppercase, 10.5px, 0.14em, neutral-700). */
  label: ReactNode;
  /** Right-aligned meta text (11.5px neutral-700) or any node. */
  meta?: ReactNode;
  /** 2px bottom rule (default true). */
  rule?: boolean;
  /** Element for the label (default h2). */
  as?: "h2" | "h3" | "h4" | "div";
  id?: string;
  className?: string;
}

export function SectionHeader({ label, meta, rule = true, as: Tag = "h2", id, className }: SectionHeaderProps) {
  return (
    <div className={cx("section-header", className)} data-rule={rule || undefined}>
      <Tag id={id} className="section-label section-header-title">
        {label}
      </Tag>
      {meta !== undefined && meta !== null ? <div className="meta">{meta}</div> : null}
    </div>
  );
}
