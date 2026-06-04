// Card 42 — Semantic operator summaries (Phase-1 minimal).
//
// Desktop mirror of web/src/lib/operatorSummaries.ts. Pure
// deterministic, client-side string builders that turn Card 39
// EngineV1OperatorAPI outputs into human-readable plain-text
// interpretations for the Operator Console. No backend, no styling,
// no formatting beyond newlines + dashes.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "./api";

function fmtDelta(n: number): string {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

function collectTransitionPairs(
  diff: EngineV1LineageMap["diffs"][string],
): Array<[number, number]> {
  const seen = new Set<string>();
  const out:  Array<[number, number]> = [];
  const push = (from: number, to: number) => {
    const key = `${from}->${to}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push([from, to]);
  };
  for (const to of diff.appearance.added)   push(to - 1, to);
  for (const to of diff.appearance.removed) push(to - 1, to);
  for (const c of diff.metadataChanges)  push(c.indexFrom, c.indexTo);
  for (const c of diff.hydraulicChanges) push(c.indexFrom, c.indexTo);
  for (const c of diff.overlayChanges)   push(c.indexFrom, c.indexTo);
  out.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return out;
}

export function summarizeLineageMap(map: EngineV1LineageMap): string {
  if (map.primitive_ids.length === 0) return "(no primitives)";
  const blocks: string[] = [];
  for (const id of map.primitive_ids) {
    const lineage     = map.lineages[id];
    const presentRuns = lineage.runs.filter((r) => r.primitive !== null);
    const firstSeen   = presentRuns.length > 0
      ? `run ${presentRuns[0].index}`
      : "never present";
    const lastSeen    = presentRuns.length > 0
      ? `run ${presentRuns[presentRuns.length - 1].index}`
      : "never present";

    const transitions = collectTransitionPairs(map.diffs[id]);
    const changedText = transitions.length > 0
      ? transitions.map(([from, to]) => `[${from}→${to}]`).join(", ")
      : "(none)";

    blocks.push(
      `Primitive: ${id}\n` +
      `- First seen: ${firstSeen}\n` +
      `- Last seen: ${lastSeen}\n` +
      `- Total appearances: ${presentRuns.length}\n` +
      `- Changed between runs: ${changedText}`,
    );
  }
  return blocks.join("\n\n");
}

export function summarizeHydraulicEvolution(
  evo: EngineV1HydraulicEvolutionMap,
): string {
  if (evo.perRun.length === 0) return "(no runs)";
  return evo.perRun.map((r) => (
    `Run ${r.index}:\n` +
    `- laminar: ${r.laminar}\n` +
    `- transitional: ${r.transitional}\n` +
    `- turbulent: ${r.turbulent}\n` +
    `- critical-zone primitives: ${r.critical_zone}\n` +
    `- upper-branch primitives: ${r.upper_branch}`
  )).join("\n\n");
}

function primitivesEntering(
  evo: EngineV1HydraulicEvolutionMap,
  field: "in_critical_zone" | "on_upper_branch",
): string[] {
  const out: string[] = [];
  for (const id of evo.primitive_ids) {
    const runs = evo.perPrimitive[id].runs;
    for (let i = 0; i < runs.length - 1; i++) {
      const aIn = runs[i].overlay?.[field]     ?? false;
      const bIn = runs[i + 1].overlay?.[field] ?? false;
      if (!aIn && bIn) { out.push(id); break; }
    }
  }
  return out;
}

export function summarizeSystemOverlay(overlay: EngineV1SystemOverlay): string {
  const totalPrimitives = overlay.primitive_ids.length;
  const runs            = overlay.hydraulicEvolution.perRun.length;
  const withChanges = overlay.primitive_ids.filter((id) => {
    const d = overlay.lineageMap.diffs[id];
    return (
      d.appearance.added.length   > 0 ||
      d.appearance.removed.length > 0 ||
      d.metadataChanges.length    > 0 ||
      d.hydraulicChanges.length   > 0 ||
      d.overlayChanges.length     > 0
    );
  }).length;

  const enteringCritical = primitivesEntering(
    overlay.hydraulicEvolution, "in_critical_zone",
  );
  const enteringUpper    = primitivesEntering(
    overlay.hydraulicEvolution, "on_upper_branch",
  );

  const listOrNone = (ids: string[]) =>
    ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;

  return (
    `System Overlay:\n` +
    `- total primitives: ${totalPrimitives}\n` +
    `- runs: ${runs}\n` +
    `- primitives with changes: ${withChanges}\n` +
    `- primitives entering critical zone: ${listOrNone(enteringCritical)}\n` +
    `- primitives entering upper branch: ${listOrNone(enteringUpper)}`
  );
}

export function summarizeRegression(
  diff: EngineV1SystemRegressionDiff,
): string {
  const listOrNone = (ids: string[]) =>
    ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
  return (
    `Regression (${diff.fromIndex} → ${diff.toIndex}):\n` +
    `- added primitives: ${listOrNone(diff.primitiveChanges.added)}\n` +
    `- removed primitives: ${listOrNone(diff.primitiveChanges.removed)}\n` +
    `- changed primitives: ${listOrNone(diff.primitiveChanges.changed)}\n` +
    `- hydraulic deltas:\n` +
    `  laminar: ${fmtDelta(diff.hydraulic.laminarDelta)}\n` +
    `  transitional: ${fmtDelta(diff.hydraulic.transitionalDelta)}\n` +
    `  turbulent: ${fmtDelta(diff.hydraulic.turbulentDelta)}\n` +
    `  critical-zone: ${fmtDelta(diff.hydraulic.criticalZoneDelta)}\n` +
    `  upper-branch: ${fmtDelta(diff.hydraulic.upperBranchDelta)}`
  );
}
