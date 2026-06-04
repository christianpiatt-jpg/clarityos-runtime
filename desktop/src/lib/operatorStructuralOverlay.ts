// Card 46 — Multi-run system structural overlay (Phase-1 minimal).
//
// Desktop mirror of web/src/lib/operatorStructuralOverlay.ts. Pure
// deterministic, client-side string builder producing the four-
// section multi-run structural snapshot.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

function totalChanges(
  diff: EngineV1LineageMap["diffs"][string],
): number {
  return (
    diff.appearance.added.length +
    diff.appearance.removed.length +
    diff.metadataChanges.length +
    diff.hydraulicChanges.length +
    diff.overlayChanges.length
  );
}

interface PerPrimRow {
  id:        string;
  activeIxs: number[];
  hydraulic: string[];
  critZone:  string[];
  upperBr:   string[];
}

function collectPerPrimitive(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): PerPrimRow[] {
  const rows: PerPrimRow[] = [];
  for (const id of lineageMap.primitive_ids) {
    const lineage = lineageMap.lineages[id];
    const evoRuns = evo.perPrimitive[id]?.runs ?? [];

    const activeIxs: number[] = [];
    const hydraulic: string[] = [];
    const critZone:  string[] = [];
    const upperBr:   string[] = [];

    for (const lineageRun of lineage.runs) {
      if (lineageRun.primitive === null) continue;
      activeIxs.push(lineageRun.index);
      const evoRun = evoRuns.find((r) => r.index === lineageRun.index);
      const ov     = evoRun?.overlay ?? null;
      hydraulic.push(ov?.flow_regime ?? "n/a");
      critZone.push(String(ov?.in_critical_zone ?? false));
      upperBr.push(String(ov?.on_upper_branch  ?? false));
    }

    if (activeIxs.length === 0) continue;
    rows.push({ id, activeIxs, hydraulic, critZone, upperBr });
  }
  return rows;
}

function buildPrimitiveEvolutionSection(rows: PerPrimRow[]): string {
  if (rows.length === 0) {
    return `[Primitive Structural Evolution]\n(no primitives)`;
  }
  const body = rows.map((r) => (
    `${r.id}:\n` +
    `  runs: [${r.activeIxs.join(",")}]\n` +
    `  hydraulic: ${r.hydraulic.join(" → ")}\n` +
    `  critical-zone: ${r.critZone.join(" → ")}\n` +
    `  upper-branch: ${r.upperBr.join(" → ")}`
  )).join("\n\n");
  return `[Primitive Structural Evolution]\n${body}`;
}

function buildSystemMapSection(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  let stable     = 0;
  let volatile_  = 0;
  let critPrims  = 0;
  let upperPrims = 0;
  for (const id of lineageMap.primitive_ids) {
    const changes = totalChanges(lineageMap.diffs[id]);
    if (changes === 0)  stable++;
    if (changes >= 2)   volatile_++;
    const evoRuns = evo.perPrimitive[id]?.runs ?? [];
    if (evoRuns.some((r) => r.overlay?.in_critical_zone)) critPrims++;
    if (evoRuns.some((r) => r.overlay?.on_upper_branch))  upperPrims++;
  }
  return (
    `[System Structural Map]\n` +
    `- total primitives: ${lineageMap.primitive_ids.length}\n` +
    `- stable primitives: ${stable}\n` +
    `- volatile primitives: ${volatile_}\n` +
    `- critical-zone primitives: ${critPrims}\n` +
    `- upper-branch primitives: ${upperPrims}`
  );
}

function buildCrossRunDeltasSection(
  lineageMap: EngineV1LineageMap,
  runCount:   number,
): string {
  if (runCount < 2) {
    return `[Cross-Run Structural Deltas]\n(no transitions)`;
  }
  const lines: string[] = [];
  for (let i = 0; i < runCount - 1; i++) {
    let changes = 0;
    for (const id of lineageMap.primitive_ids) {
      const d = lineageMap.diffs[id];
      if (d.appearance.added.includes(i + 1))   changes++;
      if (d.appearance.removed.includes(i + 1)) changes++;
      if (d.metadataChanges.some((c)  => c.indexFrom === i && c.indexTo === i + 1)) changes++;
      if (d.hydraulicChanges.some((c) => c.indexFrom === i && c.indexTo === i + 1)) changes++;
      if (d.overlayChanges.some((c)   => c.indexFrom === i && c.indexTo === i + 1)) changes++;
    }
    lines.push(`Run ${i} → ${i + 1}:\n  structural changes: ${changes}`);
  }
  return `[Cross-Run Structural Deltas]\n${lines.join("\n")}`;
}

function buildClustersSection(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  const stableLaminar:   string[] = [];
  const oscillators:     string[] = [];
  const critEntrants:    string[] = [];
  const upperEntrants:   string[] = [];

  for (const id of lineageMap.primitive_ids) {
    const changes = totalChanges(lineageMap.diffs[id]);
    const evoRuns = evo.perPrimitive[id]?.runs ?? [];

    const presentOverlays = evoRuns
      .map((r) => r.overlay)
      .filter((ov): ov is NonNullable<typeof ov> => ov !== null);

    if (
      changes === 0 &&
      presentOverlays.length > 0 &&
      presentOverlays.every((ov) => ov.flow_regime === "laminar")
    ) {
      stableLaminar.push(id);
    }

    let regimeFlips     = 0;
    let hasTransitional = false;
    for (let i = 0; i < evoRuns.length - 1; i++) {
      const a = evoRuns[i].overlay;
      const b = evoRuns[i + 1].overlay;
      if (a && b && a.flow_regime !== b.flow_regime) regimeFlips++;
    }
    for (const r of evoRuns) {
      if (r.overlay?.flow_regime === "transitional") { hasTransitional = true; break; }
    }
    if (regimeFlips >= 2 && hasTransitional) oscillators.push(id);

    for (let i = 0; i < evoRuns.length - 1; i++) {
      const aCrit = evoRuns[i].overlay?.in_critical_zone     ?? false;
      const bCrit = evoRuns[i + 1].overlay?.in_critical_zone ?? false;
      if (!aCrit && bCrit) { critEntrants.push(id); break; }
    }

    for (let i = 0; i < evoRuns.length - 1; i++) {
      const aUp = evoRuns[i].overlay?.on_upper_branch     ?? false;
      const bUp = evoRuns[i + 1].overlay?.on_upper_branch ?? false;
      if (!aUp && bUp) { upperEntrants.push(id); break; }
    }
  }

  return (
    `[Structural Clusters]\n` +
    `- Cluster A (stable laminar): ${listOrNone(stableLaminar)}\n` +
    `- Cluster B (transitional oscillators): ${listOrNone(oscillators)}\n` +
    `- Cluster C (critical-zone entrants): ${listOrNone(critEntrants)}\n` +
    `- Cluster D (upper-branch entrants): ${listOrNone(upperEntrants)}`
  );
}

export function buildMultiRunStructuralOverlay(
  overlay:    EngineV1SystemOverlay,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  void overlay;

  const perPrim = collectPerPrimitive(lineageMap, evo);
  const blocks: string[] = [];
  blocks.push("=== Multi-Run Structural Overlay ===");
  blocks.push(buildPrimitiveEvolutionSection(perPrim));
  blocks.push(buildSystemMapSection(lineageMap, evo));
  blocks.push(buildCrossRunDeltasSection(lineageMap, evo.perRun.length));
  blocks.push(buildClustersSection(lineageMap, evo));
  return blocks.join("\n\n");
}
