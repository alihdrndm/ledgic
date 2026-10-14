import type { ReactNode } from "react";
import { cx } from "./cx";

export interface EmptyStateProps {
  /** Section-label line, e.g. "Queue clear". */
  title: ReactNode;
  /** One sentence in neutral-700. */
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Flush-left, no illustration. Render inside the region it replaces. */
export function EmptyState({ title, children, action, className }: EmptyStateProps) {
  return (
    <div className={cx("empty-state", className)} role="status">
      <div className="section-label">{title}</div>
      {children ? <p>{children}</p> : null}
      {action ? <div style={{ marginTop: 8 }}>{action}</div> : null}
    </div>
  );
}
