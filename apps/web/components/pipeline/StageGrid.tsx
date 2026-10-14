import { KeyValueRow } from "@/components/ui";
import { conf, count, duration } from "@/lib/format";
import type { ChannelTodayRow, ExtractionModel, StageTodayRow } from "@/lib/queries/pipeline";
import { policyMoney, policyPct } from "./labels";
import styles from "./pipeline.module.css";

const INTAKE_ROWS: { channel: ChannelTodayRow["channel"]; label: string; always: boolean }[] = [
  { channel: "email", label: "Email PDFs", always: true },
  { channel: "photo", label: "Photo OCR", always: true },
  { channel: "portal", label: "Vendor portals", always: true },
  { channel: "edi", label: "EDI 810", always: true },
  { channel: "upload", label: "Uploads", always: false },
];

export interface StageGridProps {
  stages: StageTodayRow | null;
  channels: ChannelTodayRow[];
  model: ExtractionModel | null;
}

function StageCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="stage-col" aria-label={title}>
      <h3 className="section-label stage-col-head" style={{ margin: 0 }}>
        {title}
      </h3>
      {children}
    </section>
  );
}

/** Five stage columns, every number from v_stage_today / v_channel_today. */
export function StageGrid({ stages: s, channels, model }: StageGridProps) {
  const byChannel = new Map(channels.map((c) => [c.channel, c.count]));
  const n = (v: number | undefined | null) => count(v ?? 0);
  const gate = s?.confidence_gate ?? null;

  return (
    <div className="stage-grid">
      <StageCol title="01 Intake">
        {INTAKE_ROWS.filter((r) => r.always || (byChannel.get(r.channel) ?? 0) > 0).map((r) => (
          <KeyValueRow key={r.channel} label={r.label} value={n(byChannel.get(r.channel))} />
        ))}
        <div className="stage-col-foot">Uploads and dock photos · every file hashed and stored before parsing.</div>
      </StageCol>

      <StageCol title="02 Extraction">
        <KeyValueRow label="Auto-passed" value={n(s?.extraction_auto_passed)} />
        <KeyValueRow label="Below gate → review" value={n(s?.extraction_below_gate)} risk={(s?.extraction_below_gate ?? 0) > 0} />
        <KeyValueRow label="Median time" value={duration(s?.extraction_median_seconds ?? null, { precise: true })} />
        <div className={`stage-col-note ${styles.stageNote}`}>
          Confidence gate at <strong>{conf(gate)}</strong>. Every field carries a score; anything under the gate goes to a
          person before it moves.
        </div>
        <div className="stage-col-foot">
          {model ? `model ${model.model} · prompt ${model.prompt}` : "model version not recorded yet"}
        </div>
      </StageCol>

      <StageCol title="03 Enrichment">
        <KeyValueRow label="Vendor resolved" value={n(s?.vendor_resolved)} />
        <KeyValueRow label="PO linked" value={n(s?.po_linked)} />
        <KeyValueRow label="GL predicted" value={n(s?.gl_predicted)} />
        <KeyValueRow label="Duplicate screen" value={n(s?.duplicate_screened)} />
        <div className="stage-col-foot">Entity and location coding applied here, so the ERP write needs no manual touch.</div>
      </StageCol>

      <StageCol title="04 Three-way match">
        <KeyValueRow label="Clean" value={n(s?.match_clean)} />
        <KeyValueRow label="Price variance" value={n(s?.match_price_variance)} risk={(s?.match_price_variance ?? 0) > 0} />
        <KeyValueRow label="Quantity mismatch" value={n(s?.match_qty_mismatch)} />
        <KeyValueRow label="No PO found" value={n(s?.match_no_po)} />
        <div className="stage-col-foot">
          Tolerance: auto-approve within ±{policyPct(s?.tolerance_pct)} or {policyMoney(s?.tolerance_abs)}, whichever is
          lower.
        </div>
      </StageCol>

      <StageCol title="05 Approve + post">
        <KeyValueRow label="Awaiting a person" value={n(s?.awaiting_person)} risk={(s?.awaiting_person ?? 0) > 0} />
        <KeyValueRow label="Posted · QuickBooks (mock)" value={n(s?.posted_quickbooks)} />
        <KeyValueRow label="Posted · NetSuite (mock)" value={n(s?.posted_netsuite)} />
        <div className="stage-col-foot">Nothing posts without entity + location + GL coding attached.</div>
      </StageCol>
    </div>
  );
}
