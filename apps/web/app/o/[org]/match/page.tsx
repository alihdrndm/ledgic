import { notFound, redirect } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getDefaultMatchInvoice, getMatchStatus } from "@/lib/queries/match";
import { MatchEmpty } from "@/components/match/MatchEmpty";

export const dynamic = "force-dynamic";
export const metadata = { title: "Three-way match" };

/** /match → oldest open price/quantity exception, else the most recently matched invoice. */
export default async function MatchIndex({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const target = await getDefaultMatchInvoice(session.context.org.id);
  if (target) redirect(`/o/${org}/match/${target}`);
  const status = await getMatchStatus(session.context.org.id);
  return <MatchEmpty workflowVersion={status.workflowVersion} degraded={status.degraded} />;
}
