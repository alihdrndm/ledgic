"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@ledgic/db-types";
import { supabaseEnv } from "./env";

let browserClient: SupabaseClient<Database> | undefined;

/** Singleton Supabase client for client components (RLS as the signed-in user). */
export function createClient(): SupabaseClient<Database> {
  if (!browserClient) {
    const { url, anonKey } = supabaseEnv();
    browserClient = createBrowserClient<Database>(url, anonKey);
  }
  return browserClient;
}
