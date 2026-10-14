import { notFound } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getExtractionStats, getInvoiceDetail, getReviewQueue, pageImagePath, signedDocumentUrl } from "@/lib/queries/extraction";
import { ExtractionReview } from "@/components/extraction/ExtractionReview";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ org: string; invoiceId: string }> }) {
  const { org, invoiceId } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") return { title: "Extraction review" };
  const inv = await getInvoiceDetail(session.context.org.id, invoiceId).catch(() => null);
  return { title: inv?.invoice_number ? `${inv.invoice_number} · Extraction review` : "Extraction review" };
}

export default async function ExtractionItem({ params }: { params: Promise<{ org: string; invoiceId: string }> }) {
  const { org, invoiceId } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const orgId = session.context.org.id;
  const [invoice, queue, stats] = await Promise.all([getInvoiceDetail(orgId, invoiceId), getReviewQueue(orgId), getExtractionStats(orgId)]);
  if (!invoice) notFound();
  const img = pageImagePath(invoice);
  const imageUrl = img ? await signedDocumentUrl(img.path) : null;
  return (
    <ExtractionReview
      orgSlug={session.context.org.slug}
      invoice={invoice}
      queue={queue.map((q) => ({ invoice_id: q.invoice_id, queue_position: q.queue_position }))}
      stats={stats}
      imageUrl={imageUrl}
      imageKind={img?.kind ?? null}
      inQueue={queue.some((q) => q.invoice_id === invoiceId)}
    />
  );
}
