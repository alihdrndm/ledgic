"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";
import { DataTable, type Column } from "@/components/ui";
import { money, time } from "@/lib/format";
import type { RecentRunRow } from "@/lib/queries/pipeline";
import { stageLabel } from "./labels";

export interface RecentRunsTableProps {
  rows: RecentRunRow[];
  selectedRunId: string | null;
  timeZone: string;
}

/** Recent runs: row click selects the run in the inspector via ?run=<id>. */
export function RecentRunsTable({ rows, selectedRunId, timeZone }: RecentRunsTableProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [, startTransition] = useTransition();

  const columns: Column<RecentRunRow>[] = [
    { key: "time", header: "Time", muted: true, width: 92, render: (r) => time(r.started_at, timeZone) },
    { key: "vendor", header: "Vendor", render: (r) => r.vendor_name ?? "—" },
    { key: "invoice", header: "Invoice", render: (r) => r.invoice_number ?? "—" },
    { key: "location", header: "Location", render: (r) => r.location_name ?? "—" },
    { key: "amount", header: "Amount", numeric: true, render: (r) => money(r.total) },
    { key: "stage", header: "Stage", muted: true, render: (r) => stageLabel(r.current_stage, r.invoice_status) },
    {
      key: "status",
      header: "Status",
      render: (r) => (r.is_exception ? <span className="risk-text-strong">{r.status_label}</span> : r.status_label),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      getRowKey={(r) => r.run_id}
      selectedKey={selectedRunId}
      caption="Recent pipeline runs, newest first"
      onRowClick={(r) =>
        startTransition(() => router.replace(`${pathname}?run=${encodeURIComponent(r.run_id)}`, { scroll: false }))
      }
    />
  );
}
