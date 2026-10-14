"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui";
import { decideException, markExceptionViewed, type DecideExceptionInput, type DecisionAction } from "@/lib/actions/exceptions";

/**
 * Decision helper for an exception detail: measures time on task (opened → decided, capped 1800s by the
 * action), marks the exception viewed once, toasts on success and refreshes server data.
 */
export function useDecide(orgSlug: string, exceptionId: string) {
  const router = useRouter();
  const { toast } = useToast();
  const openedAt = useRef(Date.now());
  const [busy, setBusy] = useState<DecisionAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ action: DecisionAction; at: string; comment: string | null } | null>(null);

  useEffect(() => {
    openedAt.current = Date.now();
    setError(null);
    setDone(null);
    void markExceptionViewed(exceptionId).catch(() => undefined);
  }, [exceptionId]);

  const decide = useCallback(
    async (
      action: DecisionAction,
      opts: Omit<DecideExceptionInput, "orgSlug" | "exceptionId" | "action" | "timeSpent"> & { success: string; inDialog?: boolean },
    ): Promise<string | void> => {
      setBusy(action);
      setError(null);
      const { success, inDialog, ...rest } = opts;
      const res = await decideException({
        orgSlug,
        exceptionId,
        action,
        timeSpent: (Date.now() - openedAt.current) / 1000,
        ...rest,
      });
      setBusy(null);
      if (!res.ok) {
        if (res.code === "CONFLICT") router.refresh();
        if (inDialog) return res.message;
        setError(res.message);
        return;
      }
      toast(success);
      setDone({ action, at: new Date().toISOString(), comment: rest.comment ?? null });
      router.refresh();
    },
    [orgSlug, exceptionId, router, toast],
  );

  return { decide, busy, error, setError, done };
}
