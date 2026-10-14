"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export interface RealtimeRefreshOptions {
  /** Org id to filter `org_id=eq.<id>`; omit to receive every row RLS allows. */
  orgId?: string;
  /** Debounce window for router.refresh() (default 500ms, per 03-screens §1). */
  debounceMs?: number;
  /** Postgres change events to watch (default "*"). */
  event?: "INSERT" | "UPDATE" | "DELETE" | "*";
  /** Set false to pause the subscription. */
  enabled?: boolean;
}

/**
 * Subscribes to Supabase Realtime changes on `tables` and refreshes the current route's
 * server components (debounced). Use from a small client component on each screen:
 *
 *   useRealtimeRefresh(["pipeline_events"], { orgId });
 */
export function useRealtimeRefresh(tables: readonly string[], opts: RealtimeRefreshOptions = {}): void {
  const { orgId, debounceMs = 500, event = "*", enabled = true } = opts;
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const key = tables.join(",");

  useEffect(() => {
    if (!enabled || key.length === 0) return;
    let supabase: ReturnType<typeof createClient>;
    try {
      supabase = createClient();
    } catch {
      return; // Supabase env missing (e.g. design gallery) — nothing to subscribe to.
    }
    const schedule = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => router.refresh(), debounceMs);
    };
    const channel = supabase.channel(`refresh:${key}:${orgId ?? "all"}`);
    for (const table of key.split(",")) {
      channel.on(
        "postgres_changes",
        { event, schema: "public", table, ...(orgId ? { filter: `org_id=eq.${orgId}` } : {}) },
        schedule,
      );
    }
    channel.subscribe();
    return () => {
      if (timer.current) clearTimeout(timer.current);
      void supabase.removeChannel(channel);
    };
  }, [key, orgId, debounceMs, event, enabled, router]);
}

/** Drop-in client component wrapper for server pages: <RealtimeRefresh tables={["exceptions"]} orgId={org.id} /> */
export function RealtimeRefresh(props: { tables: readonly string[] } & RealtimeRefreshOptions): null {
  const { tables, ...opts } = props;
  useRealtimeRefresh(tables, opts);
  return null;
}
