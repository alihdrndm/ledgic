import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";
import { getStatusBar, viewClient, type Num, type StatusBarRow } from "./pipeline";

export const PERIODS = ["mtd", "qtd", "l30"] as const;
export type PeriodKey = (typeof PERIODS)[number];

export function parsePeriod(v: string | string[] | undefined): PeriodKey {
  const s = Array.isArray(v) ? v[0] : v;
  return (PERIODS as readonly string[]).includes(s ?? "") ? (s as PeriodKey) : "mtd";
}

export interface TopCatch {
  exception_id: string | null;
  invoice_number: string | null;
  vendor_name: string | null;
  amount: Num;
  text: string | null;
}

export interface ErpSync {
  system: string;
  posted_count: number;
  last_posted_at: string | null;
  failing: boolean;
  mock: boolean;
}

export interface OpsPeriodRow {
  org_id: string;
  period_key: PeriodKey;
  period_start: string;
  period_end: string;
  invoices: number;
  locations: number;
  entities: number;
  cost_llm: Num;
  cost_ocr: Num;
  cost_infra: Num;
  cost_human: Num;
  cost_total: Num;
  cost_per_invoice: Num | null;
  touchless_rate: Num | null;
  touchless_rate_first_week: Num | null;
  median_cycle_seconds: Num | null;
  held_variances: Num;
  held_duplicates: Num;
  held_fraud: Num;
  held_total: Num;
  short_pays_accepted: number;
  avg_decision_seconds: Num | null;
  decisions_logged_pct: Num | null;
  top_catches: TopCatch[] | null;
  erp_sync: ErpSync[] | null;
  refreshed_at: string | null;
}

export interface LocationPeriodRow {
  org_id: string;
  period_key: PeriodKey;
  location_id: string;
  location_name: string;
  location_code: string;
  volume: number;
  exception_rate: Num;
  rank: number;
  locations_total: number;
  org_median_exception_rate: Num | null;
  vendors_without_contract: number;
}

export interface EvalWeekRow {
  org_id: string;
  week_start: string;
  week_index: number;
  accuracy: Num;
  sample_size: number;
  prompt_version: string | null;
  prompt_deployed_at: string | null;
}

export interface CostAssumptions {
  loaded_hourly_rate_usd: Num;
  infra_monthly_usd: Num;
}

export interface OperationsData {
  period: OpsPeriodRow | null;
  quarter: OpsPeriodRow | null;
  locations: LocationPeriodRow[];
  highestException: LocationPeriodRow | null;
  evalWeeks: EvalWeekRow[];
  assumptions: CostAssumptions | null;
  status: StatusBarRow | null;
}

function must<T>(res: { data: T; error: { message: string } | null }, what: string): T {
  if (res.error) throw new Error(`${what}: ${res.error.message}`);
  return res.data;
}

export async function getOperationsData(
  supabase: SupabaseClient<Database>,
  orgId: string,
  period: PeriodKey,
): Promise<OperationsData> {
  const db = viewClient(supabase);
  const [opsRes, locRes, worstRes, evalRes, settingsRes, status] = await Promise.all([
    db.from("v_ops_period").select("*").eq("org_id", orgId).in("period_key", Array.from(new Set([period, "qtd"]))),
    db
      .from("v_location_period")
      .select("*")
      .eq("org_id", orgId)
      .eq("period_key", period)
      .order("rank", { ascending: true })
      .limit(8),
    db
      .from("v_location_period")
      .select("*")
      .eq("org_id", orgId)
      .eq("period_key", period)
      .gt("volume", 0)
      .order("exception_rate", { ascending: false })
      .order("volume", { ascending: false })
      .limit(1)
      .maybeSingle(),
    db.from("v_eval_weekly").select("*").eq("org_id", orgId).order("week_index", { ascending: true }),
    supabase.from("org_settings").select("loaded_hourly_rate_usd, infra_monthly_usd").eq("org_id", orgId).maybeSingle(),
    getStatusBar(supabase, orgId),
  ]);
  const ops = (must(opsRes, "v_ops_period") ?? []) as OpsPeriodRow[];
  return {
    period: ops.find((r) => r.period_key === period) ?? null,
    quarter: ops.find((r) => r.period_key === "qtd") ?? null,
    locations: (must(locRes, "v_location_period") ?? []) as LocationPeriodRow[],
    highestException: (worstRes.data as LocationPeriodRow | null) ?? null,
    evalWeeks: (must(evalRes, "v_eval_weekly") ?? []) as EvalWeekRow[],
    assumptions: (settingsRes.data as CostAssumptions | null) ?? null,
    status,
  };
}
