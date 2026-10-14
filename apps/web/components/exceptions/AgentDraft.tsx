"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Chip } from "@/components/ui";
import { needsRole, useShell } from "@/components/shell";
import { CitationChip, MarkdownLite } from "@/components/copilot";
import { dateTime } from "@/lib/format";
import { requestDraft } from "@/lib/actions/exceptions";
import type { DraftRow } from "@/lib/queries/exceptions";
import "./exceptions.css";

const KIND_LABEL: Record<DraftRow["kind"], string> = { vendor_notice: "Vendor notice", explanation: "Explanation" };

/**
 * AGENT DRAFT panel (D9): the resolution agent's vendor notice / explanation with clause citations.
 * Drafts are prose only — the money guard in core ensures every figure equals the deterministic recommendation.
 */
export function AgentDraft({ orgSlug, exceptionId, drafts, kinds }: { orgSlug: string; exceptionId: string; drafts: DraftRow[]; kinds: DraftRow["kind"][] }) {
  const { role, org } = useShell();
  const router = useRouter();
  const [busy, setBusy] = useState<DraftRow["kind"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fresh, setFresh] = useState<Record<string, DraftRow>>({});
  const [tab, setTab] = useState<DraftRow["kind"]>(drafts[0]?.kind ?? kinds[0] ?? "vendor_notice");
  const reason = needsRole(role, "ap_clerk");

  const byKind = (k: DraftRow["kind"]) => fresh[k] ?? drafts.find((d) => d.kind === k) ?? null;
  const current = byKind(tab);

  async function draft(kind: DraftRow["kind"], regenerate: boolean) {
    setBusy(kind);
    setError(null);
    const res = await requestDraft({ orgSlug, exceptionId, kind, regenerate });
    setBusy(null);
    if (!res.ok) {
      setError(res.message);
      return;
    }
    const d = res.data;
    setFresh((f) => ({
      ...f,
      [kind]: {
        id: d.draft_id,
        kind: d.kind,
        body_md: d.body_md,
        citations: d.citations ?? [],
        model: d.model,
        prompt_version: d.prompt_version,
        mode: d.mode,
        created_at: d.created_at,
      },
    }));
    setTab(kind);
    router.refresh();
  }

  return (
    <section className="xd-draft" aria-label="Agent draft">
      <header className="xd-draft-head">
        <span className="section-label">Agent draft</span>
        {kinds.length > 1 ? (
          <div className="xd-tabs" role="tablist" aria-label="Draft kind">
            {kinds.map((k) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} className="xd-tab" onClick={() => setTab(k)}>
                {KIND_LABEL[k]}
              </button>
            ))}
          </div>
        ) : null}
        <span className="xd-draft-actions">
          <Button
            variant="outline"
            size="sm"
            disabledReason={reason}
            loading={busy === tab}
            onClick={() => void draft(tab, Boolean(current))}
          >
            {current ? "Redraft with agent" : "Draft with agent"}
          </Button>
        </span>
      </header>
      {error ? (
        <p className="xd-draft-error" role="alert">
          {error}
        </p>
      ) : null}
      {current ? (
        <div className="xd-draft-body">
          <MarkdownLite text={current.body_md} citations={current.citations} />
          {current.citations.length ? (
            <div className="xd-draft-cites">
              <span className="field-label">Citations</span>
              {current.citations.map((c, i) => (
                <CitationChip key={c.chunk_id ?? i} citation={{ ...c, n: c.n ?? i + 1 }} showTitle />
              ))}
            </div>
          ) : null}
          <p className="meta xd-draft-meta">
            Drafted by resolution agent · {current.mode}
            {current.model ? ` · ${current.model}` : ""}
            {current.prompt_version ? ` · ${current.prompt_version}` : ""} · {dateTime(current.created_at, org.timezone)}
            <Chip variant="neutral" size="sm" style={{ marginLeft: 8 }}>
              Not sent — review before use
            </Chip>
          </p>
        </div>
      ) : (
        <p className="meta xd-draft-empty">
          No draft yet. The resolution agent reads the contract clauses, vendor history and the recommendation, then writes a{" "}
          {tab === "vendor_notice" ? "vendor notice" : "plain-language explanation"} with citations. It never changes the amounts.
        </p>
      )}
    </section>
  );
}
