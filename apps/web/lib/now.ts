"use client";

import { useEffect, useState } from "react";

/** Wall-clock time that re-renders every `intervalMs`, so relative ages stay current without calling Date.now() in render. */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
