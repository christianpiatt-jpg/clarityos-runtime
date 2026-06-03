// Card 45 — Structural diagnostics (Phase-1 minimal).
//
// Pure deterministic, client-side string builder that produces an
// operator-grade structural-analysis report for the entire loaded
// Engine V1 evolution. Reads from the Card 36 system overlay, Card 32
// per-primitive diffs, and Card 35 hydraulic evolution map; emits a
// single human-readable plain-text report.
//
// Five sections:
//   [System Stability]      stability / volatility / drift scalars
//   [Primitive Churn]       totals + per-id high-churn list
//   [Hydraulic Volatility]  regime / zone transition counts
//   [Structural Anomalies]  metadata / oscillation / drift sets
//   [System-Level Outliers] per-run flags (critical-zone + churn)
//
// Phase-1 heuristics are deliberately simple: scalar scores are
// fractions in [0, 1] formatted to 2 decimals; outliers use a
// `value > mean × 1.5` rule so the report stays deterministic across
// surfaces without pulling in a stats library.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

// 2-decimal stable formatter — JS Number.toFixed already gives the
// "0.82" / "0.14" / "0.03" shapes the spec example uses.
function formatScore(n: number): string {
  return n.toFixed(2);
}

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

function mean(xs: number[]): number {
  if (xs.length === 0) return 0;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

// Stability = 1 − (observed changes / maximum possible changes), where
// "maximum possible" assumes every primitive could change in every
// metadata / hydraulic / overlay slot for every adjacent run pair.
// Zero primitives or single-run contexts → 1.0 (nothing to destabilise).
function computeStabilityScore(
  lineageMap: EngineV1LineageMap,
  runCount:   number,
): number {
  const n     = lineageMap.primitive_ids.length;
  const pairs = runCount - 1;
  if (n === 0 || pairs <= 0) return 1.0;
  let observed = 0;
  for (const id of lineageMap.primitive_ids) {
    const d = lineageMap.diffs[id];
    observed += d.metadataChanges.length;
    observed += d.hydraulicChanges.length;
    observed += d.overlayChanges.length;
  }
  const possible = n * pairs * 3;
  return 1 - observed / possible;
}

// Volatility = fraction of adjacent overlay pairs whose flow_regime
// flipped. Counts only pairs where BOTH sides have an overlay (a
// primitive that's absent on one side isn't "volatile", it's missing).
function computeVolatilityIndex(
  evo: EngineV1HydraulicEvolutionMap,
): number {
  let flips = 0;
  let pairs = 0;
  for (const id of evo.primitive_ids) {
    const runs = evo.perPrimitive[id].runs;
    for (let i = 0; i < runs.length - 1; i++) {
      const a = runs[i].overlay;
      const b = runs[i + 1].overlay;
      if (a && b) {
        pairs++;
        if (a.flow_regime !== b.flow_regime) flips++;
      }
    }
  }
  if (pairs === 0) return 0;
  return flips / pairs;
}

// Drift = fraction of primitives whose FIRST overlay regime differs
// from their LAST overlay regime. Captures cumulative one-way shift
// even when intermediate runs were stable.
function computeDriftIndex(
  evo: EngineV1HydraulicEvolutionMap,
): number {
  const n = evo.primitive_ids.length;
  if (n === 0) return 0;
  let drifted = 0;
  for (const id of evo.primitive_ids) {
    const runs        = evo.perPrimitive[id].runs;
    const firstOv     = runs.find((r) => r.overlay !== null)?.overlay ?? null;
    const reversed    = runs.slice().reverse();
    const lastOv      = reversed.find((r) => r.overlay !== null)?.overlay ?? null;
    if (firstOv && lastOv && firstOv.flow_regime !== lastOv.flow_regime) drifted++;
  }
  return drifted / n;
}

interface ChurnReport {
  total:     number;
  added:     number;
  removed:   number;
  highChurn: string[];
}

// Churn report: aggregate appearance counts + per-id total-change
// counts. A primitive is "high-churn" if its summed change count
// (appearances + field changes) is ≥ 2 — pragmatic Phase-1 cutoff.
function computePrimitiveChurn(lineageMap: EngineV1LineageMap): ChurnReport {
  let added   = 0;
  let removed = 0;
  const highChurn: string[] = [];
  for (const id of lineageMap.primitive_ids) {
    const d = lineageMap.diffs[id];
    added   += d.appearance.added.length;
    removed += d.appearance.removed.length;
    const total =
      d.appearance.added.length +
      d.appearance.removed.length +
      d.metadataChanges.length +
      d.hydraulicChanges.length +
      d.overlayChanges.length;
    if (total >= 2) highChurn.push(id);
  }
  return {
    total: lineageMap.primitive_ids.length,
    added,
    removed,
    highChurn,
  };
}

interface HydraulicVolatility {
  laminarToTrans: number;
  transToTurb:    number;
  critEntries:    number;
  upperEntries:   number;
}

// Hydraulic volatility counts (per spec): specifically the two
// "escalating" regime transitions plus zone entries (false → true).
function computeHydraulicVolatility(
  evo: EngineV1HydraulicEvolutionMap,
): HydraulicVolatility {
  let laminarToTrans = 0;
  let transToTurb    = 0;
  let critEntries    = 0;
  let upperEntries   = 0;
  for (const id of evo.primitive_ids) {
    const runs = evo.perPrimitive[id].runs;
    for (let i = 0; i < runs.length - 1; i++) {
      const a = runs[i].overlay;
      const b = runs[i + 1].overlay;
      if (a && b) {
        if (a.flow_regime === "laminar" && b.flow_regime === "transitional") laminarToTrans++;
        if (a.flow_regime === "transitional" && b.flow_regime === "turbulent") transToTurb++;
      }
      const aCrit  = a?.in_critical_zone ?? false;
      const bCrit  = b?.in_critical_zone ?? false;
      if (!aCrit  && bCrit)  critEntries++;
      const aUp    = a?.on_upper_branch  ?? false;
      const bUp    = b?.on_upper_branch  ?? false;
      if (!aUp    && bUp)    upperEntries++;
    }
  }
  return { laminarToTrans, transToTurb, critEntries, upperEntries };
}

interface AnomalyReport {
  inconsistent: string[];   // metadata flipped at least once
  oscillating:  string[];   // regime changed ≥ 2 times
  drift:        string[];   // first vs last regime differ
}

function detectAnomalies(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): AnomalyReport {
  const inconsistent = lineageMap.primitive_ids.filter(
    (id) => lineageMap.diffs[id].metadataChanges.length > 0,
  );
  const oscillating  = evo.primitive_ids.filter((id) => {
    const runs = evo.perPrimitive[id].runs;
    let transitions = 0;
    for (let i = 0; i < runs.length - 1; i++) {
      const a = runs[i].overlay;
      const b = runs[i + 1].overlay;
      if (a && b && a.flow_regime !== b.flow_regime) transitions++;
    }
    return transitions >= 2;
  });
  const drift = evo.primitive_ids.filter((id) => {
    const runs     = evo.perPrimitive[id].runs;
    const firstOv  = runs.find((r) => r.overlay !== null)?.overlay ?? null;
    const lastOv   = runs.slice().reverse().find((r) => r.overlay !== null)?.overlay ?? null;
    return Boolean(firstOv && lastOv && firstOv.flow_regime !== lastOv.flow_regime);
  });
  return { inconsistent, oscillating, drift };
}

// Per-transition churn (appearance + field) so we can compare each
// transition's churn to the mean. Returned vector is indexed by the
// destination run (so index 0 corresponds to the 0→1 transition).
function churnPerTransition(
  lineageMap: EngineV1LineageMap,
  runCount:   number,
): number[] {
  const out: number[] = [];
  for (let i = 0; i < runCount - 1; i++) {
    let churn = 0;
    for (const id of lineageMap.primitive_ids) {
      const d = lineageMap.diffs[id];
      if (d.appearance.added.includes(i + 1))   churn++;
      if (d.appearance.removed.includes(i + 1)) churn++;
      if (d.metadataChanges.some((c)  => c.indexFrom === i && c.indexTo === i + 1)) churn++;
      if (d.hydraulicChanges.some((c) => c.indexFrom === i && c.indexTo === i + 1)) churn++;
      if (d.overlayChanges.some((c)   => c.indexFrom === i && c.indexTo === i + 1)) churn++;
    }
    out.push(churn);
  }
  return out;
}

// Outliers — runs that exceed `mean × 1.5` on a given metric. The
// strictly-greater-than-zero guard avoids flagging trivial all-zero
// systems where every run technically ≥ the (zero) mean.
function detectOutliers(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string[] {
  const perRun = evo.perRun;
  if (perRun.length === 0) return [];
  const out: string[] = [];

  // Critical-zone outliers.
  const critValues = perRun.map((r) => r.critical_zone);
  const meanCrit   = mean(critValues);
  for (let i = 0; i < perRun.length; i++) {
    if (perRun[i].critical_zone > meanCrit * 1.5 && perRun[i].critical_zone > 0) {
      out.push(`run ${i}: unusually high critical-zone pressure`);
    }
  }

  // Churn outliers — flagged on the destination run of each transition.
  const churns    = churnPerTransition(lineageMap, perRun.length);
  const meanChurn = mean(churns);
  for (let i = 0; i < churns.length; i++) {
    if (churns[i] > meanChurn * 1.5 && churns[i] > 0) {
      out.push(`run ${i + 1}: anomalous primitive churn`);
    }
  }

  return out;
}

export function buildStructuralDiagnostics(
  overlay:    EngineV1SystemOverlay,
  timeline:   string,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): string {
  // `timeline` is part of the signature for future-proofing but is
  // not consumed in Phase-1: every report metric comes from the
  // structured Card 36/35/32 inputs rather than from string-parsing.
  void timeline;

  const runCount    = evo.perRun.length;
  const stability   = computeStabilityScore(lineageMap, runCount);
  const volatility  = computeVolatilityIndex(evo);
  const drift       = computeDriftIndex(evo);
  const churn       = computePrimitiveChurn(lineageMap);
  const hydraulicVol = computeHydraulicVolatility(evo);
  const anomalies   = detectAnomalies(lineageMap, evo);
  const outliers    = detectOutliers(lineageMap, evo);

  // Defensive: if the overlay's primitive list happens to disagree
  // with the lineage map's, the report still emits — operators want
  // the report even when the input is partial.
  void overlay;

  const blocks: string[] = [];
  blocks.push("=== Structural Diagnostics ===");

  blocks.push(
    `[System Stability]\n` +
    `- stability score: ${formatScore(stability)}\n` +
    `- volatility index: ${formatScore(volatility)}\n` +
    `- drift index: ${formatScore(drift)}`,
  );

  blocks.push(
    `[Primitive Churn]\n` +
    `- total primitives: ${churn.total}\n` +
    `- added across runs: ${churn.added}\n` +
    `- removed across runs: ${churn.removed}\n` +
    `- high-churn primitives: ${listOrNone(churn.highChurn)}`,
  );

  blocks.push(
    `[Hydraulic Volatility]\n` +
    `- laminar → transitional transitions: ${hydraulicVol.laminarToTrans}\n` +
    `- transitional → turbulent transitions: ${hydraulicVol.transToTurb}\n` +
    `- critical-zone entries: ${hydraulicVol.critEntries}\n` +
    `- upper-branch entries: ${hydraulicVol.upperEntries}`,
  );

  blocks.push(
    `[Structural Anomalies]\n` +
    `- primitives with inconsistent metadata: ${listOrNone(anomalies.inconsistent)}\n` +
    `- primitives with oscillating hydraulic regimes: ${listOrNone(anomalies.oscillating)}\n` +
    `- primitives with long-range drift: ${listOrNone(anomalies.drift)}`,
  );

  const outliersBody = outliers.length === 0
    ? "(none)"
    : outliers.map((line) => `- ${line}`).join("\n");
  blocks.push(`[System-Level Outliers]\n${outliersBody}`);

  return blocks.join("\n\n");
}
