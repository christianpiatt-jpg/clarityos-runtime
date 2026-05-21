// tests/acceptance/surfaces/web.ts
//
// Playwright web driver. Onboarding helpers + artifact-presence reads.
// Selectors and routes follow the shipped surface integration code from
// Deliverables 2/4 — adjust if the operator's local UI diverges.

import { chromium, Browser, Page } from "@playwright/test";
import { AcceptanceConfig, OperatorConfig } from "../config";

export interface WebSession {
  browser: Browser;
  page: Page;
  close: () => Promise<void>;
}

async function open(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<WebSession> {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(cfg.surfaces.web.baseUrl);
  // Login screen (existing /login route in web/src/routes/Login.tsx).
  // The harness assumes the login form has email + password inputs.
  await page.locator('input[name="email"], input[type="email"]')
    .first().fill(op.email);
  await page.locator('input[name="password"], input[type="password"]')
    .first().fill(op.vault_secret);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), {
    timeout: 30_000,
  });
  return { browser, page, close: () => browser.close() };
}

export async function onboardWeb(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<void> {
  const s = await open(cfg, op);
  try {
    // Panel 1 — identity
    await s.page.locator('input[name="handle"]').fill(op.handle);
    await s.page.locator('input[name="displayName"]').fill(op.handle);
    await s.page.getByRole("button", { name: /continue/i }).click();
    // Panel 2 — start fresh
    await s.page.getByRole("button", { name: /start fresh/i }).click();
    // Panel 3 — vault
    await s.page.locator('input[type="password"]').first().fill(op.vault_secret);
    await s.page.getByRole("button", { name: /initialize/i }).click();
    // Panel 4 — primer
    await s.page.getByRole("button", { name: /continue/i }).click();
    // Panel 5 — first run
    await s.page.locator("textarea")
      .first().fill("acceptance harness scenario text — at least 32 characters total.");
    await s.page.getByRole("button", { name: /^run$/i }).click();
    await s.page.locator('input[placeholder*="what this run"]')
      .first().fill("acceptance harness annotation");
    await s.page.getByRole("button", { name: /save annotation/i }).click();
    // Panel 6 — finish
    await s.page.getByRole("button", { name: /enter cockpit/i }).click();
    await s.page.waitForURL((u) => u.pathname === "/" || u.pathname === "/cockpit",
                            { timeout: 30_000 });
  } finally {
    await s.close();
  }
}

export interface WebArtifactSet {
  threads: string[];
  elins: string[];
  projects: string[];
}

export async function verifyWebArtifacts(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<WebArtifactSet> {
  const s = await open(cfg, op);
  try {
    const out: WebArtifactSet = { threads: [], elins: [], projects: [] };
    // Threads
    await s.page.goto(cfg.surfaces.web.baseUrl + "/threads");
    out.threads = await s.page.$$eval(
      "[data-thread-id]",
      (els) => els.map((e) => e.getAttribute("data-thread-id") ?? ""),
    ).catch(() => []);
    // ELINS
    await s.page.goto(cfg.surfaces.web.baseUrl + "/elins");
    out.elins = await s.page.$$eval(
      "[data-elins-key]",
      (els) => els.map((e) => e.getAttribute("data-elins-key") ?? ""),
    ).catch(() => []);
    // Projects (best-effort; route may be absent on this build)
    try {
      await s.page.goto(cfg.surfaces.web.baseUrl + "/projects");
      out.projects = await s.page.$$eval(
        "[data-project-id]",
        (els) => els.map((e) => e.getAttribute("data-project-id") ?? ""),
      );
    } catch {
      out.projects = [];
    }
    return out;
  } finally {
    await s.close();
  }
}
