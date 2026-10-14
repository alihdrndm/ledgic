import Link from "next/link";
import { notFound } from "next/navigation";
import { Screen } from "@/components/shell";
import { Button } from "@/components/ui";
import { InvoicesTable } from "@/components/invoices/InvoicesTable";
import { SegLinks } from "@/components/invoices/SegLinks";
import styles from "@/components/invoices/invoices.module.css";
import { count } from "@/lib/format";
import { RealtimeRefresh } from "@/lib/realtime";
import {
  getInvoiceList,
  INVOICES_PAGE_SIZE,
  parseInvoiceFilters,
  type InvoiceListFilters,
  type InvoiceSegment,
} from "@/lib/queries/invoices";
import { getSessionContext } from "@/lib/supabase/session";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Invoices · Ledgic" };

const SEGMENTS: { key: InvoiceSegment; label: string }[] = [
  { key: "all", label: "All" },
  { key: "touchless", label: "Touchless" },
  { key: "exceptions", label: "Exceptions" },
  { key: "posted", label: "Posted" },
  { key: "held", label: "Held" },
];

function hrefFor(base: string, f: InvoiceListFilters, patch: Partial<InvoiceListFilters>): string {
  const n = { ...f, ...patch };
  const qs = new URLSearchParams();
  if (n.segment !== "all") qs.set("status", n.segment);
  if (n.vendor) qs.set("vendor", n.vendor);
  if (n.location) qs.set("location", n.location);
  if (n.from) qs.set("from", n.from);
  if (n.to) qs.set("to", n.to);
  if (n.page > 1) qs.set("page", String(n.page));
  const s = qs.toString();
  return s ? `${base}?${s}` : base;
}

export default async function InvoicesPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ org: orgSlug }, sp] = await Promise.all([params, searchParams]);
  const session = await getSessionContext(orgSlug);
  if (session.status !== "ok") notFound();
  const { org } = session.context;
  const filters = parseInvoiceFilters(sp);
  const base = `/o/${org.slug}/invoices`;

  const supabase = await createClient();
  const data = await getInvoiceList(supabase, org.id, filters);
  const pages = Math.max(1, Math.ceil(data.total / INVOICES_PAGE_SIZE));
  const page = Math.min(filters.page, pages);
  const firstRow = data.total === 0 ? 0 : (page - 1) * INVOICES_PAGE_SIZE + 1;
  const lastRow = Math.min(data.total, (page - 1) * INVOICES_PAGE_SIZE + data.rows.length);
  const hasFilters = Boolean(filters.vendor || filters.location || filters.from || filters.to);

  return (
    <Screen title="Invoices" context={`${count(data.total)} ${data.total === 1 ? "invoice" : "invoices"}`}>
      <RealtimeRefresh tables={["pipeline_events", "exceptions"]} orgId={org.id} />
      <div className={styles.filterBar}>
        <SegLinks
          label="Invoice status"
          current={filters.segment}
          items={SEGMENTS.map((s) => ({ ...s, href: hrefFor(base, filters, { segment: s.key, page: 1 }) }))}
        />
        <form method="get" action={base} className={styles.filterForm} aria-label="Filter invoices">
          {filters.segment !== "all" ? <input type="hidden" name="status" value={filters.segment} /> : null}
          <div className={styles.field}>
            <label className="field-label" htmlFor="f-vendor">
              Vendor
            </label>
            <select id="f-vendor" name="vendor" className={`input ${styles.select}`} defaultValue={filters.vendor ?? ""}>
              <option value="">All vendors</option>
              {data.vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label className="field-label" htmlFor="f-location">
              Location
            </label>
            <select id="f-location" name="location" className={`input ${styles.select}`} defaultValue={filters.location ?? ""}>
              <option value="">All locations</option>
              {data.locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label className="field-label" htmlFor="f-from">
              Received from
            </label>
            <input id="f-from" type="date" name="from" className={`input ${styles.date}`} defaultValue={filters.from ?? ""} />
          </div>
          <div className={styles.field}>
            <label className="field-label" htmlFor="f-to">
              To
            </label>
            <input id="f-to" type="date" name="to" className={`input ${styles.date}`} defaultValue={filters.to ?? ""} />
          </div>
          <Button type="submit" variant="outline" size="sm">
            Apply
          </Button>
          {hasFilters ? (
            <Link className={styles.clear} href={hrefFor(base, filters, { vendor: undefined, location: undefined, from: undefined, to: undefined, page: 1 })}>
              Clear filters
            </Link>
          ) : null}
        </form>
      </div>

      <div className={styles.list}>
        <InvoicesTable rows={data.rows} orgSlug={org.slug} timeZone={org.timezone} />
        <div className={styles.pager}>
          <span>
            {data.total === 0 ? "No invoices" : `${count(firstRow)}–${count(lastRow)} of ${count(data.total)}`} · page {page} of{" "}
            {pages}
          </span>
          <span className={styles.pagerLinks}>
            <Link
              className={styles.pagerLink}
              href={hrefFor(base, filters, { page: page - 1 })}
              aria-disabled={page <= 1}
              tabIndex={page <= 1 ? -1 : undefined}
            >
              Previous
            </Link>
            <Link
              className={styles.pagerLink}
              href={hrefFor(base, filters, { page: page + 1 })}
              aria-disabled={page >= pages}
              tabIndex={page >= pages ? -1 : undefined}
            >
              Next
            </Link>
          </span>
        </div>
      </div>
    </Screen>
  );
}
