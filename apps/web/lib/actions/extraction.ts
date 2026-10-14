"use server";

import { revalidatePath } from "next/cache";
import { untypedClient } from "./db";
import { clampTimeSpent, fromRpcError, validatePositive, type ActionResult } from "./result";
import { wakeRunInternal } from "./wake";

export interface ConfirmFieldInput {
  /** Header field name (e.g. "total", "invoice_number"). */
  field?: string;
  /** Line cell: invoice_lines.id + key. */
  lineId?: string;
  key?: "qty" | "unit_price" | "amount" | "description" | "uom";
  value: string;
}

export interface ConfirmExtractionInput {
  orgSlug: string;
  invoiceId: string;
  fields: ConfirmFieldInput[];
  /** Client-measured seconds from opening the item to confirming (capped at 1800). */
  timeSpent?: number | null;
}

const MONEY_FIELDS = new Set(["total", "subtotal", "tax", "freight", "unit_price", "amount"]);

/**
 * Extraction review confirm/correct → rpc_confirm_fields (as the user; the RPC enforces role ≥ ap_clerk,
 * open review exception, numeric validity, audit + resume) → best-effort core wake.
 */
export async function confirmExtraction(
  input: ConfirmExtractionInput,
): Promise<ActionResult<{ approvalId: string | null; runId: string | null; changed: number }>> {
  if (!input.invoiceId || !Array.isArray(input.fields) || input.fields.length === 0) {
    return { ok: false, code: "INVALID", message: "Nothing to confirm." };
  }
  const payload: Array<Record<string, string>> = [];
  for (const f of input.fields) {
    const name = f.field ?? f.key ?? "";
    let value = String(f.value ?? "").trim();
    if (name === "qty" || MONEY_FIELDS.has(name)) {
      const v = validatePositive(value, name === "qty" ? 3 : name === "unit_price" ? 4 : 2, name === "qty" ? "Quantity" : "Amount");
      if ("error" in v) return { ok: false, code: "INVALID", message: v.error };
      value = v.value;
    } else if (!value) {
      return { ok: false, code: "INVALID", message: "Values can't be blank." };
    }
    if (f.lineId && f.key) payload.push({ line_id: f.lineId, key: f.key, value });
    else if (f.field) payload.push({ field: f.field, value });
  }

  const supabase = await untypedClient();
  const { data, error } = await supabase.rpc("rpc_confirm_fields", {
    p_invoice_id: input.invoiceId,
    p_fields: payload,
    p_time_spent: clampTimeSpent(input.timeSpent),
  });
  if (error) return fromRpcError(error);
  const res = (data ?? {}) as { approval_id?: string; run_id?: string | null; changed?: number };
  if (res.run_id) await wakeRunInternal(res.run_id);
  revalidatePath(`/o/${input.orgSlug}/extraction`, "layout");
  return { ok: true, data: { approvalId: res.approval_id ?? null, runId: res.run_id ?? null, changed: res.changed ?? 0 } };
}
