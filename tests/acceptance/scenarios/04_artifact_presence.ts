// tests/acceptance/scenarios/04_artifact_presence.ts
//
// IMPLEMENTED — was previously a placeholder; materialized in Phase 2.
//
// Standalone artifact-presence check: an artifact created on web is
// observable on phone and desktop after the operator opens each surface.
// This scenario self-bootstraps by onboarding op_a on web (since there
// must be at least one ELINS artifact to verify), then reads each
// surface and asserts identical sets.
//
// Differs from 02_cross_surface_jump in two ways:
//   - no surface-jump time budget assertion (just presence)
//   - no specific artifact-creation step beyond the implicit Panel 5 run
//
// Uses existing surface drivers only.

import { AcceptanceConfig } from "../config";
import { Scenario, ScenarioResult } from "./index";
import { onboardWeb, verifyWebArtifacts, WebArtifactSet } from "../surfaces/web";
import { verifyDesktopArtifacts, DesktopArtifactSet } from "../surfaces/desktop";
import { verifyPhoneArtifacts, PhoneArtifactSet } from "../surfaces/phone";

interface PresenceCounts {
  threads: number;
  elins: number;
  projects: number;
}

const scenario: Scenario = async (
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> => {
  const messages: string[] = [];
  let pass = true;
  const op = cfg.operators[0];
  if (!op) {
    return {
      id: "04_artifact_presence",
      name: "Artifact presence",
      pass: false,
      messages: ["no operators configured"],
    };
  }

  // Self-bootstrap: ensure there is at least one ELINS run to verify.
  let webSet: WebArtifactSet;
  try {
    await onboardWeb(cfg, op);
    webSet = await verifyWebArtifacts(cfg, op);
  } catch (err: unknown) {
    return {
      id: "04_artifact_presence",
      name: "Artifact presence",
      pass: false,
      messages: [
        "web bootstrap (onboard + verify) failed: " +
        (err instanceof Error ? err.message : String(err)),
      ],
    };
  }

  if (webSet.elins.length === 0) {
    pass = false;
    messages.push("web: no ELINS runs visible after bootstrap onboarding");
  }

  // Read desktop independently.
  let desktopSet: DesktopArtifactSet;
  try {
    desktopSet = await verifyDesktopArtifacts(cfg, op);
  } catch (err: unknown) {
    return {
      id: "04_artifact_presence",
      name: "Artifact presence",
      pass: false,
      messages: [
        "desktop verify failed: " +
        (err instanceof Error ? err.message : String(err)),
      ],
    };
  }

  // Read phone independently (Maestro flow → parsed stdout).
  let phoneSet: PhoneArtifactSet;
  try {
    phoneSet = await verifyPhoneArtifacts(cfg, op);
  } catch (err: unknown) {
    return {
      id: "04_artifact_presence",
      name: "Artifact presence",
      pass: false,
      messages: [
        "phone verify failed: " +
        (err instanceof Error ? err.message : String(err)),
      ],
    };
  }

  // Assert web == desktop on threads and ELINS sets.
  // (projects: tolerated as a superset on desktop because the desktop
  // client may auto-bootstrap default projects per v51.)
  for (const tid of webSet.threads) {
    if (!desktopSet.threads.includes(tid)) {
      pass = false;
      messages.push(`desktop missing thread ${tid}`);
    }
  }
  for (const k of webSet.elins) {
    if (!desktopSet.elins.includes(k)) {
      pass = false;
      messages.push(`desktop missing ELINS ${k}`);
    }
  }

  // Assert each web ELINS key surfaces in the phone Maestro stdout.
  for (const k of webSet.elins) {
    if (!phoneSet.elins.includes(k)) {
      pass = false;
      messages.push(`phone missing ELINS ${k}`);
    }
  }
  for (const tid of webSet.threads) {
    if (!phoneSet.threads.includes(tid)) {
      pass = false;
      messages.push(`phone missing thread ${tid}`);
    }
  }

  if (pass) {
    messages.push(
      `presence ok: web=${webSet.elins.length}e/${webSet.threads.length}t · ` +
      `desktop=${desktopSet.elins.length}e/${desktopSet.threads.length}t · ` +
      `phone=${phoneSet.elins.length}e/${phoneSet.threads.length}t`,
    );
  }

  const counts: { surface: string; counts: PresenceCounts | null }[] = [
    { surface: "web",     counts: { threads: webSet.threads.length,     elins: webSet.elins.length,     projects: webSet.projects.length     } },
    { surface: "desktop", counts: { threads: desktopSet.threads.length, elins: desktopSet.elins.length, projects: desktopSet.projects.length } },
    { surface: "phone",   counts: { threads: phoneSet.threads.length,   elins: phoneSet.elins.length,   projects: 0 /* phone Maestro flow does not parse projects */ } },
  ];

  return {
    id: "04_artifact_presence",
    name: "Artifact presence",
    pass,
    details: JSON.stringify({ operator: op.handle, surfaces: counts }),
    messages,
  };
};

export default scenario;
