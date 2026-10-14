import type { ReactNode } from "react";

export interface StatusItem {
  /** Stable key (defaults to the text when it is a string). */
  key?: string;
  text: ReactNode;
  /** accent-700 text, e.g. "QuickBooks sync failing". */
  risk?: boolean;
}

export interface StatusBarProps {
  /** Only real, live system status — never marketing or disclosures. */
  items: Array<StatusItem | string>;
  /** Right-aligned workflow version, e.g. "v14". */
  version?: string;
  /** Degraded: shows "Pipeline paused — <reason>" first, in accent-700. */
  degraded?: string | null;
}

/** 34px status bar: 10.5px uppercase, 0.06em, neutral-700. */
export function StatusBar({ items, version, degraded }: StatusBarProps) {
  const list: StatusItem[] = items.map((i) => (typeof i === "string" ? { text: i } : i));
  return (
    <footer className="ledgic-statusbar" aria-label="System status">
      {degraded ? (
        <span data-tone="risk" role="status">
          Pipeline paused — {degraded}
        </span>
      ) : null}
      {list.map((item, idx) => (
        <span key={item.key ?? (typeof item.text === "string" ? item.text : idx)} data-tone={item.risk ? "risk" : undefined}>
          {item.text}
        </span>
      ))}
      {version ? <span className="ledgic-statusbar-version">{version}</span> : null}
    </footer>
  );
}
