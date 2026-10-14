"use client";

import { useEffect } from "react";
import { Screen } from "@/components/shell";
import { Button, RiskCallout } from "@/components/ui";

export interface ScreenErrorProps {
  title: string;
  error: Error & { digest?: string };
  reset: () => void;
  what: string;
}

/** Route error state: neutral RiskCallout (errors are not money at risk) with Retry. */
export function ScreenError({ title, error, reset, what }: ScreenErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <Screen title={title}>
      <div style={{ padding: "18px var(--pad-page)" }}>
        <RiskCallout
          tone="neutral"
          live
          title={`Couldn't load ${what}`}
          actions={
            <Button variant="ink" size="sm" onClick={reset}>
              Retry
            </Button>
          }
        >
          {error.digest ? `The server reported an error (ref ${error.digest}).` : error.message || "Something went wrong."} Nothing
          was changed.
        </RiskCallout>
      </div>
    </Screen>
  );
}
