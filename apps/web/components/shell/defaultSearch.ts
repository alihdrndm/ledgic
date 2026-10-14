"use client";

import type { PaletteGroup, PaletteSearch } from "@/components/ui/CommandPalette";
import { createClient } from "@/lib/supabase/client";
import { money } from "@/lib/format";

/** Escape PostgREST ilike wildcards/separators in user input. */
function clean(q: string): string {
  return q.replace(/[%_,()\\]/g, " ").trim();
}

/**
 * Default palette search: RLS-scoped ilike over invoices, vendors and open exceptions.
 * Screens/agents can replace it by passing `search` to <AppShell>.
 */
export function makeDefaultSearch(orgId: string, orgSlug: string): PaletteSearch {
  return async (query, signal) => {
    const q = clean(query);
    if (q.length < 2) return [];
    const supabase = createClient();
    const like = `%${q}%`;
    const base = `/o/${orgSlug}`;

    const [inv, ven, exc] = await Promise.all([
      supabase
        .from("invoices")
        .select("id, invoice_number, total, vendors(display_name)")
        .eq("org_id", orgId)
        .ilike("invoice_number", like)
        .order("created_at", { ascending: false })
        .limit(6)
        .abortSignal(signal),
      supabase
        .from("vendors")
        .select("id, display_name, category")
        .eq("org_id", orgId)
        .ilike("display_name", like)
        .limit(5)
        .abortSignal(signal),
      supabase
        .from("exceptions")
        .select("id, type, reason, amount_at_risk")
        .eq("org_id", orgId)
        .in("status", ["open", "escalated"])
        .ilike("reason", like)
        .limit(5)
        .abortSignal(signal),
    ]);

    type InvRow = { id: string; invoice_number: string | null; total: string | number | null; vendors: { display_name: string } | { display_name: string }[] | null };
    type VenRow = { id: string; display_name: string; category: string | null };
    type ExcRow = { id: string; type: string; reason: string; amount_at_risk: string | number | null };

    const groups: PaletteGroup[] = [
      {
        label: "Invoices",
        items: ((inv.data ?? []) as InvRow[]).map((r) => {
          const v = Array.isArray(r.vendors) ? r.vendors[0] : r.vendors;
          return {
            id: r.id,
            title: r.invoice_number ?? "Unnumbered invoice",
            meta: [v?.display_name, money(r.total)].filter(Boolean).join(" · "),
            href: `${base}/invoices/${r.id}`,
          };
        }),
      },
      {
        label: "Vendors",
        items: ((ven.data ?? []) as VenRow[]).map((r) => ({
          id: r.id,
          title: r.display_name,
          meta: r.category ?? undefined,
          href: `${base}/invoices?vendor=${r.id}`,
        })),
      },
      {
        label: "Exceptions",
        items: ((exc.data ?? []) as ExcRow[]).map((r) => ({
          id: r.id,
          title: r.reason,
          meta: `${r.type.replace(/_/g, " ")} · ${money(r.amount_at_risk)}`,
          href: `${base}/exceptions/${r.id}`,
        })),
      },
    ];
    if (inv.error && ven.error && exc.error) throw new Error("search failed");
    return groups;
  };
}
