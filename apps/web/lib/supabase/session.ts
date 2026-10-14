import "server-only";
import { cache } from "react";
import type { User } from "@supabase/supabase-js";
import { createClient } from "./server";

import type { MemberRole } from "@/components/shell/roles";

export type { MemberRole };

export interface SessionOrg {
  id: string;
  slug: string;
  name: string;
  is_demo: boolean;
  timezone: string;
}

export interface SessionProfile {
  user_id: string;
  full_name: string;
  initials: string;
}

export interface SessionContext {
  user: User;
  org: SessionOrg;
  role: MemberRole;
  profile: SessionProfile;
  /** Every org this user belongs to (for the org switcher). */
  orgs: { slug: string; name: string; role: MemberRole }[];
}

export type SessionResult =
  | { status: "ok"; context: SessionContext }
  | { status: "unauthenticated" }
  | { status: "forbidden" };

function initialsFrom(name: string, email?: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const raw = parts.length >= 2 ? `${parts[0]?.[0] ?? ""}${parts[parts.length - 1]?.[0] ?? ""}` : (parts[0] ?? email ?? "?").slice(0, 2);
  return raw.toUpperCase();
}

interface MembershipRow {
  role: MemberRole;
  orgs: SessionOrg | SessionOrg[] | null;
}

/**
 * Resolves the signed-in user, the org addressed by `orgSlug`, their membership role and profile.
 * Cached per request (layout + page share one lookup).
 */
export const getSessionContext = cache(async (orgSlug: string): Promise<SessionResult> => {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { status: "unauthenticated" };

  const [membershipsRes, profileRes] = await Promise.all([
    supabase.from("memberships").select("role, orgs(id, slug, name, is_demo, timezone)").eq("user_id", user.id),
    supabase.from("profiles").select("user_id, full_name, initials").eq("user_id", user.id).maybeSingle(),
  ]);

  const memberships = ((membershipsRes.data ?? []) as MembershipRow[]).flatMap((m) => {
    const org = Array.isArray(m.orgs) ? m.orgs[0] : m.orgs;
    return org ? [{ role: m.role, org }] : [];
  });
  const current = memberships.find((m) => m.org.slug.toLowerCase() === orgSlug.toLowerCase());
  if (!current) return { status: "forbidden" };

  const rawProfile = profileRes.data as SessionProfile | null;
  const fullName = rawProfile?.full_name ?? user.email ?? "User";
  const profile: SessionProfile = {
    user_id: user.id,
    full_name: fullName,
    initials: rawProfile?.initials ?? initialsFrom(fullName, user.email),
  };

  return {
    status: "ok",
    context: {
      user,
      org: current.org,
      role: current.role,
      profile,
      orgs: memberships.map((m) => ({ slug: m.org.slug, name: m.org.name, role: m.role })),
    },
  };
});
