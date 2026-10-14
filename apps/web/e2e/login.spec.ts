import { expect, test } from "@playwright/test";
import { ORG } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("login page renders", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send sign-in link" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Explore the demo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open the demo" })).toBeEnabled();
});

test("Open the demo signs in as viewer and lands on the pipeline", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Open the demo" }).click();
  await page.waitForURL(`**/o/${ORG}/pipeline`, { timeout: 45_000 });
  await expect(page.getByRole("heading", { level: 1, name: "Pipeline" })).toBeVisible();
});
