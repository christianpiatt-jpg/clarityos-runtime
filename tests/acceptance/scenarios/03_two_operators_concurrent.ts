// tests/acceptance/scenarios/03_two_operators_concurrent.ts
//
// IMPLEMENTED — was previously a placeholder; materialized in Phase 2.
//
// Two operators (op_a, op_b from cfg.operators) onboard concurrently
// on the web surface. After both complete, each operator's artifact
// set is read independently. Pass criteria:
//   1. Both onboardings complete under cfg.thresholds.onboarding_max_minutes.
//   2. The two operators' vault key sets (threads, ELINS, projects)
//      are mutually disjoint — no cross-contamination of artifacts.
//
// Use of existing surface drivers only; no new dependencies.

import { AcceptanceConfig, OperatorConfig } from "../config";
import { Scenario, ScenarioResult } from "./index";
import { startTimer } from "../timer";
import { onboardWeb, verifyWebArtifacts, WebArtifactSet } from "../surfaces/web";

interface ConcurrentLeg {
  op: OperatorConfig;
  ms: number;
  artifacts: WebArtifactSet | null;
  error: string | null;
}

async function leg(
  cfg: AcceptanceConfig,
  op: OperatorConfig,
): Promise<ConcurrentLeg> {
  const t = startTimer(`web:${op.handle}`);
  let error: string | null = null;
  let artifacts: WebArtifactSet | null = null;
  try {
    await onboardWeb(cfg, op);
    artifacts = await verifyWebArtifacts(cfg, op);
  } catch (err: unknown) {
    error = err instanceof Error ? err.message : String(err);
  }
  return { op, ms: t.stop(), artifacts, error };
}

function intersect(a: string[], b: string[]): string[] {
  const sb = new Set(b);
  return a.filter((x) => sb.has(x));
}

const scenario: Scenario = async (
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> => {
  const messages: string[] = [];
  let pass = true;

  if (cfg.operators.length < 2) {
    return {
      id: "03_two_operators_concurrent",
      name: "Two operators concurrent",
      pass: false,
      messages: [
        `need >= 2 operators in config; have ${cfg.operators.length}`,
      ],
    };
  }

  const limitMs = cfg.thresholds.onboarding_max_minutes * 60_000;
  const [op_a, op_b] = [cfg.operators[0], cfg.operators[1]];

  // Drive both onboardings concurrently. Each launches its own headless
  // Chromium, so they do not share browser state.
  const [a, b] = await Promise.all([leg(cfg, op_a), leg(cfg, op_b)]);

  // Per-operator threshold check
  for (const lg of [a, b]) {
    if (lg.error) {
      pass = false;
      messages.push(`onboarding failed for ${lg.op.handle}: ${lg.error}`);
      continue;
    }
    if (lg.ms > limitMs) {
      pass = false;
      messages.push(
        `onboarding for ${lg.op.handle} took ${lg.ms}ms (limit ${limitMs}ms)`,
      );
    } else {
      messages.push(`onboarding for ${lg.op.handle}: ${lg.ms}ms ok`);
    }
  }

  // Cross-contamination check (only if both legs produced artifact sets)
  if (a.artifacts && b.artifacts) {
    const overlap_threads = intersect(a.artifacts.threads, b.artifacts.threads);
    const overlap_elins = intersect(a.artifacts.elins, b.artifacts.elins);
    const overlap_projects = intersect(
      a.artifacts.projects,
      b.artifacts.projects,
    );

    if (overlap_threads.length > 0) {
      pass = false;
      messages.push(
        `vault isolation breach (threads): shared keys ${overlap_threads.join(", ")}`,
      );
    }
    if (overlap_elins.length > 0) {
      pass = false;
      messages.push(
        `vault isolation breach (ELINS): shared keys ${overlap_elins.join(", ")}`,
      );
    }
    if (overlap_projects.length > 0) {
      pass = false;
      messages.push(
        `vault isolation breach (projects): shared keys ${overlap_projects.join(", ")}`,
      );
    }
    if (
      overlap_threads.length === 0
      && overlap_elins.length === 0
      && overlap_projects.length === 0
    ) {
      messages.push(
        "vault isolation: confirmed disjoint sets " +
        `(${a.op.handle}: ${a.artifacts.threads.length}t/${a.artifacts.elins.length}e/${a.artifacts.projects.length}p, ` +
        `${b.op.handle}: ${b.artifacts.threads.length}t/${b.artifacts.elins.length}e/${b.artifacts.projects.length}p)`,
      );
    }
  } else {
    pass = false;
    messages.push(
      "could not run isolation check — at least one operator's artifact set was unavailable",
    );
  }

  const details = JSON.stringify({
    op_a: { handle: a.op.handle, ms: a.ms, error: a.error,
            counts: a.artifacts ? {
              threads: a.artifacts.threads.length,
              elins: a.artifacts.elins.length,
              projects: a.artifacts.projects.length,
            } : null },
    op_b: { handle: b.op.handle, ms: b.ms, error: b.error,
            counts: b.artifacts ? {
              threads: b.artifacts.threads.length,
              elins: b.artifacts.elins.length,
              projects: b.artifacts.projects.length,
            } : null },
  });

  return {
    id: "03_two_operators_concurrent",
    name: "Two operators concurrent",
    pass,
    details,
    messages,
  };
};

export default scenario;
