"use client";

import { ScreenError } from "@/components/pipeline/ScreenError";

export default function OperationsError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Operations" what="operations figures" error={error} reset={reset} />;
}
