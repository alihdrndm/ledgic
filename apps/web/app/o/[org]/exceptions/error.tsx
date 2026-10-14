"use client";

import { ScreenError } from "@/components/extraction/states";

export default function ExceptionsError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Exceptions" reset={reset} />;
}
