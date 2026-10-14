"use client";

import type { ReactNode } from "react";
import { TopBar, type TopBarProps } from "./TopBar";
import { StatusBar, type StatusItem } from "./StatusBar";
import { useOptionalShell } from "./ShellContext";

export interface ScreenProps extends TopBarProps {
  /** Status bar items for this screen (02-design-system §5.3). */
  statusItems?: Array<StatusItem | string>;
  /** Degraded reason → "Pipeline paused — <reason>" in accent-700. */
  degraded?: string | null;
  /** Override the shell's version label. */
  version?: string;
  children: ReactNode;
}

/**
 * One authenticated screen: TopBar + scrolling content + StatusBar.
 * Every page under /o/[org]/ renders exactly one <Screen>. Server-rendered children pass straight through.
 */
export function Screen({ statusItems = [], degraded, version, children, ...topBar }: ScreenProps) {
  const shell = useOptionalShell();
  return (
    <div className="ledgic-screen">
      <TopBar
        {...topBar}
        status={degraded ? { text: topBar.status?.text ?? `Paused — ${degraded}`, degraded: true } : topBar.status}
      />
      <main className="ledgic-content" id="main">
        {children}
      </main>
      <StatusBar items={statusItems} version={version ?? shell?.version} degraded={degraded} />
    </div>
  );
}
