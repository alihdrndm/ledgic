import { notFound } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getExceptionDetail, getExceptionHeader, getExceptionQueue } from "@/lib/queries/exceptions";
import { ExceptionsView } from "@/components/exceptions/ExceptionsView";
import { parseSort } from "@/components/exceptions/sort";

export const dynamic = "force-dynamic";
export const metadata = { title: "Exceptions" };

export default async function ExceptionPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string; id: string }>;
  searchParams: Promise<{ sort?: string }>;
}) {
  const [{ org, id }, sp] = await Promise.all([params, searchParams]);
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const orgId = session.context.org.id;
  const [queue, detail, header] = await Promise.all([getExceptionQueue(orgId), getExceptionDetail(orgId, id), getExceptionHeader(orgId)]);
  if (!detail) notFound();
  return <ExceptionsView orgSlug={session.context.org.slug} queue={queue} detail={detail} header={header} sort={parseSort(sp.sort)} />;
}
