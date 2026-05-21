// tests/acceptance/surfaces/desktop.ts
//
// Playwright Electron driver. Launches the desktop binary configured
// in cfg.surfaces.desktop.binaryPath, drives onboarding, and reads
// artifacts. Markup is assumed identical to web (per Deliverable 6
// desktop onboarding mirrors web routes structurally), so the helpers
// reuse the same selectors.

import { _electron as electron, ElectronApplication, Page } from "@playwright/test";
import { AcceptanceConfig, OperatorConfig } from "../config";

export interface DesktopSession {
  app: ElectronApplication;
  page: Page;
  close: () => Promise<void>;
}

async function open(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<DesktopSession> {
  const app = await electron.launch({
    executablePath: cfg.surfaces.desktop.binaryPath,
  });
  const page = await app.firstWindow();
  // The desktop client also has a login flow per v50/v51. If a session
  // is already cached, the page will skip login — handle both.
  const hasLogin = await page.locator('input[name="email"], input[type="email"]')
    .first().isVisible().catch(() => false);
  if (hasLogin) {
    await page.locator('input[name="email"], input[type="email"]')
      .first().fill(op.email);
    await page.locator('input[name="password"], input[type="password"]')
      .first().fill(op.vault_secret);
    await page.locator('button[type="submit"]').first().click();
  }
  return { app, page, close: () => app.close() };
}

export async function onboardDesktop(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<void> {
  const s = await open(cfg, op);
  try {
    // Markup mirrors web onboarding; same selectors apply.
    await s.page.locator('input[name="handle"]').fill(op.handle);
    await s.page.locator('input[name="displayName"]').fill(op.handle);
    await s.page.getByRole("button", { name: /continue/i }).click();
    await s.page.getByRole("button", { name: /start fresh/i }).click();
    await s.page.locator('input[type="password"]').first().fill(op.vault_secret);
    await s.page.getByRole("button", { name: /initialize/i }).click();
    await s.page.getByRole("button", { name: /continue/i }).click();
    await s.page.locator("textarea")
      .first().fill("acceptance harness scenario text — at least 32 characters total.");
    await s.page.getByRole("button", { name: /^run$/i }).click();
    await s.page.locator('input[placeholder*="what this run"]')
      .first().fill("acceptance harness annotation");
    await s.page.getByRole("button", { name: /save annotation/i }).click();
    await s.page.getByRole("button", { name: /enter cockpit/i }).click();
  } finally {
    await s.close();
  }
}

export interface DesktopArtifactSet {
  threads: string[];
  elins: string[];
  projects: string[];
}

export async function verifyDesktopArtifacts(
  cfg: AcceptanceConfig, op: OperatorConfig,
): Promise<DesktopArtifactSet> {
  const s = await open(cfg, op);
  try {
    const out: DesktopArtifactSet = { threads: [], elins: [], projects: [] };
    // Desktop uses HashRouter — navigate via location.hash.
    await s.page.evaluate(() => { window.location.hash = "#/threads"; });
    out.threads = await s.page.$$eval(
      "[data-thread-id]",
      (els) => els.map((e) => e.getAttribute("data-thread-id") ?? ""),
    ).catch(() => []);
    await s.page.evaluate(() => { window.location.hash = "#/elins"; });
    out.elins = await s.page.$$eval(
      "[data-elins-key]",
      (els) => els.map((e) => e.getAttribute("data-elins-key") ?? ""),
    ).catch(() => []);
    try {
      await s.page.evaluate(() => { window.location.hash = "#/projects"; });
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
