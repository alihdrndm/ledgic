"use client";

import Link from "next/link";
import { Chip, RiskCallout } from "@/components/ui";
import { conf as fmtConf, money, shortDate, time } from "@/lib/format";
import type { AuditEntry, ExceptionQueueRow } from "@/lib/queries/exceptions";
import { ACTION_LABEL } from "@/components/match/model";
import "./exceptions.css";

const SIGNAL_LABEL: Record<string, string> = {
  bank_mismatch_w9: "Bank details differ from the W-9 on file",
  no_po: "No purchase order",
  remit_address_new: "Remit-to address recently added or changed",
};

/** Client copy of lib/queries/exceptions signalLabel (that module is server-only). */
export function signalText(s: { signal: string; detail?: Record<string, unknown> | null }): string {
  const d = s.detail ?? {};
  if (typeof d.label === "string" && d.label) return d.label;
  if (s.signal === "vendor_age_lt_14d") {
    const days = d.age_days ?? d.days;
    return days !== undefined ? `Vendor record ${days} day${String(days) === "1" ? "" : "s"} old` : "Vendor record under 14 days old";
  }
  if (s.signal === "amount_anomaly") return d.z ? `Amount is ${d.z}σ above this vendor's 90-day mean` : "Amount unusual for this vendor";
  return SIGNAL_LABEL[s.signal] ?? s.signal.replace(/_/g, " ");
}

/** Fraud callout (new-vendor screen). Compact = the clickable summary shown on other details. */
export function FraudCallout({ row, href, expanded }: { row: ExceptionQueueRow; href?: string; expanded?: boolean }) {
  const signals = row.signals ?? [];
  const title = (
    <>
      New vendor screen — {row.vendor_name ?? "Unknown vendor"}, first invoice, {money(row.invoice_total ?? row.amount_at_risk)}
      <Chip variant="risk" size="sm" style={{ marginLeft: 10, verticalAlign: "middle" }}>
        Held
      </Chip>
    </>
  );
  const body = (
    <div className="xf-signals">
      {signals.map((s) => (
        <span key={s.signal}>{signalText(s)}</span>
      ))}
      <span>Signal score {fmtConf(row.signal_score)}</span>
    </div>
  );
  const callout = (
    <RiskCallout title={title} actions={<span className="xf-routed">Routed to the controller</span>} className="xf-callout">
      {body}
    </RiskCallout>
  );
  if (href && !expanded) {
    return (
      <Link href={href} className="xf-link" aria-label={`Open new vendor screen for ${row.vendor_name ?? "vendor"}`}>
        {callout}
      </Link>
    );
  }
  return callout;
}

function shortName(full: string | undefined): string | null {
  if (!full) return null;
  const parts = full.trim().split(/\s+/);
  if (parts.length < 2) return full;
  return `${parts[0]![0]}. ${parts[parts.length - 1]}`;
}

const SCREEN_NAME: Record<string, string> = {
  duplicate: "duplicate screen",
  new_vendor_screen: "fraud screen",
  price_variance: "three-way match",
  qty_mismatch: "three-way match",
  unmatched_line: "three-way match",
  no_po: "PO lookup",
  posting_failed: "ERP posting",
  extraction_review: "confidence gate",
};

function describe(a: AuditEntry, type: string, names: Record<string, string>): string {
  const who = a.actor_type === "user" || a.actor_type === "mcp" ? shortName(names[a.actor_id ?? ""]) : null;
  const by = who ? ` by ${who}` : a.actor_type === "agent" ? " by the resolution agent" : "";
  const [ns, verb = ""] = a.action.split(".");
  if (ns === "exception") {
    if (verb === "opened" || verb === "created") return `flagged by the ${SCREEN_NAME[type] ?? "pipeline"}`;
    if (verb === "assigned" || verb === "routed") {
      const to = (a.after?.assigned_to_name as string | undefined) ?? (a.after?.assigned_role as string | undefined);
      return `routed${to ? ` to ${shortName(to) ?? to}` : ""}`;
    }
    if (verb === "escalated") return "escalated to the controller";
    if (verb === "viewed") return `opened${by}`;
    return `${verb.replace(/_/g, " ")}${by}`;
  }
  if (ns === "decision") return `${(ACTION_LABEL[verb] ?? verb.replace(/_/g, " ")).toLowerCase()}${by}`;
  if (ns === "field") return `${verb === "confirmed" ? "field confirmed" : "field corrected"}${by}`;
  if (ns === "payment" || a.action.includes("hold")) return `payment hold ${verb.replace(/_/g, " ") || "set"}${by}`;
  return `${a.action.replace(/[._]/g, " ")}${by}`;
}

/** Pinned audit strip: one chronological line joined with " · " (append-only audit_log). */
export function AuditStrip({
  orgSlug,
  invoiceId,
  invoiceNumber,
  entries,
  names,
  type,
  open,
  tz,
}: {
  orgSlug: string;
  invoiceId: string;
  invoiceNumber: string | null;
  entries: AuditEntry[];
  names: Record<string, string>;
  type: string;
  open: boolean;
  tz: string;
}) {
  let lastDay = "";
  const parts = entries.slice(-12).map((a) => {
    const day = shortDate(a.at, tz);
    const stamp = day === lastDay ? time(a.at, tz, { seconds: false }) : `${day} ${time(a.at, tz, { seconds: false })}`;
    lastDay = day;
    return `${stamp} ${describe(a, type, names)}`;
  });
  if (open) parts.push("decision pending, and it will record actor and timestamp.");
  return (
    <footer className="xa">
      <div className="section-label">Audit trail · {invoiceNumber ?? "invoice"} · append-only</div>
      <p className="xa-line">
        {parts.length ? parts.join(" · ") : "No audit entries yet."}{" "}
        <Link href={`/o/${orgSlug}/invoices/${invoiceId}`} className="xa-link">
          View full trail
        </Link>
      </p>
    </footer>
  );
}
