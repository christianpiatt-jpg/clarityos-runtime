// tests/acceptance/scenarios/02_cross_surface_jump.ts
//
// Operator A onboards on web, then opens phone, then opens desktop.
// Each transition uses the same auth — no re-login between surfaces.
// All artifacts created on web must be present on phone and desktop.
// Total elapsed time from "onboarding complete on web" to "all artifacts
// observed on desktop" must be within cfg.thresholds.surface_jump_minutes.

import { AcceptanceConfig } from "../config";
import { Scenario, ScenarioResult } from "./index";
import { startTimer } from "../timer";
import { onboardWeb, verifyWebArtifacts } from "../surfaces/web";
import { verifyDesktopArtifacts } from "../surfaces/desktop";
import { verifyPhoneArtifacts } from "../surfaces/phone";

const scenario: Scenario = async (
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> => {
  const messages: string[] = [];
  let pass = true;
  const limitMs = cfg.thresholds.surface_jump_minutes * 60_000;
  const op = cfg.operators[0];
  if (!op) {
    return {
      id: "02_cross_surface_jump",
      name: "Cross-surface jump",
      pass: false,
      messages: ["no operators configured"],
    };
  }

  const t = startTimer("cross_surface_jump");

  // Step 1 — onboard on web; capture initial artifacts.
  let webArtifacts: { threads: string[]; elins: string[]; projects: string[] };
  try {
    await onboardWeb(cfg, op);
    webArtifacts = await verifyWebArtifacts(cfg, op);
  } catch (err: unknown) {
    return {
      id: "02_cross_surface_jump",
      name: "Cross-surface jump",
      pass: false,
      messages: [
        "web onboarding/verify failed: " +
        (err instanceof Error ? err.message : String(err)),
      ],
    };
  }

  if (webArtifacts.elins.length < 1) {
    pass = false;
    messages.push("web: no ELINS runs visible after onboarding");
  } else {
    messages.push(`web: ${webArtifacts.elins.length} ELINS, ${webArtifacts.threads.length} threads`);
  }

  // Step 2 — phone surface jump. The Maestro flow asserts no re-login
  // and prints visible inbound + ELINS keys to stdout for parsing.
  try {
    const phoneArtifacts = await verifyPhoneArtifacts(cfg, op);
    for (const k of webArtifacts.elins) {
      if (!phoneArtifacts.elins.includes(k)) {
        pass = false;
        messages.push(`phone: missing ELINS run ${k}`);
      }
    }
  } catch (err: unknown) {
    pass = false;
    messages.push(
      "phone verify failed: " +
      (err instanceof Error ? err.message : String(err)),
    );
  }

  // Step 3 — desktop surface jump.
  try {
    const desktopArtifacts = await verifyDesktopArtifacts(cfg, op);
    for (const k of webArtifacts.elins) {
      if (!desktopArtifacts.elins.includes(k)) {
        pass = false;
        messages.push(`desktop: missing ELINS run ${k}`);
      }
    }
    for (const tid of webArtifacts.threads) {
      if (!desktopArtifacts.threads.includes(tid)) {
        pass = false;
        messages.push(`desktop: missing thread ${tid}`);
      }
    }
  } catch (err: unknown) {
    pass = false;
    messages.push(
      "desktop verify failed: " +
      (err instanceof Error ? err.message : String(err)),
    );
  }

  const ms = t.stop();
  if (ms > limitMs) {
    pass = false;
    messages.push(`cross-surface jump took ${ms}ms (limit ${limitMs}ms)`);
  } else {
    messages.push(`cross-surface jump: ${ms}ms ok`);
  }

  return {
    id: "02_cross_surface_jump",
    name: "Cross-surface jump",
    pass,
    messages,
  };
};

export default scenario;
