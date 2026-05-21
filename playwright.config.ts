// playwright.config.ts
//
// Minimal Playwright configuration for the acceptance harness. Two
// projects: web (chromium) and electron (Electron app driven by
// Playwright Electron). Test files are not collected here — the
// runner is invoked directly via ts-node from tests/acceptance/runner.ts.

import { defineConfig } from "@playwright/test";

const BASE_URL = process.env.CLARITYOS_WEB_BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "tests/acceptance",
  // We do not run under Playwright's test runner; the harness orchestrates
  // its own scenarios. testMatch is intentionally narrow to avoid pulling
  // in scenario .ts files as Playwright tests.
  testMatch: [],
  timeout: 5 * 60 * 1000,
  reporter: [
    ["json", { outputFile: "tests/acceptance/reports/playwright.json" }],
    ["list"],
  ],
  use: {
    baseURL: BASE_URL,
    headless: true,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "web", use: { browserName: "chromium" } },
    { name: "electron", use: { browserName: "chromium" } }, // electron driver invoked directly
  ],
});
