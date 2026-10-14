import { notFound } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getInvoiceDetail } from "@/lib/queries/extraction";
import { getMatch, getMatchStatus } from "@/lib/queries/match";
import { MatchView } from "@/components/match/MatchView";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ org: string; invoiceId: string }> }) {
  const { org, invoiceId } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") return { title: "Three-way match" };
  const inv = await getInvoiceDetail(session.context.org.id, invoiceId).catch(() => null);
  return { title: inv?.invoice_number ? `${inv.invoice_number} · Three-way match` : "Three-way match" };
}

export default async function MatchPage({ params }: { params: Promise<{ org: string; invoiceId: string }> }) {
  const { org, invoiceId } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const orgId = session.context.org.id;
  const [invoice, match, status] = await Promise.all([getInvoiceDetail(orgId, invoiceId), getMatch(orgId, invoiceId), getMatchStatus(orgId)]);
  if (!invoice) notFound();
  return (
    <MatchView
      orgSlug={session.context.org.slug}
      invoice={invoice}
      match={match}
      workflowVersion={status.workflowVersion}
      degraded={status.degraded}
    />
  );
}
