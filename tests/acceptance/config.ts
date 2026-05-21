// tests/acceptance/config.ts
//
// Loads tests/acceptance/config.local.json. Operator IDs / paths are
// environment-specific and must be filled before running the harness.

import * as fs from "node:fs/promises";
import * as path from "node:path";
import { randomBytes } from "node:crypto";

export interface OperatorConfig {
  id: string;
  email: string;
  handle: string;
  vault_secret: string;     // may be unused by runner (regenerated per run)
}

export interface SurfaceConfig {
  web: { os: "macos" | "windows" | "linux"; baseUrl: string };
  phone: { platform: "ios" | "android" };
  desktop: { os: "macos" | "windows"; binaryPath: string };
}

export interface ThresholdConfig {
  surface_jump_minutes: number;
  onboarding_max_minutes: number;
  stability_window_hours: number;
}

export interface AcceptanceConfig {
  backend_base_url: string;
  operators: OperatorConfig[];
  surfaces: SurfaceConfig;
  thresholds: ThresholdConfig;
}

const DEFAULT_PATH = path.resolve("tests/acceptance/config.local.json");

export async function loadConfig(
  configPath: string = DEFAULT_PATH,
): Promise<AcceptanceConfig> {
  const raw = await fs.readFile(configPath, "utf-8");
  // tolerate JSONC (// line comments) by stripping them before parse.
  const stripped = raw.replace(/^\s*\/\/.*$/gm, "");
  const cfg = JSON.parse(stripped) as AcceptanceConfig;

  // Regenerate per-run vault secrets so prior persisted secrets do not
  // leak between runs. The placeholder value in config.local.json is
  // intentionally a marker; the runner overwrites it.
  for (const op of cfg.operators) {
    op.vault_secret = randomBytes(24).toString("base64url");
  }
  return cfg;
}
