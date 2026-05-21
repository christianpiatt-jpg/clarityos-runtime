// tests/acceptance/scenarios/01_onboarding_per_surface.ts
//
// For each operator and each surface (web, phone, desktop), drive
// onboarding end-to-end and time it. Pass iff every surface completes
// under cfg.thresholds.onboarding_max_minutes for every operator.

import { AcceptanceConfig } from "../config";
import { ScenarioResult, Scenario } from "./index";
import { startTimer } from "../timer";
import { onboardWeb } from "../surfaces/web";
import { onboardDesktop } from "../surfaces/desktop";
import { onboardPhone } from "../surfaces/phone";

const scenario: Scenario = async (
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> => {
  const messages: string[] = [];
  let pass = true;
  const limitMs = cfg.thresholds.onboarding_max_minutes * 60_000;

  for (const op of cfg.operators) {
    // WEB
    {
      const t = startTimer(`web:${op.handle}`);
      try {
        await onboardWeb(cfg, op);
      } catch (err: unknown) {
        pass = false;
        messages.push(
          `web onboarding failed for ${op.handle}: ` +
          (err instanceof Error ? err.message : String(err)),
        );
        continue;
      }
      const ms = t.stop();
      if (ms > limitMs) {
        pass = false;
        messages.push(
          `web onboarding for ${op.handle} took ${ms}ms (limit ${limitMs}ms)`,
        );
      } else {
        messages.push(`web onboarding for ${op.handle}: ${ms}ms ok`);
      }
    }

    // PHONE
    {
      const t = startTimer(`phone:${op.handle}`);
      try {
        await onboardPhone(cfg, op);
      } catch (err: unknown) {
        pass = false;
        messages.push(
          `phone onboarding failed for ${op.handle}: ` +
          (err instanceof Error ? err.message : String(err)),
        );
        continue;
      }
      const ms = t.stop();
      if (ms > limitMs) {
        pass = false;
        messages.push(
          `phone onboarding for ${op.handle} took ${ms}ms (limit ${limitMs}ms)`,
        );
      } else {
        messages.push(`phone onboarding for ${op.handle}: ${ms}ms ok`);
      }
    }

    // DESKTOP
    {
      const t = startTimer(`desktop:${op.handle}`);
      try {
        await onboardDesktop(cfg, op);
      } catch (err: unknown) {
        pass = false;
        messages.push(
          `desktop onboarding failed for ${op.handle}: ` +
          (err instanceof Error ? err.message : String(err)),
        );
        continue;
      }
      const ms = t.stop();
      if (ms > limitMs) {
        pass = false;
        messages.push(
          `desktop onboarding for ${op.handle} took ${ms}ms (limit ${limitMs}ms)`,
        );
      } else {
        messages.push(`desktop onboarding for ${op.handle}: ${ms}ms ok`);
      }
    }
  }

  return {
    id: "01_onboarding_per_surface",
    name: "Onboarding per surface",
    pass,
    messages,
  };
};

export default scenario;
