import Link from "next/link";
import { Chip, EmptyState, Panel } from "@/components/ui";
import { count, duration, money } from "@/lib/format";
import type { SelectedRun } from "@/lib/queries/pipeline";
import { RunTimeline } from "./RunTimeline";
import styles from "./pipeline.module.css";

export interface RunInspectorProps {
  selected: SelectedRun | null;
  /** v_pipeline_today.routed_to_people */
  routedToPeople: number;
  orgSlug: string;
  timeZone: string;
}

function Footer({ selected, routedToPeople, orgSlug }: Omit<RunInspectorProps, "timeZone">) {
  if (!selected) return null;
  const { run, humanTouches } = selected;
  if (run.touchless) {
    return (
      <span className={styles.footer}>
        No person opened this invoice. The {count(routedToPeople)} that needed one{" "}
        {routedToPeople === 1 ? "is" : "are"} in the exception queue.
      </span>
    );
  }
  const n = humanTouches ?? 0;
  const touched =
    n === 0 ? "No person has touched this invoice yet." : `${count(n)} ${n === 1 ? "person" : "people"} touched this invoice.`;
  return (
    <span className={styles.footer}>
      {touched}{" "}
      {run.open_exception_id ? (
        <Link href={`/o/${orgSlug}/exceptions/${run.open_exception_id}`}>Open the exception</Link>
      ) : run.invoice_id ? (
        <Link href={`/o/${orgSlug}/invoices/${run.invoice_id}`}>Open the invoice</Link>
      ) : null}
    </span>
  );
}

/** 392px right rail: summary block, event timeline, footer. */
export function RunInspector({ selected, routedToPeople, orgSlug, timeZone }: RunInspectorProps) {
  const run = selected?.run;
  const sub = run ? [run.invoice_number, run.total !== null ? money(run.total) : null, run.location_name].filter(Boolean).join(" · ") : "";
  return (
    <Panel
      label="Run inspector"
      meta={run ? `run ${count(run.run_number)}` : undefined}
      className={styles.inspector}
      style={{ flex: "none", borderLeft: "var(--rule-major)" }}
      footer={<Footer selected={selected} routedToPeople={routedToPeople} orgSlug={orgSlug} />}
      aria-live="polite"
    >
      {run && selected ? (
        <>
          <div className={styles.summary}>
            <p className={styles.vendor}>{run.vendor_name ?? "Vendor not resolved yet"}</p>
            {sub ? <div className={styles.sub}>{sub}</div> : null}
            <div className={styles.chips}>
              {run.touchless ? (
                <Chip variant="ink">Touchless</Chip>
              ) : (
                <Chip variant={run.is_exception ? "risk" : "neutral"}>{run.status_label}</Chip>
              )}
              {run.end_to_end_seconds !== null && run.end_to_end_seconds !== undefined ? (
                <Chip variant="neutral">{duration(run.end_to_end_seconds)} end to end</Chip>
              ) : null}
            </div>
          </div>
          {selected.timeline.length ? (
            <RunTimeline events={selected.timeline} timeZone={timeZone} />
          ) : (
            <EmptyState title="No events yet">This run has not recorded a stage event.</EmptyState>
          )}
        </>
      ) : (
        <EmptyState title="No run selected">Pick a run from the table to see every step it took.</EmptyState>
      )}
    </Panel>
  );
}
