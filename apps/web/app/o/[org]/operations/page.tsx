import Link from "next/link";
import { notFound } from "next/navigation";
import { Screen } from "@/components/shell";
import { Chip, EmptyState, MetricCell, SectionHeader, SparkLine, type SparkMarker } from "@/components/ui";
import { AutoRefresh } from "@/components/operations/AutoRefresh";
import { PeriodMenu } from "@/components/operations/PeriodMenu";
import styles from "@/components/operations/operations.module.css";
import { countWord, erpLabel } from "@/components/pipeline/labels";
import { count, duration, money, monthYear, pct, time, type Numeric } from "@/lib/format";
import { getOperationsData, parsePeriod, type LocationPeriodRow, type OpsPeriodRow, type PeriodKey } from "@/lib/queries/operations";
import { getSessionContext } from "@/lib/supabase/session";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Operations · Ledgic" };

const BENCHMARK =
  "The manual comparison ($12–30 per invoice) is a published industry benchmark for hand-keyed accounts payable, not a figure produced by this system.";

const toNum = (v: Numeric): number => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};

function periodLabel(key: PeriodKey, row: OpsPeriodRow | null, tz: string): string {
  if (key === "l30") return "Last 30 days";
  // Date-only columns: read in UTC so the calendar day doesn't shift.
  const start = row?.period_start ? new Date(`${row.period_start}T00:00:00Z`) : new Date();
  const zone = row?.period_start ? "UTC" : tz;
  if (key === "mtd") return `${monthYear(start, zone)}, month to date`;
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, month: "numeric", year: "numeric" }).formatToParts(start);
  const m = Number(parts.find((p) => p.type === "month")?.value ?? "1");
  const y = parts.find((p) => p.type === "year")?.value ?? "";
  return `Q${Math.floor((m - 1) / 3) + 1} ${y}, quarter to date`;
}

function plural(n: number, one: string, many: string) {
  return `${count(n)} ${n === 1 ? one : many}`;
}

function LocationNote({ worst }: { worst: LocationPeriodRow | null }) {
  if (!worst) return null;
  const n = worst.vendors_without_contract ?? 0;
  return (
    <p className={`${styles.note} ${styles.autoNote}`}>
      {n > 0
        ? `${worst.location_name} runs high because ${countWord(n)} ${n === 1 ? "supplier there has" : "suppliers there have"} no contract pricing on file.`
        : `${worst.location_name} has the highest exception rate this period.`}
    </p>
  );
}

export default async function OperationsPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ org: orgSlug }, sp] = await Promise.all([params, searchParams]);
  const session = await getSessionContext(orgSlug);
  if (session.status !== "ok") notFound();
  const { org } = session.context;
  const tz = org.timezone;
  const periodKey = parsePeriod(sp.period);

  const supabase = await createClient();
  const data = await getOperationsData(supabase, org.id, periodKey);
  const p = data.period;
  const q = data.quarter;

  const options = (["mtd", "qtd", "l30"] as const).map((k) => ({
    key: k,
    label: k === "mtd" ? "Month to date" : k === "qtd" ? "Quarter to date" : "Last 30 days",
  }));
  const label = periodLabel(periodKey, p, tz);
  const context = (
    <>
      <PeriodMenu label={label} current={periodKey} options={options} />
      {p
        ? ` · ${plural(p.invoices, "invoice", "invoices")} · ${plural(p.locations, "location", "locations")} · ${plural(p.entities, "entity", "entities")}`
        : null}
    </>
  );

  // Status bar: refresh time + ERP health (only real, live status).
  const erpRows = (p?.erp_sync ?? []).filter((e) => e.system && e.system !== "none");
  const failing = new Set<string>([...(data.status?.erp_failing ?? []), ...erpRows.filter((e) => e.failing).map((e) => e.system)]);
  const refreshedAt = p?.refreshed_at ?? data.status?.mv_refreshed_at ?? null;
  const statusItems = [
    refreshedAt ? `Refreshed ${time(refreshedAt, tz)}` : "Not refreshed yet",
    ...(failing.size
      ? Array.from(failing).map((s) => ({ key: s, text: `${erpLabel(s)} sync failing`, risk: true }))
      : ["ERP in sync"]),
  ];

  const disclosure = (
    <div className={styles.disclosure}>
      <Chip variant="outline" size="sm">
        Computed
      </Chip>
      <p>
        {org.is_demo
          ? `These figures are computed from pipeline runs over the synthetic demo corpus, not a client account. ${BENCHMARK}`
          : BENCHMARK}
      </p>
    </div>
  );

  if (!p || p.invoices === 0) {
    return (
      <Screen title="Operations" context={context} statusItems={statusItems} version={data.status?.workflow_version ?? undefined}>
        <AutoRefresh seconds={60} />
        {disclosure}
        <EmptyState title="No invoices in this period">
          Figures appear once invoices are received in this period.
        </EmptyState>
      </Screen>
    );
  }

  const rate = data.assumptions?.loaded_hourly_rate_usd;
  const infra = data.assumptions?.infra_monthly_usd;
  const costInfo = (
    <>
      <p className={styles.formula}>
        Cost per invoice = (model + OCR + infrastructure + reviewer time) ÷ invoices received in the period.
      </p>
      <p className={styles.formula}>
        This period: {money(p.cost_llm)} model · {money(p.cost_ocr)} OCR · {money(p.cost_infra)} infrastructure ·{" "}
        {money(p.cost_human)} reviewer time = {money(p.cost_total)} over {plural(p.invoices, "invoice", "invoices")}.
      </p>
      <p className={`${styles.formula} ${styles.formulaMuted}`}>
        Reviewer time is priced at a loaded rate of {money(rate)}/hour and infrastructure at {money(infra)}/month —
        assumptions set in Settings → Org.
      </p>
    </>
  );

  const tr = p.touchless_rate;
  const first = p.touchless_rate_first_week;
  let touchlessMeta = "Share of invoices no person touched";
  if (first !== null && first !== undefined && tr !== null && tr !== undefined) {
    const a = Math.round(toNum(tr) * 100);
    const b = Math.round(toNum(first) * 100);
    touchlessMeta = a > b ? `Up from ${b}% at dataset start` : a < b ? `Down from ${b}% at dataset start` : `Same as at dataset start`;
  }

  const heldRow = q ?? p;
  const heldParts = [
    `${money(heldRow.held_variances, { decimals: 0 })} variances`,
    `${money(heldRow.held_duplicates, { decimals: 0 })} duplicates`,
    ...(toNum(heldRow.held_fraud) > 0 ? [`${money(heldRow.held_fraud, { decimals: 0 })} fraud holds`] : []),
  ];

  const catches = (heldRow.top_catches ?? []).slice(0, 3);
  const logged = heldRow.decisions_logged_pct;
  const loggedShort = logged !== null && logged !== undefined && toNum(logged) < 1;

  const locs = data.locations;
  const maxVol = Math.max(1, ...locs.map((l) => l.volume));
  const median = locs[0]?.org_median_exception_rate;
  const locTotal = locs[0]?.locations_total ?? locs.length;

  const weeks = data.evalWeeks;
  const points = weeks.map((w) => ({ label: `wk ${w.week_index}`, value: toNum(w.accuracy) }));
  const markers: SparkMarker[] = weeks.flatMap((w, i) =>
    w.prompt_deployed_at ? [{ index: i, label: `prompt ${w.prompt_version ?? ""} shipped`.replace("  ", " ") }] : [],
  );

  return (
    <Screen title="Operations" context={context} statusItems={statusItems} version={data.status?.workflow_version ?? undefined}>
      <AutoRefresh seconds={60} />
      {disclosure}

      <div className={styles.metrics}>
        <MetricCell
          label="Cost per invoice"
          value={money(p.cost_per_invoice)}
          meta="Industry benchmark for manual: $12–30"
          info={costInfo}
          infoLabel="How cost per invoice is computed"
        />
        <MetricCell label="Touchless rate" value={pct(tr, { digits: 0 })} meta={touchlessMeta} />
        <MetricCell label="Median cycle" value={duration(p.median_cycle_seconds)} meta="Receipt to posted" />
        <MetricCell label="Held back this quarter" value={money(heldRow.held_total, { decimals: 0 })} meta={heldParts.join(" · ")} risk />
      </div>

      <div className={styles.grid}>
        <section className={styles.col} aria-labelledby="catches-title">
          <SectionHeader as="h2" id="catches-title" label="Largest catches this quarter" />
          {catches.length ? (
            catches.map((c, i) => (
              <div key={c.exception_id ?? i} className={styles.catch}>
                <span className={styles.catchAmount}>{money(c.amount)}</span>
                <span className={styles.catchText}>
                  <strong>{c.vendor_name ?? "Unknown vendor"}</strong>
                  {" · "}
                  {c.exception_id ? (
                    <Link href={`/o/${org.slug}/exceptions/${c.exception_id}`}>{c.invoice_number ?? "invoice"}</Link>
                  ) : (
                    (c.invoice_number ?? "invoice")
                  )}
                  {c.text ? ` — ${c.text}` : null}
                </span>
              </div>
            ))
          ) : (
            <EmptyState title="Nothing held back yet">Catches appear when a decision holds money back.</EmptyState>
          )}
          <div className={styles.footStats}>
            <span className={styles.footStat}>
              <span className="numeral-s">{count(heldRow.short_pays_accepted)}</span>
              <span className={styles.footStatLabel}>short-pays accepted</span>
            </span>
            <span className={styles.footStat}>
              <span className="numeral-s">{duration(heldRow.avg_decision_seconds)}</span>
              <span className={styles.footStatLabel}>average decision time</span>
            </span>
            <span className={styles.footStat}>
              <span className={`numeral-s ${loggedShort ? styles.footStatRisk : ""}`}>{pct(logged, { digits: 0 })}</span>
              <span className={styles.footStatLabel}>decisions logged</span>
            </span>
          </div>
        </section>

        <section className={styles.col} aria-labelledby="loc-title">
          <SectionHeader
            as="h2"
            id="loc-title"
            label="By location"
            meta={`Top ${locs.length} of ${count(locTotal)} · volume and exception rate`}
          />
          {locs.length ? (
            <div role="table" aria-label="Locations by volume">
              {locs.map((l) => {
                const high = median !== null && median !== undefined && toNum(l.exception_rate) > 2 * toNum(median);
                return (
                  <div key={l.location_id} role="row" className={`${styles.locRow} ${l.rank === 1 ? styles.locTop : ""}`}>
                    <span role="cell" className={styles.locName} title={l.location_name}>
                      {l.location_name}
                    </span>
                    <span role="cell" className={styles.locTrack} aria-hidden="true">
                      <span className={styles.locFill} style={{ width: `${(l.volume / maxVol) * 100}%` }} />
                    </span>
                    <span role="cell" className={styles.locNum}>
                      {count(l.volume)}
                    </span>
                    <span role="cell" className={`${styles.locNum} ${high ? styles.locHigh : ""}`}>
                      {pct(l.exception_rate)}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="No location volume yet" />
          )}
          <LocationNote worst={data.highestException} />
        </section>

        <section className={styles.col} aria-labelledby="acc-title">
          <SectionHeader as="h2" id="acc-title" label="Extraction accuracy · 12 weeks" />
          {points.length ? (
            <div className={styles.spark}>
              <SparkLine points={points} floor={0.95} markers={markers} />
            </div>
          ) : (
            <EmptyState title="No samples yet">Accuracy is sampled weekly once invoices have been verified.</EmptyState>
          )}
          <p className={styles.accNote}>
            {org.is_demo
              ? "Sampled weekly against hand-keyed values from the demo dataset."
              : "Sampled weekly against human-verified corrections."}
          </p>
          <div className={styles.erp}>
            <div className="field-label">ERP sync</div>
            {erpRows.length ? (
              erpRows.map((e) => (
                <div key={e.system} className={styles.erpRow}>
                  <span>
                    {erpLabel(e.system)}
                    {e.mock !== false ? " (mock)" : ""}
                  </span>
                  {e.failing ? (
                    <span className={styles.erpFail}>sync failing</span>
                  ) : (
                    <span className={styles.erpVal}>
                      {count(e.posted_count)} · {e.last_posted_at ? time(e.last_posted_at, tz) : "never"}
                    </span>
                  )}
                </div>
              ))
            ) : (
              <p className={styles.note} style={{ marginTop: 8 }}>
                Nothing posted this period.
              </p>
            )}
            <p className={styles.note} style={{ marginTop: 8, marginBottom: 0 }}>
              Every posted invoice carries entity, location and GL coding.
            </p>
          </div>
        </section>
      </div>
    </Screen>
  );
}
