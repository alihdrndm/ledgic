import "server-only";
import { cache } from "react";
import { untypedClient } from "@/lib/actions/db";

/* ------------------------------------------------------------------------------------------------
 * Row types (contracts/views.md). Numerics arrive as strings or numbers from PostgREST.
 * ---------------------------------------------------------------------------------------------- */
export type Num = string | number | null;

export interface BBox {
  page?: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface FieldValue {
  value: string | null;
  confidence: Num;
  raw_confidence?: Num;
  bbox?: BBox | null;
  source?: string;
  version?: number;
  set_by?: string | null;
  set_at?: string | null;
}

export interface InvoiceLine {
  id: string;
  line_no: number;
  description: string;
  qty: Num;
  uom: string | null;
  unit_price: Num;
  amount: Num;
  confidences: Record<string, Num> | null;
  bboxes: Record<string, BBox | null> | null;
  gl_number?: string | null;
  gl_name?: string | null;
  gl_confidence?: Num;
  po_line_id?: string | null;
}

export interface InvoiceDetail {
  org_id: string;
  invoice_id: string;
  document_id: string;
  invoice_number: string | null;
  terms: string | null;
  currency: string | null;
  invoice_date: string | null;
  due_date: string | null;
  subtotal: Num;
  tax: Num;
  freight: Num;
  total: Num;
  status: string;
  doc_confidence: Num;
  gate_passed: boolean | null;
  touchless: boolean | null;
  human_touches: number | null;
  extraction_mode: string | null;
  received_at: string | null;
  posted_at: string | null;
  duplicate_of: string | null;
  vendor_id: string | null;
  vendor_name: string | null;
  vendor_legal_name: string | null;
  vendor_category: string | null;
  entity_id: string | null;
  entity_name: string | null;
  entity_short_code: string | null;
  location_id: string | null;
  location_name: string | null;
  location_code: string | null;
  po_id: string | null;
  po_number: string | null;
  po_total: Num;
  po_source: string | null;
  grn_numbers: string[] | null;
  grn_received_at: string | null;
  grn_in_full: boolean | null;
  channel: string;
  storage_path: string | null;
  original_filename: string | null;
  mime: string | null;
  page_count: number | null;
  preprocessing: { skew_deg?: Num; perspective?: boolean; pages?: Array<string | { path?: string }> } | null;
  source_meta: Record<string, unknown> | null;
  run_id: string | null;
  run_number: number | null;
  workflow_version: string | null;
  fields: Record<string, FieldValue> | null;
  lines: InvoiceLine[] | null;
  erp_system: string | null;
  erp_external_id: string | null;
  erp_status: string | null;
}

export interface ReviewQueueRow {
  org_id: string;
  exception_id: string;
  invoice_id: string;
  run_id: string | null;
  queue_position: number;
  queue_size: number;
  opened_at: string;
  vendor_name: string | null;
  invoice_number: string | null;
  location_name: string | null;
  channel: string;
  original_filename: string | null;
  doc_confidence: Num;
  flagged_count: number;
}

export interface ExtractionStats {
  accuracy: Num;
  autoPassed: number | null;
  received: number | null;
  medianSeconds: Num;
  confidenceGate: Num;
  fieldFloor: Num;
  lastAutosaveAt: string | null;
  reviewQueueSize: number | null;
  workflowVersion: string | null;
  degraded: string | null;
}

/* ---------------------------------------------------------------------------------------------- */

export async function getReviewQueue(orgId: string): Promise<ReviewQueueRow[]> {
  const db = await untypedClient();
  const { data, error } = await db
    .from("v_review_queue")
    .select("*")
    .eq("org_id", orgId)
    .order("queue_position", { ascending: true })
    .limit(200);
  if (error) throw new Error(`review queue: ${error.message}`);
  return (data ?? []) as ReviewQueueRow[];
}

/** One invoice from v_invoice_detail (null when missing / not visible under RLS). Cached per request. */
export const getInvoiceDetail = cache(async (orgId: string, invoiceId: string): Promise<InvoiceDetail | null> => {
  if (!isUuid(invoiceId)) return null;
  const db = await untypedClient();
  const { data, error } = await db
    .from("v_invoice_detail")
    .select("*")
    .eq("org_id", orgId)
    .eq("invoice_id", invoiceId)
    .maybeSingle();
  if (error) throw new Error(`invoice detail: ${error.message}`);
  if (!data) return null;
  const d = data as InvoiceDetail;
  d.lines = [...(d.lines ?? [])].sort((a, b) => a.line_no - b.line_no);
  return d;
});

export async function getExtractionStats(orgId: string): Promise<ExtractionStats> {
  const db = await untypedClient();
  const [evalRes, stageRes, pipeRes, barRes] = await Promise.all([
    db.from("v_eval_weekly").select("accuracy, week_start").eq("org_id", orgId).order("week_start", { ascending: false }).limit(1).maybeSingle(),
    db
      .from("v_stage_today")
      .select("extraction_auto_passed, extraction_median_seconds, confidence_gate, field_floor")
      .eq("org_id", orgId)
      .maybeSingle(),
    db.from("v_pipeline_today").select("received").eq("org_id", orgId).maybeSingle(),
    db
      .from("v_status_bar")
      .select("last_autosave_at, review_queue_size, workflow_version, pipeline_paused_reason")
      .eq("org_id", orgId)
      .maybeSingle(),
  ]);
  const ev = evalRes.data as { accuracy: Num } | null;
  const st = stageRes.data as { extraction_auto_passed: number; extraction_median_seconds: Num; confidence_gate: Num; field_floor: Num } | null;
  const pi = pipeRes.data as { received: number } | null;
  const sb = barRes.data as { last_autosave_at: string | null; review_queue_size: number; workflow_version: string | null; pipeline_paused_reason: string | null } | null;
  return {
    accuracy: ev?.accuracy ?? null,
    autoPassed: st?.extraction_auto_passed ?? null,
    received: pi?.received ?? null,
    medianSeconds: st?.extraction_median_seconds ?? null,
    confidenceGate: st?.confidence_gate ?? "0.900",
    fieldFloor: st?.field_floor ?? "0.750",
    lastAutosaveAt: sb?.last_autosave_at ?? null,
    reviewQueueSize: sb?.review_queue_size ?? null,
    workflowVersion: sb?.workflow_version ?? null,
    degraded: sb?.pipeline_paused_reason ?? null,
  };
}

/** Storage path of the rendered page image (preprocessing.pages[n-1]) or the original image. */
export function pageImagePath(d: InvoiceDetail, page = 1): { path: string; kind: "image" | "pdf" } | null {
  const pages = d.preprocessing?.pages;
  const p = Array.isArray(pages) ? pages[page - 1] : undefined;
  const fromPages = typeof p === "string" ? p : p && typeof p === "object" ? p.path : undefined;
  if (fromPages) return { path: fromPages, kind: "image" };
  if (!d.storage_path) return null;
  if ((d.mime ?? "").startsWith("image/")) return { path: d.storage_path, kind: "image" };
  if ((d.mime ?? "").includes("pdf")) return { path: d.storage_path, kind: "pdf" };
  return null;
}

/** 5-minute signed URL for a document in bucket `documents` (storage RLS applies to the user). */
export async function signedDocumentUrl(path: string, expiresIn = 300): Promise<string | null> {
  const db = await untypedClient();
  const { data, error } = await db.storage.from("documents").createSignedUrl(path, expiresIn);
  if (error || !data?.signedUrl) return null;
  return data.signedUrl;
}

export function isUuid(v: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}
