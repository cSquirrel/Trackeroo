import { defineConfig, devices } from "@playwright/test";

// The stack under test is the full Docker image (FastAPI serving the built
// Svelte frontend same-origin). global-setup boots it fresh each run so the
// seeded database is deterministic; global-teardown tears it down.
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:8001";

export default defineConfig({
  testDir: "./tests",
  // One backend, one SQLite DB — tests mutate shared server state, so they must
  // run serially. Each test resets to seed state in beforeEach (helpers/reset).
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"]],
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // Wide enough that all five default columns fit without horizontal
      // scroll, so drag targets on the far-right (Done) column are reachable.
      use: { ...devices["Desktop Chrome"], viewport: { width: 1680, height: 900 } },
    },
  ],
});
