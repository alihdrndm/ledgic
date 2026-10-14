import "server-only";
import type { SupabaseClient, User } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";
import { hasRole, type MemberRole } from "@/components/shell/roles";
import { isDemoElena } from "./demo";

export interface CaptureOrg {
  id: string;
  slug: string;
  name: string;
  role: MemberRole;
}

interface Row {
  role: MemberRole;
  orgs: { id: string; slug: string; name: string } | { id: string; slug: string; name: string }[] | null;
}

/** The signed-in user's orgs (RLS-scoped). */
export async function userOrgs(supabase: SupabaseClient<Database>, userId: string): Promise<CaptureOrg[]> {
  const { data } = await supabase.from("memberships").select("role, orgs(id, slug, name)").eq("user_id", userId);
  return ((data ?? []) as unknown as Row[]).flatMap((m) => {
    const org = Array.isArray(m.orgs) ? m.orgs[0] : m.orgs;
    return org ? [{ id: org.id, slug: org.slug, name: org.name, role: m.role }] : [];
  });
}

/** Capture (upload) needs role ≥ ap_clerk, or the demo "Try as Elena" account. */
export function canCapture(user: User, role: MemberRole): boolean {
  return hasRole(role, "ap_clerk") || isDemoElena(user.email);
}
