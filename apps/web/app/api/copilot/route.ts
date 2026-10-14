import type { NextRequest } from "next/server";
import { coreFetch, userAccessToken } from "@/lib/core";
import { untypedClient } from "@/lib/actions/db";
import { getSessionContext } from "@/lib/supabase/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

const USER_LIMIT = { limit: 30, window: 3600 };
const IP_LIMIT = { limit: 60, window: 3600 };

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** A one-shot SSE stream carrying a single `error` event (so the client has one code path). */
function sseError(code: string, message: string, retryable: boolean, status = 200): Response {
  return new Response(sse("error", { code, message, retryable }), {
    status,
    headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function clientIp(req: NextRequest): string {
  const fwd = req.headers.get("x-forwarded-for");
  return (fwd?.split(",")[0] ?? req.headers.get("x-real-ip") ?? "local").trim();
}

/**
 * POST /api/copilot  body {org: slug, question, context?: {invoice_id?, exception_id?}}
 * Proxies to core POST /v1/copilot/ask (SSE passthrough) as the signed-in user.
 * Optional BYOK: `X-OpenAI-Key` is forwarded for this request only — never stored or logged.
 */
export async function POST(req: NextRequest) {
  let body: { org?: string; question?: string; context?: { invoice_id?: string; exception_id?: string } };
  try {
    body = await req.json();
  } catch {
    return sseError("INVALID", "Bad request.", false, 400);
  }
  const question = String(body.question ?? "").trim();
  if (!question) return sseError("INVALID", "Ask a question first.", false, 422);
  if (question.length > 500) return sseError("INVALID", "Questions are limited to 500 characters.", false, 422);

  const session = await getSessionContext(String(body.org ?? ""));
  if (session.status === "unauthenticated") return sseError("UNAUTHENTICATED", "Sign in to ask Ledgic.", false, 401);
  if (session.status === "forbidden") return sseError("NOT_FOUND", "Organization not found.", false, 404);
  const { org, user } = session.context;

  // Rate limits (rpc rate_limit_hit returns true when over the limit). Missing RPC → allow.
  const db = await untypedClient();
  const [u, ip] = await Promise.all([
    db.rpc("rate_limit_hit", { p_key: `copilot:user:${user.id}`, p_limit: USER_LIMIT.limit, p_window_seconds: USER_LIMIT.window }),
    db.rpc("rate_limit_hit", { p_key: `copilot:ip:${clientIp(req)}`, p_limit: IP_LIMIT.limit, p_window_seconds: IP_LIMIT.window }),
  ]);
  if (u.data === true || ip.data === true) {
    return sseError("RATE_LIMITED", "You've asked a lot of questions this hour. Try again later.", true, 429);
  }

  const context: Record<string, string> = {};
  const uuid = /^[0-9a-f-]{36}$/i;
  if (body.context?.invoice_id && uuid.test(body.context.invoice_id)) context.invoice_id = body.context.invoice_id;
  if (body.context?.exception_id && uuid.test(body.context.exception_id)) context.exception_id = body.context.exception_id;

  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const byok = req.headers.get("x-openai-key")?.trim();
  if (byok && byok.length < 300 && /^sk-[A-Za-z0-9_\-]+$/.test(byok)) headers["X-OpenAI-Key"] = byok;

  let res: Response;
  try {
    const accessToken = await userAccessToken();
    res = await coreFetch("/v1/copilot/ask", {
      method: "POST",
      accessToken,
      headers,
      body: { org_id: org.id, question, context, stream: true },
      timeoutMs: 55000,
      signal: req.signal,
    });
  } catch {
    return sseError("CORE_UNAVAILABLE", "Ask Ledgic is offline right now — the core service didn't answer.", true, 503);
  }

  const type = res.headers.get("content-type") ?? "";
  if (!res.ok || !type.includes("text/event-stream") || !res.body) {
    let message = "Ask Ledgic couldn't answer right now.";
    let code = "INTERNAL";
    let retryable = res.status >= 500 || res.status === 429;
    try {
      const env = (await res.json()) as { ok?: boolean; data?: unknown; error?: { code: string; message: string; retryable: boolean } };
      if (env.ok && env.data) {
        // Core answered with JSON (non-stream). Re-emit as a single `done` event.
        return new Response(sse("done", env.data), {
          headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store" },
        });
      }
      if (env.error) ({ code, message, retryable } = env.error);
    } catch {
      // keep defaults
    }
    return sseError(code, message, retryable, res.status >= 400 ? res.status : 502);
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
