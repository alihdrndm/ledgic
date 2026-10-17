// ---- Content-Security-Policy (11-security §4) ------------------------------------------
// Per-request nonce: middleware mints one, Next reads it from the request's CSP header and stamps it on
// its own inline hydration scripts, so script-src needs no 'unsafe-inline'. 'strict-dynamic' lets those
// trusted scripts load the app's chunks. Every page renders dynamically (app/layout.tsx), because a
// statically prerendered page would carry no nonce. Styles keep 'unsafe-inline': React style attributes
// and next/font need it, and inline CSS cannot run script.

function origin(raw: string | undefined): string | null {
  if (!raw) return null;
  try {
    return new URL(raw).origin;
  } catch {
    return null;
  }
}

export function newNonce(): string {
  return btoa(crypto.randomUUID());
}

export function contentSecurityPolicy(nonce: string, isDev = process.env.NODE_ENV !== "production"): string {
  const supabase = origin(process.env.NEXT_PUBLIC_SUPABASE_URL);
  const supabaseWs = supabase ? supabase.replace(/^http/, "ws") : null;
  const core = origin(process.env.NEXT_PUBLIC_CORE_URL);
  const connect = ["'self'", supabase, supabaseWs, core, isDev ? "ws:" : null].filter(Boolean).join(" ");
  const media = ["'self'", "data:", "blob:", supabase].filter(Boolean).join(" ");

  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src ${media}`,
    "font-src 'self' data:",
    `connect-src ${connect}`,
    `frame-src 'self' blob: ${supabase ?? ""}`.trim(),
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}
