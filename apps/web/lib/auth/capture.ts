import "server-only";
import { NextResponse } from "next/server";
import type { SupabaseClient, User } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";
import { createClient } from "@/lib/supabase/server";
import type { MemberRole } from "@/components/shell/roles";
import { canCapture } from "./membership";

export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const CAPTURE_TYPES = { "image/jpeg": "jpg", "application/pdf": "pdf" } as const;
export type CaptureContentType = keyof typeof CAPTURE_TYPES;

export function jsonError(status: number, code: string, message: string, retryable = false) {
  return NextResponse.json({ ok: false, error: { code, message, retryable } }, { status });
}

export type CaptureAuth =
  | { ok: true; user: User; role: MemberRole; supabase: SupabaseClient<Database> }
  | { ok: false; response: NextResponse };

/** Re-checks the caller server-side (UI gating is cosmetic): signed in, member of the org, may upload. */
export async function authorizeCapture(orgId: unknown): Promise<CaptureAuth> {
  if (typeof orgId !== "string" || !UUID.test(orgId)) {
    return { ok: false, response: jsonError(422, "INVALID", "org_id must be a uuid") };
  }
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, response: jsonError(401, "UNAUTHENTICATED", "Sign in to send invoices.") };

  const { data } = await supabase
    .from("memberships")
    .select("role")
    .eq("org_id", orgId)
    .eq("user_id", user.id)
    .maybeSingle();
  const role = (data as { role: MemberRole } | null)?.role;
  if (!role) return { ok: false, response: jsonError(403, "FORBIDDEN", "You're not a member of this organisation.") };
  if (!canCapture(user, role)) {
    return { ok: false, response: jsonError(403, "FORBIDDEN", "Read-only access") };
  }
  return { ok: true, user, role, supabase };
}

export async function readJson(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await request.json();
    return body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}
