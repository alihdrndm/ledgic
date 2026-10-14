"use client";

import { ScreenError } from "@/components/pipeline/ScreenError";

export default function PipelineError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Pipeline" what="the pipeline" error={error} reset={reset} />;
}
