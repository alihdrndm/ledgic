import { notFound } from "next/navigation";
import { Screen } from "@/components/shell";
import { AttritionBars, EmptyState } from "@/components/ui";
import { RecentRunsTable } from "@/components/pipeline/RecentRunsTable";
import { RunInspector } from "@/components/pipeline/RunInspector";
import { StageGrid } from "@/components/pipeline/StageGrid";
import styles from "@/components/pipeline/pipeline.module.css";
import { count, time } from "@/lib/format";
import { RealtimeRefresh } from "@/lib/realtime";
import { getPipelineData, RECENT_RUNS_LIMIT } from "@/lib/queries/pipeline";
import { getSessionContext } from "@/lib/supabase/session";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Pipeline · Ledgic" };

export default async function PipelinePage({
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
  const runParam = Array.isArray(sp.run) ? sp.run[0] : sp.run;

  const supabase = await createClient();
  const data = await getPipelineData(supabase, org.id, runParam);
  const { today, status } = data;
  const received = today?.received ?? 0;
  const runsToday = status?.runs_today ?? received;
  const lastRun = status?.last_run_at ? time(status.last_run_at, tz) : null;
  const paused = status?.pipeline_paused_reason ?? null;

  const statusItems = [
    lastRun ? `Last run ${lastRun}` : "No runs yet",
    `${count(runsToday)} runs today`,
    { text: `Dead-letter queue ${count(status?.dead_letters_open ?? 0)}`, risk: (status?.dead_letters_open ?? 0) > 0 },
  ];

  return (
    <Screen
      title="Pipeline"
      context="ap-invoice-pipeline"
      status={paused ? undefined : { text: lastRun ? `running · last run ${lastRun}` : "running · waiting for the first run" }}
      degraded={paused}
      statusItems={statusItems}
      version={status?.workflow_version ?? undefined}
    >
      <RealtimeRefresh tables={["pipeline_events"]} orgId={org.id} />

      <section className={styles.ledger} aria-labelledby="ledger-title">
        <div className={styles.ledgerHead}>
          <h2 id="ledger-title" className="section-label">
            Today · volume through the pipeline
          </h2>
          <span className="meta">durable Python orchestrator + LLM extraction agent · retries and dead-letter on every stage</span>
        </div>
        <div className={styles.ledgerBars} aria-live="polite">
          {received === 0 ? (
            <EmptyState title="No documents yet today">
              The first delivery usually lands around 06:00.
            </EmptyState>
          ) : (
            <AttritionBars
              items={[
                { label: "received", value: received },
                { label: "extracted above gate", value: today?.extracted_above_gate ?? 0 },
                { label: "enriched, PO linked", value: today?.enriched_po_linked ?? 0 },
                { label: "matched clean → ERP", value: today?.matched_clean ?? 0 },
                { label: "routed to people", value: today?.routed_to_people ?? 0, risk: true },
              ]}
            />
          )}
        </div>
      </section>

      <div className={styles.body}>
        <div className={styles.left}>
          <StageGrid stages={data.stages} channels={data.channels} model={data.model} />
          <section className={styles.runs} aria-labelledby="runs-title">
            <div className={styles.runsHead}>
              <h2 id="runs-title" className="section-label">
                Recent runs
              </h2>
              <span className="meta">
                {runsToday > 0
                  ? `Last ${Math.min(RECENT_RUNS_LIMIT, data.recent.length)} of ${count(runsToday)} today · newest first`
                  : `Last ${data.recent.length} ${data.recent.length === 1 ? "run" : "runs"} · newest first`}
              </span>
            </div>
            {data.recent.length ? (
              <RecentRunsTable rows={data.recent} selectedRunId={data.selected?.run.run_id ?? null} timeZone={tz} />
            ) : (
              <EmptyState title="No runs yet">Runs appear here as soon as a document is received.</EmptyState>
            )}
          </section>
        </div>
        <RunInspector
          selected={data.selected}
          routedToPeople={today?.routed_to_people ?? 0}
          orgSlug={org.slug}
          timeZone={tz}
        />
      </div>
    </Screen>
  );
}
