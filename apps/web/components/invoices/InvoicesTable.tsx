"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { DataTable, EmptyState, type Column } from "@/components/ui";
import { dateTime, money } from "@/lib/format";
import type { RecentRunRow } from "@/lib/queries/pipeline";
import { erpLabel } from "@/components/pipeline/labels";
import styles from "./invoices.module.css";

export interface InvoicesTableProps {
  rows: RecentRunRow[];
  orgSlug: string;
  timeZone: string;
}

/** Received · Vendor · Invoice · Location · Entity · Amount · Status · Posted to. Row click opens the detail. */
export function InvoicesTable({ rows, orgSlug, timeZone }: InvoicesTableProps) {
  const router = useRouter();
  const href = (r: RecentRunRow) => `/o/${orgSlug}/invoices/${r.invoice_id}`;
  const columns: Column<RecentRunRow>[] = [
    { key: "received", header: "Received", muted: true, width: 110, render: (r) => dateTime(r.started_at, timeZone) },
    { key: "vendor", header: "Vendor", render: (r) => r.vendor_name ?? "—" },
    {
      key: "invoice",
      header: "Invoice",
      render: (r) => (
        <Link href={href(r)} className={styles.rowLink} onClick={(e) => e.stopPropagation()}>
          {r.invoice_number ?? "Unnumbered"}
        </Link>
      ),
    },
    { key: "location", header: "Location", render: (r) => r.location_name ?? "—" },
    { key: "entity", header: "Entity", muted: true, render: (r) => r.entity_short_code ?? "—" },
    { key: "amount", header: "Amount", numeric: true, render: (r) => money(r.total) },
    {
      key: "status",
      header: "Status",
      render: (r) => (r.is_exception ? <span className="risk-text-strong">{r.status_label}</span> : r.status_label),
    },
    {
      key: "posted",
      header: "Posted to",
      render: (r) =>
        r.erp_system && r.erp_system !== "none" ? (
          <>
            {erpLabel(r.erp_system)} (mock)
            {r.erp_external_id ? <span className={styles.sub}>{r.erp_external_id}</span> : null}
          </>
        ) : (
          "—"
        ),
    },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      getRowKey={(r) => r.run_id}
      caption="Invoices, newest first"
      onRowClick={(r) => router.push(href(r))}
      empty={<EmptyState title="No invoices match">Try another status or clear the filters.</EmptyState>}
    />
  );
}
