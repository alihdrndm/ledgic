"use client";

import { EmptyState } from "@/components/ui";
import { Screen } from "@/components/shell";
import { AskLedgicButton, CopilotProvider } from "@/components/copilot";

export function MatchEmpty({ workflowVersion, degraded }: { workflowVersion: string | null; degraded: string | null }) {
  return (
    <CopilotProvider>
      <Screen
        title="Three-way match"
        context="No invoices matched yet"
        riskChip={<AskLedgicButton />}
        degraded={degraded}
        version={workflowVersion ?? undefined}
        searchOptional
      >
        <EmptyState title="Nothing to compare">No invoice has reached the three-way match today. Matches appear here as the pipeline runs.</EmptyState>
      </Screen>
    </CopilotProvider>
  );
}
