import { expect, test } from "@playwright/test";
import { expectScreen, invoiceHref, matchHrefFor, signInAs } from "./helpers";

// Makes a real short-pay decision on production demo data. Opt in with E2E_ALLOW_WRITES=1.
test.skip(process.env.E2E_ALLOW_WRITES !== "1", "set E2E_ALLOW_WRITES=1 to run write tests");
test.use({ storageState: { cookies: [], origins: [] } });

test("Try as Elena: short-pay PS-88214 to contract price", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1600", "decide once per run");
  await signInAs(page, "elena");
  const href = await invoiceHref(page, "PS-88214");
  test.skip(!href, "hero PS-88214 is not seeded yet");
  await page.goto(matchHrefFor(href!));
  await expectScreen(page, "Three-way match");
  const shortPay = page.getByRole("button", { name: "Short-pay $2,759.60 and notify vendor" });
  test.skip(!(await shortPay.isVisible()), "PS-88214 is already decided today");
  await expect(shortPay).toBeEnabled();
  await shortPay.click();
  await expect(shortPay).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByText("$2,759.60").first()).toBeVisible();
  await expect(page.getByText(/Elena/).first()).toBeVisible();
});
