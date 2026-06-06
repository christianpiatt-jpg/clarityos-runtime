// Card 50 — Structural signature (Phase-1 minimal).
//
// Pure deterministic, client-side string builder that produces an
// eight-section structural fingerprint of the entire system:
//
//   [Run-Level Structural Fingerprints]  one compressed token per run
//   [System-Level Signature String]      regime + pressure across runs
//   [Hydraulic Signature]                regime sequence
//   [Critical-Zone Signature]            crit-zone count sequence
//   [Upper-Branch Signature]             upper-branch count sequence
//   [Volatility Signature]               regime-change count sequence
//   [Drift Signature]                    drift-active count sequence
//   [Phase-Transition Signature]         pressure-level label sequence
//
// The per-run state computation mirrors Card 49's banding so the
// signature stays consistent with the operator's banded view. Phase-1
// pressure mapping uses two-char "--" for the low fingerprint band
// (matching the spec example) and single-char "-" / "=" / "#" for the
// system signature string.

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1SystemOverlay,
} from "./api";

const LEGEND =
  "Legend:\n" +
  "L = laminar\n" +
  "T = transitional\n" +
  "U = turbulent\n" +
  "C = critical-zone\n" +
  "B = upper-branch\n" +
  "! = volatility\n" +
  "~ = drift\n" +
  "# = high pressure\n" +
  "= = medium pressure\n" +
  "- = low pressure";

function regimeIntensity(regime: string | undefined): number {
  switch (regime) {
    case "transitional": return 1;
    case "turbulent":    return 2;
    default:             return 0;
  }
}

// Two-char band token used by the run-level fingerprint (matches the
// "L--" / "L=C" / "U#CB!~" spec examples).
function fingerprintPressure(sum: number): string {
  if (sum <= 10) return "--";
  if (sum <= 40) return "=";
  return "#";
}

// Single-char band token used by the system-level signature string
// (matches the "L-L=T-U#" spec example).
function signaturePressure(sum: number): string {
  if (sum <= 10) return "-";
  if (sum <= 40) return "=";
  return "#";
}

// Card 49-style 5-band token (`--` / `-=` / `==` / `##` / `###`) —
// kept on every signature so Card 51's diff can show the pressure-
// band transition in the same symbol set the bands view uses.
export function pressureBandSymbol(sum: number): string {
  if (sum <= 10) return "--";
  if (sum <= 20) return "-=";
  if (sum <= 40) return "==";
  if (sum <= 60) return "##";
  return "###";
}

// Pressure-level label for the phase-transition signature. Four
// distinct labels match the spec example's "low → medium → high → high+"
// progression.
export function pressureLevelLabel(sum: number): string {
  if (sum <= 10) return "low";
  if (sum <= 40) return "medium";
  if (sum <= 60) return "high";
  return "high+";
}

// Dominant regime letter for a run: the regime with the highest
// count in the Card 35 per-run roll-up. Ties resolve in L > T > U
// order so the signature is deterministic across surfaces. Empty
// run → "L" (no overlays present anywhere → treat as quiescent).
export function dominantRegimeForRun(
  perRunEntry: EngineV1HydraulicEvolutionMap["perRun"][number],
): "L" | "T" | "U" {
  const { laminar, transitional, turbulent } = perRunEntry;
  if (laminar >= transitional && laminar >= turbulent) return "L";
  if (transitional >= turbulent)                       return "T";
  return "U";
}

interface RunState {
  sum:         number;
  hasCrit:     boolean;
  hasUpper:    boolean;
  hasVolatile: boolean;
  hasDrift:    boolean;
  // Per-run counts (different from boolean any-flags above) — used
  // for the count-signature sections.
  critCount:        number;
  upperCount:       number;
  volatilityCount:  number;
  driftCount:       number;
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
    let sum             = 0;
    let hasCrit         = false;
    let hasUpper        = false;
    let hasVolatile     = false;
    let hasDrift        = false;
    let critCount       = 0;
    let upperCount      = 0;
    let volatilityCount = 0;
    let driftCount      = 0;
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
      if (inCrit)     { sum++; hasCrit     = true; critCount++; }
      if (upper)      { sum++; hasUpper    = true; upperCount++; }
      if (isVolatile) { sum++; hasVolatile = true; volatilityCount++; }
      if (isDrifting) { sum++; hasDrift    = true; driftCount++; }
    }
    out.push({
      sum, hasCrit, hasUpper, hasVolatile, hasDrift,
      critCount, upperCount, volatilityCount, driftCount,
    });
  }
  return out;
}

function buildFingerprintsBlock(
  states:  RunState[],
  evo:     EngineV1HydraulicEvolutionMap,
): string {
  if (states.length === 0) return `[Run-Level Structural Fingerprints]\n(no runs)`;
  const lines = states.map((s, i) => {
    const regime = dominantRegimeForRun(evo.perRun[i]);
    let cell = regime + fingerprintPressure(s.sum);
    if (s.hasCrit)     cell += "C";
    if (s.hasUpper)    cell += "B";
    if (s.hasVolatile) cell += "!";
    if (s.hasDrift)    cell += "~";
    return `R${i}: ${cell}`;
  });
  return `[Run-Level Structural Fingerprints]\n${lines.join("\n")}`;
}

function buildSignatureStringBlock(
  states: RunState[],
  evo:    EngineV1HydraulicEvolutionMap,
): string {
  if (states.length === 0) return `[System-Level Signature String]\n(empty)`;
  const tokens = states.map(
    (s, i) => dominantRegimeForRun(evo.perRun[i]) + signaturePressure(s.sum),
  );
  return `[System-Level Signature String]\n${tokens.join("")}`;
}

function buildHydraulicSignatureBlock(
  evo: EngineV1HydraulicEvolutionMap,
): string {
  if (evo.perRun.length === 0) return `[Hydraulic Signature]\n(empty)`;
  return `[Hydraulic Signature]\n${evo.perRun.map(dominantRegimeForRun).join(" → ")}`;
}

function buildCountBlock(label: string, counts: number[]): string {
  if (counts.length === 0) return `[${label}]\n(empty)`;
  return `[${label}]\n${counts.join(" → ")}`;
}

function buildPhaseSignatureBlock(states: RunState[]): string {
  if (states.length === 0) return `[Phase-Transition Signature]\n(empty)`;
  return (
    `[Phase-Transition Signature]\n` +
    states.map((s) => pressureLevelLabel(s.sum)).join(" → ")
  );
}

// Card 51 — per-run signature object exposed for the signature-diff
// engine. Carries every scalar Card 50 derives so the diff helper
// can format every section without re-walking the overlay.
export interface EngineV1StructuralSignature {
  runIndex:        number;
  regime:          "L" | "T" | "U";
  pressureSum:     number;
  fingerprint:     string;     // e.g. "L=C!" — same token as Card 50
  signatureToken:  string;     // e.g. "L="   — single-char pressure
  pressureBand:    string;     // e.g. "-="   — Card 49-style banding
  pressureLabel:   string;     // e.g. "medium"
  hasCrit:         boolean;
  hasUpper:        boolean;
  hasVolatile:     boolean;
  hasDrift:        boolean;
  critCount:       number;
  upperCount:      number;
  volatilityCount: number;
  driftCount:      number;
}

// Extract one EngineV1StructuralSignature per run from the same
// inputs Card 50 consumes. Pure deterministic — no side effects.
export function extractStructuralSignatures(
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
): EngineV1StructuralSignature[] {
  if (evo.perRun.length === 0) return [];
  const flags  = derivePrimitiveFlags(lineageMap, evo);
  const states = computeRunStates(lineageMap, evo, flags);
  return states.map((s, i) => {
    const regime = dominantRegimeForRun(evo.perRun[i]);
    let fingerprint = regime + fingerprintPressure(s.sum);
    if (s.hasCrit)     fingerprint += "C";
    if (s.hasUpper)    fingerprint += "B";
    if (s.hasVolatile) fingerprint += "!";
    if (s.hasDrift)    fingerprint += "~";
    return {
      runIndex:        i,
      regime,
      pressureSum:     s.sum,
      fingerprint,
      signatureToken:  regime + signaturePressure(s.sum),
      pressureBand:    pressureBandSymbol(s.sum),
      pressureLabel:   pressureLevelLabel(s.sum),
      hasCrit:         s.hasCrit,
      hasUpper:        s.hasUpper,
      hasVolatile:     s.hasVolatile,
      hasDrift:        s.hasDrift,
      critCount:       s.critCount,
      upperCount:      s.upperCount,
      volatilityCount: s.volatilityCount,
      driftCount:      s.driftCount,
    };
  });
}

export function buildStructuralSignature(
  overlay:    EngineV1SystemOverlay,
  lineageMap: EngineV1LineageMap,
  evo:        EngineV1HydraulicEvolutionMap,
  heatmap:    string,
  bands:      string,
): string {
  // Overlay + heatmap + bands kept for signature parity with the
  // spec; signature derives from the structured inputs.
  void overlay;
  void heatmap;
  void bands;

  const runCount = evo.perRun.length;
  if (lineageMap.primitive_ids.length === 0 && runCount === 0) {
    return `=== Structural Signature ===\n\n${LEGEND}\n\n(no data)`;
  }

  const flags  = derivePrimitiveFlags(lineageMap, evo);
  const states = computeRunStates(lineageMap, evo, flags);

  return (
    `=== Structural Signature ===\n\n` +
    LEGEND + "\n\n" +
    buildFingerprintsBlock(states, evo)                                    + "\n\n" +
    buildSignatureStringBlock(states, evo)                                 + "\n\n" +
    buildHydraulicSignatureBlock(evo)                                      + "\n\n" +
    buildCountBlock("Critical-Zone Signature", states.map((s) => s.critCount))       + "\n\n" +
    buildCountBlock("Upper-Branch Signature",  states.map((s) => s.upperCount))      + "\n\n" +
    buildCountBlock("Volatility Signature",    states.map((s) => s.volatilityCount)) + "\n\n" +
    buildCountBlock("Drift Signature",         states.map((s) => s.driftCount))      + "\n\n" +
    buildPhaseSignatureBlock(states)
  );
}
