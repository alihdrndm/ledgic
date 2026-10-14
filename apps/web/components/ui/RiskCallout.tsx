import type { ReactNode } from "react";
import { cx } from "./cx";

export interface RiskCalloutProps {
  title: ReactNode;
  children?: ReactNode;
  /** Right-side actions (buttons, chips). */
  actions?: ReactNode;
  /** "risk" = money at risk (accent). "neutral" = errors (ink border, no accent) — errors are not risk. */
  tone?: "risk" | "neutral";
  /** role="alert" for messages that appear after an action. */
  live?: boolean;
  className?: string;
}

export function RiskCallout({ title, children, actions, tone = "risk", live, className }: RiskCalloutProps) {
  return (
    <div className={cx("risk-callout", className)} data-tone={tone} role={live ? "alert" : undefined}>
      <div className="risk-callout-main">
        <p className="risk-callout-title">{title}</p>
        {children ? <div className="risk-callout-body">{children}</div> : null}
      </div>
      {actions ? <div className="risk-callout-actions">{actions}</div> : null}
    </div>
  );
}
