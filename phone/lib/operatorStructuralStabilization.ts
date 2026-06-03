// Card 58 — Structural stabilization engine (Phase-3, Tier-5).
//
// Phone mirror of web/src/lib/operatorStructuralStabilization.ts.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

const PRESSURE_RANK: Record<string, number> = {
  low: 0, medium: 1, high: 2, "high+": 3,
};

type IdentityState = "stable" | "transitional" | "escalated" | "escalated+";

function identityState(sig: EngineV1StructuralSignature): IdentityState {
  if (sig.regime === "U" || sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
    return "escalated";
  }
  if (sig.regime === "T" || sig.pressureLabel === "medium") {
    return "transitional";
  }
  return "stable";
}

function riskScore(sig: EngineV1StructuralSignature): number {
  let s = 0;
  if (sig.hasCrit)     s += 1;
  if (sig.hasUpper)    s += 2;
  if (sig.hasVolatile) s += 1;
  if (sig.hasDrift)    s += 2;
  s += PRESSURE_RANK[sig.pressureLabel] ?? 0;
  return s;
}

interface DimensionTrend {
  values:    number[];
  max:       number;
  last:      number;
  prev:      number;
  decaying:  boolean;
  flat:      boolean;
  rising:    boolean;
}

function describeTrend(values: number[]): DimensionTrend {
  if (values.length === 0) {
    return { values, max: 0, last: 0, prev: 0, decaying: false, flat: false, rising: false };
  }
  const last = values[values.length - 1];
  const prev = values.length >= 2 ? values[values.length - 2] : last;
  const max  = Math.max(...values);
  return {
    values,
    max,
    last,
    prev,
    decaying: last < prev && max > 0,
    flat:     last === prev && max > 0,
    rising:   last > prev,
  };
}

function pressureRanks(signatures: EngineV1StructuralSignature[]): number[] {
  return signatures.map((s) => PRESSURE_RANK[s.pressureLabel] ?? 0);
}

function regimeRanks(signatures: EngineV1StructuralSignature[]): number[] {
  const RANK: Record<string, number> = { L: 0, T: 1, U: 2 };
  return signatures.map((s) => RANK[s.regime] ?? 0);
}

interface Trends {
  vol:      DimensionTrend;
  drift:    DimensionTrend;
  crit:     DimensionTrend;
  upper:    DimensionTrend;
  pressure: DimensionTrend;
  regime:   DimensionTrend;
}

function buildTrends(signatures: EngineV1StructuralSignature[]): Trends {
  return {
    vol:      describeTrend(signatures.map((s) => s.volatilityCount)),
    drift:    describeTrend(signatures.map((s) => s.driftCount)),
    crit:     describeTrend(signatures.map((s) => s.critCount)),
    upper:    describeTrend(signatures.map((s) => s.upperCount)),
    pressure: describeTrend(pressureRanks(signatures)),
    regime:   describeTrend(regimeRanks(signatures)),
  };
}

function collectIndicators(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.decaying)                       out.push("volatility decay detected");
  if (t.drift.flat || t.drift.decaying)     out.push("drift slope flattening");
  if (t.crit.decaying)                      out.push("CZ relaxation beginning");
  if (t.pressure.flat || t.pressure.decaying) out.push("pressure plateau forming");
  if (t.regime.flat)                        out.push("hydraulic stabilization");
  return out;
}

function projectWindow(numIndicators: number): string {
  if (numIndicators >= 4) return "next 1–2 runs";
  if (numIndicators === 3) return "next 2–3 runs";
  if (numIndicators === 2) return "next 3–4 runs";
  if (numIndicators === 1) return "5+ runs";
  return "not projected";
}

function projectProbability(numIndicators: number): string {
  if (numIndicators >= 4) return "HIGH";
  if (numIndicators === 3) return "MEDIUM-HIGH";
  if (numIndicators === 2) return "MEDIUM";
  return "LOW";
}

function projectTrajectory(
  signatures: EngineV1StructuralSignature[],
  numIndicators: number,
): string {
  const states = signatures.map(identityState);
  if (numIndicators >= 2) {
    return `${states.join(" → ")} → stabilized (projected)`;
  }
  return `${states.join(" → ")} (no projected stabilization)`;
}

function collectBlockers(t: Trends): string[] {
  const out: string[] = [];
  if (t.drift.last  > 0)                  out.push("residual drift pressure");
  if (t.upper.last  > 0)                  out.push("upper-branch instability");
  if (t.crit.last   >= 3)                 out.push("critical-zone saturation");
  if (t.vol.last    >= 3 && !t.vol.decaying) out.push("volatility persistence");
  return out;
}

function collectAccelerators(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.decaying)      out.push("volatility dampening");
  if (t.crit.decaying)     out.push("CZ stabilization");
  if (t.pressure.decaying) out.push("pressure relief");
  if (t.drift.decaying)    out.push("drift suppression");
  if (t.upper.decaying)    out.push("upper-branch constraint");
  return out;
}

function dimStatus(t: DimensionTrend, decayWord: string, flatWord: string): string {
  if (t.max === 0)        return "no activity";
  if (t.decaying)         return decayWord;
  if (t.flat)             return flatWord;
  if (t.rising)           return "rising";
  return "stable";
}

function buildPostIntervention(t: Trends): string {
  const lines = [
    `Volatility: ${dimStatus(t.vol,      "decreasing", "flattening")}`,
    `Drift: ${dimStatus(t.drift,         "decreasing", "flattening")}`,
    `CZ: ${dimStatus(t.crit,             "relaxing",   "plateau")}`,
    `Upper-Branch: ${dimStatus(t.upper,  "stabilizing", "stable")}`,
  ];
  return `[Post-Intervention Effects]\n${lines.join("\n")}`;
}

function buildSummary(
  indicators: string[],
  blockers:   string[],
): string {
  if (indicators.length === 0 && blockers.length === 0) {
    return "No stabilization assessment needed. System is operating within stable bounds.";
  }
  if (indicators.length === 0) {
    return `No stabilization signals yet. Active blockers: ${blockers.join(", ")}.`;
  }
  const parts: string[] = [];
  parts.push(
    `The system shows early signs of stabilization driven by ${indicators.join(", ")}.`,
  );
  if (blockers.length > 0) {
    parts.push(`${blockers.join(" and ")} remain the primary blockers.`);
  } else {
    parts.push("No structural blockers remain.");
  }
  return parts.join(" ");
}

export function buildStructuralStabilization(
  signatures:    EngineV1StructuralSignature[],
  diffs:         EngineV1StructuralSignatureDiff[],
  interventions: string,
): string {
  void diffs;
  void interventions;

  if (signatures.length === 0) {
    return `=== Structural Stabilization ===\n\n(no data)`;
  }

  const everActive = signatures.some((s) => riskScore(s) > 0);
  if (!everActive) {
    return (
      `=== Structural Stabilization ===\n\n` +
      `[Stabilization Indicators]\n(none — system has not shown structural risk)\n\n` +
      `[Stabilization Window]\nnot needed\n\n` +
      `[Stabilization Probability]\nN/A\n\n` +
      `[Stabilization Trajectory]\n${signatures.map(identityState).join(" → ")} (already stable)\n\n` +
      `[Stabilization Blockers]\n(none)\n\n` +
      `[Stabilization Accelerators]\n(none)\n\n` +
      `[Post-Intervention Effects]\n` +
      `Volatility: no activity\nDrift: no activity\nCZ: no activity\nUpper-Branch: no activity\n\n` +
      `[System-Level Stabilization Summary]\n` +
      `No stabilization assessment needed. System is operating within stable bounds.`
    );
  }

  const t           = buildTrends(signatures);
  const indicators  = collectIndicators(t);
  const window      = projectWindow(indicators.length);
  const probability = projectProbability(indicators.length);
  const trajectory  = projectTrajectory(signatures, indicators.length);
  const blockers    = collectBlockers(t);
  const accelerators = collectAccelerators(t);

  const blocks: string[] = [];
  blocks.push("=== Structural Stabilization ===");
  blocks.push(
    indicators.length === 0
      ? `[Stabilization Indicators]\n(none — no stabilization signals yet)`
      : `[Stabilization Indicators]\n${indicators.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Stabilization Window]\nProjected: ${window}`);
  blocks.push(`[Stabilization Probability]\n${probability}`);
  blocks.push(`[Stabilization Trajectory]\n${trajectory}`);
  blocks.push(
    blockers.length === 0
      ? `[Stabilization Blockers]\n(none)`
      : `[Stabilization Blockers]\n${blockers.map((b) => `- ${b}`).join("\n")}`,
  );
  blocks.push(
    accelerators.length === 0
      ? `[Stabilization Accelerators]\n(none)`
      : `[Stabilization Accelerators]\n${accelerators.map((a) => `- ${a}`).join("\n")}`,
  );
  blocks.push(buildPostIntervention(t));
  blocks.push(`[System-Level Stabilization Summary]\n${buildSummary(indicators, blockers)}`);

  return blocks.join("\n\n");
}
