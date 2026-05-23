import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir:   "./tests/e2e",
  fullyParallel: false,
  retries:   process.env.CI ? 2 : 0,
  timeout:   30_000,

  use: {
    baseURL:    process.env.E2E_BASE_URL ?? "http://localhost:3002",
    // Pass auth cookies automatically across tests
    storageState: "tests/e2e/.auth/user.json",
    trace:     "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    // Setup project: authenticates once, saves cookie state
    {
      name:  "setup",
      testMatch: "**/auth.setup.ts",
      use: { storageState: undefined },
    },
    // Main test suite runs after setup
    {
      name:    "chromium",
      use:     { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],

  // Start dev server automatically when running locally
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url:     "http://localhost:3002",
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
