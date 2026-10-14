"use client";

import { ScreenError } from "@/components/pipeline/ScreenError";

export default function InvoiceError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Invoice" what="this invoice" error={error} reset={reset} />;
}
