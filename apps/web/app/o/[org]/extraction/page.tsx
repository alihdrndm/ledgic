import { notFound, redirect } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getExtractionStats, getReviewQueue } from "@/lib/queries/extraction";
import { ExtractionEmpty } from "@/components/extraction/ExtractionEmpty";

export const dynamic = "force-dynamic";
export const metadata = { title: "Extraction review" };

/** /extraction → oldest item in the review queue, or "Queue clear". */
export default async function ExtractionIndex({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const orgId = session.context.org.id;
  const queue = await getReviewQueue(orgId);
  const first = queue[0];
  if (first) redirect(`/o/${org}/extraction/${first.invoice_id}`);
  const stats = await getExtractionStats(orgId);
  return <ExtractionEmpty stats={stats} />;
}
