import Decimal from "decimal.js";
import type { ExceptionQueueRow } from "@/lib/queries/exceptions";

export type QueueSort = "oldest" | "impact";

/** Group order follows the design (04-exceptions.png), then the derived types. */
export const GROUP_ORDER = [
  "price_variance",
  "qty_mismatch",
  "no_po",
  "unmatched_line",
  "duplicate",
  "new_vendor_screen",
  "posting_failed",
  "extraction_review",
] as const;

export const GROUP_LABEL: Record<string, string> = {
  price_variance: "Price variance",
  qty_mismatch: "Quantity mismatch",
  no_po: "No purchase order",
  unmatched_line: "Unmatched line",
  duplicate: "Suspected duplicate",
  new_vendor_screen: "New vendor screen",
  posting_failed: "Posting failed",
  extraction_review: "Extraction review",
};

export interface QueueGroup {
  type: string;
  label: string;
  risk: boolean;
  items: ExceptionQueueRow[];
}

function amt(v: unknown): Decimal {
  try {
    return new Decimal(String(v ?? 0));
  } catch {
    return new Decimal(0);
  }
}

export function parseSort(v: string | string[] | undefined | null): QueueSort {
  return v === "impact" ? "impact" : "oldest";
}

export function groupQueue(rows: ExceptionQueueRow[], sort: QueueSort): QueueGroup[] {
  const by = new Map<string, ExceptionQueueRow[]>();
  for (const r of rows) {
    const list = by.get(r.type) ?? [];
    list.push(r);
    by.set(r.type, list);
  }
  const types = [...GROUP_ORDER.filter((t) => by.has(t)), ...[...by.keys()].filter((t) => !(GROUP_ORDER as readonly string[]).includes(t))];
  return types.map((t) => {
    const items = [...(by.get(t) ?? [])];
    items.sort((a, b) =>
      sort === "impact"
        ? amt(b.amount_at_risk).comparedTo(amt(a.amount_at_risk)) || a.opened_at.localeCompare(b.opened_at)
        : a.opened_at.localeCompare(b.opened_at),
    );
    return {
      type: t,
      label: items[0]?.group_label ?? GROUP_LABEL[t] ?? t,
      risk: items[0]?.is_risk_group ?? (t === "duplicate" || t === "new_vendor_screen"),
      items,
    };
  });
}

export function flatOrder(groups: QueueGroup[]): string[] {
  return groups.flatMap((g) => g.items.map((i) => i.exception_id));
}
