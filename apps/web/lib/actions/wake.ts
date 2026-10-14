import "server-only";
import { coreJson } from "@/lib/core";

/**
 * POST /v1/runs/{id}/wake — belt-and-braces nudge after an RPC decision (the RPC already pg_notify'd).
 * Best effort: failures are swallowed, the worker's poll picks the run up anyway.
 */
export async function wakeRunInternal(runId: string): Promise<boolean> {
  if (!/^[0-9a-f-]{36}$/i.test(runId)) return false;
  const res = await coreJson<{ run_id: string; status: string; queued: boolean }>(`/v1/runs/${runId}/wake`, {
    method: "POST",
    body: {},
    timeoutMs: 4000,
  });
  return res.ok;
}
