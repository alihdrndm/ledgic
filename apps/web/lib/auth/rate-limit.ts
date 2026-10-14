import "server-only";
import { createAdminClient } from "./admin";

export interface RateLimitRule {
  /** e.g. `demo:ip:203.0.113.4` (see contracts/rpc.md rate_limit_hit). */
  key: string;
  limit: number;
  windowSeconds: number;
}

let warned = false;

/**
 * True when the caller is over the limit. Fixed-window counter in Postgres via
 * `rate_limit_hit` (service role). Degrades open (returns false) when the RPC or
 * the service key is unavailable, so a missing migration never locks people out.
 */
export async function isRateLimited({ key, limit, windowSeconds }: RateLimitRule): Promise<boolean> {
  const admin = createAdminClient();
  if (!admin) return false;
  try {
    const { data, error } = await admin.rpc("rate_limit_hit", {
      p_key: key,
      p_limit: limit,
      p_window_seconds: windowSeconds,
    });
    if (error) {
      if (!warned) {
        warned = true;
        console.warn(`[rate-limit] rate_limit_hit unavailable (${error.code ?? "?"}): ${error.message} — failing open`);
      }
      return false;
    }
    return data === true;
  } catch (err) {
    if (!warned) {
      warned = true;
      console.warn("[rate-limit] rate_limit_hit call failed — failing open", err);
    }
    return false;
  }
}
