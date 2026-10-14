import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  // Against a deployed site keep the load (and demo sign-ins, which are rate limited) modest.
  workers: process.env.E2E_BASE_URL ? 3 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/, use: { ...devices["Desktop Chrome"] } },
    {
      name: "desktop-1600",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } },
      dependencies: ["setup"],
    },
    {
      name: "desktop-1280",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
      dependencies: ["setup"],
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: "pnpm start", url: baseURL, reuseExistingServer: true, timeout: 120_000 },
});
