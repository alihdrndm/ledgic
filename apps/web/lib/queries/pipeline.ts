import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";

/**
 * Read-model views (contracts/views.md) are queried through an untyped handle so this module
 * compiles whether or not the generated types include the views yet. Row shapes below mirror
 * the frozen contract exactly.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ViewClient = SupabaseClient<any, "public", any>;
export function viewClient(supabase: SupabaseClient<Database>): ViewClient {
  return supabase as unknown as ViewClient;
}

/** numeric columns arrive as number (or string for very large values). */
export type Num = number | string;

export type Channel = "email" | "photo" | "portal" | "edi" | "upload";
export type Stage =
  | "intake"
  | "extraction"
  | "review"
  | "enrichment"
  | "screening"
  | "match"
  | "approval"
  | "posting"
  | "notify"
  | "close";

export interface PipelineTodayRow {
  org_id: string;
  day: string;
  received: number;
  extracted_above_gate: number;
  enriched_po_linked: number;
  matched_clean: number;
  routed_to_people: number;
}

export interface StageTodayRow {
  org_id: string;
  extraction_auto_passed: number;
  extraction_below_gate: number;
  extraction_median_seconds: Num | null;
  vendor_resolved: number;
  po_linked: number;
  gl_predicted: number;
  duplicate_screened: number;
  match_clean: number;
  match_price_variance: number;
  match_qty_mismatch: number;
  match_no_po: number;
  awaiting_person: number;
  posted_quickbooks: number;
  posted_netsuite: number;
  tolerance_pct: Num | null;
  tolerance_abs: Num | null;
  confidence_gate: Num | null;
  field_floor: Num | null;
}

export interface ChannelTodayRow {
  org_id: string;
  channel: Channel;
  count: number;
}

export interface RecentRunRow {
  org_id: string;
  run_id: string;
  run_number: number;
  started_at: string;
  finished_at: string | null;
  run_status: string;
  current_stage: Stage;
  invoice_id: string | null;
  invoice_number: string | null;
  vendor_id: string | null;
  vendor_name: string | null;
  location_id: string | null;
  location_name: string | null;
  location_code: string | null;
  entity_short_code: string | null;
  total: Num | null;
  invoice_status: string | null;
  channel: Channel;
  touchless: boolean | null;
  open_exception_id: string | null;
  open_exception_type: string | null;
  status_label: string;
  is_exception: boolean;
  end_to_end_seconds: Num | null;
  erp_system: string | null;
  erp_external_id: string | null;
}

export interface RunTimelineRow {
  org_id: string;
  run_id: string;
  event_id: number;
  at: string;
  stage: Stage;
  status: string;
  duration_ms: number | null;
  summary: string | null;
  detail: Record<string, unknown> | null;
  actor_name: string | null;
}

export interface StatusBarRow {
  org_id: string;
  last_run_at: string | null;
  runs_today: number;
  dead_letters_open: number;
  workflow_version: string | null;
  review_queue_size: number;
  exceptions_open: number;
  exceptions_raised_today: number;
  exceptions_cleared_today: number;
  payments_blocked: number;
  avg_decision_seconds_today: Num | null;
  last_autosave_at: string | null;
  erp_failing: string[] | null;
  mv_refreshed_at: string | null;
  pipeline_paused_reason: string | null;
}

export interface ExtractionModel {
  model: string;
  prompt: string;
}

export interface SelectedRun {
  run: RecentRunRow;
  timeline: RunTimelineRow[];
  /** invoices.human_touches for non-touchless runs. */
  humanTouches: number | null;
}

export interface PipelineData {
  today: PipelineTodayRow | null;
  stages: StageTodayRow | null;
  channels: ChannelTodayRow[];
  recent: RecentRunRow[];
  status: StatusBarRow | null;
  model: ExtractionModel | null;
  selected: SelectedRun | null;
}

export const RECENT_RUNS_LIMIT = 9;

/** Throws so the route's error boundary renders the neutral error state. */
function must<T>(res: { data: T; error: { message: string } | null }, what: string): T {
  if (res.error) throw new Error(`${what}: ${res.error.message}`);
  return res.data;
}

export async function getStatusBar(supabase: SupabaseClient<Database>, orgId: string): Promise<StatusBarRow | null> {
  const db = viewClient(supabase);
  const res = await db.from("v_status_bar").select("*").eq("org_id", orgId).maybeSingle();
  return must(res, "v_status_bar") as StatusBarRow | null;
}

export async function getRunTimeline(supabase: SupabaseClient<Database>, orgId: string, runId: string): Promise<RunTimelineRow[]> {
  const db = viewClient(supabase);
  const res = await db
    .from("v_run_timeline")
    .select("*")
    .eq("org_id", orgId)
    .eq("run_id", runId)
    .order("at", { ascending: true })
    .order("event_id", { ascending: true });
  return (must(res, "v_run_timeline") ?? []) as RunTimelineRow[];
}

/** Latest deployed extraction prompt + model (prompt_versions); falls back to the eval series. */
async function getExtractionModel(supabase: SupabaseClient<Database>, orgId: string): Promise<ExtractionModel | null> {
  const db = viewClient(supabase);
  const pv = await db
    .from("prompt_versions")
    .select("id, model, deployed_at")
    .lte("deployed_at", new Date().toISOString())
    .order("deployed_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (!pv.error && pv.data) {
    const row = pv.data as { id: string; model: string };
    return { model: row.model, prompt: row.id };
  }
  const ev = await db
    .from("v_eval_weekly")
    .select("prompt_version")
    .eq("org_id", orgId)
    .order("week_start", { ascending: false })
    .limit(1)
    .maybeSingle();
  const prompt = (ev.data as { prompt_version?: string } | null)?.prompt_version;
  return prompt ? { model: process.env.LLM_MODEL ?? "gpt-4.1-mini", prompt } : null;
}

async function getSelectedRun(
  supabase: SupabaseClient<Database>,
  orgId: string,
  runId: string | undefined,
  recent: RecentRunRow[],
): Promise<SelectedRun | null> {
  const db = viewClient(supabase);
  let run: RecentRunRow | null = null;
  if (runId && /^[0-9a-f-]{36}$/i.test(runId)) {
    run = recent.find((r) => r.run_id === runId) ?? null;
    if (!run) {
      const res = await db.from("v_recent_runs").select("*").eq("org_id", orgId).eq("run_id", runId).maybeSingle();
      run = (res.data as RecentRunRow | null) ?? null;
    }
  }
  if (!run) {
    // Default: most recent touchless run (03-screens §2).
    run = recent.find((r) => r.touchless === true) ?? null;
    if (!run) {
      const res = await db
        .from("v_recent_runs")
        .select("*")
        .eq("org_id", orgId)
        .eq("touchless", true)
        .order("started_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      run = (res.data as RecentRunRow | null) ?? recent[0] ?? null;
    }
  }
  if (!run) return null;

  const [timeline, touches] = await Promise.all([
    getRunTimeline(supabase, orgId, run.run_id),
    run.invoice_id && run.touchless !== true
      ? supabase.from("invoices").select("human_touches").eq("id", run.invoice_id).maybeSingle()
      : Promise.resolve({ data: null }),
  ]);
  const humanTouches = (touches.data as { human_touches?: number } | null)?.human_touches ?? null;
  return { run, timeline, humanTouches };
}

export async function getPipelineData(
  supabase: SupabaseClient<Database>,
  orgId: string,
  selectedRunId?: string,
): Promise<PipelineData> {
  const db = viewClient(supabase);
  const [todayRes, stagesRes, channelsRes, recentRes, status, model] = await Promise.all([
    db.from("v_pipeline_today").select("*").eq("org_id", orgId).maybeSingle(),
    db.from("v_stage_today").select("*").eq("org_id", orgId).maybeSingle(),
    db.from("v_channel_today").select("*").eq("org_id", orgId),
    db
      .from("v_recent_runs")
      .select("*")
      .eq("org_id", orgId)
      .order("started_at", { ascending: false })
      .limit(RECENT_RUNS_LIMIT),
    getStatusBar(supabase, orgId),
    getExtractionModel(supabase, orgId),
  ]);
  const recent = (must(recentRes, "v_recent_runs") ?? []) as RecentRunRow[];
  const selected = await getSelectedRun(supabase, orgId, selectedRunId, recent);
  return {
    today: must(todayRes, "v_pipeline_today") as PipelineTodayRow | null,
    stages: must(stagesRes, "v_stage_today") as StageTodayRow | null,
    channels: (must(channelsRes, "v_channel_today") ?? []) as ChannelTodayRow[],
    recent,
    status,
    model,
    selected,
  };
}
