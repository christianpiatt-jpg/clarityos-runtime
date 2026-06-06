// Card 43 — Engine V1 evolution timeline (Phase-1 minimal).
//
// Pure deterministic, client-side string builder that produces a
// human-readable temporal cross-section of the Card 36 system
// overlay: per-run state blocks (active primitives + system-wide
// hydraulic regime counts) interleaved with per-pair transition
// blocks (added / removed / changed primitives + hydraulic deltas).
//
// The `regression` argument is the Card 37 helper bound to a
// specific overlay — typically `(from, to) => api.computeSystemRegression(overlay, from, to)`.
// Passed in (rather than re-binding here) so the Operator Console
// keeps a single source-of-truth for which API instance is in use.

import type {
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "./api";

type RegressionFn = (
  fromIndex: number,
  toIndex:   number,
) => EngineV1SystemRegressionDiff;

// Same delta formatter shape used by Card 42's operatorSummaries —
// explicit "+N" for positive numbers, plain "0" for zero, default
// "-N" for negative numbers.
function fmtDelta(n: number): string {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

// Which primitive_ids have a non-null primitive at the given run
// index. Walks `overlay.lineageMap.lineages` — the same source of
// truth Card 37's regression engine uses for added/removed.
function activePrimitivesAtRun(
  overlay:  EngineV1SystemOverlay,
  runIndex: number,
): string[] {
  return overlay.primitive_ids.filter((id) => {
    const runs = overlay.lineageMap.lineages[id].runs;
    return runs[runIndex]?.primitive != null;
  });
}

// Evolution timeline output format:
//
//   === Run 0 ===
//   Primitives active: [a, b, c]
//   Hydraulic:
//   - laminar: 12
//   - transitional: 3
//   - turbulent: 1
//   - critical-zone: 2
//   - upper-branch: 0
//
//   === Run 0 → Run 1 ===
//   Added: [d]
//   Removed: [b]
//   Changed: [a, c]
//   Hydraulic deltas:
//   - laminar: +1
//   - transitional: -1
//   - turbulent: 0
//   - critical-zone: +1
//   - upper-branch: 0
//
//   === Run 1 ===
//   ...
//
// Empty perRun returns "(no runs)".
export function buildEvolutionTimeline(
  overlay:    EngineV1SystemOverlay,
  regression: RegressionFn,
): string {
  const perRun = overlay.hydraulicEvolution.perRun;
  if (perRun.length === 0) return "(no runs)";

  const blocks: string[] = [];
  for (let i = 0; i < perRun.length; i++) {
    const run    = perRun[i];
    const active = activePrimitivesAtRun(overlay, i);

    blocks.push(
      `=== Run ${i} ===\n` +
      `Primitives active: ${listOrNone(active)}\n` +
      `Hydraulic:\n` +
      `- laminar: ${run.laminar}\n` +
      `- transitional: ${run.transitional}\n` +
      `- turbulent: ${run.turbulent}\n` +
      `- critical-zone: ${run.critical_zone}\n` +
      `- upper-branch: ${run.upper_branch}`,
    );

    // Transition to the next run (only between adjacent pairs — the
    // regression engine's `changed` set is only populated for
    // adjacent indices anyway).
    if (i + 1 < perRun.length) {
      const diff = regression(i, i + 1);
      blocks.push(
        `=== Run ${i} → Run ${i + 1} ===\n` +
        `Added: ${listOrNone(diff.primitiveChanges.added)}\n` +
        `Removed: ${listOrNone(diff.primitiveChanges.removed)}\n` +
        `Changed: ${listOrNone(diff.primitiveChanges.changed)}\n` +
        `Hydraulic deltas:\n` +
        `- laminar: ${fmtDelta(diff.hydraulic.laminarDelta)}\n` +
        `- transitional: ${fmtDelta(diff.hydraulic.transitionalDelta)}\n` +
        `- turbulent: ${fmtDelta(diff.hydraulic.turbulentDelta)}\n` +
        `- critical-zone: ${fmtDelta(diff.hydraulic.criticalZoneDelta)}\n` +
        `- upper-branch: ${fmtDelta(diff.hydraulic.upperBranchDelta)}`,
      );
    }
  }

  return blocks.join("\n\n");
}
