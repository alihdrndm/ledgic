import type { ReactNode } from "react";
import { notFound, redirect } from "next/navigation";
import { AppShell } from "@/components/shell";
import { getSessionContext } from "@/lib/supabase/session";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

/** Deployed workflow/orchestrator version shown in the rail and status bar. */
function workflowVersion(): string {
  return process.env.LEDGIC_WORKFLOW_VERSION ?? process.env.NEXT_PUBLIC_LEDGIC_VERSION ?? "v1";
}

export default async function OrgLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ org: string }>;
}) {
  const { org: orgSlug } = await params;
  const session = await getSessionContext(orgSlug);
  if (session.status === "unauthenticated") {
    redirect(`/login?next=${encodeURIComponent(`/o/${orgSlug}/pipeline`)}`);
  }
  if (session.status === "forbidden") notFound();
  const { context } = session;

  // Rail badge: open + escalated exceptions (RLS-scoped). Failure just hides the badge.
  const supabase = await createClient();
  const { count } = await supabase
    .from("exceptions")
    .select("id", { count: "exact", head: true })
    .eq("org_id", context.org.id)
    .in("status", ["open", "escalated"]);

  return (
    <AppShell
      org={context.org}
      user={{
        id: context.user.id,
        email: context.user.email ?? null,
        fullName: context.profile.full_name,
        initials: context.profile.initials,
      }}
      role={context.role}
      orgs={context.orgs}
      exceptionsCount={count ?? 0}
      version={workflowVersion()}
    >
      {children}
    </AppShell>
  );
}
