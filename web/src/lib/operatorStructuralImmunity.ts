// Card 60 — Structural immunity engine (Phase-3, Tier-7).
//
// Prevention layer: where resilience (Card 59) asks "can the system
// resist a return to instability?", immunity asks "can the system
// prevent instability from beginning in the first place?". The
// distinguishing additions over resilience are:
//
//   [Immunity Thresholds]         fixed safe-operating bounds
//   [Immunity Breach Conditions]  what would tip the system
//   [Early-Warning Signals]       fresh slope changes in the last
//                                 transition
//
// Eleven sections, scored on a 5-step ladder
// (LOW / LOW-MEDIUM / MEDIUM / MEDIUM-HIGH / HIGH).

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

// ----- Drivers + Inhibitors + Early-Warning ------------------------------

function collectDrivers(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.decaying)                          out.push("volatility decay");
  if (t.drift.decaying)                        out.push("drift suppression");
  if (t.crit.decaying)                         out.push("CZ relaxation");
  if (t.pressure.flat || t.pressure.decaying)  out.push("pressure plateau");
  if (t.upper.decaying)                        out.push("upper-branch normalization");
  return out;
}

function collectInhibitors(t: Trends): string[] {
  const out: string[] = [];
  if (t.crit.last  > 0)                          out.push("residual CZ vulnerability");
  if (t.upper.last > 0)                          out.push("upper-branch instability");
  if (t.drift.last > 0)                          out.push("incomplete drift containment");
  if (t.vol.last   >= 2 && !t.vol.decaying)      out.push("volatility persistence");
  return out;
}

// Early-warning signals fire only on the most recent transition —
// they're forward-looking rather than historical.
function collectEarlyWarning(t: Trends): string[] {
  const out: string[] = [];
  if (t.vol.last      > t.vol.prev)        out.push("rising volatility slope");
  if (t.crit.last     > t.crit.prev)       out.push("CZ uptick");
  if (t.drift.last    > t.drift.prev)      out.push("drift acceleration");
  if (t.pressure.last > t.pressure.prev)   out.push("pressure climb");
  if (t.upper.last    > t.upper.prev)      out.push("upper-branch tick");
  return out;
}

// ----- Score + Trajectory ------------------------------------------------

type ImmunityScore = "LOW" | "LOW-MEDIUM" | "MEDIUM" | "MEDIUM-HIGH" | "HIGH";

const SCORE_RANK: Record<ImmunityScore, number> = {
  LOW: 0, "LOW-MEDIUM": 1, MEDIUM: 2, "MEDIUM-HIGH": 3, HIGH: 4,
};
const RANK_TO_SCORE: Record<number, ImmunityScore> = {
  0: "LOW", 1: "LOW-MEDIUM", 2: "MEDIUM", 3: "MEDIUM-HIGH", 4: "HIGH",
};

function scoreFrom(drivers: number, inhibitors: number, warnings: number): ImmunityScore {
  // Immunity penalises both inhibitors and early-warning signals —
  // future-resistance demands cleaner state than mere recovery.
  const delta = drivers - inhibitors - warnings;
  if (delta >= 3)  return "HIGH";
  if (delta === 2) return "MEDIUM-HIGH";
  if (delta >= 0)  return "MEDIUM";
  if (delta === -1) return "LOW-MEDIUM";
  return "LOW";
}

function projectScore(current: ImmunityScore, drivers: number, inhibitors: number, warnings: number): ImmunityScore {
  const dir = drivers > inhibitors + warnings ? +1
            : drivers < inhibitors + warnings ? -1 : 0;
  const next = Math.max(0, Math.min(4, SCORE_RANK[current] + dir));
  return RANK_TO_SCORE[next];
}

function projectScoreTwoStep(current: ImmunityScore, projected: ImmunityScore): ImmunityScore {
  const dir = SCORE_RANK[projected] - SCORE_RANK[current];
  const next = Math.max(0, Math.min(4, SCORE_RANK[projected] + dir));
  return RANK_TO_SCORE[next];
}

function trajectoryDirection(drivers: number, inhibitors: number, warnings: number): "improving" | "deteriorating" | "stable" {
  if (drivers > inhibitors + warnings) return "improving";
  if (drivers < inhibitors + warnings) return "deteriorating";
  return "stable";
}

function buildTrajectory(
  current:   ImmunityScore,
  projected: ImmunityScore,
  twoStep:   ImmunityScore,
  direction: "improving" | "deteriorating" | "stable",
): string {
  const tail = direction === "stable" ? "(stable)" : `(${direction})`;
  const labels = [current, projected, twoStep].map((s) => s.toLowerCase());
  return `${labels.join(" → ")} ${tail}`;
}

// ----- Profile + Per-Dimension Immunity ---------------------------------

type Strength = "strong" | "moderate" | "weak";

function dimensionStrength(t: DimensionTrend, weakBar: number): Strength {
  if (t.max === 0)                              return "strong";
  if (t.last >= weakBar && !t.decaying)         return "weak";
  if (t.rising)                                 return "weak";
  if (t.decaying || t.flat)                     return "moderate";
  return "moderate";
}

interface ImmunityProfile {
  vol:    Strength;
  drift:  Strength;
  crit:   Strength;
  upper:  Strength;
}

function buildProfileObj(t: Trends): ImmunityProfile {
  return {
    vol:    dimensionStrength(t.vol,   2),
    drift:  dimensionStrength(t.drift, 1),
    crit:   dimensionStrength(t.crit,  2),
    upper:  dimensionStrength(t.upper, 1),
  };
}

function strengthLine(label: string, s: Strength): string {
  return `- ${s} ${label} immunity`;
}

function buildProfileBlock(p: ImmunityProfile): string {
  const lines = [
    strengthLine("CZ",            p.crit),
    strengthLine("volatility",    p.vol),
    strengthLine("drift",         p.drift),
    strengthLine("upper-branch",  p.upper),
  ];
  return `[Immunity Profile]\n${lines.join("\n")}`;
}

// ----- Decay + Breach + Thresholds + Reinforcement ----------------------

function collectDecay(t: Trends): string[] {
  const out: string[] = [];
  if (t.crit.max  > 0)  out.push("CZ may re-expand under pressure");
  if (t.drift.max > 0)  out.push("drift may re-activate under volatility");
  if (t.upper.max > 0)  out.push("upper-branch may re-emerge under CZ instability");
  return out;
}

// Breach conditions = what would push the system back into instability.
// Listed when the system has shown ANY structural load, so the operator
// always knows the failure modes for the current configuration.
function collectBreachConditions(t: Trends): string[] {
  const out: string[] = [];
  if (t.pressure.max > 0)  out.push("pressure escalation");
  if (t.vol.max      > 0)  out.push("volatility resurgence");
  if (t.crit.max     > 0)  out.push("CZ re-expansion");
  if (t.drift.max    > 0)  out.push("drift reactivation");
  if (t.upper.max    > 0)  out.push("upper-branch emergence");
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

// Immunity thresholds are fixed safe-operating bounds. They describe
// the boundary inside which the system is considered immune.
const THRESHOLD_LINES = [
  "- CZ must remain below 2",
  "- volatility must remain below 2",
  "- drift must remain below 1",
  "- upper-branch must remain at 0",
];

// ----- System-Level Summary ---------------------------------------------

function buildSummary(
  score:      ImmunityScore,
  drivers:    string[],
  inhibitors: string[],
  warnings:   string[],
): string {
  const direction = trajectoryDirection(drivers.length, inhibitors.length, warnings.length);
  const parts: string[] = [];
  parts.push(`The system shows ${score.toLowerCase()} immunity with ${direction} trajectory.`);
  if (inhibitors.length > 0) {
    parts.push(`Primary vulnerabilities: ${inhibitors.join(", ")}.`);
  } else {
    parts.push("No primary vulnerabilities detected.");
  }
  if (warnings.length > 0) {
    parts.push(`Early-warning signals: ${warnings.join(", ")}.`);
  }
  if (drivers.length > 0 && inhibitors.length === 0) {
    parts.push("Immunity is well-positioned and reinforcing.");
  } else if (direction === "improving") {
    parts.push("Immunity is improving but not yet robust.");
  } else if (direction === "deteriorating") {
    parts.push("Immunity is weakening — reinforcement recommended.");
  }
  return parts.join(" ");
}

export function buildStructuralImmunity(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  resilience: string,
): string {
  // `diffs` + `resilience` kept on the signature for spec parity;
  // Phase-1 immunity is computed from the structured signature
  // trends directly.
  void diffs;
  void resilience;

  if (signatures.length === 0) {
    return `=== Structural Immunity ===\n\n(no data)`;
  }

  // Never-active short-circuit: baseline immunity is HIGH because the
  // system has never been challenged. No drivers / inhibitors / warnings
  // exist; thresholds + breach conditions reduce to sentinels.
  const everActive = signatures.some((s) => riskScore(s) > 0);
  if (!everActive) {
    return (
      `=== Structural Immunity ===\n\n` +
      `[Immunity Score]\nHIGH\n\n` +
      `[Immunity Profile]\n` +
      `- strong CZ immunity\n` +
      `- strong volatility immunity\n` +
      `- strong drift immunity\n` +
      `- strong upper-branch immunity\n\n` +
      `[Immunity Trajectory]\nhigh → high → high (stable)\n\n` +
      `[Immunity Drivers]\n(none — system has not faced challenges)\n\n` +
      `[Immunity Inhibitors]\n(none)\n\n` +
      `[Immunity Thresholds]\n${THRESHOLD_LINES.join("\n")}\n\n` +
      `[Immunity Breach Conditions]\n(none — system is not under structural load)\n\n` +
      `[Immunity Reinforcement]\n(none — baseline immunity maintained)\n\n` +
      `[Immunity Decay]\n(none)\n\n` +
      `[Early-Warning Signals]\n(none)\n\n` +
      `[System-Level Immunity Summary]\n` +
      `System has not been challenged. Baseline immunity is HIGH and well-positioned to prevent future instability.`
    );
  }

  const t          = buildTrends(signatures);
  const drivers    = collectDrivers(t);
  const inhibitors = collectInhibitors(t);
  const warnings   = collectEarlyWarning(t);
  const score      = scoreFrom(drivers.length, inhibitors.length, warnings.length);
  const projected  = projectScore(score, drivers.length, inhibitors.length, warnings.length);
  const twoStep    = projectScoreTwoStep(score, projected);
  const direction  = trajectoryDirection(drivers.length, inhibitors.length, warnings.length);
  const profile    = buildProfileObj(t);
  const decay      = collectDecay(t);
  const breach     = collectBreachConditions(t);
  const reinforce  = collectReinforcement(t);

  const blocks: string[] = [];
  blocks.push("=== Structural Immunity ===");
  blocks.push(`[Immunity Score]\n${score}`);
  blocks.push(buildProfileBlock(profile));
  blocks.push(`[Immunity Trajectory]\n${buildTrajectory(score, projected, twoStep, direction)}`);
  blocks.push(
    drivers.length === 0
      ? `[Immunity Drivers]\n(none)`
      : `[Immunity Drivers]\n${drivers.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    inhibitors.length === 0
      ? `[Immunity Inhibitors]\n(none)`
      : `[Immunity Inhibitors]\n${inhibitors.map((i) => `- ${i}`).join("\n")}`,
  );
  blocks.push(`[Immunity Thresholds]\n${THRESHOLD_LINES.join("\n")}`);
  blocks.push(
    breach.length === 0
      ? `[Immunity Breach Conditions]\n(none)`
      : `[Immunity Breach Conditions]\n${breach.map((b) => `- ${b}`).join("\n")}`,
  );
  blocks.push(
    reinforce.length === 0
      ? `[Immunity Reinforcement]\n(none)`
      : `[Immunity Reinforcement]\n${reinforce.map((r) => `- ${r}`).join("\n")}`,
  );
  blocks.push(
    decay.length === 0
      ? `[Immunity Decay]\n(none)`
      : `[Immunity Decay]\n${decay.map((d) => `- ${d}`).join("\n")}`,
  );
  blocks.push(
    warnings.length === 0
      ? `[Early-Warning Signals]\n(none)`
      : `[Early-Warning Signals]\n${warnings.map((w) => `- ${w}`).join("\n")}`,
  );
  blocks.push(`[System-Level Immunity Summary]\n${buildSummary(score, drivers, inhibitors, warnings)}`);

  return blocks.join("\n\n");
}
