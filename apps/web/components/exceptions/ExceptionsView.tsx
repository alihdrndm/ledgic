"use client";

import { Chip, EmptyState } from "@/components/ui";
import { Screen, useShell } from "@/components/shell";
import { AskLedgicButton, CopilotProvider } from "@/components/copilot";
import { RealtimeRefresh } from "@/lib/realtime";
import { conf as fmtConf, count, money, pct } from "@/lib/format";
import type { ExceptionDetail, ExceptionHeader, ExceptionQueueRow } from "@/lib/queries/exceptions";
import { AgentDraft } from "./AgentDraft";
import { DuplicateDetail, ExtractionReviewDetail, NewVendorDetail, NoPoDetail, PostingFailedDetail, VarianceDetail } from "./details";
import { ExceptionQueue } from "./ExceptionQueue";
import { AuditStrip, FraudCallout } from "./parts";
import { GROUP_LABEL, type QueueSort } from "./sort";
import "./exceptions.css";

export interface ExceptionsViewProps {
  orgSlug: string;
  queue: ExceptionQueueRow[];
  detail: ExceptionDetail | null;
  header: ExceptionHeader;
  sort: QueueSort;
}

export function ExceptionsView(props: ExceptionsViewProps) {
  return (
    <CopilotProvider context={props.detail ? { exception_id: props.detail.row.exception_id, invoice_id: props.detail.row.invoice_id } : undefined}>
      <ExceptionsInner {...props} />
    </CopilotProvider>
  );
}

function headingChip(row: ExceptionQueueRow) {
  switch (row.type) {
    case "duplicate":
      return `Duplicate · similarity ${fmtConf(row.similarity)}`;
    case "new_vendor_screen":
      return `New vendor screen · signal score ${fmtConf(row.signal_score)}`;
    case "price_variance":
    case "qty_mismatch":
    case "unmatched_line":
      return `${GROUP_LABEL[row.type]} · ${money(row.amount_at_risk)}`;
    default:
      return row.group_label || GROUP_LABEL[row.type] || row.type;
  }
}

function headingNote(row: ExceptionQueueRow): string {
  if (row.status === "resolved") return "Resolved";
  if (row.payment_blocked) return "Payment blocked while held";
  if (row.status === "disputed") return "Disputed — payment held";
  if (row.status === "awaiting_vendor") return "Waiting on the vendor";
  if (row.escalated) return "Escalated to the controller";
  return row.assigned_to_name ? `Assigned to ${row.assigned_to_name}` : `Routed to ${row.assigned_role === "controller" ? "the controller" : "AP"}`;
}

function ExceptionsInner({ orgSlug, queue, detail, header, sort }: ExceptionsViewProps) {
  const { org } = useShell();
  const base = `/o/${orgSlug}/exceptions`;
  const fraud = queue.filter((q) => q.type === "new_vendor_screen" && q.exception_id !== detail?.row.exception_id);
  const context = `${count(header.open ?? queue.length)} open · ${count(header.raisedToday)} raised today · ${count(header.clearedToday)} cleared`;
  const row = detail?.row ?? null;
  const open = row ? row.status !== "resolved" : false;
  const draftKinds: Array<"vendor_notice" | "explanation"> =
    row?.type === "price_variance" || row?.type === "qty_mismatch" || row?.type === "unmatched_line" || row?.type === "duplicate"
      ? ["vendor_notice", "explanation"]
      : ["explanation", "vendor_notice"];

  return (
    <Screen
      title="Exceptions"
      context={context}
      riskChip={<AskLedgicButton />}
      degraded={header.degraded}
      version={header.workflowVersion ?? undefined}
      statusItems={[
        { key: "open", text: `${count(header.open ?? queue.length)} open` },
        { key: "blocked", text: `${count(header.paymentsBlocked ?? queue.filter((q) => q.payment_blocked).length)} payments blocked` },
      ]}
    >
      <RealtimeRefresh tables={["exceptions", "approvals"]} orgId={org.id} />
      <div className="xv-body">
        <ExceptionQueue orgSlug={orgSlug} rows={queue} selectedId={row?.exception_id ?? null} sort={sort} />
        <section className="xv-detail" aria-label="Exception detail">
          {!detail || !row ? (
            <EmptyState title="No open exceptions">Everything that needed a person has been decided.</EmptyState>
          ) : (
            <>
              <div className="xv-scroll">
                <header className="xd-heading">
                  <h2 className="xd-title">
                    {row.vendor_name ?? "Unknown vendor"} · {row.invoice_number ?? "—"}
                  </h2>
                  <Chip variant={row.status === "resolved" ? "neutral" : "risk"}>{headingChip(row)}</Chip>
                  <span className="meta xd-heading-note">{headingNote(row)}</span>
                </header>
                {row.type !== "duplicate" && row.type !== "new_vendor_screen" ? (
                  <p className="xd-reason meta">
                    {row.location_name ? `${row.location_name} · ` : ""}
                    {row.reason}
                    {row.type === "price_variance" && row.amount_at_risk ? ` · ${money(row.amount_at_risk)} at risk` : ""}
                    {row.similarity ? ` · similarity ${pct(row.similarity)}` : ""}
                  </p>
                ) : null}
                {row.type === "duplicate" ? <DuplicateDetail orgSlug={orgSlug} detail={detail} /> : null}
                {row.type === "new_vendor_screen" ? <NewVendorDetail orgSlug={orgSlug} detail={detail} /> : null}
                {row.type === "price_variance" || row.type === "qty_mismatch" || row.type === "unmatched_line" ? (
                  <VarianceDetail orgSlug={orgSlug} detail={detail} />
                ) : null}
                {row.type === "no_po" ? <NoPoDetail orgSlug={orgSlug} detail={detail} /> : null}
                {row.type === "posting_failed" ? <PostingFailedDetail orgSlug={orgSlug} detail={detail} /> : null}
                {row.type === "extraction_review" ? <ExtractionReviewDetail orgSlug={orgSlug} detail={detail} /> : null}

                {fraud[0] ? (
                  <div className="xd-pad">
                    <FraudCallout row={fraud[0]} href={`${base}/${fraud[0].exception_id}${sort === "impact" ? "?sort=impact" : ""}`} />
                  </div>
                ) : null}

                {row.type !== "extraction_review" ? (
                  <div className="xd-pad">
                    <AgentDraft orgSlug={orgSlug} exceptionId={row.exception_id} drafts={detail.drafts} kinds={draftKinds} />
                  </div>
                ) : null}
              </div>
              <AuditStrip
                orgSlug={orgSlug}
                invoiceId={row.invoice_id}
                invoiceNumber={row.invoice_number}
                entries={detail.audit}
                names={detail.actorNames}
                type={row.type}
                open={open}
                tz={org.timezone}
              />
            </>
          )}
        </section>
      </div>
    </Screen>
  );
}
