"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "./cx";
import { Tooltip } from "./Tooltip";

export type ButtonVariant = "ink" | "outline" | "ghost";
export type ButtonSize = "md" | "sm";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Replaces the label with "Working…" and a 2px progress bar along the bottom edge. */
  loading?: boolean;
  /** Disables the button and shows this reason as a tooltip (e.g. "Needs controller"). */
  disabledReason?: string;
  /** Trailing keyboard hint, e.g. "↵" or "E". */
  kbd?: string;
  block?: boolean;
  children: ReactNode;
}

const variantClass: Record<ButtonVariant, string> = {
  ink: "btn-ink",
  outline: "btn-outline",
  ghost: "btn-plain",
};

/** Modernist button: zero radius, flush-left label, ink primary (never accent). */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "outline", size = "md", loading = false, disabledReason, kbd, block, className, children, disabled, type, ...rest },
  ref,
) {
  const isDisabled = Boolean(disabled || disabledReason);
  const btn = (
    <button
      ref={ref}
      type={type ?? "button"}
      className={cx("btn ledgic-btn", variantClass[variant], `ledgic-btn-${size}`, block && "ledgic-btn-block", className)}
      disabled={isDisabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <span>Working…</span>
          <span className="btn-progress" aria-hidden="true" />
        </>
      ) : (
        <>
          {children}
          {kbd ? (
            <kbd className="btn-kbd" aria-hidden="true">
              {kbd}
            </kbd>
          ) : null}
        </>
      )}
    </button>
  );
  if (disabledReason) {
    return (
      <Tooltip content={disabledReason} focusable block={block}>
        {btn}
      </Tooltip>
    );
  }
  return btn;
});
