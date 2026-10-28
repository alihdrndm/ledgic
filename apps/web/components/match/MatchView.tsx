"use client";

import { Chip, EmptyState, SectionHeader } from "@/components/ui";
import { Screen, useShell } from "@/components/shell";
import { AskLedgicButton, CopilotProvider } from "@/components/copilot";
import { RealtimeRefresh } from "@/lib/realtime";
import { conf as fmtConf, dateTime, money } from "@/lib/format";
import type { InvoiceDetail } from "@/lib/queries/extraction";
import type { MatchData } from "@/lib/queries/match";
import { DecisionRail } from "./DecisionRail";
import { MatchTable } from "./MatchTable";
import { ACTION_LABEL, CHANNEL_SOURCE, ERP_LABEL, VERDICT_LABEL, dec, isFailing, numberWord, toleranceLabels, toleranceSentence, unitLabel } from "./model";
import "./match.css";

export interface MatchViewProps {
  orgSlug: string;
  invoice: InvoiceDetail;
  match: MatchData;
  workflowVersion: string | null;
  degraded: string | null;
}

export function MatchView(props: MatchViewProps) {
  return (
    <CopilotProvider context={{ invoice_id: props.invoice.invoice_id, exception_id: props.match.exception?.id }}>
      <MatchViewInner {...props} />
    </CopilotProvider>
  );
}

function MatchViewInner({ orgSlug, invoice: inv, match, workflowVersion, degraded }: MatchViewProps) {
  const { org } = useShell();
  const lines = match.lines;
  const head = lines[0];
  const failing = lines.filter(isFailing);
  const exc = match.exception;
  const decision = head?.decision ?? null;
  const verdict = head?.verdict ?? null;
  const clean = verdict === "clean";
  const held = Boolean(exc && exc.status !== "resolved") || inv.status === "disputed";
  const { pctLabel, absLabel } = toleranceLabels(head);

  const invTotal = dec(inv.total);
  const poTotal = dec(inv.po_total) ?? dec(head?.expected_total);
  const diff = dec(head?.total_delta) ?? (invTotal && poTotal ? invTotal.minus(poTotal) : null);
  const contractLine = lines.find((l) => l.contract_id && l.expected_source === "contract");

  const chip = decision ? (
    <Chip variant="ink">{ACTION_LABEL[decision.action] ?? decision.action}</Chip>
  ) : verdict ? (
    clean ? <Chip variant="ink">Matched</Chip> : <Chip variant="risk">{VERDICT_LABEL[verdict] ?? verdict}</Chip>
  ) : null;

  const statusItems = [
    ...(held ? [{ key: "hold", text: "Payment on hold" }] : []),
    ...(head?.duration_ms !== null && head?.duration_ms !== undefined ? [{ key: "dur", text: `Matched in ${(head.duration_ms / 1000).toFixed(1)}s` }] : []),
  ];

  const topBar = {
    title: "Three-way match",
    context: [inv.invoice_number, inv.vendor_name, inv.location_name].filter(Boolean).join(" · "),
    riskChip: (
      <>
        {chip}
        <AskLedgicButton />
      </>
    ),
    searchOptional: true,
  };

  if (lines.length === 0) {
    return (
      <Screen {...topBar} degraded={degraded} version={workflowVersion ?? undefined} statusItems={statusItems}>
        <RealtimeRefresh tables={["exceptions", "approvals"]} orgId={org.id} />
        <EmptyState title="Not matched yet">
          {inv.po_id
            ? "This invoice hasn't reached the three-way match stage. It appears here as soon as the match runs."
            : "No purchase order is linked to this invoice, so there is nothing to compare yet."}
        </EmptyState>
      </Screen>
    );
  }

  const grn = inv.grn_numbers?.[0] ?? null;
  const priceFail = failing.find((l) => l.line_verdict === "price_variance");

  return (
    <Screen {...topBar} degraded={degraded} version={workflowVersion ?? undefined} statusItems={statusItems}>
      <RealtimeRefresh tables={["exceptions", "approvals"]} orgId={org.id} />
      <div className="mt-trio">
        <div className="mt-trio-cell">
          <div className="field-label">Invoice</div>
          <div className="mt-trio-value">
            {inv.invoice_number ?? "—"} · {money(inv.total)}
          </div>
          <div className="meta">
            {CHANNEL_SOURCE[inv.channel] ?? inv.channel}, {dateTime(inv.received_at, org.timezone)} · extraction conf {fmtConf(inv.doc_confidence)}
          </div>
        </div>
        <div className="mt-trio-cell">
          <div className="field-label">Purchase order</div>
          <div className="mt-trio-value">
            {inv.po_number ?? "—"} · {money(inv.po_total)}
          </div>
          <div className="meta">
            {inv.po_source ? (ERP_LABEL[inv.po_source] ?? inv.po_source) : "Purchasing"} ·{" "}
            {lines.some((l) => l.expected_source === "contract") ? "contract pricing applied" : "PO pricing"}
          </div>
        </div>
        <div className="mt-trio-cell">
          <div className="field-label">Goods receipt</div>
          <div className="mt-trio-value">
            {grn ?? "—"}
            {grn ? (inv.grn_in_full ? " · in full" : " · partial") : ""}
            {inv.grn_numbers && inv.grn_numbers.length > 1 ? ` +${inv.grn_numbers.length - 1}` : ""}
          </div>
          <div className="meta">{inv.grn_received_at ? `Receiving app, ${dateTime(inv.grn_received_at, org.timezone)}` : "No receipt recorded"}</div>
        </div>
        <div className="mt-trio-cell mt-diff" data-risk={failing.length > 0 || undefined}>
          <div>
            <div className="field-label mt-diff-label">Difference to purchase order</div>
            <div className="mt-diff-value">{money(diff, { signed: true })}</div>
          </div>
          <div className="mt-diff-note">
            {failing.length ? (
              <>
                {numberWord(failing.length)} line{failing.length === 1 ? "" : "s"} of {numberWord(lines.length)}
                <br />
                exceed{failing.length === 1 ? "s" : ""} tolerance
              </>
            ) : (
              <>
                all {numberWord(lines.length)} lines
                <br />
                within tolerance
              </>
            )}
          </div>
        </div>
      </div>

      <div className="mt-body">
        <section className="mt-compare" aria-label="Line-level comparison" tabIndex={0}>
          <SectionHeader label="Line-level comparison" meta={`Auto-approve within ${pctLabel} or ${absLabel}, whichever is lower`} rule={false} />
          <MatchTable lines={lines} invoiceTotal={inv.total} poTotal={inv.po_total ?? head?.expected_total} />
          <div className="mt-tolerance">
            <span className="field-label">Tolerance</span>
            <span className="mt-tolerance-text">{toleranceSentence(lines)}</span>
            <span className="meta mt-tolerance-right">
              {head?.lines_verified ?? lines.length - failing.length} of {head?.lines_total ?? lines.length} lines auto-verified
            </span>
          </div>
          <div className="mt-spacer" />
          <p className="mt-provenance">
            <strong>Provenance</strong> — invoice values from extraction-{inv.workflow_version ?? workflowVersion ?? "v1"} (conf {fmtConf(inv.doc_confidence)}
            ); purchase order from {inv.po_source ? (ERP_LABEL[inv.po_source] ?? inv.po_source) : "the purchasing system"}; receipt from the receiving app.
            {contractLine ? (
              <>
                {" "}
                Contract price of {unitLabel((priceFail ?? contractLine).expected_unit_price, (priceFail ?? contractLine).uom, true)} comes from the{" "}
                {match.contractUrl ? (
                  <a href={match.contractUrl} target="_blank" rel="noreferrer">
                    vendor agreement on file
                  </a>
                ) : (
                  "vendor agreement on file"
                )}
                {contractLine.contract_title ? ` (${contractLine.contract_title})` : ""}
                {(priceFail ?? contractLine).clause_ref ? `, clause ${(priceFail ?? contractLine).clause_ref}` : ""}
                {contractLine.contract_effective_to ? `, in effect through ${monthYearShort(contractLine.contract_effective_to)}` : ""}.
              </>
            ) : null}
          </p>
        </section>
        <DecisionRail
          key={exc?.id ?? inv.invoice_id}
          orgSlug={orgSlug}
          exceptionId={exc?.id ?? null}
          exceptionStatus={exc?.status ?? null}
          recommendation={head?.recommendation ?? null}
          decision={decision}
          lines={lines}
          invoiceNumber={inv.invoice_number}
          invoiceTotal={inv.total}
          amountAtRisk={exc?.amount_at_risk ?? null}
          erp={{ system: inv.erp_system, externalId: inv.erp_external_id, status: inv.erp_status, postedAt: inv.posted_at }}
          clean={clean}
        />
      </div>
    </Screen>
  );
}

function monthYearShort(isoDate: string): string {
  const d = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", year: "numeric" }).format(d);
}
