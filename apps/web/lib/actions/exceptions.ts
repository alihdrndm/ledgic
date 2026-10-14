"use server";

import Decimal from "decimal.js";
import { revalidatePath } from "next/cache";
import { coreJson } from "@/lib/core";
import { untypedClient } from "./db";
import { clampTimeSpent, fromRpcError, moneyString, type ActionResult } from "./result";
import { wakeRunInternal } from "./wake";

export type DecisionAction =
  | "short_pay"
  | "approve_as_is"
  | "dispute"
  | "reject_invoice"
  | "link_po"
  | "approve_without_po"
  | "merge"
  | "reject_copy"
  | "not_duplicate"
  | "request_w9"
  | "release_hold"
  | "retry_posting";

const ACTIONS = new Set<DecisionAction>([
  "short_pay",
  "approve_as_is",
  "dispute",
  "reject_invoice",
  "link_po",
  "approve_without_po",
  "merge",
  "reject_copy",
  "not_duplicate",
  "request_w9",
  "release_hold",
  "retry_posting",
]);

const COMMENT_REQUIRED = new Set<DecisionAction>(["approve_as_is", "approve_without_po", "not_duplicate", "release_hold", "dispute"]);

export interface DecideExceptionInput {
  orgSlug: string;
  exceptionId: string;
  action: DecisionAction;
  /** Decimal strings, 2 dp. Short-pay defaults to the recommendation when both are omitted. */
  payAmount?: string | null;
  holdAmount?: string | null;
  comment?: string | null;
  timeSpent?: number | null;
  extra?: { po_id?: string; keep_invoice_id?: string; verified_by_phone?: boolean };
}

export interface DecisionOutcome {
  approvalId: string | null;
  runId: string | null;
  exceptionStatus: string | null;
}

/**
 * Every money / duplicate / fraud / posting decision → rpc_decide_exception with the user's session.
 * The RPC is the authority for roles, limits and segregation of duties; this only shapes input.
 */
export async function decideException(input: DecideExceptionInput): Promise<ActionResult<DecisionOutcome>> {
  if (!input.exceptionId || !ACTIONS.has(input.action)) {
    return { ok: false, code: "INVALID", message: "Action not allowed for this exception" };
  }
  const comment = (input.comment ?? "").trim();
  if (COMMENT_REQUIRED.has(input.action) && !comment) {
    return { ok: false, code: "INVALID", message: "A comment is required for this decision." };
  }
  if (input.action === "release_hold" && input.extra?.verified_by_phone !== true) {
    return { ok: false, code: "INVALID", message: "Confirm you verified the bank details with the vendor by phone." };
  }
  if (input.action === "link_po" && !input.extra?.po_id) {
    return { ok: false, code: "INVALID", message: "Choose a purchase order to link." };
  }
  const pay = moneyString(input.payAmount);
  const hold = moneyString(input.holdAmount);
  if ((input.payAmount && !pay) || (input.holdAmount && !hold)) {
    return { ok: false, code: "INVALID", message: "Amounts must be numbers with two decimals." };
  }
  if (input.action === "short_pay" && hold && new Decimal(hold).lte(0)) {
    return { ok: false, code: "INVALID", message: "The held amount must be greater than zero." };
  }

  const supabase = await untypedClient();
  const { data, error } = await supabase.rpc("rpc_decide_exception", {
    p_exception_id: input.exceptionId,
    p_action: input.action,
    p_pay_amount: pay,
    p_hold_amount: hold,
    p_comment: comment || null,
    p_time_spent: clampTimeSpent(input.timeSpent),
    p_extra: input.extra ?? {},
  });
  if (error) return fromRpcError(error);
  const res = (data ?? {}) as { approval_id?: string; run_id?: string | null; exception_status?: string };
  if (res.run_id) await wakeRunInternal(res.run_id);
  revalidatePath(`/o/${input.orgSlug}`, "layout");
  return {
    ok: true,
    data: { approvalId: res.approval_id ?? null, runId: res.run_id ?? null, exceptionStatus: res.exception_status ?? null },
  };
}

export interface DraftResult {
  draft_id: string;
  kind: "vendor_notice" | "explanation";
  body_md: string;
  citations: Array<{ n?: number; chunk_id?: string; document_id?: string; title?: string; clause_ref?: string | null; quote?: string }>;
  mode: "live" | "recorded";
  model: string | null;
  prompt_version: string | null;
  cost_usd: string;
  created_at: string;
  guard?: { passed: boolean; figures: string[] };
}

/** Resolution-agent draft (vendor notice / explanation) via core POST /v1/exceptions/{id}/draft as the user. */
export async function requestDraft(input: {
  orgSlug: string;
  exceptionId: string;
  kind: "vendor_notice" | "explanation";
  regenerate?: boolean;
}): Promise<ActionResult<DraftResult>> {
  if (!/^[0-9a-f-]{36}$/i.test(input.exceptionId)) return { ok: false, code: "INVALID", message: "Unknown exception." };
  const res = await coreJson<DraftResult>(`/v1/exceptions/${input.exceptionId}/draft`, {
    method: "POST",
    body: { kind: input.kind, regenerate: Boolean(input.regenerate) },
    timeoutMs: 60000,
  });
  if (!res.ok) {
    const code =
      res.error.code === "FORBIDDEN"
        ? "FORBIDDEN"
        : res.error.code === "NOT_FOUND"
          ? "NOT_FOUND"
          : res.error.code === "CORE_UNAVAILABLE"
            ? "UNAVAILABLE"
            : "ERROR";
    return { ok: false, code, message: res.error.message || "The resolution agent couldn't draft this right now." };
  }
  revalidatePath(`/o/${input.orgSlug}/exceptions/${input.exceptionId}`);
  return { ok: true, data: res.data };
}

/** Public wake action (e.g. a "Retry" control). Best effort. */
export async function wakeRun(runId: string): Promise<ActionResult<{ queued: boolean }>> {
  const queued = await wakeRunInternal(runId);
  return { ok: true, data: { queued } };
}

/** rpc_mark_exception_viewed — first_viewed_at + ui_events(opened). Silent on failure. */
export async function markExceptionViewed(exceptionId: string): Promise<void> {
  if (!/^[0-9a-f-]{36}$/i.test(exceptionId)) return;
  const supabase = await untypedClient();
  await supabase.rpc("rpc_mark_exception_viewed", { p_exception_id: exceptionId });
}
