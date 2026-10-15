import "server-only";
import { untypedClient } from "@/lib/actions/db";
import { isUuid, type Num } from "./extraction";

export interface Recommendation {
  action: string;
  pay_amount: Num;
  hold_amount: Num;
  confidence: Num;
  /** Templated bullets (06 §8). Strings, or `{text}` objects. */
  reasons: Array<string | { text?: string }> | null;
}

export interface Decision {
  approval_id: string;
  action: string;
  actor_id: string;
  actor_name: string | null;
  decided_at: string;
  pay_amount: Num;
  hold_amount: Num;
  comment: string | null;
}

export interface MatchLineRow {
  org_id: string;
  invoice_id: string;
  match_result_id: string;
  verdict: string;
  tolerance_pct: Num;
  tolerance_abs: Num;
  expected_total: Num;
  total_delta: Num;
  lines_verified: number;
  lines_total: number;
  duration_ms: number | null;
  computed_at: string;
  invoice_line_id: string;
  line_no: number;
  description: string;
  uom: string | null;
  inv_qty: Num;
  inv_unit_price: Num;
  inv_amount: Num;
  po_line_id: string | null;
  po_qty: Num;
  po_unit_price: Num;
  po_amount: Num;
  grn_qty: Num;
  expected_unit_price: Num;
  expected_source: string | null;
  expected_amount: Num;
  delta_amount: Num;
  allowed_amount: Num;
  delta_pct: Num;
  line_verdict: string;
  note: string | null;
  contract_id: string | null;
  contract_title: string | null;
  contract_document_path: string | null;
  contract_effective_to: string | null;
  clause_ref: string | null;
  exception_id: string | null;
  recommendation: Recommendation | null;
  decision: Decision | null;
}

export interface ExceptionLite {
  id: string;
  type: string;
  status: string;
  amount_at_risk: Num;
}

export interface MatchData {
  lines: MatchLineRow[];
  exception: ExceptionLite | null;
  contractUrl: string | null;
}

/** Line-level match rows for one invoice (v_match_detail), plus the exception they hang off. */
export async function getMatch(orgId: string, invoiceId: string): Promise<MatchData> {
  if (!isUuid(invoiceId)) return { lines: [], exception: null, contractUrl: null };
  const db = await untypedClient();
  const { data, error } = await db
    .from("v_match_detail")
    .select("*")
    .eq("org_id", orgId)
    .eq("invoice_id", invoiceId)
    .order("line_no", { ascending: true });
  if (error) throw new Error(`match detail: ${error.message}`);
  const lines = (data ?? []) as MatchLineRow[];
  const excId = lines.find((l) => l.exception_id)?.exception_id ?? null;
  let exception: ExceptionLite | null = null;
  if (excId) {
    const { data: ex } = await db.from("exceptions_public").select("id, type, status, amount_at_risk").eq("id", excId).maybeSingle();
    exception = (ex as ExceptionLite | null) ?? null;
  }
  const contractPath = lines.find((l) => l.contract_document_path)?.contract_document_path ?? null;
  let contractUrl: string | null = null;
  if (contractPath) {
    const { data: signed } = await db.storage.from("documents").createSignedUrl(contractPath, 600);
    contractUrl = signed?.signedUrl ?? null;
  }
  return { lines, exception, contractUrl };
}

/** Where /match (no id) should land: oldest open price/qty exception, else the latest matched invoice. */
export async function getDefaultMatchInvoice(orgId: string): Promise<string | null> {
  const db = await untypedClient();
  const { data: ex } = await db
    .from("v_exception_queue")
    .select("invoice_id, opened_at")
    .eq("org_id", orgId)
    .in("type", ["price_variance", "qty_mismatch", "unmatched_line"])
    .neq("status", "resolved")
    .order("opened_at", { ascending: true })
    .limit(1)
    .maybeSingle();
  if (ex && (ex as { invoice_id: string }).invoice_id) return (ex as { invoice_id: string }).invoice_id;
  // Latest received invoice that has a match result. Not v_match_detail: sorting that per-line view
  // across every invoice outlasts the statement timeout, which used to leave /match empty.
  const { data: m, error } = await db
    .from("invoices")
    .select("id, match_results!inner(invoice_id)")
    .eq("org_id", orgId)
    .order("received_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) console.error("getDefaultMatchInvoice:", error.message);
  return (m as { id: string } | null)?.id ?? null;
}

export async function getMatchStatus(orgId: string): Promise<{ workflowVersion: string | null; degraded: string | null }> {
  const db = await untypedClient();
  const { data } = await db.from("v_status_bar").select("workflow_version, pipeline_paused_reason").eq("org_id", orgId).maybeSingle();
  const r = data as { workflow_version: string | null; pipeline_paused_reason: string | null } | null;
  return { workflowVersion: r?.workflow_version ?? null, degraded: r?.pipeline_paused_reason ?? null };
}

export function reasonText(r: string | { text?: string }): string {
  return typeof r === "string" ? r : (r.text ?? "");
}
