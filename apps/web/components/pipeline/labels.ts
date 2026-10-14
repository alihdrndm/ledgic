import Decimal from "decimal.js";
import type { Num } from "@/lib/queries/pipeline";

const STAGE_LABEL: Record<string, string> = {
  intake: "Intake",
  extraction: "Extraction",
  review: "Review",
  enrichment: "Enrichment",
  screening: "Screening",
  match: "Match",
  approval: "Approval",
  posting: "Posting",
  notify: "Notify",
  close: "Closed",
};

/** Stage column text for a run row: "Posted" once the invoice is in the ERP, else the current stage. */
export function stageLabel(stage: string, invoiceStatus?: string | null): string {
  if (invoiceStatus === "posted") return "Posted";
  return STAGE_LABEL[stage] ?? stage;
}

const ERP_LABEL: Record<string, string> = { quickbooks: "QuickBooks", netsuite: "NetSuite" };
export function erpLabel(system: string | null | undefined): string {
  if (!system || system === "none") return "—";
  return ERP_LABEL[system] ?? system;
}

const CHANNEL_LABEL: Record<string, string> = {
  email: "email PDF",
  photo: "dock photo",
  portal: "vendor portal",
  edi: "EDI 810",
  upload: "upload",
};
export function channelLabel(channel: string): string {
  return CHANNEL_LABEL[channel] ?? channel;
}

/** 0.02 → "2%", 0.025 → "2.5%" (policy values, no trailing zeros). */
export function policyPct(v: Num | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${new Decimal(v).times(100).toDecimalPlaces(2).toString()}%`;
}

/** 25 → "$25", 25.5 → "$25.50". */
export function policyMoney(v: Num | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const d = new Decimal(v);
  return d.isInteger() ? `$${d.toFixed(0)}` : `$${d.toFixed(2)}`;
}

const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
export function countWord(n: number): string {
  return WORDS[n] ?? String(n);
}
