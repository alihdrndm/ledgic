"use client";

import type { ReactNode } from "react";
import { Button, RiskCallout, Skeleton, StatCell, StatRow, EmptyState } from "@/components/ui";
import { Screen } from "@/components/shell";
import { AskLedgicButton, CopilotProvider } from "@/components/copilot";
import { duration, pct } from "@/lib/format";
import type { ExtractionStats } from "@/lib/queries/extraction";

/** Loading skeleton shaped like a stats row + two-pane body. */
export function ScreenLoading({ title, stats = 4, rail = 400, left }: { title: string; stats?: number; rail?: number; left?: number }) {
  return (
    <Screen title={title} context="Loading…">
      {stats ? (
        <StatRow>
          {Array.from({ length: stats }, (_, i) => (
            <StatCell key={i} label={<span className="skeleton-block" style={{ display: "inline-block", width: 90 }} />} value={<span className="skeleton-block" style={{ display: "inline-block", width: 70, height: 18 }} />} />
          ))}
        </StatRow>
      ) : null}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {left ? (
          <div style={{ width: left, flex: "none", borderRight: "var(--rule-major)", padding: "16px 20px" }}>
            <Skeleton rows={10} columns={[3, 1]} label={`Loading ${title}`} />
          </div>
        ) : null}
        <div style={{ flex: 1, padding: "18px 24px" }}>
          <Skeleton rows={8} columns={[4, 1, 1, 1, 1]} label={`Loading ${title}`} />
        </div>
        {rail ? (
          <div style={{ width: rail, flex: "none", borderLeft: "var(--rule-major)", padding: "16px 20px" }}>
            <Skeleton rows={6} columns={[1]} />
          </div>
        ) : null}
      </div>
    </Screen>
  );
}

/** Error boundary body: neutral RiskCallout (errors are not money at risk) with Retry. */
export function ScreenError({ title, reset, children }: { title: string; reset: () => void; children?: ReactNode }) {
  return (
    <Screen title={title}>
      <div style={{ padding: "18px 24px" }}>
        <RiskCallout
          tone="neutral"
          live
          title={`${title} couldn't load`}
          actions={
            <Button variant="ink" size="sm" onClick={reset}>
              Retry
            </Button>
          }
        >
          {children ?? "The data service didn't answer. Nothing was changed — try again in a moment."}
        </RiskCallout>
      </div>
    </Screen>
  );
}

/** Empty review queue. */
export function ExtractionEmpty({ stats }: { stats: ExtractionStats }) {
  return (
    <CopilotProvider>
      <Screen
        title="Extraction review"
        context={`0 of ${stats.received ?? "—"} documents need a person today`}
        riskChip={<AskLedgicButton />}
        degraded={stats.degraded}
        statusItems={["0 documents in queue"]}
        version={stats.workflowVersion ?? undefined}
      >
        <StatRow>
          <StatCell label="Field accuracy, sampled" value={pct(stats.accuracy)} />
          <StatCell label="Auto-passed today" value={`${stats.autoPassed ?? "—"} / ${stats.received ?? "—"}`} />
          <StatCell label="Median extraction" value={duration(stats.medianSeconds, { precise: true })} />
          <StatCell label="Queue position" value="—" />
        </StatRow>
        <EmptyState title="Queue clear">Every document today passed the confidence gate.</EmptyState>
      </Screen>
    </CopilotProvider>
  );
}
