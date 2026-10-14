import Decimal from "decimal.js";

/** Result of every G2 server action. `message` is UI copy (safe to show as-is). */
export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; code: "FORBIDDEN" | "NOT_FOUND" | "CONFLICT" | "INVALID" | "UNAUTHENTICATED" | "UNAVAILABLE" | "ERROR"; message: string };

const PREFIX: Record<string, Exclude<ActionResult<never>, { ok: true }>["code"]> = {
  LEDGIC_FORBIDDEN: "FORBIDDEN",
  LEDGIC_NOT_FOUND: "NOT_FOUND",
  LEDGIC_CONFLICT: "CONFLICT",
  LEDGIC_INVALID: "INVALID",
};

const FALLBACK: Record<string, string> = {
  FORBIDDEN: "You don't have permission to do that.",
  NOT_FOUND: "This item no longer exists, or isn't in your organization.",
  CONFLICT: "Someone already decided this item. The page has been refreshed.",
  INVALID: "That value isn't valid.",
};

/**
 * Maps a PostgREST/RPC error (`LEDGIC_<CODE>: <ui copy>`, contracts/rpc.md) to an ActionResult.
 * Unknown errors get generic copy — never leak SQL text to the UI.
 */
export function fromRpcError(error: { message?: string; code?: string } | null | undefined): Exclude<ActionResult<never>, { ok: true }> {
  const msg = error?.message ?? "";
  const idx = msg.indexOf(":");
  const prefix = idx > 0 ? msg.slice(0, idx).trim() : "";
  const code = PREFIX[prefix];
  if (code) {
    const copy = msg.slice(idx + 1).trim();
    return { ok: false, code, message: copy || FALLBACK[code] || "Something went wrong." };
  }
  if (error?.code === "42501") return { ok: false, code: "FORBIDDEN", message: "Read-only access" };
  if (error?.code === "PGRST202" || error?.code === "42883") {
    return { ok: false, code: "UNAVAILABLE", message: "Decisions aren't available yet — the database functions are missing." };
  }
  return { ok: false, code: "ERROR", message: "Something went wrong. Nothing was changed." };
}

/** Clamp client-measured time on task to the 0..1800s window the DB accepts. */
export function clampTimeSpent(seconds: number | null | undefined): number | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  return Math.max(0, Math.min(1800, Math.round(seconds)));
}

/** Money as a 2-dp decimal string ("2759.60"), or null when not a finite number. */
export function moneyString(v: string | number | null | undefined): string | null {
  if (v === null || v === undefined || v === "") return null;
  try {
    const d = new Decimal(typeof v === "string" ? v.replace(/[$,\s]/g, "") : v);
    if (!d.isFinite()) return null;
    return d.toFixed(2, Decimal.ROUND_HALF_UP);
  } catch {
    return null;
  }
}

/** Positive decimal string with at most `dp` places, or an error message. */
export function validatePositive(raw: string, dp: number, label: string): { value: string } | { error: string } {
  const s = raw.replace(/[$,\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(s)) return { error: `${label} must be a number.` };
  const d = new Decimal(s);
  if (d.lte(0)) return { error: `${label} must be greater than 0.` };
  if (d.decimalPlaces() > dp) return { error: `${label} allows at most ${dp} decimals.` };
  return { value: d.toFixed(Math.max(dp === 2 ? 2 : 0, d.decimalPlaces())) };
}
