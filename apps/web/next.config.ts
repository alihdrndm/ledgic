import type { NextConfig } from "next";

// ---- Security headers (11-security §4) -------------------------------------------------
// Static CSP. Next's App Router hydration emits inline <script>s, so script-src needs
// 'unsafe-inline' unless every page is rendered dynamically with a per-request nonce;
// statically prerendered pages would break under a nonce CSP. Everything else is locked down.
const isDev = process.env.NODE_ENV !== "production";

function origin(raw: string | undefined): string | null {
  if (!raw) return null;
  try {
    return new URL(raw).origin;
  } catch {
    return null;
  }
}

function securityHeaders() {
  const supabase = origin(process.env.NEXT_PUBLIC_SUPABASE_URL);
  const supabaseWs = supabase ? supabase.replace(/^http/, "ws") : null;
  const core = origin(process.env.NEXT_PUBLIC_CORE_URL);
  const connect = ["'self'", supabase, supabaseWs, core, isDev ? "ws:" : null].filter(Boolean).join(" ");
  const media = ["'self'", "data:", "blob:", supabase].filter(Boolean).join(" ");

  const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
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

  return [
    { key: "Content-Security-Policy", value: csp },
    ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }]),
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    {
      key: "Permissions-Policy",
      value: "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
    },
  ];
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@ledgic/db-types"],
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders() }];
  },
};

export default nextConfig;
