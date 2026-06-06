// Card 59 — Structural resilience engine (Phase-3, Tier-6).
//
// Phone mirror of web/src/lib/operatorStructuralResilience.ts.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

const PRESSURE_RANK: Record<string, number> = {
  low: 0, medium: 1, high: 2, "high+": 3,
};

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
  values:   number[];
  max:      number;
  last:     number;
  prev:     number;
  decaying: boolean;
  flat:     boolean;
  rising:   boolean;
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

function collectDrivers(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.decaying)                          out.push("volatility decay");
  if (t.crit.decaying)                         out.push("CZ relaxation");
  if (t.pressure.flat || t.pressure.decaying)  out.push("pressure plateau");
  if (t.drift.flat || t.drift.decaying)        out.push("drift flattening");
  if (t.regime.flat)                           out.push("hydraulic stabilization");
  return out;
}

function collectInhibitors(t: Trends): string[] {
  const out: string[] = [];
  if (t.drift.last  > 0)                            out.push("residual drift pressure");
  if (t.upper.last  > 0)                            out.push("upper-branch instability");
  if (t.crit.last   >= 2 && !t.crit.decaying)       out.push("incomplete CZ stabilization");
  if (t.vol.last    >= 3 && !t.vol.decaying)        out.push("volatility persistence");
  return out;
}

type ResilienceScore = "LOW" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

function scoreFromCounts(driverCount: number, inhibitorCount: number): ResilienceScore {
  const delta = driverCount - inhibitorCount;
  if (delta >= 3)  return "HIGH";
  if (delta === 2) return "MEDIUM-HIGH";
  if (delta >= 0)  return "MEDIUM";
  return "LOW";
}

const SCORE_RANK: Record<ResilienceScore, number> = {
  LOW: 0, MEDIUM: 1, "MEDIUM-HIGH": 2, HIGH: 3,
};
const RANK_TO_SCORE: Record<number, ResilienceScore> = {
  0: "LOW", 1: "MEDIUM", 2: "MEDIUM-HIGH", 3: "HIGH",
};

function projectScore(current: ResilienceScore, drivers: number, inhibitors: number): ResilienceScore {
  const dir = drivers > inhibitors ? +1 : drivers < inhibitors ? -1 : 0;
  const next = Math.max(0, Math.min(3, SCORE_RANK[current] + dir));
  return RANK_TO_SCORE[next];
}

function trajectoryDirection(drivers: number, inhibitors: number): "improving" | "deteriorating" | "stable" {
  if (drivers > inhibitors) return "improving";
  if (drivers < inhibitors) return "deteriorating";
  return "stable";
}

function buildTrajectory(
  current: ResilienceScore,
  projected: ResilienceScore,
  direction: "improving" | "deteriorating" | "stable",
): string {
  const tail = direction === "stable"
    ? (current === projected ? "(stable)" : "(projected)")
    : `(${direction})`;
  return `${current.toLowerCase()} → ${projected.toLowerCase()} ${tail}`;
}

type Resistance = "high" | "moderate" | "low";

function dimensionResistance(t: DimensionTrend, highBar: number): Resistance {
  if (t.max === 0)                       return "high";
  if (t.decaying)                        return "moderate";
  if (t.last >= highBar && !t.decaying)  return "low";
  if (t.rising)                          return "low";
  return "moderate";
}

interface ResistanceProfile {
  vol:    Resistance;
  drift:  Resistance;
  crit:   Resistance;
  upper:  Resistance;
}

function buildResistanceProfile(t: Trends): ResistanceProfile {
  return {
    vol:    dimensionResistance(t.vol,   3),
    drift:  dimensionResistance(t.drift, 2),
    crit:   dimensionResistance(t.crit,  3),
    upper:  dimensionResistance(t.upper, 2),
  };
}

function profileLine(label: string, r: Resistance, noun: string): string {
  switch (r) {
    case "high":     return `- strong resistance to ${noun}`;
    case "moderate": return `- moderate resistance to ${noun}`;
    case "low":      return `- low resistance to ${noun}`;
    default:         return `- ${label} resistance`;
  }
}

function buildProfileBlock(p: ResistanceProfile): string {
  const lines = [
    profileLine("volatility", p.vol,   "volatility resurgence"),
    profileLine("drift",      p.drift, "drift reactivation"),
    profileLine("crit",       p.crit,  "CZ re-expansion"),
    profileLine("upper",      p.upper, "upper-branch reactivation"),
  ];
  return `[Resilience Profile]\n${lines.join("\n")}`;
}

function collectDecayRisks(t: Trends): string[] {
  const out: string[] = [];
  if (t.crit.max  > 0 && (t.pressure.last >= 1 || t.pressure.flat)) {
    out.push("CZ may re-expand under pressure");
  }
  if (t.drift.max > 0 && t.vol.last >= 1) {
    out.push("drift may re-activate under volatility");
  }
  if (t.upper.max > 0 && t.crit.last >= 1) {
    out.push("upper-branch may re-emerge under CZ saturation");
  }
  return out;
}

function collectReinforcement(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.decaying)      out.push("maintain volatility dampening");
  if (t.crit.decaying)     out.push("maintain CZ stabilization");
  if (t.pressure.decaying) out.push("maintain pressure relief");
  if (t.drift.decaying)    out.push("maintain drift suppression");
  if (t.upper.decaying)    out.push("maintain upper-branch constraint");
  return out;
}

function resistanceWord(r: Resistance): string {
  switch (r) {
    case "high":     return "strong";
    case "moderate": return "moderate";
    case "low":      return "low";
  }
}

function buildResistanceBlock(p: ResistanceProfile): string {
  const lines = [
    `Volatility: ${resistanceWord(p.vol)}`,
    `Drift: ${resistanceWord(p.drift)}`,
    `CZ: ${resistanceWord(p.crit)}`,
    `Upper-Branch: ${resistanceWord(p.upper)}`,
  ];
  return `[Post-Stabilization Resistance]\n${lines.join("\n")}`;
}

function buildSummary(
  score:    ResilienceScore,
  drivers:  string[],
  inhibitors: string[],
  direction: "improving" | "deteriorating" | "stable",
): string {
  const parts: string[] = [];
  parts.push(`The system shows ${score.toLowerCase()} resilience with ${direction} trajectory.`);
  if (drivers.length > 0) {
    parts.push(`Resilience is being driven by ${drivers.join(", ")}.`);
  }
  if (inhibitors.length > 0) {
    parts.push(`${inhibitors.join(" and ")} remain the primary inhibitors to long-term stability.`);
  } else {
    parts.push("No structural inhibitors remain.");
  }
  return parts.join(" ");
}

export function buildStructuralResilience(
  signatures:    EngineV1StructuralSignature[],
  diffs:         EngineV1StructuralSignatureDiff[],
  stabilization: string,
): string {
  void diffs;
  void stabilization;

  if (signatures.length === 0) {
    return `=== Structural Resilience ===\n\n(no data)`;
  }

  const everActive = signatures.some((s) => riskScore(s) > 0);
  if (!everActive) {
    return (
      `=== Structural Resilience ===\n\n` +
      `[Resilience Score]\nHIGH\n\n` +
      `[Resilience Profile]\n` +
      `- strong resistance to volatility resurgence\n` +
      `- strong resistance to drift reactivation\n` +
      `- strong resistance to CZ re-expansion\n` +
      `- strong resistance to upper-branch reactivation\n\n` +
      `[Resilience Trajectory]\nhigh → high (stable)\n\n` +
      `[Resilience Drivers]\n(none — system has not faced challenges)\n\n` +
      `[Resilience Inhibitors]\n(none)\n\n` +
      `[Resilience Decay]\n(none)\n\n` +
      `[Resilience Reinforcement]\n(none — baseline resilience maintained)\n\n` +
      `[Post-Stabilization Resistance]\n` +
      `Volatility: strong\nDrift: strong\nCZ: strong\nUpper-Branch: strong\n\n` +
      `[System-Level Resilience Summary]\n` +
      `System has not experienced structural challenges. Baseline resilience is HIGH and unchallenged.`
    );
  }

  const t          = buildTrends(signatures);
  const drivers    = collectDrivers(t);
  const inhibitors = collectInhibitors(t);
  const score      = scoreFromCounts(drivers.length, inhibitors.length);
  const projected  = projectScore(score, drivers.length, inhibitors.length);
  const direction  = trajectoryDirection(drivers.length, inhibitors.length);
  const profile    = buildResistanceProfile(t);
  const decay      = collectDecayRisks(t);
  const reinforce  = collectReinforcement(t);

  const blocks: string[] = [];
  blocks.push("=== Structural Resilience ===");
  blocks.push(`[Resilience Score]\n${score}`);
  blocks.push(buildProfileBlock(profile));
  blocks.push(`[Resilience Trajectory]\n${buildTrajectory(score, projected, direction)}`);
  blocks.push(
    drivers.length === 0
      ? `[Resilience Drivers]\n(none)`
      : `[Resilience Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Resilience Inhibitors]\n(none)`
      : `[Resilience Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Resilience Decay]\n(none)`
      : `[Resilience Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    reinforce.length === 0
      ? `[Resilience Reinforcement]\n(none)`
      : `[Resilience Reinforcement]\n${reinforce.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(buildResistanceBlock(profile));
  blocks.push(`[System-Level Resilience Summary]\n${buildSummary(score, drivers, inhibitors, direction)}`);

  return blocks.join("\n\n");
}
