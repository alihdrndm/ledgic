import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";
import { getRunTimeline, viewClient, type Num, type RecentRunRow, type RunTimelineRow } from "./pipeline";

export const INVOICE_SEGMENTS = ["all", "touchless", "exceptions", "posted", "held"] as const;
export type InvoiceSegment = (typeof INVOICE_SEGMENTS)[number];
export const INVOICES_PAGE_SIZE = 50;

export interface InvoiceListFilters {
  segment: InvoiceSegment;
  vendor?: string;
  location?: string;
  /** yyyy-mm-dd, org-local day boundaries are approximated in UTC. */
  from?: string;
  to?: string;
  page: number;
}

type SP = Record<string, string | string[] | undefined>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) || undefined;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function parseInvoiceFilters(sp: SP): InvoiceListFilters {
  const seg = first(sp.status);
  const vendor = first(sp.vendor);
  const location = first(sp.location);
  const from = first(sp.from);
  const to = first(sp.to);
  const page = Number.parseInt(first(sp.page) ?? "1", 10);
  return {
    segment: (INVOICE_SEGMENTS as readonly string[]).includes(seg ?? "") ? (seg as InvoiceSegment) : "all",
    vendor: vendor && UUID.test(vendor) ? vendor : undefined,
    location: location && UUID.test(location) ? location : undefined,
    from: from && DATE.test(from) ? from : undefined,
    to: to && DATE.test(to) ? to : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export interface Option {
  id: string;
  name: string;
}

export interface InvoiceListData {
  rows: RecentRunRow[];
  total: number;
  vendors: Option[];
  locations: Option[];
}

function must<T>(res: { data: T; error: { message: string } | null }, what: string): T {
  if (res.error) throw new Error(`${what}: ${res.error.message}`);
  return res.data;
}

function nextDay(d: string): string {
  const t = new Date(`${d}T00:00:00Z`);
  t.setUTCDate(t.getUTCDate() + 1);
  return t.toISOString().slice(0, 10);
}

export async function getInvoiceList(
  supabase: SupabaseClient<Database>,
  orgId: string,
  f: InvoiceListFilters,
): Promise<InvoiceListData> {
  const db = viewClient(supabase);
  let q = db
    .from("v_recent_runs")
    .select("*", { count: "exact" })
    .eq("org_id", orgId)
    .not("invoice_id", "is", null);
  switch (f.segment) {
    case "touchless":
      q = q.eq("touchless", true);
      break;
    case "exceptions":
      q = q.eq("is_exception", true);
      break;
    case "posted":
      q = q.eq("invoice_status", "posted");
      break;
    case "held":
      // Payment blocked: open duplicate / new-vendor screen (exception_type) holds.
      q = q.in("open_exception_type", ["duplicate", "new_vendor_screen"]);
      break;
  }
  if (f.vendor) q = q.eq("vendor_id", f.vendor);
  if (f.location) q = q.eq("location_id", f.location);
  if (f.from) q = q.gte("started_at", `${f.from}T00:00:00Z`);
  if (f.to) q = q.lt("started_at", `${nextDay(f.to)}T00:00:00Z`);
  const offset = (f.page - 1) * INVOICES_PAGE_SIZE;
  q = q.order("started_at", { ascending: false }).range(offset, offset + INVOICES_PAGE_SIZE - 1);

  const [listRes, vendorsRes, locationsRes] = await Promise.all([
    q,
    supabase.from("vendors").select("id, display_name").eq("org_id", orgId).order("display_name"),
    supabase.from("locations").select("id, name").eq("org_id", orgId).order("name"),
  ]);
  const rows = (must(listRes, "v_recent_runs") ?? []) as RecentRunRow[];
  return {
    rows,
    total: listRes.count ?? rows.length,
    vendors: ((vendorsRes.data ?? []) as { id: string; display_name: string }[]).map((v) => ({ id: v.id, name: v.display_name })),
    locations: ((locationsRes.data ?? []) as { id: string; name: string }[]).map((l) => ({ id: l.id, name: l.name })),
  };
}

// ---------------------------------------------------------------- detail

export interface InvoiceLineJson {
  id: string;
  line_no: number;
  description: string;
  qty: Num | null;
  uom: string | null;
  unit_price: Num | null;
  amount: Num | null;
  confidences: Record<string, Num> | null;
  gl_number: string | null;
  gl_name: string | null;
  gl_confidence: Num | null;
  po_line_id: string | null;
}

export interface InvoiceDetailRow {
  org_id: string;
  invoice_id: string;
  document_id: string;
  invoice_number: string | null;
  terms: string | null;
  currency: string | null;
  invoice_date: string | null;
  due_date: string | null;
  subtotal: Num | null;
  tax: Num | null;
  freight: Num | null;
  total: Num | null;
  status: string;
  doc_confidence: Num | null;
  gate_passed: boolean | null;
  touchless: boolean | null;
  human_touches: number;
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
  po_total: Num | null;
  po_source: string | null;
  grn_numbers: string[] | null;
  grn_received_at: string | null;
  grn_in_full: boolean | null;
  channel: string;
  storage_path: string | null;
  original_filename: string | null;
  mime: string | null;
  page_count: number | null;
  preprocessing: { pages?: unknown[] } | null;
  source_meta: Record<string, unknown> | null;
  run_id: string | null;
  run_number: number | null;
  workflow_version: string | null;
  lines: InvoiceLineJson[] | null;
  erp_system: string | null;
  erp_external_id: string | null;
  erp_status: string | null;
}

export interface MatchLineRow {
  verdict: string;
  invoice_line_id: string;
  line_no: number;
  description: string;
  uom: string | null;
  inv_qty: Num | null;
  inv_unit_price: Num | null;
  inv_amount: Num | null;
  po_qty: Num | null;
  po_unit_price: Num | null;
  po_amount: Num | null;
  grn_qty: Num | null;
  delta_amount: Num | null;
  delta_pct: Num | null;
  line_verdict: string;
  note: string | null;
}

export interface AuditRow {
  id: number;
  at: string;
  actor_type: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before: unknown;
  after: unknown;
  hash: string;
}

export interface InvoiceStatusInfo {
  label: string | null;
  isException: boolean;
  openExceptionId: string | null;
}

export async function getInvoiceDetail(
  supabase: SupabaseClient<Database>,
  orgId: string,
  invoiceId: string,
): Promise<{ invoice: InvoiceDetailRow; status: InvoiceStatusInfo } | null> {
  if (!UUID.test(invoiceId)) return null;
  const db = viewClient(supabase);
  const [res, runRes] = await Promise.all([
    db.from("v_invoice_detail").select("*").eq("org_id", orgId).eq("invoice_id", invoiceId).maybeSingle(),
    db
      .from("v_recent_runs")
      .select("status_label, is_exception, open_exception_id")
      .eq("org_id", orgId)
      .eq("invoice_id", invoiceId)
      .order("started_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
  ]);
  const invoice = must(res, "v_invoice_detail") as InvoiceDetailRow | null;
  if (!invoice) return null;
  const run = runRes.data as { status_label: string; is_exception: boolean; open_exception_id: string | null } | null;
  return {
    invoice,
    status: {
      label: run?.status_label ?? null,
      isException: run?.is_exception ?? false,
      openExceptionId: run?.open_exception_id ?? null,
    },
  };
}

export async function getMatchLines(supabase: SupabaseClient<Database>, orgId: string, invoiceId: string): Promise<MatchLineRow[]> {
  const db = viewClient(supabase);
  const res = await db
    .from("v_match_detail")
    .select(
      "verdict, invoice_line_id, line_no, description, uom, inv_qty, inv_unit_price, inv_amount, po_qty, po_unit_price, po_amount, grn_qty, delta_amount, delta_pct, line_verdict, note",
    )
    .eq("org_id", orgId)
    .eq("invoice_id", invoiceId)
    .order("line_no", { ascending: true });
  if (res.error) return [];
  return (res.data ?? []) as MatchLineRow[];
}

export async function getInvoiceTimeline(
  supabase: SupabaseClient<Database>,
  orgId: string,
  runId: string | null,
): Promise<RunTimelineRow[]> {
  return runId ? getRunTimeline(supabase, orgId, runId) : [];
}

/** Every audit row about this invoice or the records hanging off it (fields, lines, exceptions, approvals, postings). */
export async function getInvoiceAudit(
  supabase: SupabaseClient<Database>,
  orgId: string,
  invoiceId: string,
): Promise<AuditRow[]> {
  const db = viewClient(supabase);
  const [exc, lines, fields, postings] = await Promise.all([
    db.from("exceptions_public").select("id").eq("org_id", orgId).eq("invoice_id", invoiceId),
    supabase.from("invoice_lines").select("id").eq("invoice_id", invoiceId),
    supabase.from("invoice_fields").select("id").eq("invoice_id", invoiceId),
    supabase.from("erp_postings").select("id").eq("invoice_id", invoiceId),
  ]);
  const excIds = ((exc.data ?? []) as { id: string }[]).map((r) => r.id);
  const approvals = excIds.length
    ? await supabase.from("approvals").select("id").in("exception_id", excIds)
    : { data: [] as { id: string }[] };
  const ids = [
    invoiceId,
    ...excIds,
    ...((approvals.data ?? []) as { id: string }[]).map((r) => r.id),
    ...((lines.data ?? []) as { id: string }[]).map((r) => r.id),
    ...((fields.data ?? []) as { id: string }[]).map((r) => r.id),
    ...((postings.data ?? []) as { id: string }[]).map((r) => r.id),
  ];
  const res = await db
    .from("v_invoice_audit")
    .select("audit_id, at, actor_type, actor_id, actor_name, action, entity_type, entity_id, before, after, hash")
    .eq("org_id", orgId)
    .or(`invoice_key.eq.${invoiceId},entity_id.in.(${ids.join(",")})`)
    .order("audit_id", { ascending: true })
    .limit(500);
  const rows = (must(res, "v_invoice_audit") ?? []) as (Omit<AuditRow, "id"> & { audit_id: number })[];
  return rows.map(({ audit_id, ...r }) => ({ ...r, id: audit_id }));
}

/** Signed URL (5 min) for the first rendered page, else the original file, in the private `documents` bucket. */
export async function getDocumentUrl(
  supabase: SupabaseClient<Database>,
  invoice: InvoiceDetailRow,
): Promise<{ url: string; kind: "image" | "pdf" } | null> {
  const pages = Array.isArray(invoice.preprocessing?.pages) ? invoice.preprocessing.pages : [];
  const firstPage = pages[0];
  const pagePath =
    typeof firstPage === "string"
      ? firstPage
      : firstPage && typeof firstPage === "object" && "path" in firstPage && typeof firstPage.path === "string"
        ? firstPage.path
        : null;
  const path = pagePath ?? invoice.storage_path;
  if (!path) return null;
  const key = path.replace(/^\/+/, "").replace(/^documents\//, "");
  const { data, error } = await supabase.storage.from("documents").createSignedUrl(key, 300);
  if (error || !data?.signedUrl) return null;
  const isPdf = !pagePath && (invoice.mime === "application/pdf" || key.toLowerCase().endsWith(".pdf"));
  return { url: data.signedUrl, kind: isPdf ? "pdf" : "image" };
}
