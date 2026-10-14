import { DataTable, EmptyState, type Column } from "@/components/ui";
import { conf, count, money, pct } from "@/lib/format";
import type { InvoiceDetailRow, InvoiceLineJson, MatchLineRow } from "@/lib/queries/invoices";
import styles from "./invoices.module.css";

const VERDICT: Record<string, string> = {
  matched: "Matched",
  favorable: "Favorable",
  price_variance: "Price variance",
  qty_over_receipt: "Over receipt",
  qty_over_order: "Over order",
  unmatched_line: "Unmatched line",
};
const OK = new Set(["matched", "favorable"]);

const qty = (v: unknown) => (v === null || v === undefined ? "—" : String(Number(v)));

function Cell({ main, sub }: { main: string; sub?: string | null }) {
  return (
    <>
      <span className={styles.cellMain}>{main}</span>
      {sub ? <span className={styles.cellSub}>{sub}</span> : null}
    </>
  );
}

/** Lines tab: the match comparison when a match result exists, otherwise the extracted lines. */
export function LinesTable({ invoice, matchLines }: { invoice: InvoiceDetailRow; matchLines: MatchLineRow[] }) {
  if (matchLines.length) {
    const columns: Column<MatchLineRow>[] = [
      { key: "item", header: "Line item", render: (r) => <Cell main={r.description} sub={r.uom ? `per ${r.uom}` : null} /> },
      {
        key: "inv",
        header: "Invoice",
        numeric: true,
        render: (r) => <Cell main={`${money(r.inv_unit_price)} · ${qty(r.inv_qty)}`} sub={money(r.inv_amount)} />,
      },
      {
        key: "po",
        header: "Purchase order",
        numeric: true,
        render: (r) =>
          r.po_unit_price !== null && r.po_unit_price !== undefined ? (
            <Cell main={`${money(r.po_unit_price)} · ${qty(r.po_qty)}`} sub={money(r.po_amount)} />
          ) : (
            "—"
          ),
      },
      {
        key: "grn",
        header: "Receipt",
        numeric: true,
        render: (r) => (r.grn_qty !== null && r.grn_qty !== undefined ? `${qty(r.grn_qty)} ✓` : "—"),
      },
      {
        key: "verdict",
        header: "Verdict",
        width: 210,
        render: (r) =>
          OK.has(r.line_verdict) ? (
            <Cell main={VERDICT[r.line_verdict] ?? r.line_verdict} sub={r.note} />
          ) : (
            <span className="risk-text-strong">
              <span className={styles.cellMain}>{VERDICT[r.line_verdict] ?? r.line_verdict}</span>
              {r.delta_amount !== null && r.delta_amount !== undefined ? (
                <span className={styles.cellSub}>
                  {r.delta_pct !== null && r.delta_pct !== undefined ? `${pct(r.delta_pct, { signed: true })} · ` : ""}
                  {money(r.delta_amount)} impact
                </span>
              ) : null}
            </span>
          ),
      },
    ];
    return (
      <DataTable
        columns={columns}
        rows={matchLines}
        getRowKey={(r) => r.invoice_line_id}
        isRiskRow={(r) => !OK.has(r.line_verdict)}
        caption="Line-level comparison"
        density="comfortable"
        stickyHeader={false}
        footer={
          <tr>
            <td>Total</td>
            <td className="is-num">{money(invoice.total)}</td>
            <td className="is-num">{money(invoice.po_total)}</td>
            <td className="is-num">{invoice.grn_in_full ? "all received" : "—"}</td>
            <td />
          </tr>
        }
      />
    );
  }

  const lines = invoice.lines ?? [];
  const columns: Column<InvoiceLineJson>[] = [
    { key: "no", header: "#", muted: true, width: 40, render: (r) => count(r.line_no) },
    { key: "desc", header: "Line item", render: (r) => r.description },
    { key: "qty", header: "Qty", numeric: true, render: (r) => qty(r.qty) },
    { key: "uom", header: "Unit", muted: true, render: (r) => r.uom ?? "—" },
    { key: "unit", header: "Unit price", numeric: true, render: (r) => money(r.unit_price) },
    { key: "amount", header: "Extended", numeric: true, render: (r) => money(r.amount) },
    {
      key: "gl",
      header: "GL",
      render: (r) => (r.gl_number ? <Cell main={`${r.gl_number} ${r.gl_name ?? ""}`.trim()} sub={`conf ${conf(r.gl_confidence)}`} /> : "—"),
    },
  ];
  return (
    <DataTable
      columns={columns}
      rows={lines}
      getRowKey={(r) => r.id}
      caption="Extracted lines"
      stickyHeader={false}
      empty={<EmptyState title="No lines extracted">Lines appear after extraction.</EmptyState>}
      footer={
        lines.length ? (
          <tr>
            <td colSpan={5}>Total</td>
            <td className="is-num">{money(invoice.total)}</td>
            <td />
          </tr>
        ) : undefined
      }
    />
  );
}
