"use client";

import { Chip } from "@/components/ui";
import { type Numeric, money, pct } from "@/lib/format";
import type { MatchLineRow } from "@/lib/queries/match";
import { LINE_VERDICT_LABEL, dec, isFailing, qtyLabel, unitLabel } from "./model";
import "./match.css";

export interface MatchTableProps {
  lines: MatchLineRow[];
  invoiceTotal: Numeric;
  poTotal: Numeric;
  compact?: boolean;
}

/** Line-level comparison: Line item · Invoice · Purchase order · Receipt · Verdict, with a totals row. */
export function MatchTable({ lines, invoiceTotal, poTotal, compact }: MatchTableProps) {
  const allReceived = lines.every((l) => {
    const g = dec(l.grn_qty);
    const q = dec(l.inv_qty);
    return g !== null && q !== null && g.gte(q);
  });
  const head = lines[0];
  const delta = dec(head?.total_delta) ?? (dec(invoiceTotal) && dec(poTotal) ? dec(invoiceTotal)!.minus(dec(poTotal)!) : null);
  return (
    <div className="mt-table-wrap" data-compact={compact || undefined}>
      <table className="mt-table">
        <caption className="sr-only">Line-level comparison of invoice, purchase order and receipt</caption>
        <thead>
          <tr>
            <th scope="col">Line item</th>
            <th scope="col" className="is-num">Invoice</th>
            <th scope="col" className="is-num">Purchase order</th>
            <th scope="col" className="is-num">Receipt</th>
            <th scope="col" style={{ width: compact ? 170 : 210 }}>
              Verdict
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => {
            const failing = isFailing(l);
            const priceFail = l.line_verdict === "price_variance";
            const poUnit = l.po_unit_price ?? l.expected_unit_price;
            const poAmt = l.po_amount ?? l.expected_amount;
            const poQty = l.po_qty;
            const g = dec(l.grn_qty);
            const q = dec(l.inv_qty);
            const received = g !== null && q !== null && g.gte(q);
            return (
              <tr key={l.invoice_line_id} data-risk={failing || undefined}>
                <td>
                  <div className={failing ? "mt-strong" : undefined}>{l.description}</div>
                  {failing && priceFail ? (
                    <div className="mt-sub">
                      {qtyLabel(l.inv_qty)} {l.uom ?? ""} total
                    </div>
                  ) : l.note ? (
                    <div className="mt-sub">{l.note}</div>
                  ) : null}
                </td>
                <td className="is-num">
                  <div className={priceFail ? "mt-risk-strong" : undefined}>
                    {priceFail ? unitLabel(l.inv_unit_price, l.uom, true) : `${unitLabel(l.inv_unit_price)} · ${qtyLabel(l.inv_qty)}`}
                  </div>
                  <div>{money(l.inv_amount)}</div>
                </td>
                <td className="is-num">
                  {poUnit !== null && poUnit !== undefined ? (
                    <>
                      <div>{priceFail ? unitLabel(poUnit, l.uom, true) : `${unitLabel(poUnit)} · ${qtyLabel(poQty ?? l.inv_qty)}`}</div>
                      <div>{money(poAmt)}</div>
                    </>
                  ) : (
                    <div className="mt-muted">no PO line</div>
                  )}
                </td>
                <td className="is-num mt-receipt">
                  {g === null ? (
                    <span className="mt-muted">—</span>
                  ) : received ? (
                    <>
                      {qtyLabel(g)}
                      {priceFail && l.uom ? ` ${l.uom}` : ""} ✓
                    </>
                  ) : (
                    <span className="mt-risk-strong">
                      {qtyLabel(g)} of {qtyLabel(q)}
                    </span>
                  )}
                </td>
                <td>
                  {failing ? (
                    <>
                      <Chip variant="risk" size="sm">
                        {LINE_VERDICT_LABEL[l.line_verdict] ?? l.line_verdict}
                      </Chip>
                      <div className="mt-impact">
                        {l.delta_pct !== null && l.delta_pct !== undefined ? `${pct(l.delta_pct, { signed: true })} · ` : ""}
                        {money(l.delta_amount)} impact
                      </div>
                    </>
                  ) : (
                    <>
                      <div>{l.line_verdict === "favorable" ? "Matched · favorable" : "Matched"}</div>
                      {l.note && !compact ? <div className="mt-sub">quantity verified against receipt</div> : null}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td>Totals</td>
            <td className="is-num">{money(invoiceTotal)}</td>
            <td className="is-num">{money(poTotal)}</td>
            <td className="is-num mt-muted-cell">{allReceived ? "all received" : "partially received"}</td>
            <td className={delta && !delta.isZero() ? "mt-risk-strong" : undefined}>Δ {money(delta ?? 0)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
