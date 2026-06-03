// Card 61 — Structural governance engine (Phase-4, Tier-1).
//
// Phone mirror of web/src/lib/operatorStructuralGovernance.ts.

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
    values, max, last, prev,
    decaying: last < prev && max > 0,
    flat:     last === prev && max > 0,
    rising:   last > prev,
  };
}

function pressureRanks(signatures: EngineV1StructuralSignature[]): number[] {
  return signatures.map((s) => PRESSURE_RANK[s.pressureLabel] ?? 0);
}

interface Trends {
  vol:      DimensionTrend;
  drift:    DimensionTrend;
  crit:     DimensionTrend;
  upper:    DimensionTrend;
  pressure: DimensionTrend;
}

function buildTrends(signatures: EngineV1StructuralSignature[]): Trends {
  return {
    vol:      describeTrend(signatures.map((s) => s.volatilityCount)),
    drift:    describeTrend(signatures.map((s) => s.driftCount)),
    crit:     describeTrend(signatures.map((s) => s.critCount)),
    upper:    describeTrend(signatures.map((s) => s.upperCount)),
    pressure: describeTrend(pressureRanks(signatures)),
  };
}

function collectDrivers(t: Trends): string[] {
  const out: string[] = [];
  const anyDecaying = t.vol.decaying || t.drift.decaying || t.crit.decaying || t.upper.decaying;
  if (anyDecaying)      out.push("immunity stabilization");
  if (t.vol.decaying)   out.push("volatility dampening");
  if (t.drift.decaying) out.push("drift suppression");
  if (t.crit.decaying)  out.push("CZ stabilization");
  if (t.upper.decaying) out.push("upper-branch containment");
  return out;
}

function collectInhibitors(t: Trends): string[] {
  const out: string[] = [];
  if (t.crit.last  > 0)                            out.push("CZ vulnerability");
  if (t.upper.last > 0)                            out.push("upper-branch instability");
  if (t.drift.last > 0)                            out.push("incomplete drift containment");
  if (t.vol.last   >= 2 && !t.vol.decaying)        out.push("volatility breach");
  return out;
}

type GovernanceLevel = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

const LEVEL_RANK: Record<GovernanceLevel, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_LEVEL: Record<number, GovernanceLevel> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

function levelFrom(drivers: number, inhibitors: number): GovernanceLevel {
  const delta = drivers - inhibitors;
  if (delta >= 3)   return "HIGH";
  if (delta === 2)  return "MEDIUM-HIGH";
  if (delta >= 0)   return "MEDIUM";
  if (delta === -1) return "LOW-MEDIUM";
  return "LOW";
}

function projectLevel(current: GovernanceLevel, drivers: number, inhibitors: number): GovernanceLevel {
  const dir = drivers > inhibitors ? +1 : drivers < inhibitors ? -1 : 0;
  const next = Math.max(0, Math.min(4, LEVEL_RANK[current] + dir));
  return RANK_TO_LEVEL[next];
}

function projectLevelTwoStep(current: GovernanceLevel, projected: GovernanceLevel): GovernanceLevel {
  const dir = LEVEL_RANK[projected] - LEVEL_RANK[current];
  const next = Math.max(0, Math.min(4, LEVEL_RANK[projected] + dir));
  return RANK_TO_LEVEL[next];
}

type TrajectoryDir = "improving" | "deteriorating" | "stable";

function trajectoryDirection(drivers: number, inhibitors: number): TrajectoryDir {
  if (drivers > inhibitors) return "improving";
  if (drivers < inhibitors) return "deteriorating";
  return "stable";
}

function buildTrajectory(
  current:   GovernanceLevel,
  projected: GovernanceLevel,
  twoStep:   GovernanceLevel,
): string {
  const labels = [current, projected, twoStep].map((s) => s.toLowerCase());
  const moves  = current !== projected || projected !== twoStep;
  const tail   = moves ? "(projected)" : "(stable)";
  return `${labels.join(" → ")} ${tail}`;
}

type Strength = "strong" | "moderate" | "weak";

function dimensionStrength(t: DimensionTrend, weakBar: number): Strength {
  if (t.max === 0)                              return "strong";
  if (t.last >= weakBar && !t.decaying)         return "weak";
  if (t.rising)                                 return "weak";
  if (t.decaying || t.flat)                     return "moderate";
  return "moderate";
}

interface GovernanceProfile {
  crit:   Strength;
  drift:  Strength;
  upper:  Strength;
  vol:    Strength;
}

function buildProfileObj(t: Trends): GovernanceProfile {
  return {
    crit:   dimensionStrength(t.crit,  2),
    drift:  dimensionStrength(t.drift, 1),
    upper:  dimensionStrength(t.upper, 1),
    vol:    dimensionStrength(t.vol,   2),
  };
}

function invariantWord(s: Strength): string {
  switch (s) {
    case "strong":   return "full";
    case "moderate": return "partial";
    case "weak":     return "weak";
  }
}

function buildProfileBlock(p: GovernanceProfile): string {
  const lines = [
    `- ${invariantWord(p.crit)} invariant compliance`,
    `- ${p.drift} threshold adherence`,
    `- ${p.upper} upper-branch containment`,
    `- ${p.vol} volatility control`,
  ];
  return `[Governance Profile]\n${lines.join("\n")}`;
}

const INVARIANT_LINES = [
  "- CZ must not exceed 2",
  "- volatility must not exceed 2",
  "- drift must not exceed 1",
  "- upper-branch activation must remain suppressed",
];

const THRESHOLD_LINES = [
  "- CZ < 2",
  "- volatility < 2",
  "- drift < 1",
];

function collectBreachConditions(t: Trends): string[] {
  const out: string[] = [];
  const thresholdCrossed =
    t.crit.max >= 2 || t.vol.max >= 2 || t.drift.max >= 1 || t.upper.max >= 1;
  if (thresholdCrossed)   out.push("threshold violation");
  if (t.vol.max   >= 3)   out.push("volatility spike");
  if (t.crit.max  > 0)    out.push("CZ re-expansion");
  if (t.drift.max > 0)    out.push("drift reactivation");
  if (t.upper.max > 0)    out.push("upper-branch emergence");
  return out;
}

function collectReinforcement(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.max   > 0) out.push("maintain volatility dampening");
  if (t.drift.max > 0) out.push("maintain drift suppression");
  if (t.crit.max  > 0) out.push("maintain CZ stabilization");
  if (t.upper.max > 0) out.push("constrain upper-branch activation");
  return out;
}

function collectDecay(t: Trends): string[] {
  const out: string[] = [];
  const anyHistoricalLoad = t.crit.max > 0 || t.vol.max > 0 || t.drift.max > 0;
  if (anyHistoricalLoad)  out.push("thresholds may weaken under pressure");
  if (t.drift.max > 0)    out.push("drift may re-activate under volatility");
  if (t.upper.max > 0)    out.push("upper-branch may re-emerge under CZ instability");
  return out;
}

function buildSummary(
  level:      GovernanceLevel,
  drivers:    string[],
  inhibitors: string[],
): string {
  const direction = trajectoryDirection(drivers.length, inhibitors.length);
  const parts: string[] = [];

  parts.push(`The system shows ${level.toLowerCase().replace("-", "-to-")} governance strength.`);

  if (inhibitors.length === 0) {
    parts.push("Invariants are fully met.");
  } else if (drivers.length >= inhibitors.length) {
    parts.push("Invariants are partially met, but CZ and upper-branch vulnerabilities remain.");
  } else {
    parts.push("Invariants are weakly held with significant vulnerabilities.");
  }

  if (direction === "improving") {
    parts.push("Governance is improving but not yet robust.");
  } else if (direction === "deteriorating") {
    parts.push("Governance is weakening — reinforcement recommended.");
  } else if (level === "HIGH") {
    parts.push("Governance is robust and well-positioned.");
  }

  return parts.join(" ");
}

export function buildStructuralGovernance(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  immunity:   string,
): string {
  void diffs;
  void immunity;

  if (signatures.length === 0) {
    return `=== Structural Governance ===\n\n(no data)`;
  }

  const everActive = signatures.some((s) => riskScore(s) > 0);
  if (!everActive) {
    return (
      `=== Structural Governance ===\n\n` +
      `[Governance Level]\nHIGH\n\n` +
      `[Structural Invariants]\n${INVARIANT_LINES.join("\n")}\n\n` +
      `[Governance Profile]\n` +
      `- full invariant compliance\n` +
      `- strong threshold adherence\n` +
      `- strong upper-branch containment\n` +
      `- strong volatility control\n\n` +
      `[Governance Trajectory]\nhigh → high → high (stable)\n\n` +
      `[Governance Drivers]\n(none — system has not faced challenges)\n\n` +
      `[Governance Inhibitors]\n(none)\n\n` +
      `[Governance Thresholds]\n${THRESHOLD_LINES.join("\n")}\n\n` +
      `[Governance Breach Conditions]\n(none — invariants fully held)\n\n` +
      `[Governance Reinforcement]\n(none — baseline governance maintained)\n\n` +
      `[Governance Decay]\n(none)\n\n` +
      `[System-Level Governance Summary]\n` +
      `System has not been challenged. Baseline governance is HIGH and invariants are fully held.`
    );
  }

  const t          = buildTrends(signatures);
  const drivers    = collectDrivers(t);
  const inhibitors = collectInhibitors(t);
  const level      = levelFrom(drivers.length, inhibitors.length);
  const projected  = projectLevel(level, drivers.length, inhibitors.length);
  const twoStep    = projectLevelTwoStep(level, projected);
  const profile    = buildProfileObj(t);
  const breach     = collectBreachConditions(t);
  const reinforce  = collectReinforcement(t);
  const decay      = collectDecay(t);

  const blocks: string[] = [];
  blocks.push("=== Structural Governance ===");
  blocks.push(`[Governance Level]\n${level}`);
  blocks.push(`[Structural Invariants]\n${INVARIANT_LINES.join("\n")}`);
  blocks.push(buildProfileBlock(profile));
  blocks.push(`[Governance Trajectory]\n${buildTrajectory(level, projected, twoStep)}`);
  blocks.push(
    drivers.length === 0
      ? `[Governance Drivers]\n(none)`
      : `[Governance Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Governance Inhibitors]\n(none)`
      : `[Governance Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Governance Thresholds]\n${THRESHOLD_LINES.join("\n")}`);
  blocks.push(
    breach.length === 0
      ? `[Governance Breach Conditions]\n(none)`
      : `[Governance Breach Conditions]\n${breach.map((b) => `- ${b}`).join("\n")}`,
  );
  blocks.push(
    reinforce.length === 0
      ? `[Governance Reinforcement]\n(none)`
      : `[Governance Reinforcement]\n${reinforce.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Governance Decay]\n(none)`
      : `[Governance Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(`[System-Level Governance Summary]\n${buildSummary(level, drivers, inhibitors)}`);

  return blocks.join("\n\n");
}
