"use client";

import { ScreenError } from "@/components/pipeline/ScreenError";

export default function InvoicesError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ScreenError title="Invoices" what="invoices" error={error} reset={reset} />;
}
