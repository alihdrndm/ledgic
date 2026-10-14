import { expect, type Page } from "@playwright/test";

export const ORG = process.env.E2E_ORG ?? "northside";
export const VIEWER_STATE = "e2e/.auth/viewer.json";

export const SCREENS = [
  { path: "pipeline", title: "Pipeline" },
  { path: "extraction", title: "Extraction review" },
  { path: "match", title: "Three-way match" },
  { path: "exceptions", title: "Exceptions" },
  { path: "operations", title: "Operations" },
  { path: "invoices", title: "Invoices" },
] as const;

/** The screen title (h1 in the top bar) is visible and no route error boundary rendered. */
export async function expectScreen(page: Page, title: string) {
  await expect(page.getByRole("heading", { level: 1, name: title, exact: true })).toBeVisible();
  await expect(page.getByText(/^Couldn.t load /)).toHaveCount(0);
  await expect(page.getByText("Application error")).toHaveCount(0);
}

/** Resolve an invoice number to its detail href through the palette search API (RLS-scoped). */
export async function invoiceHref(page: Page, invoiceNumber: string): Promise<string | null> {
  const res = await page.request.get(`/api/search?org=${ORG}&q=${encodeURIComponent(invoiceNumber)}`);
  if (!res.ok()) return null;
  const body = (await res.json()) as { groups: { label: string; items: { title: string; href?: string }[] }[] };
  const inv = body.groups.find((g) => g.label === "Invoices");
  const hit = inv?.items.find((i) => i.title.includes(invoiceNumber));
  return hit?.href ?? null;
}

/** /o/<org>/invoices/<id> → /o/<org>/match/<id> */
export function matchHrefFor(invoiceHref: string): string {
  return invoiceHref.replace("/invoices/", "/match/");
}

export async function signInAs(page: Page, persona: "viewer" | "elena") {
  await page.goto("/login");
  const name = persona === "viewer" ? "Open the demo" : /Try as Elena/;
  await page.getByRole("button", { name }).click();
  await page.waitForURL(new RegExp(`/o/${ORG}/`), { timeout: 45_000 });
}
