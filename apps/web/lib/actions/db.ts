import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";

/**
 * The generated Database type does not (yet) include the read-model views or the decision RPCs
 * from contracts/views.md + rpc.md, so G2 code talks to them through an untyped client.
 * Same session, same RLS — only the TypeScript surface differs.
 */
export async function untypedClient(): Promise<SupabaseClient> {
  return (await createClient()) as unknown as SupabaseClient;
}
