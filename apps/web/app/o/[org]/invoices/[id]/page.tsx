import Link from "next/link";
import { notFound } from "next/navigation";
import { Screen } from "@/components/shell";
import { Chip, EmptyState } from "@/components/ui";
import { AuditTable } from "@/components/invoices/AuditTable";
import { LinesTable } from "@/components/invoices/LinesTable";
import { SegLinks } from "@/components/invoices/SegLinks";
import { VerifyChainButton } from "@/components/invoices/VerifyChainButton";
import styles from "@/components/invoices/invoices.module.css";
import { channelLabel, erpLabel } from "@/components/pipeline/labels";
import { RunTimeline } from "@/components/pipeline/RunTimeline";
import { conf, count, dateTime, money } from "@/lib/format";
import { RealtimeRefresh } from "@/lib/realtime";
import {
  getDocumentUrl,
  getInvoiceAudit,
  getInvoiceDetail,
  getInvoiceTimeline,
  getMatchLines,
  type InvoiceDetailRow,
} from "@/lib/queries/invoices";
import { getSessionContext } from "@/lib/supabase/session";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const TABS = [
  { key: "lines", label: "Lines" },
  { key: "document", label: "Document" },
  { key: "timeline", label: "Timeline" },
  { key: "audit", label: "Audit" },
] as const;
type Tab = (typeof TABS)[number]["key"];

function parseTab(v: string | string[] | undefined): Tab {
  const s = Array.isArray(v) ? v[0] : v;
  return TABS.some((t) => t.key === s) ? (s as Tab) : "lines";
}

function Trio({ inv, tz }: { inv: InvoiceDetailRow; tz: string }) {
  const grns = inv.grn_numbers?.filter(Boolean) ?? [];
  const channel = channelLabel(inv.channel);
  return (
    <div className={styles.trio}>
      <div className={styles.trioCell}>
        <div className="field-label">Invoice</div>
        <div className={styles.trioValue}>
          {inv.invoice_number ?? "Unnumbered"} · {money(inv.total)}
        </div>
        <div className={styles.trioSub}>
          {channel.charAt(0).toUpperCase() + channel.slice(1)}, {dateTime(inv.received_at, tz)} · extraction conf{" "}
          {conf(inv.doc_confidence)}
        </div>
      </div>
      <div className={styles.trioCell}>
        <div className="field-label">Purchase order</div>
        <div className={styles.trioValue}>{inv.po_number ? `${inv.po_number} · ${money(inv.po_total)}` : "No purchase order"}</div>
        <div className={styles.trioSub}>{inv.po_source ? (["quickbooks", "netsuite"].includes(inv.po_source) ? `${erpLabel(inv.po_source)} (mock)` : inv.po_source) : inv.po_number ? "" : "Not linked"}</div>
      </div>
      <div className={styles.trioCell}>
        <div className="field-label">Goods receipt</div>
        <div className={styles.trioValue}>
          {grns.length ? `${grns.join(", ")}${inv.grn_in_full ? " · in full" : ""}` : "No receipt"}
        </div>
        <div className={styles.trioSub}>{inv.grn_received_at ? `Received ${dateTime(inv.grn_received_at, tz)}` : ""}</div>
      </div>
      <div className={styles.trioCell}>
        <div className="field-label">Posted to</div>
        <div className={styles.trioValue}>
          {inv.erp_system && inv.erp_system !== "none"
            ? `${erpLabel(inv.erp_system)} (mock)${inv.erp_external_id ? ` · ${inv.erp_external_id}` : ""}`
            : "Not posted"}
        </div>
        <div className={styles.trioSub}>
          {inv.posted_at ? `Posted ${dateTime(inv.posted_at, tz)}` : inv.erp_status ? `Posting ${inv.erp_status}` : ""}
          {inv.entity_short_code ? `${inv.posted_at || inv.erp_status ? " · " : ""}${inv.entity_short_code}` : ""}
          {inv.location_code ? ` · loc ${inv.location_code}` : ""}
        </div>
      </div>
    </div>
  );
}

export default async function InvoiceDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string; id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ org: orgSlug, id }, sp] = await Promise.all([params, searchParams]);
  const session = await getSessionContext(orgSlug);
  if (session.status !== "ok") notFound();
  const { org } = session.context;
  const tz = org.timezone;
  const tab = parseTab(sp.tab);

  const supabase = await createClient();
  const detail = await getInvoiceDetail(supabase, org.id, id);
  if (!detail) notFound();
  const { invoice: inv, status } = detail;
  const base = `/o/${org.slug}/invoices/${inv.invoice_id}`;

  let body: React.ReactNode = null;
  if (tab === "lines") {
    const matchLines = await getMatchLines(supabase, org.id, inv.invoice_id);
    body = <LinesTable invoice={inv} matchLines={matchLines} />;
  } else if (tab === "document") {
    const doc = await getDocumentUrl(supabase, inv);
    const meta = [inv.original_filename, inv.page_count ? `${count(inv.page_count)} ${inv.page_count === 1 ? "page" : "pages"}` : null]
      .filter(Boolean)
      .join(" · ");
    body = doc ? (
      <>
        <div className={styles.docFrame}>
          {doc.kind === "pdf" ? (
            <iframe className={styles.docPdf} src={doc.url} title={`Source document for ${inv.invoice_number ?? "invoice"}`} />
          ) : (
            // Signed, short-lived storage URL: next/image optimisation doesn't apply.
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.docImg} src={doc.url} alt={`Source document for invoice ${inv.invoice_number ?? ""}`} />
          )}
        </div>
        <p className={styles.docMeta}>
          {meta ? `${meta} · ` : ""}Link valid for 5 minutes ·{" "}
          <a href={doc.url} target="_blank" rel="noreferrer">
            Open original
          </a>
        </p>
      </>
    ) : (
      <EmptyState title="Document unavailable">The stored file could not be found or you don&apos;t have access to it.</EmptyState>
    );
  } else if (tab === "timeline") {
    const events = await getInvoiceTimeline(supabase, org.id, inv.run_id);
    body = events.length ? (
      <div style={{ marginInline: -20 }}>
        <RunTimeline events={events} timeZone={tz} />
      </div>
    ) : (
      <EmptyState title="No pipeline events">This invoice has no recorded run.</EmptyState>
    );
  } else {
    const rows = await getInvoiceAudit(supabase, org.id, inv.invoice_id);
    body = (
      <>
        <div className={styles.auditHead}>
          <span className="section-label">Audit trail · {inv.invoice_number ?? "invoice"} · append-only</span>
          <VerifyChainButton orgId={org.id} />
        </div>
        <AuditTable rows={rows} timeZone={tz} />
      </>
    );
  }

  const context = [inv.invoice_number, inv.vendor_name, inv.location_name].filter(Boolean).join(" · ");
  const statusItems = [
    inv.run_number ? `Run ${count(inv.run_number)}` : null,
    inv.touchless ? "Touchless" : `${count(inv.human_touches)} human ${inv.human_touches === 1 ? "touch" : "touches"}`,
  ].filter((s): s is string => Boolean(s));

  return (
    <Screen
      title="Invoice"
      context={context || "Invoice"}
      riskChip={
        status.isException && status.label ? (
          <Chip variant="risk">{status.label}</Chip>
        ) : status.label ? (
          <Chip variant={inv.touchless ? "ink" : "neutral"}>{status.label}</Chip>
        ) : null
      }
      statusItems={statusItems}
      version={inv.workflow_version ?? undefined}
    >
      <RealtimeRefresh tables={["pipeline_events", "exceptions", "approvals"]} orgId={org.id} />
      <Trio inv={inv} tz={tz} />
      <div className={styles.tabs}>
        <SegLinks
          label="Invoice detail"
          current={tab}
          items={TABS.map((t) => ({ key: t.key, label: t.label, href: t.key === "lines" ? base : `${base}?tab=${t.key}` }))}
        />
        <span className="meta">
          {status.openExceptionId ? (
            <Link className={styles.metaLink} href={`/o/${org.slug}/exceptions/${status.openExceptionId}`}>
              Open the exception
            </Link>
          ) : (
            <Link className={styles.metaLink} href={`/o/${org.slug}/invoices`}>
              All invoices
            </Link>
          )}
        </span>
      </div>
      <div className={styles.tabBody}>{body}</div>
    </Screen>
  );
}
