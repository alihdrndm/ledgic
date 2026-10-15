import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { expectScreen, invoiceHref, matchHrefFor, ORG, SCREENS, VIEWER_STATE } from "./helpers";

test.use({ storageState: VIEWER_STATE });

for (const s of SCREENS) {
  test(`${s.title} renders without an error boundary`, async ({ page }) => {
    await page.goto(`/o/${ORG}/${s.path}`);
    await expectScreen(page, s.title);
  });
}

test("Verify chain on an invoice's audit trail", async ({ page }) => {
  await page.goto(`/o/${ORG}/invoices`);
  await expectScreen(page, "Invoices");
  const href = await page.locator(`a[href^="/o/${ORG}/invoices/"]`).first().getAttribute("href");
  expect(href, "at least one invoice in the list").toBeTruthy();
  await page.goto(`${href}?tab=audit`);
  await expect(page.getByText(/Audit trail · .* · append-only/)).toBeVisible();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByText(/Chain verified · [\d,]+ entr/)).toBeVisible({ timeout: 30_000 });
});

test("Ctrl/Cmd+K opens the command palette", async ({ page }) => {
  await page.goto(`/o/${ORG}/pipeline`);
  await expectScreen(page, "Pipeline");
  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette).toBeVisible();
  await expect(palette.getByRole("combobox", { name: "Search" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(palette).toBeHidden();
});

test("Ask Ledgic answers a suggested question with a citation", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto(`/o/${ORG}/match`);
  await expectScreen(page, "Three-way match");
  const drawer = page.getByRole("dialog", { name: "Ask Ledgic" });
  // Retry the click until hydration has attached the handler.
  await expect(async () => {
    await page.getByRole("button", { name: "Ask Ledgic" }).first().click();
    await expect(drawer).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  await drawer.getByRole("button", { name: "What does clause 4.2 of the Protein Supplier agreement say about shrimp?" }).click();
  // Live, cached or retrieval-only (AI budget reached) all pass, as long as a source is cited.
  await expect(drawer.locator(".cp-cite").first()).toBeVisible({ timeout: 90_000 });
  await expect(drawer.getByRole("alert")).toHaveCount(0);
});

test("Ask Ledgic cites the contract clause behind the PS-88214 hold", async ({ page }) => {
  // Not cached by design (it reads live exception data), so against a deployed site this spends one
  // live answer unless the day's AI budget is gone (then the retrieval-only answer must cite it too).
  test.skip(!process.env.E2E_ALLOW_LIVE_AI && !!process.env.E2E_BASE_URL, "set E2E_ALLOW_LIVE_AI=1 to run against a deployed site");
  test.setTimeout(120_000);
  await page.goto(`/o/${ORG}/match`);
  const drawer = page.getByRole("dialog", { name: "Ask Ledgic" });
  await expect(async () => {
    await page.getByRole("button", { name: "Ask Ledgic" }).first().click();
    await expect(drawer).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  await drawer.getByRole("button", { name: "Why is PS-88214 on hold?" }).click();
  const chip = drawer.locator(".cp-cite").first();
  await expect(chip).toBeVisible({ timeout: 90_000 });
  await expect(drawer.locator(".cp-sources")).toContainText(/4\.2/);
  await expect(drawer.getByRole("alert")).toHaveCount(0);
});

test("/match opens an invoice instead of the empty state once anything has matched", async ({ page }) => {
  await page.goto(`/o/${ORG}/match`);
  await expect(page).toHaveURL(new RegExp(`/o/${ORG}/match/[0-9a-f-]{36}`));
  await expectScreen(page, "Three-way match");
});

test("viewer sees decision buttons disabled with Read-only access", async ({ page }) => {
  const href = await invoiceHref(page, "PS-88214");
  test.skip(!href, "hero PS-88214 is not seeded yet");
  await page.goto(matchHrefFor(href!));
  await expectScreen(page, "Three-way match");
  await expect(page.getByRole("button", { name: /^Short-pay/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve as-is" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Dispute" })).toBeDisabled();
  await expect(page.locator('[role="tooltip"]', { hasText: "Read-only access" }).first()).toBeAttached();
});

test.describe("accessibility (axe)", () => {
  const pages = [...SCREENS.map((s) => ({ url: `/o/${ORG}/${s.path}`, title: s.title })), { url: "/login", title: "Login" }];
  for (const p of pages) {
    test(`no serious/critical violations: ${p.title}`, async ({ page }, info) => {
      if (p.url === "/login") await page.context().clearCookies();
      await page.goto(p.url);
      await page.waitForLoadState("networkidle").catch(() => {});
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      await info.attach("axe-violations", { body: JSON.stringify(results.violations, null, 2), contentType: "application/json" });
      const bad = results.violations
        .filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => `${v.impact} ${v.id}: ${v.help} (${v.nodes.length}) → ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
      expect(bad, bad.join("\n")).toEqual([]);
    });
  }
});
