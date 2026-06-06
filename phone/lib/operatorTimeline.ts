// Card 43 — Engine V1 evolution timeline (Phase-1 minimal).
//
// Phone mirror of web/src/lib/operatorTimeline.ts. Pure deterministic,
// client-side string builder producing a human-readable temporal
// cross-section of the Card 36 system overlay.

import type {
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "./api";

type RegressionFn = (
  fromIndex: number,
  toIndex:   number,
) => EngineV1SystemRegressionDiff;

function fmtDelta(n: number): string {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

function activePrimitivesAtRun(
  overlay:  EngineV1SystemOverlay,
  runIndex: number,
): string[] {
  return overlay.primitive_ids.filter((id) => {
    const runs = overlay.lineageMap.lineages[id].runs;
    return runs[runIndex]?.primitive != null;
  });
}

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
