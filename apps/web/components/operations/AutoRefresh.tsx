"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Re-runs the server components every `seconds` (Operations reads minute-refreshed materialized views). */
export function AutoRefresh({ seconds = 60 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds]);
  return null;
}
