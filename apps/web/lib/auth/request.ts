import "server-only";
import { headers } from "next/headers";

/** Best-effort client IP (Vercel sets x-forwarded-for / x-real-ip). */
export function ipFrom(h: Headers): string {
  const fwd = h.get("x-forwarded-for");
  const first = fwd?.split(",")[0]?.trim();
  return first || h.get("x-real-ip")?.trim() || "unknown";
}

export async function clientIp(): Promise<string> {
  return ipFrom(await headers());
}

/** Public origin of this deployment, for auth redirect URLs. */
export async function siteOrigin(): Promise<string> {
  const configured = process.env.NEXT_PUBLIC_SITE_URL;
  if (configured) return configured.replace(/\/+$/, "");
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https");
  return `${proto}://${host}`;
}
