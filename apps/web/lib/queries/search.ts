import "server-only";
import { untypedClient } from "@/lib/actions/db";
import { money } from "@/lib/format";

export interface SearchItem {
  id: string;
  title: string;
  meta?: string;
  href: string;
}
export interface SearchGroup {
  label: "Invoices" | "Vendors" | "Exceptions";
  items: SearchItem[];
}

/** Escape PostgREST ilike wildcards / filter separators in user input. */
function clean(q: string): string {
  return q.replace(/[%_,()\\*:]/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * ⌘K palette search (RLS-scoped): invoices by number, vendors by name, open exceptions by
 * invoice number or vendor name. Groups always returned in the palette's order.
 */
export async function searchOrg(orgId: string, orgSlug: string, query: string): Promise<SearchGroup[]> {
  const q = clean(query).slice(0, 80);
  if (q.length < 2) return [];
  const db = await untypedClient();
  const like = `%${q}%`;
  const base = `/o/${orgSlug}`;
  const [inv, ven, exc] = await Promise.all([
    db
      .from("v_recent_runs")
      .select("invoice_id, invoice_number, vendor_name, location_name, total, status_label")
      .eq("org_id", orgId)
      .not("invoice_id", "is", null)
      .ilike("invoice_number", like)
      .order("started_at", { ascending: false })
      .limit(6),
    db.from("vendors").select("id, display_name, category").eq("org_id", orgId).ilike("display_name", like).limit(5),
    db
      .from("v_exception_queue")
      .select("exception_id, group_label, invoice_number, vendor_name, amount_at_risk")
      .eq("org_id", orgId)
      .neq("status", "resolved")
      .or(`invoice_number.ilike.${like},vendor_name.ilike.${like}`)
      .order("opened_at", { ascending: true })
      .limit(5),
  ]);
  if (inv.error && ven.error && exc.error) throw new Error("search failed");

  const seen = new Set<string>();
  const invoices: SearchItem[] = [];
  for (const r of (inv.data ?? []) as Array<{
    invoice_id: string;
    invoice_number: string | null;
    vendor_name: string | null;
    location_name: string | null;
    total: string | number | null;
    status_label: string | null;
  }>) {
    if (seen.has(r.invoice_id)) continue;
    seen.add(r.invoice_id);
    invoices.push({
      id: r.invoice_id,
      title: r.invoice_number ?? "Unnumbered invoice",
      meta: [r.vendor_name, r.location_name, money(r.total), r.status_label].filter(Boolean).join(" · "),
      href: `${base}/invoices/${r.invoice_id}`,
    });
  }
  return [
    { label: "Invoices", items: invoices },
    {
      label: "Vendors",
      items: ((ven.data ?? []) as Array<{ id: string; display_name: string; category: string | null }>).map((r) => ({
        id: r.id,
        title: r.display_name,
        meta: r.category ?? undefined,
        href: `${base}/vendors/${r.id}`,
      })),
    },
    {
      label: "Exceptions",
      items: (
        (exc.data ?? []) as Array<{
          exception_id: string;
          group_label: string;
          invoice_number: string | null;
          vendor_name: string | null;
          amount_at_risk: string | number | null;
        }>
      ).map((r) => ({
        id: r.exception_id,
        title: `${r.vendor_name ?? "Unknown vendor"} · ${r.invoice_number ?? "—"}`,
        meta: `${r.group_label} · ${money(r.amount_at_risk)}`,
        href: `${base}/exceptions/${r.exception_id}`,
      })),
    },
  ];
}
