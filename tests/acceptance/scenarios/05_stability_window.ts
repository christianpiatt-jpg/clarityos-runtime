// tests/acceptance/scenarios/05_stability_window.ts
//
// IMPLEMENTED — was previously a placeholder; materialized in Phase 2.
//
// Short-loop stability check: re-runs scenario 04 (artifact presence)
// three times in sequence and asserts:
//   1. All three iterations pass independently.
//   2. Per-iteration artifact counts are non-decreasing — accumulated
//      state from earlier iterations remains visible (no stale-vault
//      eviction), and no cross-iteration leakage manifests as missing
//      artifacts between runs.
//   3. Timing variance is bounded — max iteration time <= 2x mean
//      iteration time (catches progressive slowdown / leak-induced
//      degradation).
//
// Note: the polish-plan §8 "72h stability window" is a separate,
// passive check against the incident store — it is intentionally NOT
// the same artifact as this short-loop scenario. The dashboard's
// stability_window_pass field reflects that 72h passive window;
// scenario 05 here is the active short-loop confirmation.

import { AcceptanceConfig } from "../config";
import { Scenario, ScenarioResult } from "./index";
import { startTimer } from "../timer";
import scenario_04 from "./04_artifact_presence";

const ITERATIONS = 3;
const MAX_TO_MEAN_RATIO = 2.0;

interface IterationRecord {
  index: number;
  pass: boolean;
  duration_ms: number;
  details_parsed: { surfaces?: { surface: string; counts: { elins: number } | null }[] } | null;
  messages?: string[];
}

function parseDetails(s: string | undefined): IterationRecord["details_parsed"] {
  if (!s) return null;
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function elinsCountFromIteration(rec: IterationRecord): number {
  const surfaces = rec.details_parsed?.surfaces ?? [];
  // Use web surface as the canonical count for monotonicity check.
  const web = surfaces.find((s) => s.surface === "web");
  return web?.counts?.elins ?? 0;
}

const scenario: Scenario = async (
  cfg: AcceptanceConfig,
): Promise<ScenarioResult> => {
  const messages: string[] = [];
  let pass = true;
  const records: IterationRecord[] = [];

  for (let i = 1; i <= ITERATIONS; i++) {
    const t = startTimer(`stability_iter_${i}`);
    let inner: ScenarioResult | null = null;
    try {
      inner = await scenario_04(cfg);
    } catch (err: unknown) {
      pass = false;
      messages.push(
        `iteration ${i} threw: ` +
        (err instanceof Error ? err.message : String(err)),
      );
      records.push({
        index: i,
        pass: false,
        duration_ms: t.stop(),
        details_parsed: null,
        messages: [
          err instanceof Error ? err.message : String(err),
        ],
      });
      continue;
    }
    const dur = t.stop();
    const rec: IterationRecord = {
      index: i,
      pass: inner.pass,
      duration_ms: dur,
      details_parsed: parseDetails(inner.details),
      messages: inner.messages,
    };
    records.push(rec);
    if (!inner.pass) {
      pass = false;
      messages.push(
        `iteration ${i} failed: ${(inner.messages ?? []).join("; ").slice(0, 240)}`,
      );
    } else {
      messages.push(`iteration ${i}: ${dur}ms ok`);
    }
  }

  // Monotonicity: accumulated artifact count must not drop between
  // iterations. (It can stay equal — the bootstrap onboards a fresh
  // op_a once and subsequent iterations may not add new artifacts; it
  // can grow — onboardings add ELINS runs. It must NOT shrink.)
  const counts = records.map(elinsCountFromIteration);
  for (let i = 1; i < counts.length; i++) {
    if (counts[i] < counts[i - 1]) {
      pass = false;
      messages.push(
        `monotonicity violated: iteration ${i + 1} ELINS count ${counts[i]} ` +
        `< iteration ${i} count ${counts[i - 1]} (state leakage suspected)`,
      );
    }
  }

  // Timing variance bound: max <= 2x mean.
  const durations = records.filter((r) => r.pass).map((r) => r.duration_ms);
  if (durations.length === ITERATIONS) {
    const mean = durations.reduce((a, b) => a + b, 0) / durations.length;
    const max = Math.max(...durations);
    if (mean > 0 && max / mean > MAX_TO_MEAN_RATIO) {
      pass = false;
      messages.push(
        `timing variance: max ${max}ms > ${MAX_TO_MEAN_RATIO}× mean (${mean.toFixed(0)}ms) ` +
        `— possible progressive slowdown`,
      );
    } else if (mean > 0) {
      messages.push(
        `timing variance ok: max=${max}ms mean=${mean.toFixed(0)}ms ratio=${(max / mean).toFixed(2)}`,
      );
    }
  }

  // Stability metrics block — exposed in details for the dashboard.
  const stats = (() => {
    const ds = records.map((r) => r.duration_ms);
    if (ds.length === 0) return null;
    const sum = ds.reduce((a, b) => a + b, 0);
    const mean = sum / ds.length;
    const variance = ds.reduce((a, b) => a + (b - mean) ** 2, 0) / ds.length;
    return {
      iterations: records.length,
      pass_count: records.filter((r) => r.pass).length,
      mean_ms: mean,
      max_ms: Math.max(...ds),
      min_ms: Math.min(...ds),
      stddev_ms: Math.sqrt(variance),
    };
  })();

  const details = JSON.stringify({
    iterations: records.map((r) => ({
      index: r.index,
      pass: r.pass,
      duration_ms: r.duration_ms,
      web_elins_count: elinsCountFromIteration(r),
    })),
    stats,
    monotonicity_pass: counts.every(
      (c, i) => i === 0 || c >= counts[i - 1],
    ),
  });

  return {
    id: "05_stability_window",
    name: "Stability window",
    pass,
    details,
    messages,
  };
};

export default scenario;
