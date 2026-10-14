"use client";

import { ScreenError } from "@/components/extraction/states";

export default function ExtractionError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Extraction review" reset={reset} />;
}
