// Card 49 — Structural bands (Phase-1 minimal).
//
// Phone mirror of web/src/lib/operatorStructuralBands.ts. Pure
// deterministic, client-side string builder producing the three-
// section banded structural signature.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

const LEGEND =
  "Legend:\n" +
  "- = low structural pressure\n" +
  "= = medium pressure\n" +
  "# = high pressure\n" +
  "! = volatility band\n" +
  "~ = drift band\n" +
  "C = critical-zone band\n" +
  "B = upper-branch band";

function listOrNone(ids: string[]): string {
  return ids.length === 0 ? "(none)" : `[${ids.join(", ")}]`;
}

function regimeIntensity(regime: string | undefined): number {
  switch (regime) {
    case "transitional": return 1;
    case "turbulent":    return 2;
    default:             return 0;
  }
}

function bandSymbol(sum: number): string {
  if (sum <= 10) return "--";
  if (sum <= 20) return "-=";
  if (sum <= 40) return "==";
  if (sum <= 60) return "##";
  return "###";
}

function pressureLevel(sum: number): string {
  if (sum <= 10) return "low";
  if (sum <= 40) return "medium";
  return "high";
}

interface RunState {
  sum:         number;
  hasCrit:     boolean;
  hasUpper:    boolean;
  hasVolatile: boolean;
  hasDrift:    boolean;
}

interface PrimitiveFlags {
  drift:      Record<string, boolean>;
  lastActive: Record<string, number>;
}

function derivePrimitiveFlags(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): PrimitiveFlags {
  const drift:      Record<string, boolean> = {};
  const lastActive: Record<string, number>  = {};
  for (const id of lineageMap.primitive_ids) {
    const lineageRuns = lineageMap.lineages[id].runs;
    const evoRuns     = evo.perPrimitive[id]?.runs ?? [];
    const activeIxs   = lineageRuns
      .filter((r) => r.primitive !== null)
      .map((r)    => r.index);

    let isDrift = false;
    if (activeIxs.length >= 3) {
      const overlaysPresent = evoRuns.filter((r) => r.overlay !== null);
      if (overlaysPresent.length >= 1) {
        const first = overlaysPresent[0].overlay?.flow_regime;
        const last  = overlaysPresent[overlaysPresent.length - 1].overlay?.flow_regime;
        if (first && last && first !== last) isDrift = true;
      }
    }
    drift[id]      = isDrift;
    lastActive[id] = activeIxs.length > 0 ? activeIxs[activeIxs.length - 1] : -1;
  }
  return { drift, lastActive };
}

function computeRunStates(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
  flags:      PrimitiveFlags,
): RunState[] {
  const out: RunState[] = [];
  const runCount = evo.perRun.length;
  for (let i = 0; i < runCount; i++) {
    let sum         = 0;
    let hasCrit     = false;
    let hasUpper    = false;
    let hasVolatile = false;
    let hasDrift    = false;
    for (const id of lineageMap.primitive_ids) {
      const lineageRun = lineageMap.lineages[id].runs[i];
      if (!lineageRun || lineageRun.primitive === null) continue;

      const overlayHere = evo.perPrimitive[id]?.runs[i]?.overlay ?? null;
      const inCrit      = overlayHere?.in_critical_zone ?? false;
      const upper       = overlayHere?.on_upper_branch  ?? false;

      let isVolatile = false;
      if (i > 0) {
        const prev = evo.perPrimitive[id]?.runs[i - 1]?.overlay ?? null;
        if (
          prev && overlayHere &&
          prev.flow_regime !== overlayHere.flow_regime
        ) {
          isVolatile = true;
        }
      }

      const isDrifting = flags.drift[id] && i === flags.lastActive[id];

      sum += regimeIntensity(overlayHere?.flow_regime);
      if (inCrit)     { sum++; hasCrit     = true; }
      if (upper)      { sum++; hasUpper    = true; }
      if (isVolatile) { sum++; hasVolatile = true; }
      if (isDrifting) { sum++; hasDrift    = true; }
    }
    out.push({ sum, hasCrit, hasUpper, hasVolatile, hasDrift });
  }
  return out;
}

function buildRunLevelBlock(states: RunState[]): string {
  if (states.length === 0) return `[Run-Level Bands]\n(no runs)`;
  const lines = states.map((s, i) => {
    let label = bandSymbol(s.sum);
    if (s.hasCrit)     label += "C";
    if (s.hasUpper)    label += "B";
    if (s.hasVolatile) label += "!";
    if (s.hasDrift)    label += "~";
    return `R${i}: ${label}`;
  });
  return `[Run-Level Bands]\n${lines.join("\n")}`;
}

function buildPhaseBlock(states: RunState[]): string {
  if (states.length < 2) {
    return `[System-Level Phase Bands]\n(no transitions)`;
  }
  const lines: string[] = [];
  let phaseNum = 1;
  for (let i = 0; i < states.length - 1; i++) {
    const prev = states[i];
    const curr = states[i + 1];
    const changes: string[] = [];

    const prevLvl = pressureLevel(prev.sum);
    const currLvl = pressureLevel(curr.sum);
    if (prevLvl !== currLvl) {
      changes.push(`${prevLvl} → ${currLvl} pressure`);
    }
    if (!prev.hasVolatile && curr.hasVolatile) changes.push("rising volatility");
    if (!prev.hasDrift    && curr.hasDrift)    changes.push("drift onset");
    if (!prev.hasCrit     && curr.hasCrit)     changes.push("critical-zone expansion");
    if (!prev.hasUpper    && curr.hasUpper)    changes.push("upper-branch emergence");

    if (changes.length > 0) {
      lines.push(`Phase ${phaseNum} (R${i}–R${i + 1}): ${changes.join(", ")}`);
      phaseNum++;
    }
  }
  if (lines.length === 0) {
    return `[System-Level Phase Bands]\n(no phase transitions)`;
  }
  return `[System-Level Phase Bands]\n${lines.join("\n")}`;
}

interface PrimitiveBuckets {
  stable:        string[];
  volatile_:     string[];
  critZone:      string[];
  upperBranch:   string[];
  drift:         string[];
}

function bucketPrimitives(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
  flags:      PrimitiveFlags,
): PrimitiveBuckets {
  const stable:      string[] = [];
  const volatile_:   string[] = [];
  const critZone:    string[] = [];
  const upperBranch: string[] = [];
  const drift:       string[] = [];
  for (const id of lineageMap.primitive_ids) {
    const d = lineageMap.diffs[id];
    const total =
      d.appearance.added.length +
      d.appearance.removed.length +
      d.metadataChanges.length +
      d.hydraulicChanges.length +
      d.overlayChanges.length;
    if (total === 0) stable.push(id);
    if (total >= 2)  volatile_.push(id);

    const evoRuns = evo.perPrimitive[id]?.runs ?? [];
    if (evoRuns.some((r) => r.overlay?.in_critical_zone)) critZone.push(id);
    if (evoRuns.some((r) => r.overlay?.on_upper_branch))  upperBranch.push(id);
    if (flags.drift[id])                                  drift.push(id);
  }
  return { stable, volatile_, critZone, upperBranch, drift };
}

function buildSummaryBlock(b: PrimitiveBuckets): string {
  return (
    `[Primitive-Level Band Summary]\n` +
    `Stable primitives: ${listOrNone(b.stable)}\n` +
    `Volatile primitives: ${listOrNone(b.volatile_)}\n` +
    `Critical-zone cluster: ${listOrNone(b.critZone)}\n` +
    `Upper-branch cluster: ${listOrNone(b.upperBranch)}\n` +
    `Drift cluster: ${listOrNone(b.drift)}`
  );
}

export function buildStructuralBands(
  overlay:    EngineV1SystemOverlay,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
  heatmap:    string,
): string {
  void overlay;
  void heatmap;

  const primitive_ids = lineageMap.primitive_ids;
  const runCount      = evo.perRun.length;

  if (primitive_ids.length === 0 && runCount === 0) {
    return `=== Structural Bands ===\n\n${LEGEND}\n\n(no data)`;
  }

  const flags     = derivePrimitiveFlags(lineageMap, evo);
  const runStates = computeRunStates(lineageMap, evo, flags);
  const buckets   = bucketPrimitives(lineageMap, evo, flags);

  return (
    `=== Structural Bands ===\n\n` +
    LEGEND + "\n\n" +
    buildRunLevelBlock(runStates) + "\n\n" +
    buildPhaseBlock(runStates) + "\n\n" +
    buildSummaryBlock(buckets)
  );
}
