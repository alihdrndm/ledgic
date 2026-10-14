import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Header section label, e.g. "Run inspector". */
  label: ReactNode;
  /** Right side of the header, e.g. "run 88,412". */
  meta?: ReactNode;
  footer?: ReactNode;
  /** Fixed width in px (392 run inspector, 400 decision rail). Adds a 2px left rule. */
  width?: number;
  children: ReactNode;
}

/** Right-rail container: header (2px rule), scrolling body, footer (2px top rule). */
export function Panel({ label, meta, footer, width, className, children, style, ...rest }: PanelProps) {
  return (
    <section
      className={cx("panel", className)}
      style={width ? { width, flex: "none", borderLeft: "var(--rule-major)", ...style } : style}
      {...rest}
    >
      <header className="panel-header">
        <h2 className="section-label section-header-title">{label}</h2>
        {meta ? <span className="meta">{meta}</span> : null}
      </header>
      <div className="panel-body">{children}</div>
      {footer ? <footer className="panel-footer meta">{footer}</footer> : null}
    </section>
  );
}
