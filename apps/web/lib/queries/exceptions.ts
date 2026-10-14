import "server-only";
import { untypedClient } from "@/lib/actions/db";
import { getInvoiceDetail, isUuid, pageImagePath, signedDocumentUrl, type InvoiceDetail, type Num } from "./extraction";
import { getMatch, type Decision, type MatchData, type Recommendation } from "./match";

export interface ExceptionQueueRow {
  org_id: string;
  exception_id: string;
  invoice_id: string;
  run_id: string | null;
  type: string;
  group_label: string;
  is_risk_group: boolean;
  status: string;
  amount_at_risk: Num;
  reason: string;
  assigned_role: string;
  assigned_to: string | null;
  assigned_to_name: string | null;
  escalated: boolean;
  opened_at: string;
  sla_due_at: string | null;
  first_viewed_at: string | null;
  resolved_at: string | null;
  age_seconds: number;
  vendor_id: string | null;
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_total: Num;
  location_name: string | null;
  payment_blocked: boolean;
  similarity: Num;
  duplicate_evidence: (Record<string, unknown> & { candidate_invoice_id?: string }) | null;
  signal_score: Num;
  signals: Array<{ signal: string; weight: Num; detail?: Record<string, unknown> | null }> | null;
  recommendation: Recommendation | null;
  latest_decision: Decision | null;
  has_draft: boolean;
}

export interface ExceptionHeader {
  open: number | null;
  raisedToday: number | null;
  clearedToday: number | null;
  paymentsBlocked: number | null;
  workflowVersion: string | null;
  degraded: string | null;
}

export interface AuditEntry {
  id: number;
  at: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export interface DraftRow {
  id: string;
  kind: "vendor_notice" | "explanation";
  body_md: string;
  citations: Array<{ n?: number; chunk_id?: string; document_id?: string; title?: string; clause_ref?: string | null; quote?: string }>;
  model: string | null;
  prompt_version: string | null;
  mode: "live" | "recorded";
  created_at: string;
}

export interface DocMeta {
  id: string;
  channel: string;
  sha256: string;
  received_at: string;
  original_filename: string | null;
  source_meta: Record<string, unknown> | null;
  mime: string;
}

export interface DuplicateCopy {
  invoice: InvoiceDetail;
  doc: DocMeta | null;
  thumbUrl: string | null;
  uploadedBy: string | null;
}

export interface VendorRecord {
  id: string;
  display_name: string;
  legal_name: string | null;
  tax_id_last4: string | null;
  remit_address: Record<string, unknown> | string | null;
  remit_address_changed_at: string | null;
  bank_last4: string | null;
  bank_fingerprint: string | null;
  w9_on_file: boolean;
  w9_bank_fingerprint: string | null;
  contact_email: string | null;
  created_at: string;
}

export interface OpenPo {
  id: string;
  po_number: string;
  total: Num;
  ordered_at: string;
  location_id: string;
  status: string;
}

export interface PostingRow {
  system: string;
  status: string;
  external_id: string | null;
  attempts: number;
  error: string | null;
  response: unknown;
  posted_at: string | null;
}

export interface ExceptionDetail {
  row: ExceptionQueueRow;
  invoice: InvoiceDetail | null;
  audit: AuditEntry[];
  actorNames: Record<string, string>;
  drafts: DraftRow[];
  match: MatchData | null;
  copies: DuplicateCopy[] | null;
  vendor: VendorRecord | null;
  openPos: OpenPo[] | null;
  postings: PostingRow[] | null;
}

/* ---------------------------------------------------------------------------------------------- */

export async function getExceptionQueue(orgId: string): Promise<ExceptionQueueRow[]> {
  const db = await untypedClient();
  const { data, error } = await db
    .from("v_exception_queue")
    .select("*")
    .eq("org_id", orgId)
    .neq("status", "resolved")
    .order("opened_at", { ascending: true })
    .limit(500);
  if (error) throw new Error(`exception queue: ${error.message}`);
  return (data ?? []) as ExceptionQueueRow[];
}

export async function getExceptionHeader(orgId: string): Promise<ExceptionHeader> {
  const db = await untypedClient();
  const { data } = await db
    .from("v_status_bar")
    .select("exceptions_open, exceptions_raised_today, exceptions_cleared_today, payments_blocked, workflow_version, pipeline_paused_reason")
    .eq("org_id", orgId)
    .maybeSingle();
  const r = data as {
    exceptions_open: number;
    exceptions_raised_today: number;
    exceptions_cleared_today: number;
    payments_blocked: number;
    workflow_version: string | null;
    pipeline_paused_reason: string | null;
  } | null;
  return {
    open: r?.exceptions_open ?? null,
    raisedToday: r?.exceptions_raised_today ?? null,
    clearedToday: r?.exceptions_cleared_today ?? null,
    paymentsBlocked: r?.payments_blocked ?? null,
    workflowVersion: r?.workflow_version ?? null,
    degraded: r?.pipeline_paused_reason ?? null,
  };
}

async function docMeta(documentId: string | null | undefined): Promise<DocMeta | null> {
  if (!documentId) return null;
  const db = await untypedClient();
  const { data } = await db
    .from("documents")
    .select("id, channel, sha256, received_at, original_filename, source_meta, mime")
    .eq("id", documentId)
    .maybeSingle();
  return (data as DocMeta | null) ?? null;
}

async function profileNames(ids: string[]): Promise<Record<string, string>> {
  const uniq = [...new Set(ids.filter((i) => isUuid(i)))];
  if (uniq.length === 0) return {};
  const db = await untypedClient();
  const { data } = await db.from("profiles").select("user_id, full_name").in("user_id", uniq);
  const out: Record<string, string> = {};
  for (const p of (data ?? []) as Array<{ user_id: string; full_name: string }>) out[p.user_id] = p.full_name;
  return out;
}

export async function getExceptionDetail(orgId: string, exceptionId: string): Promise<ExceptionDetail | null> {
  if (!isUuid(exceptionId)) return null;
  const db = await untypedClient();
  const { data, error } = await db
    .from("v_exception_queue")
    .select("*")
    .eq("org_id", orgId)
    .eq("exception_id", exceptionId)
    .maybeSingle();
  if (error) throw new Error(`exception: ${error.message}`);
  if (!data) return null;
  const row = data as ExceptionQueueRow;

  const [invoice, auditRes, draftRes] = await Promise.all([
    getInvoiceDetail(orgId, row.invoice_id),
    db
      .from("audit_log")
      .select("id, at, actor_type, actor_id, action, entity_type, entity_id, before, after")
      .eq("org_id", orgId)
      .in("entity_id", [row.invoice_id, row.exception_id])
      .order("id", { ascending: true })
      .limit(60),
    db
      .from("exception_drafts")
      .select("id, kind, body_md, citations, model, prompt_version, mode, created_at")
      .eq("exception_id", exceptionId)
      .order("created_at", { ascending: false })
      .limit(10),
  ]);
  const audit = (auditRes.data ?? []) as AuditEntry[];
  const actorNames = await profileNames(audit.map((a) => a.actor_id ?? ""));

  // Latest draft per kind.
  const drafts: DraftRow[] = [];
  for (const d of (draftRes.data ?? []) as DraftRow[]) if (!drafts.some((x) => x.kind === d.kind)) drafts.push(d);

  const detail: ExceptionDetail = {
    row,
    invoice,
    audit,
    actorNames,
    drafts,
    match: null,
    copies: null,
    vendor: null,
    openPos: null,
    postings: null,
  };

  switch (row.type) {
    case "price_variance":
    case "qty_mismatch":
    case "unmatched_line":
      detail.match = await getMatch(orgId, row.invoice_id);
      break;
    case "duplicate": {
      const candId = row.duplicate_evidence?.candidate_invoice_id;
      const other = candId ? await getInvoiceDetail(orgId, candId) : null;
      // Copy A = the earlier-received document, Copy B = the later one.
      const pair = [invoice, other].filter((x): x is InvoiceDetail => Boolean(x));
      pair.sort((a, b) => String(a.received_at).localeCompare(String(b.received_at)));
      detail.copies = await Promise.all(
        pair.map(async (inv) => {
          const doc = await docMeta(inv.document_id);
          const img = pageImagePath(inv);
          const thumbUrl = img && img.kind === "image" ? await signedDocumentUrl(img.path) : null;
          const by = (doc?.source_meta?.uploaded_by as string | undefined) ?? null;
          const names = by ? await profileNames([by]) : {};
          return { invoice: inv, doc, thumbUrl, uploadedBy: by ? (names[by] ?? null) : null };
        }),
      );
      break;
    }
    case "new_vendor_screen": {
      if (row.vendor_id) {
        const { data: v } = await db
          .from("vendors")
          .select(
            "id, display_name, legal_name, tax_id_last4, remit_address, remit_address_changed_at, bank_last4, bank_fingerprint, w9_on_file, w9_bank_fingerprint, contact_email, created_at",
          )
          .eq("id", row.vendor_id)
          .maybeSingle();
        detail.vendor = (v as VendorRecord | null) ?? null;
      }
      break;
    }
    case "no_po": {
      if (row.vendor_id) {
        let q = db
          .from("purchase_orders")
          .select("id, po_number, total, ordered_at, location_id, status")
          .eq("org_id", orgId)
          .eq("vendor_id", row.vendor_id)
          .eq("status", "open")
          .order("ordered_at", { ascending: false })
          .limit(50);
        if (invoice?.location_id) q = q.eq("location_id", invoice.location_id);
        const { data: pos } = await q;
        detail.openPos = (pos ?? []) as OpenPo[];
      } else detail.openPos = [];
      break;
    }
    case "posting_failed": {
      const { data: p } = await db
        .from("erp_postings")
        .select("system, status, external_id, attempts, error, response, posted_at")
        .eq("invoice_id", row.invoice_id);
      detail.postings = (p ?? []) as PostingRow[];
      break;
    }
  }
  return detail;
}

/** Open new-vendor screens (for the fraud callout on other details). */
export function openFraudScreens(queue: ExceptionQueueRow[]): ExceptionQueueRow[] {
  return queue.filter((q) => q.type === "new_vendor_screen" && q.status !== "resolved");
}

/** UI label for a fraud signal (domain/fraud.py labels; detail may override). */
export function signalLabel(s: { signal: string; detail?: Record<string, unknown> | null }): string {
  const d = s.detail ?? {};
  if (typeof d.label === "string" && d.label) return d.label;
  switch (s.signal) {
    case "bank_mismatch_w9":
      return "Bank details differ from the W-9 on file";
    case "vendor_age_lt_14d": {
      const days = d.age_days ?? d.days;
      return days !== undefined ? `Vendor record ${days} day${String(days) === "1" ? "" : "s"} old` : "Vendor record under 14 days old";
    }
    case "no_po":
      return "No purchase order";
    case "remit_address_new":
      return "Remit-to address recently added or changed";
    case "amount_anomaly":
      return d.z ? `Amount is ${d.z}σ above this vendor's 90-day mean` : "Amount unusual for this vendor";
    default:
      return s.signal.replace(/_/g, " ");
  }
}
