import { notFound, redirect } from "next/navigation";
import { getSessionContext } from "@/lib/supabase/session";
import { getExceptionHeader, getExceptionQueue } from "@/lib/queries/exceptions";
import { ExceptionsView } from "@/components/exceptions/ExceptionsView";
import { flatOrder, groupQueue, parseSort } from "@/components/exceptions/sort";

export const dynamic = "force-dynamic";
export const metadata = { title: "Exceptions" };

/** /exceptions → first item in queue order (keeps ?sort), or the empty state. */
export default async function ExceptionsIndex({
  params,
  searchParams,
}: {
  params: Promise<{ org: string }>;
  searchParams: Promise<{ sort?: string }>;
}) {
  const [{ org }, sp] = await Promise.all([params, searchParams]);
  const sort = parseSort(sp.sort);
  const session = await getSessionContext(org);
  if (session.status !== "ok") notFound();
  const orgId = session.context.org.id;
  const queue = await getExceptionQueue(orgId);
  const first = flatOrder(groupQueue(queue, sort))[0];
  if (first) redirect(`/o/${org}/exceptions/${first}${sort === "impact" ? "?sort=impact" : ""}`);
  const header = await getExceptionHeader(orgId);
  return <ExceptionsView orgSlug={session.context.org.slug} queue={queue} detail={null} header={header} sort={sort} />;
}
