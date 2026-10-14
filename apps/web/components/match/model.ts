import Decimal from "decimal.js";
import { money, pct } from "@/lib/format";
import type { MatchLineRow } from "@/lib/queries/match";

export function dec(v: unknown): Decimal | null {
  if (v === null || v === undefined || v === "") return null;
  try {
    const d = new Decimal(String(v));
    return d.isFinite() ? d : null;
  } catch {
    return null;
  }
}

export const CHANNEL_SOURCE: Record<string, string> = {
  email: "Email PDF",
  photo: "Dock photo",
  upload: "Upload",
  portal: "Vendor portal",
  edi: "EDI 810",
};

export const ERP_LABEL: Record<string, string> = { quickbooks: "QuickBooks", netsuite: "NetSuite", none: "No ERP" };

export const VERDICT_LABEL: Record<string, string> = {
  clean: "Matched",
  price_variance: "Price variance",
  qty_mismatch: "Quantity mismatch",
  no_po: "No PO found",
  unmatched_line: "Unmatched line",
  mixed: "Multiple variances",
};

export const LINE_VERDICT_LABEL: Record<string, string> = {
  matched: "Matched",
  favorable: "Matched",
  price_variance: "Price variance",
  qty_over_receipt: "Over receipt",
  qty_over_order: "Over order",
  unmatched_line: "Unmatched line",
};

export const ACTION_LABEL: Record<string, string> = {
  short_pay: "Short-pay",
  approve_as_is: "Approved as-is",
  dispute: "Disputed",
  reject_invoice: "Rejected",
  link_po: "PO linked",
  approve_without_po: "Approved without PO",
  merge: "Merged",
  reject_copy: "Second copy rejected",
  not_duplicate: "Not a duplicate",
  request_w9: "W-9 re-verification requested",
  release_hold: "Hold released",
  retry_posting: "Posting retried",
  confirm_fields: "Fields confirmed",
};

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
export function numberWord(n: number): string {
  return WORDS[n] ?? String(n);
}

export function isFailing(l: MatchLineRow): boolean {
  return l.line_verdict !== "matched" && l.line_verdict !== "favorable";
}

/** "±2%" / "$25" from the policy columns. */
export function toleranceLabels(l: MatchLineRow | undefined): { pctLabel: string; absLabel: string } {
  const p = dec(l?.tolerance_pct) ?? new Decimal("0.02");
  const a = dec(l?.tolerance_abs) ?? new Decimal("25");
  const pctLabel = `±${pct(p, { digits: p.times(100).isInteger() ? 0 : 1 })}`;
  const absLabel = money(a, { decimals: a.isInteger() ? 0 : 2 });
  return { pctLabel, absLabel };
}

export function unitLabel(v: unknown, uom?: string | null, withUom = false): string {
  const d = dec(v);
  if (!d) return "—";
  const t = d.toDecimalPlaces(4);
  const m = money(t, { decimals: Math.max(2, t.decimalPlaces()) });
  return withUom && uom ? `${m}/${uom}` : m;
}

export function qtyLabel(v: unknown): string {
  const d = dec(v);
  return d ? d.toDecimalPlaces(3).toFixed() : "—";
}

/** Templated tolerance-strip sentence (03-screens §4). */
export function toleranceSentence(lines: MatchLineRow[]): string {
  const head = lines[0];
  const { pctLabel, absLabel } = toleranceLabels(head);
  const failing = lines.filter(isFailing);
  if (failing.length === 0) {
    return `Every line is within ${pctLabel} or ${absLabel}, whichever is lower — nothing needed a person.`;
  }
  const f = failing[0]!;
  const extra = failing.length - 1;
  const more = extra > 0 ? ` ${extra} more line${extra === 1 ? "" : "s"} also exceed${extra === 1 ? "s" : ""} tolerance.` : "";
  if (f.line_verdict === "price_variance") {
    const dp = dec(f.delta_pct);
    const da = dec(f.delta_amount);
    const tp = dec(f.tolerance_pct) ?? new Decimal("0.02");
    const ta = dec(f.tolerance_abs) ?? new Decimal("25");
    const overPct = dp ? dp.abs().gt(tp) : false;
    const overAbs = da ? da.abs().gt(ta) : false;
    const lead = `Line ${f.line_no} is ${pct(dp, { signed: true })} against a ${pctLabel} limit and ${money(da)} against a ${absLabel} limit`;
    let tail: string;
    if (overPct && overAbs) tail = "it fails both, so the invoice holds for approval.";
    else if (overPct) tail = `the ${pctLabel} limit is the lower one here, so it fails and the invoice holds for approval.`;
    else tail = `the ${absLabel} limit is the lower one here, so it fails and the invoice holds for approval.`;
    return `${lead} — ${tail}${more}`;
  }
  if (f.line_verdict === "qty_over_receipt") {
    return `Line ${f.line_no} invoices ${qtyLabel(f.inv_qty)} against ${qtyLabel(f.grn_qty)} received — quantity can't exceed what was received, so the invoice holds for approval.${more}`;
  }
  if (f.line_verdict === "qty_over_order") {
    return `Line ${f.line_no} invoices ${qtyLabel(f.inv_qty)} against ${qtyLabel(f.po_qty)} ordered — above the over-receipt allowance, so the invoice holds for approval.${more}`;
  }
  return `Line ${f.line_no} doesn't pair with any purchase-order line, so the invoice holds for approval.${more}`;
}

export function recommendationTitle(action: string | undefined, lines: MatchLineRow[]): string {
  const failing = lines.filter(isFailing);
  switch (action) {
    case "short_pay":
      if (failing.some((l) => l.line_verdict.startsWith("qty"))) return "Short-pay to received quantity";
      return failing.every((l) => l.expected_source === "contract") && failing.length ? "Short-pay to contract price" : "Short-pay to PO price";
    case "approve_as_is":
      return "Approve as invoiced";
    case "link_po":
      return "Link the matching purchase order";
    case "approve_without_po":
      return "Approve without a purchase order";
    case "dispute":
      return "Dispute with the vendor";
    default:
      return "No recommendation — decide manually";
  }
}

export function recommendationBasis(lines: MatchLineRow[]): string {
  return lines.some((l) => l.expected_source === "contract") ? "from contract terms and payment history" : "from purchase-order terms and payment history";
}
