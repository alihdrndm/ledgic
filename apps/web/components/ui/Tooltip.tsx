"use client";

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { cx } from "./cx";

export interface TooltipProps {
  /** Tooltip text (short; ink fill, 11px). */
  content: ReactNode;
  /** The trigger. Must be focusable (button/link) unless `focusable` is set. */
  children: ReactNode;
  side?: "top" | "right" | "bottom";
  /** Wrap in a focusable span (needed for disabled buttons, which get no hover/focus events). */
  focusable?: boolean;
  block?: boolean;
  className?: string;
}

/** CSS-driven tooltip shown on hover and keyboard focus; wired with aria-describedby. */
export function Tooltip({ content, children, side = "top", focusable = false, block = false, className }: TooltipProps) {
  const id = useId();
  const trigger =
    !focusable && isValidElement(children)
      ? cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, { "aria-describedby": id })
      : children;
  return (
    <span
      className={cx("tooltip-anchor", className)}
      data-block={block || undefined}
      tabIndex={focusable ? 0 : undefined}
      aria-describedby={focusable ? id : undefined}
    >
      {trigger}
      <span role="tooltip" id={id} className="tooltip" data-side={side}>
        {content}
      </span>
    </span>
  );
}
