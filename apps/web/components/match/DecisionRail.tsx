"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, Dialog, KeyValueRow, RiskCallout, useToast } from "@/components/ui";
import { needsRole, useShell } from "@/components/shell";
import { type Numeric, dateTime, money, conf as fmtConf } from "@/lib/format";
import { decideException, type DecisionAction } from "@/lib/actions/exceptions";
import type { Decision, MatchLineRow, Recommendation } from "@/lib/queries/match";
import { reasonTextClient } from "./reasons";
import { ACTION_LABEL, ERP_LABEL, recommendationBasis, recommendationTitle } from "./model";
import "./match.css";

export interface DecisionRailProps {
  orgSlug: string;
  exceptionId: string | null;
  exceptionStatus: string | null;
  recommendation: Recommendation | null;
  decision: Decision | null;
  lines: MatchLineRow[];
  invoiceNumber: string | null;
  invoiceTotal: Numeric;
  amountAtRisk: Numeric;
  erp: { system: string | null; externalId: string | null; status: string | null; postedAt: string | null };
  /** Compact rail inside Exceptions detail; shows "Open full match". */
  compact?: boolean;
  openFullHref?: string;
  /** Verdict is clean → "Posted" summary instead of a decision. */
  clean?: boolean;
}

interface LocalDecision {
  action: string;
  pay: string | null;
  hold: string | null;
  comment: string | null;
  at: string;
}

/** Recommended action + Short-pay / Approve as-is / Dispute, or the Decision / Posted summary. */
export function DecisionRail(props: DecisionRailProps) {
  const { orgSlug, exceptionId, exceptionStatus, recommendation: rec, decision, lines, invoiceNumber, invoiceTotal, erp, compact, openFullHref, clean } = props;
  const { role, user, org } = useShell();
  const { toast } = useToast();
  const router = useRouter();
  const openedAt = useRef(0);
  const [busy, setBusy] = useState<DecisionAction | null>(null);
  const [dialog, setDialog] = useState<"approve" | "dispute" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [local, setLocal] = useState<LocalDecision | null>(null);
  // Callers key this component by exception, so state starts fresh per exception.
  useEffect(() => {
    openedAt.current = Date.now();
  }, []);

  const erpName = erp.system ? (ERP_LABEL[erp.system] ?? erp.system) : null;
  const pay = rec?.pay_amount ?? null;
  const hold = rec?.hold_amount ?? null;
  const reason = needsRole(role, "ap_manager");
  const open = exceptionId && exceptionStatus && exceptionStatus !== "resolved" && exceptionStatus !== "disputed" && !local;

  async function decide(action: DecisionAction, comment?: string): Promise<string | void> {
    if (!exceptionId) return;
    setBusy(action);
    setError(null);
    const res = await decideException({
      orgSlug,
      exceptionId,
      action,
      payAmount: action === "short_pay" && pay !== null ? String(pay) : null,
      holdAmount: action === "short_pay" && hold !== null ? String(hold) : null,
      comment: comment ?? null,
      timeSpent: (Date.now() - openedAt.current) / 1000,
    });
    setBusy(null);
    if (!res.ok) {
      if (res.code === "CONFLICT") router.refresh();
      if (dialog) return res.message;
      setError(res.message);
      return;
    }
    const num = invoiceNumber ?? "invoice";
    const dest = erpName ? `sent to ${erpName}` : "sent for posting";
    const msg =
      action === "short_pay"
        ? `Short-paid ${num} · ${money(pay)} ${dest}, ${money(hold)} held`
        : action === "approve_as_is"
          ? `Approved ${num} as-is · ${money(invoiceTotal)} ${dest}`
          : `Disputed ${num} · payment held and vendor notified`;
    toast(msg);
    setLocal({
      action,
      pay: action === "short_pay" ? String(pay ?? "") : action === "approve_as_is" ? String(invoiceTotal ?? "") : null,
      hold: action === "short_pay" ? String(hold ?? "") : action === "dispute" ? String(invoiceTotal ?? "") : null,
      comment: comment ?? null,
      at: new Date().toISOString(),
    });
    router.refresh();
  }

  const summary = local
    ? { action: local.action, actor: user.fullName, at: local.at, pay: local.pay, hold: local.hold, comment: local.comment }
    : decision
      ? {
          action: decision.action,
          actor: decision.actor_name ?? "—",
          at: decision.decided_at,
          pay: decision.pay_amount === null ? null : String(decision.pay_amount),
          hold: decision.hold_amount === null ? null : String(decision.hold_amount),
          comment: decision.comment,
        }
      : null;

  const panelClass = compact ? "mt-rail mt-rail-compact" : "mt-rail";

  // Clean invoice → Posted summary.
  if (clean && !exceptionId) {
    return (
      <aside className={panelClass} aria-label="Posting">
        <header className="mt-rail-head section-label">Posted</header>
        <div className="mt-rail-block">
          <div className="mt-rec-title">{erp.status === "posted" ? `Posted to ${erpName ?? "the ERP"}` : "Matched clean — posting"}</div>
          <p className="meta" style={{ margin: "6px 0 0" }}>
            Every line is within tolerance, so no person needed to open this invoice.
          </p>
        </div>
        <div className="mt-rail-rows">
          <KeyValueRow label="ERP" value={erpName ?? "—"} />
          <KeyValueRow label="Reference" value={erp.externalId ?? "—"} />
          <KeyValueRow label="Posted" value={erp.postedAt ? dateTime(erp.postedAt, org.timezone) : "pending"} plainValue={!erp.postedAt} />
          <KeyValueRow label="Amount" value={money(invoiceTotal)} />
        </div>
      </aside>
    );
  }

  if (summary && !open) {
    return (
      <aside className={panelClass} aria-label="Decision">
        <header className="mt-rail-head section-label">Decision</header>
        <div className="mt-rail-block">
          <div className="mt-rec-title">{ACTION_LABEL[summary.action] ?? summary.action}</div>
          {summary.action === "short_pay" ? (
            <div className="mt-rec-amounts">
              Pay <strong>{money(summary.pay)}</strong>, hold <strong className="mt-accent-text">{money(summary.hold)}</strong>
            </div>
          ) : null}
        </div>
        <div className="mt-rail-rows">
          <KeyValueRow label="Decided by" value={summary.actor} />
          <KeyValueRow label="When" value={dateTime(summary.at, org.timezone)} />
          {summary.pay ? <KeyValueRow label="Pay" value={money(summary.pay)} /> : null}
          {summary.hold ? <KeyValueRow label="Hold" value={money(summary.hold)} /> : null}
          <KeyValueRow
            label="ERP reference"
            value={erp.externalId ? `${erpName ?? ""} ${erp.externalId}`.trim() : summary.action === "dispute" ? "held — not posted" : "posting…"}
            plainValue={!erp.externalId}
          />
          {summary.comment ? <p className="mt-comment">“{summary.comment}”</p> : null}
        </div>
        <footer className="mt-rail-foot meta">
          Written to the audit log with actor and timestamp.
          {openFullHref ? (
            <>
              {" "}
              <Link href={openFullHref}>Open full match</Link>
            </>
          ) : null}
        </footer>
      </aside>
    );
  }

  if (!exceptionId) {
    return (
      <aside className={panelClass} aria-label="Recommended action">
        <header className="mt-rail-head section-label">Recommended action</header>
        <div className="mt-rail-block">
          <p className="meta" style={{ margin: 0 }}>
            No open exception on this invoice.
          </p>
        </div>
      </aside>
    );
  }

  const reasons = (rec?.reasons ?? []).map(reasonTextClient).filter(Boolean);
  const canShortPay = rec?.action === "short_pay" && pay !== null && hold !== null;

  return (
    <aside className={panelClass} aria-label="Recommended action">
      <header className="mt-rail-head section-label">Recommended action</header>
      <div className="mt-rail-block">
        <div className="mt-rec-title">{recommendationTitle(rec?.action, lines)}</div>
        {canShortPay ? (
          <div className="mt-rec-amounts">
            Pay <strong>{money(pay)}</strong>, hold <strong className="mt-accent-text">{money(hold)}</strong>
          </div>
        ) : null}
        {rec ? (
          <p className="mt-rec-conf">
            Recommendation confidence {fmtConf(rec.confidence)}, {recommendationBasis(lines)}
          </p>
        ) : null}
      </div>
      {reasons.length ? (
        <ul className="mt-reasons">
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : (
        <div className="mt-reasons-empty" />
      )}
      <footer className="mt-rail-foot">
        {error ? (
          <RiskCallout tone="neutral" title="Not decided" live className="mt-rail-error">
            {error}
          </RiskCallout>
        ) : null}
        {canShortPay ? (
          <Button variant="ink" block disabledReason={reason} loading={busy === "short_pay"} onClick={() => void decide("short_pay")}>
            Short-pay {money(pay)} and notify vendor
          </Button>
        ) : null}
        <div className="mt-rail-pair">
          <Button variant="outline" block disabledReason={reason} disabled={Boolean(busy)} onClick={() => setDialog("approve")}>
            Approve as-is
          </Button>
          <Button variant="outline" block disabledReason={reason} disabled={Boolean(busy)} onClick={() => setDialog("dispute")}>
            Dispute
          </Button>
        </div>
        <p className="meta mt-rail-note">
          The decision posts to {erpName ?? "the ERP"} and is written to the audit log with actor and timestamp. Impacts above $500 also notify
          the controller.
          {openFullHref ? (
            <>
              {" "}
              <Link href={openFullHref}>Open full match</Link>
            </>
          ) : null}
        </p>
      </footer>

      <Dialog
        open={dialog === "approve"}
        onClose={() => setDialog(null)}
        title={`Approve ${invoiceNumber ?? "invoice"} as invoiced`}
        amount={money(invoiceTotal)}
        confirmLabel={`Approve and pay ${money(invoiceTotal)}`}
        comment={{ label: "Why pay the invoiced amount?", required: true, placeholder: "e.g. Price increase agreed by phone with the vendor rep" }}
        onConfirm={async ({ comment }) => decide("approve_as_is", comment)}
      >
        <p style={{ margin: 0 }}>
          Pays the full invoiced amount{hold ? `, including ${money(hold)} above the expected price` : ""}. Your comment is stored in the audit log.
        </p>
      </Dialog>
      <Dialog
        open={dialog === "dispute"}
        onClose={() => setDialog(null)}
        title={`Dispute ${invoiceNumber ?? "invoice"}`}
        amount={`${money(invoiceTotal)} held`}
        confirmLabel="Dispute and notify vendor"
        comment={{ label: "What should the vendor fix?", required: true }}
        onConfirm={async ({ comment }) => decide("dispute", comment)}
      >
        <p style={{ margin: 0 }}>Holds the whole invoice and notifies the vendor. The exception stays open as disputed.</p>
      </Dialog>
    </aside>
  );
}
