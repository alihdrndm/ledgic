import "server-only";
import { createClient } from "@/lib/supabase/server";

/**
 * Server-only client for the Ledgic core API (contracts/core-api.md).
 * Calls go out as the signed-in user (Supabase JWT; role checks happen in the DB as that user). The web
 * app holds no service credential for core: admin calls are operator-only (contracts/core-api.md §Auth.2).
 * The browser never talks to core directly.
 */

export interface CoreError {
  code: string;
  message: string;
  retryable: boolean;
}

export type CoreResult<T> = { ok: true; data: T; status: number } | { ok: false; error: CoreError; status: number };

export function coreUrl(): string | null {
  const url = process.env.CORE_URL;
  return url ? url.replace(/\/+$/, "") : null;
}

/** The current user's Supabase access token (from the session cookie), or null. */
export async function userAccessToken(): Promise<string | null> {
  const supabase = await createClient();
  // getUser() validates the session with Auth; getSession() then returns the (refreshed) token.
  const { data: userData } = await supabase.auth.getUser();
  if (!userData.user) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export interface CoreFetchOptions {
  method?: "GET" | "POST";
  body?: unknown;
  /** Pre-fetched access token (avoids a second auth round-trip). */
  accessToken?: string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** ms; default 15000. */
  timeoutMs?: number;
}

/** Raw fetch against core with auth applied. Throws only for configuration errors. */
export async function coreFetch(path: string, opts: CoreFetchOptions = {}): Promise<Response> {
  const base = coreUrl();
  if (!base) throw new CoreUnavailable("CORE_URL is not configured");
  const method = opts.method ?? (opts.body === undefined ? "GET" : "POST");
  const raw = opts.body === undefined ? "" : JSON.stringify(opts.body);
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  if (raw) headers["Content-Type"] = "application/json";
  const token = opts.accessToken ?? (await userAccessToken());
  if (!token) throw new CoreUnavailable("Not signed in");
  headers.Authorization = `Bearer ${token}`;
  const timeout = AbortSignal.timeout(opts.timeoutMs ?? 15000);
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout;
  return fetch(`${base}${path}`, { method, headers, body: raw || undefined, signal, cache: "no-store" });
}

export class CoreUnavailable extends Error {}

/** JSON call with the `{ok, data | error}` envelope unwrapped. Never throws. */
export async function coreJson<T>(path: string, opts: CoreFetchOptions = {}): Promise<CoreResult<T>> {
  let res: Response;
  try {
    res = await coreFetch(path, opts);
  } catch (err) {
    const message =
      err instanceof CoreUnavailable ? err.message : "The Ledgic core service is unreachable right now.";
    return { ok: false, status: 503, error: { code: "CORE_UNAVAILABLE", message, retryable: true } };
  }
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    // fall through
  }
  const env = payload as { ok?: boolean; data?: T; error?: CoreError } | null;
  if (env && env.ok === true) return { ok: true, data: env.data as T, status: res.status };
  return {
    ok: false,
    status: res.status,
    error: env?.error ?? { code: "INTERNAL", message: `Core responded ${res.status}`, retryable: res.status >= 500 },
  };
}
