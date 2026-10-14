import { time } from "@/lib/format";
import type { RunTimelineRow } from "@/lib/queries/pipeline";
import { stageLabel } from "./labels";
import styles from "./pipeline.module.css";

const STATUS_VERB: Record<string, string> = {
  started: "started",
  succeeded: "done",
  failed: "failed",
  skipped: "skipped",
  waiting: "waiting for a person",
  resumed: "resumed",
};

function headline(e: RunTimelineRow): { head: string; rest: string | null } {
  const text = e.summary?.trim() || `${stageLabel(e.stage)} ${STATUS_VERB[e.status] ?? e.status}`;
  const i = text.indexOf(" — ");
  return i > 0 ? { head: text.slice(0, i), rest: text.slice(i + 3) } : { head: text, rest: null };
}

function subLine(e: RunTimelineRow): string | null {
  const sub = e.detail && typeof e.detail.sub === "string" ? e.detail.sub : null;
  if (sub) return sub;
  if (e.actor_name && !(e.summary ?? "").includes(e.actor_name)) return e.actor_name;
  return null;
}

/** Inspector / invoice Timeline rows: 62px time column + "Head — rest" with an optional sub line. */
export function RunTimeline({ events, timeZone }: { events: RunTimelineRow[]; timeZone: string }) {
  return (
    <ol className={styles.timeline} aria-label="Run events">
      {events.map((e) => {
        const { head, rest } = headline(e);
        const sub = subLine(e);
        const risk = e.status === "waiting" || e.status === "failed";
        return (
          <li key={e.event_id} className={`${styles.event} ${risk ? styles.eventRisk : ""}`}>
            <time className={styles.eventTime} dateTime={e.at}>
              {time(e.at, timeZone)}
            </time>
            <span className={styles.eventText}>
              <strong>{head}</strong>
              {rest ? ` — ${rest}` : null}
              {sub ? <span className={styles.eventSub}>{sub}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
