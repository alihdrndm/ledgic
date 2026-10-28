"use client";

import Link from "next/link";
import { useId, useMemo, useState, type ReactNode } from "react";
import { Button, Chip, Dialog, RiskCallout } from "@/components/ui";
import { needsRole, useShell } from "@/components/shell";
import { conf as fmtConf, dateTime, money, shortDate } from "@/lib/format";
import { useNow } from "@/lib/now";
import type { DuplicateCopy, ExceptionDetail, OpenPo, VendorRecord } from "@/lib/queries/exceptions";
import { MatchTable } from "@/components/match/MatchTable";
import { DecisionRail } from "@/components/match/DecisionRail";
import { ACTION_LABEL, CHANNEL_SOURCE, ERP_LABEL } from "@/components/match/model";
import { FraudCallout, signalText } from "./parts";
import { useDecide } from "./useDecide";
import "./exceptions.css";

export interface DetailProps {
  orgSlug: string;
  detail: ExceptionDetail;
}

function ErrorLine({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <RiskCallout tone="neutral" title="Not decided" live className="xd-error">
      {error}
    </RiskCallout>
  );
}

/** Shown in place of action buttons once the exception is decided. */
export function DecidedNote({ detail, local }: { detail: ExceptionDetail; local: { action: string; at: string } | null }) {
  const { org, user } = useShell();
  const d = detail.row.latest_decision;
  const action = local?.action ?? d?.action;
  if (!action) return null;
  const who = local ? user.fullName : (d?.actor_name ?? "—");
  const at = local?.at ?? d?.decided_at;
  const status = detail.row.status;
  return (
    <div className="xd-decided" role="status">
      <Chip variant="ink">{ACTION_LABEL[action] ?? action}</Chip>
      <span>
        by {who} · {dateTime(at, org.timezone)}
        {status === "awaiting_vendor" ? " · waiting on the vendor" : status === "disputed" ? " · disputed, payment held" : ""}
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------- Duplicate ------------------ */

function copyLabel(c: DuplicateCopy): string {
  const ch = c.doc?.channel ?? c.invoice.channel;
  if (ch === "email") return "emailed PDF";
  if (ch === "photo") return "dock photo";
  if (ch === "portal") return "vendor portal";
  if (ch === "edi") return "EDI 810";
  return "upload";
}

function sourceLine(c: DuplicateCopy): string {
  const meta = c.doc?.source_meta ?? {};
  const from = (meta.from as string | undefined) ?? (meta.sender as string | undefined);
  if (from) return from;
  if (c.uploadedBy) return `Uploaded by ${c.uploadedBy}`;
  if (c.doc?.channel === "photo") return `Uploaded by ${c.invoice.location_name ?? "site"} receiving`;
  return c.doc?.original_filename ?? CHANNEL_SOURCE[c.invoice.channel] ?? "—";
}

function Thumb({ c }: { c: DuplicateCopy }) {
  const mime = c.doc?.mime ?? "";
  const tag = mime.includes("pdf") ? "PDF" : mime.includes("heic") ? "HEIC" : mime.startsWith("image/") ? "IMG" : "DOC";
  if (c.thumbUrl) {
    // eslint-disable-next-line @next/next/no-img-element -- short-lived signed Storage URL
    return <img className="xd-thumb grayscale" src={c.thumbUrl} alt={`First page of copy from ${copyLabel(c)}`} />;
  }
  return (
    <span className="xd-thumb xd-thumb-tag" data-tone={tag === "PDF" ? undefined : "img"} aria-hidden="true">
      {tag}
    </span>
  );
}

const EVIDENCE: Array<[string, string]> = [
  ["invoice_number", "Invoice no."],
  ["amount", "Amount"],
  ["invoice_date", "Invoice date"],
  ["line_items", "Line items"],
  ["file", "File"],
];

export function DuplicateDetail({ orgSlug, detail }: DetailProps) {
  const { role, org } = useShell();
  const { decide, busy, error, done } = useDecide(orgSlug, detail.row.exception_id);
  const [dialog, setDialog] = useState<"not_dup" | null>(null);
  const copies = detail.copies ?? [];
  const a = copies[0];
  const b = copies[1];
  const ev = (detail.row.duplicate_evidence ?? {}) as Record<string, unknown>;
  const decided = Boolean(done) || detail.row.status === "resolved";
  const reason = needsRole(role, "ap_manager");
  const keepLabel = a ? (copyLabel(a) === "emailed PDF" ? "the PDF" : `Copy A`) : "Copy A";
  const num = detail.row.invoice_number ?? "invoice";

  return (
    <>
      <div className="xd-cards">
        {copies.map((c, i) => (
          <article key={c.invoice.invoice_id} className="xd-card">
            <header className="xd-card-head">
              <span className="field-label">
                Copy {i === 0 ? "A" : "B"} · {copyLabel(c)}
              </span>
              <span className="field-label">{dateTime(c.doc?.received_at ?? c.invoice.received_at, org.timezone)}</span>
            </header>
            <div className="xd-card-body">
              <Thumb c={c} />
              <div className="xd-card-meta">
                <div>{sourceLine(c)}</div>
                <div>
                  Invoice date {shortDate(c.invoice.invoice_date ? `${c.invoice.invoice_date}T12:00:00Z` : null, "UTC")} ·{" "}
                  <strong>{money(c.invoice.total)}</strong>
                </div>
                <div className="meta">
                  SHA-256 …{(c.doc?.sha256 ?? "").slice(-4) || "—"} · extraction {fmtConf(c.invoice.doc_confidence)}
                </div>
              </div>
            </div>
          </article>
        ))}
        {copies.length < 2 ? <p className="meta">The other copy isn&apos;t visible — it may have been purged from the demo.</p> : null}
      </div>
      <div className="xd-evidence" role="list" aria-label="Duplicate evidence">
        {EVIDENCE.map(([k, label]) => {
          const v = ev[k];
          const text = typeof v === "string" ? v : v && typeof v === "object" ? String((v as { text?: string }).text ?? "") : "—";
          const differs = /differ|mismatch|no match/i.test(text);
          return (
            <div key={k} className="xd-evidence-cell" role="listitem">
              <div className="field-label">{label}</div>
              <div className={differs ? "xd-differs" : undefined}>{text || "—"}</div>
            </div>
          );
        })}
      </div>
      <ErrorLine error={error} />
      {decided ? (
        <div className="xd-actions">
          <DecidedNote detail={detail} local={done} />
        </div>
      ) : (
        <div className="xd-actions">
          <Button
            variant="ink"
            disabledReason={reason}
            loading={busy === "merge"}
            onClick={() =>
              void decide("merge", {
                extra: a ? { keep_invoice_id: a.invoice.invoice_id } : {},
                success: `Merged ${num} · second copy blocked from payment`,
              })
            }
          >
            Merge, keep {keepLabel} as source
          </Button>
          <Button
            variant="outline"
            disabledReason={reason}
            loading={busy === "reject_copy"}
            onClick={() => void decide("reject_copy", { success: `Rejected the second copy of ${num}` })}
          >
            Reject the second copy
          </Button>
          <Button variant="ghost" size="sm" disabledReason={needsRole(role, "controller")} onClick={() => setDialog("not_dup")}>
            Not a duplicate
          </Button>
          <span className="meta xd-actions-note">Merging blocks the second payment permanently</span>
        </div>
      )}
      <Dialog
        open={dialog === "not_dup"}
        onClose={() => setDialog(null)}
        title={`Release ${num} as not a duplicate`}
        amount={b ? money(b.invoice.total) : money(detail.row.amount_at_risk)}
        confirmLabel="Release both copies"
        comment={{ label: "Why are these different invoices?", required: true }}
        onConfirm={({ comment }) => decide("not_duplicate", { comment, inDialog: true, success: `Released ${num} — not a duplicate` })}
      >
        <p style={{ margin: 0 }}>Both copies will continue to matching and can each be paid.</p>
      </Dialog>
    </>
  );
}

/* ---------------------------------------------------------------- New vendor screen ---------- */

function addr(v: VendorRecord["remit_address"] | string | null | undefined): string {
  if (!v) return "—";
  if (typeof v === "string") return v;
  const o = v as Record<string, unknown>;
  return [o.line1, o.line2, o.city, o.state, o.postal_code ?? o.zip].filter(Boolean).join(", ") || "—";
}

function last4(v: unknown): string {
  const s = String(v ?? "").replace(/\D/g, "");
  return s ? `…${s.slice(-4)}` : "—";
}

export function NewVendorDetail({ orgSlug, detail }: DetailProps) {
  const { role, org } = useShell();
  const { decide, busy, error, done } = useDecide(orgSlug, detail.row.exception_id);
  const [dialog, setDialog] = useState<"release" | "reject" | null>(null);
  const now = useNow();
  const v = detail.vendor;
  const f = detail.invoice?.fields ?? {};
  const num = detail.row.invoice_number ?? "invoice";
  const decided = Boolean(done) || detail.row.status === "resolved";
  const awaiting = detail.row.status === "awaiting_vendor";
  const bankDiffers = Boolean(v?.bank_fingerprint && v?.w9_bank_fingerprint && v.bank_fingerprint !== v.w9_bank_fingerprint);
  const ageDays = v ? Math.max(0, Math.floor((now - new Date(v.created_at).getTime()) / 86400000)) : null;

  const rows: Array<{ label: string; file: ReactNode; inv: ReactNode; risk?: boolean }> = [
    { label: "Legal name", file: v?.legal_name ?? v?.display_name ?? "—", inv: (f.remit_to_name?.value as string) ?? (f.vendor_name?.value as string) ?? "—" },
    { label: "Tax ID, last 4", file: v?.tax_id_last4 ? `…${v.tax_id_last4}` : "—", inv: v?.tax_id_last4 ? `…${v.tax_id_last4}` : "—" },
    {
      label: "Bank account, last 4",
      file: v?.w9_on_file ? (v.w9_bank_fingerprint ? "W-9 bank on file" : "W-9 on file, no bank") : "No W-9 on file",
      inv: f.bank_account?.value ? last4(f.bank_account.value) : v?.bank_last4 ? `…${v.bank_last4}` : "—",
      risk: bankDiffers,
    },
    { label: "Bank routing, last 4", file: "—", inv: last4(f.bank_routing?.value) },
    {
      label: "Remit address",
      file: addr(v?.remit_address),
      inv: (f.remit_to_address?.value as string) ?? "—",
      risk: Boolean(v?.remit_address_changed_at && now - new Date(v.remit_address_changed_at).getTime() < 14 * 86400000),
    },
    {
      label: "Vendor record created",
      file: v ? `${shortDate(v.created_at, org.timezone)} · ${ageDays} day${ageDays === 1 ? "" : "s"} ago` : "—",
      inv: detail.invoice?.invoice_date ? `Invoice dated ${shortDate(`${detail.invoice.invoice_date}T12:00:00Z`, "UTC")}` : "—",
      risk: ageDays !== null && ageDays < 14,
    },
  ];

  return (
    <>
      <div className="xd-pad">
        <FraudCallout row={detail.row} expanded />
      </div>
      <div className="xd-pad">
        <table className="xd-compare">
          <caption className="sr-only">Vendor record on file compared with the invoice</caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">On file</th>
              <th scope="col">On this invoice</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} data-risk={r.risk || undefined}>
                <th scope="row">{r.label}</th>
                <td>{r.file}</td>
                <td className={r.risk ? "xd-differs" : undefined}>{r.inv}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="xd-signal-list">
          {(detail.row.signals ?? []).map((s) => (
            <li key={s.signal}>
              {signalText(s)} <span className="meta">· weight {fmtConf(s.weight)}</span>
            </li>
          ))}
        </ul>
      </div>
      <ErrorLine error={error} />
      {decided ? (
        <div className="xd-actions">
          <DecidedNote detail={detail} local={done} />
        </div>
      ) : (
        <div className="xd-actions">
          {awaiting ? <DecidedNote detail={detail} local={null} /> : null}
          <Button
            variant="outline"
            disabledReason={needsRole(role, "ap_manager")}
            loading={busy === "request_w9"}
            disabled={awaiting}
            onClick={() => void decide("request_w9", { success: `W-9 re-verification requested from ${detail.row.vendor_name ?? "the vendor"} · hold kept` })}
          >
            Request W-9 re-verification
          </Button>
          <Button variant="ink" disabledReason={needsRole(role, "controller")} onClick={() => setDialog("release")}>
            Release hold
          </Button>
          <Button variant="outline" disabledReason={needsRole(role, "controller")} onClick={() => setDialog("reject")}>
            Reject invoice
          </Button>
          <span className="meta xd-actions-note">Only a controller who didn&apos;t create the vendor record can release</span>
        </div>
      )}
      <Dialog
        open={dialog === "release"}
        onClose={() => setDialog(null)}
        title={`Release the hold on ${num}`}
        amount={money(detail.row.invoice_total ?? detail.row.amount_at_risk)}
        confirmLabel="Release hold"
        comment={{ label: "How were the bank details verified?", required: true }}
        acknowledge="I verified the bank details with the vendor by phone"
        onConfirm={({ comment, acknowledged }) =>
          decide("release_hold", {
            comment,
            extra: { verified_by_phone: acknowledged },
            inDialog: true,
            success: `Released ${num} · ${money(detail.row.invoice_total)} continues to matching`,
          })
        }
      >
        <p style={{ margin: 0 }}>The invoice continues to matching and can be paid to the bank details on the invoice.</p>
      </Dialog>
      <Dialog
        open={dialog === "reject"}
        onClose={() => setDialog(null)}
        title={`Reject ${num}`}
        amount={money(detail.row.invoice_total ?? detail.row.amount_at_risk)}
        confirmLabel="Reject invoice"
        comment={{ label: "Comment (optional)" }}
        onConfirm={({ comment }) => decide("reject_invoice", { comment: comment || null, inDialog: true, success: `Rejected ${num} · nothing will be paid` })}
      >
        <p style={{ margin: 0 }}>The invoice will never be paid. The vendor record stays on file for review.</p>
      </Dialog>
    </>
  );
}

/* ---------------------------------------------------------------- Price / qty ---------------- */

export function VarianceDetail({ orgSlug, detail }: DetailProps) {
  const lines = detail.match?.lines ?? [];
  const head = lines[0];
  const inv = detail.invoice;
  const full = `/o/${orgSlug}/match/${detail.row.invoice_id}`;
  return (
    <div className="xd-variance">
      <div className="xd-variance-main">
        {lines.length ? (
          <MatchTable lines={lines} invoiceTotal={inv?.total} poTotal={inv?.po_total ?? head?.expected_total} compact />
        ) : (
          <p className="meta">No line-level match results are recorded for this invoice yet.</p>
        )}
        <p className="xd-open-full">
          <Link href={full}>Open full match</Link>
        </p>
      </div>
      <DecisionRail
        key={detail.row.exception_id}
        orgSlug={orgSlug}
        exceptionId={detail.row.exception_id}
        exceptionStatus={detail.row.status}
        recommendation={detail.row.recommendation ?? head?.recommendation ?? null}
        decision={detail.row.latest_decision ?? head?.decision ?? null}
        lines={lines}
        invoiceNumber={detail.row.invoice_number}
        invoiceTotal={inv?.total ?? detail.row.invoice_total}
        amountAtRisk={detail.row.amount_at_risk}
        erp={{ system: inv?.erp_system ?? null, externalId: inv?.erp_external_id ?? null, status: inv?.erp_status ?? null, postedAt: inv?.posted_at ?? null }}
        compact
        openFullHref={full}
      />
    </div>
  );
}

/* ---------------------------------------------------------------- No PO ---------------------- */

export function NoPoDetail({ orgSlug, detail }: DetailProps) {
  const { role, org } = useShell();
  const { decide, busy, error, done } = useDecide(orgSlug, detail.row.exception_id);
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<OpenPo | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const inputId = useId();
  const pos = useMemo(() => detail.openPos ?? [], [detail.openPos]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? pos.filter((p) => p.po_number.toLowerCase().includes(q)) : pos;
  }, [pos, query]);
  const num = detail.row.invoice_number ?? "invoice";
  const decided = Boolean(done) || detail.row.status === "resolved";

  function choose(p: OpenPo) {
    setPicked(p);
    setQuery(p.po_number);
    setOpen(false);
  }

  return (
    <>
      <div className="xd-pad">
        <p className="xd-lead">
          No purchase order was referenced on {num} or found for {detail.row.vendor_name ?? "this vendor"}
          {detail.invoice?.location_name ? ` at ${detail.invoice.location_name}` : ""}. Link an open PO to re-run the three-way match.
        </p>
        <div className="xd-combo">
          <label htmlFor={inputId} className="field-label">
            Open purchase orders · {pos.length}
          </label>
          <input
            id={inputId}
            className="input"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && filtered[active] ? `${listId}-${filtered[active]!.id}` : undefined}
            placeholder={pos.length ? "Search by PO number" : "No open POs for this vendor and location"}
            disabled={pos.length === 0 || decided}
            value={query}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 120)}
            onChange={(e) => {
              setQuery(e.target.value);
              setPicked(null);
              setOpen(true);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setOpen(true);
                setActive((a) => Math.min(filtered.length - 1, a + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === "Enter" && open && filtered[active]) {
                e.preventDefault();
                choose(filtered[active]!);
              } else if (e.key === "Escape") setOpen(false);
            }}
          />
          {open && filtered.length > 0 ? (
            <ul id={listId} role="listbox" className="xd-combo-list">
              {filtered.slice(0, 12).map((p, i) => (
                <li
                  key={p.id}
                  id={`${listId}-${p.id}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    choose(p);
                  }}
                >
                  <span className="xd-combo-po">{p.po_number}</span>
                  <span className="meta">
                    {money(p.total)} · ordered {shortDate(p.ordered_at, org.timezone)}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
      <ErrorLine error={error} />
      {decided ? (
        <div className="xd-actions">
          <DecidedNote detail={detail} local={done} />
        </div>
      ) : (
        <div className="xd-actions">
          <Button
            variant="ink"
            disabledReason={needsRole(role, "ap_clerk")}
            disabled={!picked}
            loading={busy === "link_po"}
            onClick={() =>
              picked &&
              void decide("link_po", { extra: { po_id: picked.id }, success: `Linked ${picked.po_number} to ${num} · re-matching now` })
            }
          >
            {picked ? `Link ${picked.po_number} and re-match` : "Link PO and re-match"}
          </Button>
          <Button variant="outline" disabledReason={needsRole(role, "ap_manager")} onClick={() => setDialog("approve")}>
            Approve without PO
          </Button>
          <Button variant="outline" disabledReason={needsRole(role, "ap_manager")} onClick={() => setDialog("reject")}>
            Reject invoice
          </Button>
        </div>
      )}
      <Dialog
        open={dialog === "approve"}
        onClose={() => setDialog(null)}
        title={`Approve ${num} without a purchase order`}
        amount={money(detail.row.invoice_total ?? detail.row.amount_at_risk)}
        confirmLabel="Approve without PO"
        comment={{ label: "Why is there no PO?", required: true }}
        onConfirm={({ comment }) =>
          decide("approve_without_po", { comment, inDialog: true, success: `Approved ${num} without a PO · ${money(detail.row.invoice_total)} sent for posting` })
        }
      />
      <Dialog
        open={dialog === "reject"}
        onClose={() => setDialog(null)}
        title={`Reject ${num}`}
        amount={money(detail.row.invoice_total ?? detail.row.amount_at_risk)}
        confirmLabel="Reject invoice"
        comment={{ label: "Comment (optional)" }}
        onConfirm={({ comment }) => decide("reject_invoice", { comment: comment || null, inDialog: true, success: `Rejected ${num}` })}
      />
    </>
  );
}

/* ---------------------------------------------------------------- Posting failed ------------- */

export function PostingFailedDetail({ orgSlug, detail }: DetailProps) {
  const { role } = useShell();
  const { decide, busy, error, done } = useDecide(orgSlug, detail.row.exception_id);
  const [dialog, setDialog] = useState(false);
  const failed = (detail.postings ?? []).find((p) => p.status === "failed") ?? detail.postings?.[0] ?? null;
  const system = failed ? (ERP_LABEL[failed.system] ?? failed.system) : "the ERP";
  const excerpt = failed?.response ? JSON.stringify(failed.response, null, 2).slice(0, 800) : null;
  const num = detail.row.invoice_number ?? "invoice";
  const decided = Boolean(done) || detail.row.status === "resolved";
  return (
    <>
      <div className="xd-pad">
        <RiskCallout tone="neutral" title={`Posting to ${system} failed${failed ? ` after ${failed.attempts} attempt${failed.attempts === 1 ? "" : "s"}` : ""}`}>
          {failed?.error ?? detail.row.reason}
        </RiskCallout>
        {excerpt ? (
          <div className="xd-erp">
            <div className="field-label">ERP response excerpt</div>
            <pre className="xd-pre">{excerpt}</pre>
          </div>
        ) : null}
      </div>
      <ErrorLine error={error} />
      {decided ? (
        <div className="xd-actions">
          <DecidedNote detail={detail} local={done} />
        </div>
      ) : (
        <div className="xd-actions">
          <Button
            variant="ink"
            disabledReason={needsRole(role, "ap_manager")}
            loading={busy === "retry_posting"}
            onClick={() => void decide("retry_posting", { success: `Retrying ${num} → ${system}` })}
          >
            Retry posting
          </Button>
          <Button variant="outline" disabledReason={needsRole(role, "ap_manager")} onClick={() => setDialog(true)}>
            Reject invoice
          </Button>
        </div>
      )}
      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title={`Reject ${num}`}
        amount={money(detail.row.invoice_total ?? detail.row.amount_at_risk)}
        confirmLabel="Reject invoice"
        comment={{ label: "Comment (optional)" }}
        onConfirm={({ comment }) => decide("reject_invoice", { comment: comment || null, inDialog: true, success: `Rejected ${num}` })}
      />
    </>
  );
}

/* ---------------------------------------------------------------- Extraction review ---------- */

export function ExtractionReviewDetail({ orgSlug, detail }: DetailProps) {
  return (
    <div className="xd-pad">
      <p className="xd-lead">
        Extraction confidence is below the gate, so a person confirms the flagged fields before the invoice moves on.
      </p>
      <Link className="btn btn-ink ledgic-btn ledgic-btn-md" href={`/o/${orgSlug}/extraction/${detail.row.invoice_id}`}>
        Open in extraction review
      </Link>
    </div>
  );
}

export { FraudCallout };
