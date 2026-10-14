import Decimal from "decimal.js";

/** Anything we accept as a money/number input. Postgres numeric arrives as string. */
export type Numeric = Decimal | string | number | null | undefined;

function toDecimal(v: Numeric): Decimal | null {
  if (v === null || v === undefined || v === "") return null;
  try {
    const d = v instanceof Decimal ? v : new Decimal(v);
    return d.isFinite() ? d : null;
  } catch {
    return null;
  }
}

function groupThousands(intPart: string): string {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export interface MoneyOptions {
  /** Prefix "+" for positive values (deltas, e.g. "+$88.00"). */
  signed?: boolean;
  /** Fraction digits (default 2). Use 0 for headline figures like "$6,084". */
  decimals?: number;
  /** Text for null/invalid input (default "—"). */
  fallback?: string;
}

/** money("2759.6") → "$2,759.60"; money(88, {signed:true}) → "+$88.00"; money(-12.5) → "−$12.50" */
export function money(value: Numeric, opts: MoneyOptions = {}): string {
  const { signed = false, decimals = 2, fallback = "—" } = opts;
  const d = toDecimal(value);
  if (!d) return fallback;
  const fixed = d.abs().toFixed(decimals, Decimal.ROUND_HALF_UP);
  const [intPart = "0", frac] = fixed.split(".");
  const body = `$${groupThousands(intPart)}${frac ? `.${frac}` : ""}`;
  if (d.isNegative() && !d.isZero()) return `−${body}`;
  if (signed && d.gt(0)) return `+${body}`;
  return body;
}

export interface PctOptions {
  signed?: boolean;
  /** Fraction digits (default 1). */
  digits?: number;
  fallback?: string;
}

/** pct(0.12, {signed:true}) → "+12.0%"; pct(0.964) → "96.4%". Input is a ratio (0..1). */
export function pct(ratio: Numeric, opts: PctOptions = {}): string {
  const { signed = false, digits = 1, fallback = "—" } = opts;
  const d = toDecimal(ratio);
  if (!d) return fallback;
  const p = d.times(100);
  const body = `${p.abs().toFixed(digits, Decimal.ROUND_HALF_UP)}%`;
  if (p.isNegative() && !p.isZero()) return `−${body}`;
  if (signed && p.gt(0)) return `+${body}`;
  return body;
}

/** count(88412) → "88,412" */
export function count(value: Numeric, fallback = "—"): string {
  const d = toDecimal(value);
  if (!d) return fallback;
  const fixed = d.toFixed(0, Decimal.ROUND_HALF_UP);
  const neg = fixed.startsWith("-");
  const out = groupThousands(neg ? fixed.slice(1) : fixed);
  return neg ? `−${out}` : out;
}

/** Confidence / score with fixed digits: conf(0.7) → "0.70" */
export function conf(value: Numeric, digits = 2, fallback = "—"): string {
  const d = toDecimal(value);
  return d ? d.toFixed(digits, Decimal.ROUND_HALF_UP) : fallback;
}

type DateInput = string | number | Date | null | undefined;

function toDate(v: DateInput): Date | null {
  if (v === null || v === undefined || v === "") return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Wall-clock time in the org's timezone: time(ts, "America/New_York") → "09:41:23" */
export function time(value: DateInput, timeZone: string, opts: { seconds?: boolean } = {}): string {
  const d = toDate(value);
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: opts.seconds === false ? undefined : "2-digit",
    hour12: false,
  }).format(d);
}

/** shortDate(ts, tz) → "Jul 13" */
export function shortDate(value: DateInput, timeZone: string): string {
  const d = toDate(value);
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-US", { timeZone, month: "short", day: "numeric" }).format(d);
}

/** dateTime(ts, tz) → "Jul 13 09:41" */
export function dateTime(value: DateInput, timeZone: string): string {
  const d = toDate(value);
  if (!d) return "—";
  return `${shortDate(d, timeZone)} ${time(d, timeZone, { seconds: false })}`;
}

/** monthYear(ts, tz) → "July 2026" */
export function monthYear(value: DateInput, timeZone: string): string {
  const d = toDate(value);
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-US", { timeZone, month: "long", year: "numeric" }).format(d);
}

/** Relative age, compact: "now", "45s", "14m", "2h", "3d", "5w". */
export function age(from: DateInput, now: DateInput = new Date()): string {
  const a = toDate(from);
  const b = toDate(now);
  if (!a || !b) return "—";
  const s = Math.max(0, Math.floor((b.getTime() - a.getTime()) / 1000));
  if (s < 5) return "now";
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 14) return `${d}d`;
  return `${Math.floor(d / 7)}w`;
}

/** Duration in seconds → "16s", "9m", "24h"; with {precise:true} under a minute → "11.8s". */
export function duration(seconds: Numeric, opts: { precise?: boolean } = {}): string {
  const d = toDecimal(seconds);
  if (!d) return "—";
  const s = d.toNumber();
  if (s < 60 && opts.precise) return `${d.toFixed(1, Decimal.ROUND_HALF_UP)}s`;
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.round(s / 3600)}h`;
}
