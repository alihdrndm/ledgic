import { DataTable, EmptyState, type Column } from "@/components/ui";
import { shortDate, time } from "@/lib/format";
import type { AuditRow } from "@/lib/queries/invoices";
import styles from "./invoices.module.css";

const ACTOR_TYPE: Record<string, string> = {
  system: "System",
  core: "Orchestrator",
  agent: "AI agent",
  mcp: "MCP client",
  user: "User",
};

/** Compact one-line rendering of an audit before/after jsonb value. */
function summarize(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v !== "object") return String(v);
  const entries = Object.entries(v as Record<string, unknown>);
  if (!entries.length) return "—";
  const text = entries
    .map(([k, val]) => `${k}: ${val !== null && typeof val === "object" ? JSON.stringify(val) : String(val)}`)
    .join(", ");
  return text.length > 160 ? `${text.slice(0, 157)}…` : text;
}

/** Full audit trail for one invoice: Time, Actor, Action, Before → After, Hash (8 chars, mono). */
export function AuditTable({ rows, timeZone }: { rows: AuditRow[]; timeZone: string }) {
  const columns: Column<AuditRow>[] = [
    {
      key: "at",
      header: "Time",
      muted: true,
      width: 120,
      render: (r) => (
        <time dateTime={r.at}>
          {shortDate(r.at, timeZone)} {time(r.at, timeZone)}
        </time>
      ),
    },
    { key: "actor", header: "Actor", render: (r) => r.actor_name ?? ACTOR_TYPE[r.actor_type] ?? r.actor_type },
    { key: "action", header: "Action", render: (r) => r.action },
    {
      key: "diff",
      header: "Before → After",
      render: (r) => (
        <span className={styles.diff}>
          {summarize(r.before)} <span className={styles.diffArrow}>→</span> {summarize(r.after)}
        </span>
      ),
    },
    {
      key: "hash",
      header: "Hash",
      width: 90,
      render: (r) => (
        <span className={styles.hash} title={r.hash}>
          {r.hash.slice(0, 8)}
        </span>
      ),
    },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      getRowKey={(r) => String(r.id)}
      caption="Audit trail, oldest first"
      empty={<EmptyState title="No audit entries">Nothing has been recorded against this invoice yet.</EmptyState>}
    />
  );
}
