"use client";

import { useState } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";
import { Button } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { count } from "@/lib/format";
import styles from "./invoices.module.css";

interface VerifyResult {
  ok: boolean;
  entries: number;
  first_broken_id: number | null;
  head_hash: string | null;
}

type State = { kind: "idle" } | { kind: "busy" } | { kind: "done"; result: VerifyResult } | { kind: "error"; message: string };

/** Calls rpc audit_verify_org and reports "Chain verified · <n> entries" or the first broken link. */
export function VerifyChainButton({ orgId }: { orgId: string }) {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function verify() {
    setState({ kind: "busy" });
    try {
      const supabase = createClient() as unknown as SupabaseClient;
      const { data, error } = await supabase.rpc("audit_verify_org", { p_org: orgId });
      if (error) {
        const msg = error.message.includes(":") ? error.message.split(":").slice(1).join(":").trim() : error.message;
        setState({ kind: "error", message: msg || "Verification failed" });
        return;
      }
      setState({ kind: "done", result: data as VerifyResult });
    } catch (e) {
      setState({ kind: "error", message: e instanceof Error ? e.message : "Verification failed" });
    }
  }

  return (
    <div className={styles.verify}>
      <span role="status" aria-live="polite">
        {state.kind === "done" ? (
          state.result.ok ? (
            <span className={styles.verifyOk}>
              Chain verified · {count(state.result.entries)} {state.result.entries === 1 ? "entry" : "entries"}
            </span>
          ) : (
            <span className={styles.verifyBad}>
              Chain broken at entry #{state.result.first_broken_id ?? "?"} · {count(state.result.entries)} entries checked
            </span>
          )
        ) : state.kind === "error" ? (
          <span className={styles.verifyBad}>{state.message}</span>
        ) : null}
      </span>
      <Button variant="outline" size="sm" onClick={verify} loading={state.kind === "busy"}>
        Verify chain
      </Button>
    </div>
  );
}
