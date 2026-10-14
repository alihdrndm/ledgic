"use client";

import { ScreenError } from "@/components/extraction/states";

export default function MatchError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Three-way match" reset={reset} />;
}
