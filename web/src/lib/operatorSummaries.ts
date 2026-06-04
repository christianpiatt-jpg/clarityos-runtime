// Card 42 — Semantic operator summaries (Phase-1 minimal).
//
// Pure deterministic, client-side string builders that turn Card 39
// EngineV1OperatorAPI outputs into human-readable plain-text
// interpretations for the Operator Console. No backend, no styling,
// no formatting beyond newlines + dashes.
//
// All four exports return a single string. Empty / degenerate inputs
// return a stable "(none)" / "(no runs)" / "(no primitives)" sentinel
// rather than throwing — the console renders this verbatim under a
// <pre> / <Text> block.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "./api";

// Format a hydraulic-delta integer with an explicit sign: +N for
// positive, -N for negative (JS default), 0 for zero. Used in the
// regression hydraulic-deltas block.
function fmtDelta(n: number): string {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

// Collect every unique (indexFrom→indexTo) transition recorded in a
// Card 32 diff. Pulls from appearance.added / appearance.removed
// (which carry only the destination index — paired with source = dest-1
// because Card 32 only records pairwise-adjacent transitions) plus
// the three change-arrays. Returns sorted ascending by indexFrom.
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
  // Appearance transitions: Card 32 stores only the destination index
  // (b.index) — the source is always destination - 1.
  for (const to of diff.appearance.added)   push(to - 1, to);
  for (const to of diff.appearance.removed) push(to - 1, to);
  // Field-change transitions carry both indices explicitly.
  for (const c of diff.metadataChanges)  push(c.indexFrom, c.indexTo);
  for (const c of diff.hydraulicChanges) push(c.indexFrom, c.indexTo);
  for (const c of diff.overlayChanges)   push(c.indexFrom, c.indexTo);
  out.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return out;
}

// Lineage summary — one block per primitive_id.
//
//   Primitive: <id>
//   - First seen: run X       (or "never present")
//   - Last seen: run Y        (or "never present")
//   - Total appearances: N
//   - Changed between runs: [0→1], [1→2], ...   (or "(none)")
//
// Blocks are separated by blank lines. Empty primitive_ids → sentinel.
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

// Hydraulic evolution summary — one block per perRun entry.
//
//   Run i:
//   - laminar: N
//   - transitional: N
//   - turbulent: N
//   - critical-zone primitives: N
//   - upper-branch primitives: N
//
// Empty perRun → sentinel.
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

// Detect primitives that "enter" critical zone / upper branch at any
// point in their hydraulic evolution. Entry = a run i where the
// overlay is missing OR in_critical_zone === false, followed by a run
// i+1 where the overlay exists AND in_critical_zone === true.
// Returns ids in primitive_ids order.
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

// System overlay summary — single block.
//
//   System Overlay:
//   - total primitives: N
//   - runs: R
//   - primitives with changes: K
//   - primitives entering critical zone: [...]
//   - primitives entering upper branch: [...]
export function summarizeSystemOverlay(overlay: EngineV1SystemOverlay): string {
  const totalPrimitives = overlay.primitive_ids.length;
  const runs            = overlay.hydraulicEvolution.perRun.length;

  // A primitive "has changes" if any of its Card 32 diff arrays is
  // non-empty — same predicate the Card 41 lineage drill-in uses for
  // the [CHANGED] marker.
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

// Regression summary — single block.
//
//   Regression (X → Y):
//   - added primitives: [...]
//   - removed primitives: [...]
//   - changed primitives: [...]
//   - hydraulic deltas:
//     laminar: +2
//     transitional: -1
//     turbulent: 0
//     critical-zone: +1
//     upper-branch: 0
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
