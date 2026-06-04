// Card 53 — Structural trajectory engine (Phase-2, Tier-3).
//
// Phone mirror of web/src/lib/operatorStructuralTrajectory.ts.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import {
  pressureBandSymbol,
  pressureLevelLabel,
} from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

const REGIME_RANK:   Record<"L" | "T" | "U", number> = { L: 0, T: 1, U: 2 };
const REGIME_FROM_RANK: Record<number, "L" | "T" | "U"> = { 0: "L", 1: "T", 2: "U" };

type IdentityState = "stable" | "transitional" | "escalated" | "escalated+";
const IDENTITY_RANK: Record<IdentityState, number> = {
  stable:        0,
  transitional:  1,
  escalated:     2,
  "escalated+":  3,
};
const IDENTITY_FROM_RANK: Record<number, IdentityState> = {
  0: "stable",
  1: "transitional",
  2: "escalated",
  3: "escalated+",
};

function identityState(sig: EngineV1StructuralSignature): IdentityState {
  if (sig.regime === "U" || sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
    return "escalated";
  }
  if (sig.regime === "T" || sig.pressureLabel === "medium") {
    return "transitional";
  }
  return "stable";
}

interface Projection<T> {
  sequence:  T[];
  projected: T;
  note:      string;
}

function buildLine(label: string, p: Projection<string | number>): string {
  if (p.sequence.length === 0) return `[${label}]\n(no data)`;
  return `[${label}]\n${p.sequence.join(" → ")} → ${p.projected} (${p.note})`;
}

function projectRegime(regimes: ("L" | "T" | "U")[]): Projection<string> {
  if (regimes.length === 0) return { sequence: [], projected: "L", note: "no data" };
  if (regimes.length === 1) {
    return { sequence: regimes, projected: regimes[0], note: "single-run projection" };
  }
  const last = regimes[regimes.length - 1];
  const prev = regimes[regimes.length - 2];
  const inc  = REGIME_RANK[last] - REGIME_RANK[prev];
  let projected: "L" | "T" | "U";
  if (inc > 0) projected = REGIME_FROM_RANK[Math.min(2, REGIME_RANK[last] + 1)];
  else if (inc < 0) projected = REGIME_FROM_RANK[Math.max(0, REGIME_RANK[last] - 1)];
  else projected = last;

  let note: string;
  if (last === "U" && projected === "U") note = "projected stabilization at high regime";
  else if (inc > 0) note = "continued hydraulic escalation";
  else if (inc < 0) note = "continued hydraulic relaxation";
  else if (last === "L") note = "stable laminar regime";
  else note = "stable regime";

  return { sequence: regimes, projected, note };
}

function projectCount(counts: number[], domainNoun: string): Projection<number> {
  if (counts.length === 0) return { sequence: [], projected: 0, note: "no data" };
  if (counts.length === 1) {
    return { sequence: counts, projected: counts[0], note: "single-run projection" };
  }
  const last = counts[counts.length - 1];
  const prev = counts[counts.length - 2];
  const inc  = last - prev;
  const projected = Math.max(0, last + inc);

  let note: string;
  if (inc > 0 && counts.length >= 3) {
    const prevInc = counts[counts.length - 2] - counts[counts.length - 3];
    if (inc >= prevInc) note = `continued ${domainNoun} expansion`;
    else                note = `decelerating ${domainNoun} expansion`;
  } else if (inc > 0) {
    note = `continued ${domainNoun} expansion`;
  } else if (inc < 0) {
    note = `${domainNoun} contraction`;
  } else if (last === 0) {
    note = `no ${domainNoun} activity`;
  } else {
    note = `${domainNoun} plateau`;
  }
  return { sequence: counts, projected, note };
}

function projectPressureBand(sigs: EngineV1StructuralSignature[]): Projection<string> {
  if (sigs.length === 0) return { sequence: [], projected: "--", note: "no data" };
  const bands = sigs.map((s) => s.pressureBand);
  if (sigs.length === 1) {
    return { sequence: bands, projected: bands[0], note: "single-run projection" };
  }
  const sums = sigs.map((s) => s.pressureSum);
  const last = sums[sums.length - 1];
  const prev = sums[sums.length - 2];
  const inc  = last - prev;
  const projected = pressureBandSymbol(Math.max(0, last + inc));
  const lastBand  = bands[bands.length - 1];

  let note: string;
  if (projected === lastBand && inc !== 0) note = "plateau";
  else if (projected === lastBand)         note = "stable pressure";
  else if (inc > 0)                        note = "rising pressure";
  else                                     note = "falling pressure";

  return { sequence: bands, projected, note };
}

function projectPhase(sigs: EngineV1StructuralSignature[]): Projection<string> {
  if (sigs.length === 0) return { sequence: [], projected: "low", note: "no data" };
  const labels = sigs.map((s) => s.pressureLabel);
  if (sigs.length === 1) {
    return { sequence: labels, projected: labels[0], note: "single-run projection" };
  }
  const sums = sigs.map((s) => s.pressureSum);
  const last = sums[sums.length - 1];
  const prev = sums[sums.length - 2];
  const inc  = last - prev;
  const projected = pressureLevelLabel(Math.max(0, last + inc));
  const lastLabel = labels[labels.length - 1];

  let note: string;
  if (projected === lastLabel) note = "phase lock";
  else if (inc > 0)            note = "phase escalation";
  else                         note = "phase relaxation";

  return { sequence: labels, projected, note };
}

function projectIdentity(sigs: EngineV1StructuralSignature[]): Projection<string> {
  if (sigs.length === 0) return { sequence: [], projected: "stable", note: "no data" };
  const states = sigs.map(identityState);
  if (sigs.length === 1) {
    return { sequence: states, projected: states[0], note: "single-run projection" };
  }
  const last = states[states.length - 1];
  const prev = states[states.length - 2];
  const inc  = IDENTITY_RANK[last] - IDENTITY_RANK[prev];
  let projectedRank: number;
  if (inc > 0) projectedRank = Math.min(3, IDENTITY_RANK[last] + 1);
  else if (inc < 0) projectedRank = Math.max(0, IDENTITY_RANK[last] - 1);
  else projectedRank = IDENTITY_RANK[last];
  const projected = IDENTITY_FROM_RANK[projectedRank];

  let note: string;
  if (projected === "escalated+")           note = "identity consolidation";
  else if (projected === last && inc !== 0) note = "identity plateau";
  else if (projected === last)              note = "identity stable";
  else if (inc > 0)                         note = "identity escalation";
  else                                      note = "identity relaxation";

  return { sequence: states, projected, note };
}

interface ProjectionBundle {
  regime:    Projection<string>;
  pressure:  Projection<string>;
  crit:      Projection<number>;
  upper:     Projection<number>;
  vol:       Projection<number>;
  drift:     Projection<number>;
  phase:     Projection<string>;
  identity:  Projection<string>;
}

function detectRisks(sigs: EngineV1StructuralSignature[], p: ProjectionBundle): string[] {
  const out: string[] = [];
  if (sigs.length === 0) return out;
  const last = sigs[sigs.length - 1];

  if (last.driftCount > 0 && p.drift.projected > last.driftCount) {
    out.push("drift amplification");
  }
  if (last.volatilityCount >= 3 && Math.abs(p.vol.projected - last.volatilityCount) <= 1) {
    out.push("volatility lock-in");
  }
  if (sigs.length >= 2 && last.critCount > 0 && last.critCount >= sigs[sigs.length - 2].critCount) {
    out.push("critical-zone saturation");
  }
  if (sigs.length >= 2 && last.upperCount > 0 && last.upperCount > sigs[sigs.length - 2].upperCount) {
    out.push("upper-branch overextension");
  }
  return out;
}

function detectOpportunities(
  sigs: EngineV1StructuralSignature[],
  p:    ProjectionBundle,
): string[] {
  const out: string[] = [];
  if (sigs.length === 0) return out;
  const last = sigs[sigs.length - 1];

  if (
    sigs.length >= 2 &&
    sigs[sigs.length - 1].regime === sigs[sigs.length - 2].regime &&
    p.regime.projected === last.regime
  ) {
    out.push("hydraulic stabilization");
  }
  if (sigs.length >= 2 && p.pressure.projected === last.pressureBand) {
    out.push("pressure plateau");
  }
  if (sigs.length >= 2 && p.vol.projected < last.volatilityCount) {
    out.push("volatility containment");
  }
  if (last.driftCount === 0 || p.drift.projected < last.driftCount) {
    out.push("drift normalization");
  }
  return out;
}

function buildSummary(
  sigs:  EngineV1StructuralSignature[],
  p:     ProjectionBundle,
  risks: string[],
  opps:  string[],
): string {
  if (sigs.length === 0) return "(no data)";

  const projPhase    = p.phase.projected;
  const projRegime   = p.regime.projected;
  const projIdentity = p.identity.projected;
  const parts: string[] = [];
  parts.push(
    `The system is trending toward a ${projPhase}-pressure, ${projRegime}-regime configuration `
    + `with projected identity state "${projIdentity}".`,
  );
  if (risks.length > 0) {
    parts.push(`Risks: ${risks.join(", ")}.`);
  }
  if (opps.length > 0) {
    parts.push(`Opportunities: ${opps.join(", ")}.`);
  }
  return parts.join(" ");
}

export function buildStructuralTrajectory(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  overlay:    string,
): string {
  void diffs;
  void overlay;

  if (signatures.length === 0) {
    return `=== Structural Trajectory ===\n\n(no data)`;
  }

  const bundle: ProjectionBundle = {
    regime:    projectRegime(signatures.map((s) => s.regime)),
    pressure:  projectPressureBand(signatures),
    crit:      projectCount(signatures.map((s) => s.critCount),       "critical-zone"),
    upper:     projectCount(signatures.map((s) => s.upperCount),      "upper-branch"),
    vol:       projectCount(signatures.map((s) => s.volatilityCount), "volatility"),
    drift:     projectCount(signatures.map((s) => s.driftCount),      "drift"),
    phase:     projectPhase(signatures),
    identity:  projectIdentity(signatures),
  };

  const risks = detectRisks(signatures, bundle);
  const opps  = detectOpportunities(signatures, bundle);

  const risksBlock = risks.length === 0
    ? `[Projected Structural Risks]\n(none)`
    : `[Projected Structural Risks]\n${risks.map((r) => `- ${r}`).join("\n")}`;
  const oppsBlock = opps.length === 0
    ? `[Projected Structural Opportunities]\n(none)`
    : `[Projected Structural Opportunities]\n${opps.map((o) => `- ${o}`).join("\n")}`;

  return (
    `=== Structural Trajectory ===\n\n` +
    buildLine("Hydraulic Trajectory",    bundle.regime)   + "\n\n" +
    buildLine("Pressure Trajectory",     bundle.pressure) + "\n\n" +
    buildLine("Critical-Zone Trajectory", bundle.crit)    + "\n\n" +
    buildLine("Upper-Branch Trajectory", bundle.upper)    + "\n\n" +
    buildLine("Volatility Trajectory",   bundle.vol)      + "\n\n" +
    buildLine("Drift Trajectory",        bundle.drift)    + "\n\n" +
    buildLine("Phase Trajectory",        bundle.phase)    + "\n\n" +
    buildLine("Identity-Shift Trajectory", bundle.identity) + "\n\n" +
    risksBlock + "\n\n" +
    oppsBlock  + "\n\n" +
    `[System-Level Trajectory Summary]\n${buildSummary(signatures, bundle, risks, opps)}`
  );
}
