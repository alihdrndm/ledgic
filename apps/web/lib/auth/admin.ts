import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let adminClient: SupabaseClient | null | undefined;

/**
 * Service-role Supabase client. Server-only: bypasses RLS, so use it only for
 * rate limiting and storage signing after the caller's role has been checked.
 * Returns null when SUPABASE_SERVICE_ROLE_KEY isn't configured.
 */
export function createAdminClient(): SupabaseClient | null {
  if (adminClient !== undefined) return adminClient;
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  adminClient = url && key ? createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } }) : null;
  return adminClient;
}
