/** Default landing page after sign-in (the demo tenant). */
export const DEFAULT_ORG_SLUG = process.env.NEXT_PUBLIC_DEMO_ORG_SLUG ?? "northside";
export const DEFAULT_AFTER_LOGIN = `/o/${DEFAULT_ORG_SLUG}/pipeline`;

/**
 * Only same-origin, absolute-path redirects are allowed (no `//evil.com`,
 * no `/\evil.com`, no scheme). Anything else falls back to the pipeline.
 */
export function safeNext(next: string | null | undefined, fallback: string = DEFAULT_AFTER_LOGIN): string {
  if (!next || typeof next !== "string") return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f]/.test(next)) return fallback;
  if (next.startsWith("/login") || next.startsWith("/auth/")) return fallback;
  return next;
}
