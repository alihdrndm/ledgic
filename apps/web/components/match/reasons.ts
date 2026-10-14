/** Recommendation reason bullets are `{template_id, text, facts}` (domain/templates.py) or plain strings. */
export function reasonTextClient(r: string | { text?: string } | null | undefined): string {
  if (!r) return "";
  return typeof r === "string" ? r : (r.text ?? "");
}
