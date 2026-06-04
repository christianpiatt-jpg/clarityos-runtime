// Card 56 — Structural causality engine (Phase-3, Tier-3).
//
// Desktop mirror of web/src/lib/operatorStructuralCausality.ts.

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

function trendDirection(values: number[]): "rising" | "falling" | "stable" {
  if (values.length < 2) return "stable";
  const last  = values[values.length - 1];
  const first = values[0];
  if (last > first) return "rising";
  if (last < first) return "falling";
  return "stable";
}

function pressureTrendDirection(labels: string[]): "rising" | "falling" | "stable" {
  if (labels.length < 2) return "stable";
  const first = PRESSURE_RANK[labels[0]]                  ?? 0;
  const last  = PRESSURE_RANK[labels[labels.length - 1]] ?? 0;
  if (last > first) return "rising";
  if (last < first) return "falling";
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

function rootCauseForRun(
  sig:      EngineV1StructuralSignature,
  diff:     EngineV1StructuralSignatureDiff | undefined,
): string {
  if (sig.hasUpper && sig.hasDrift)           return "structural overload";
  if (diff?.notes.some((n) => n.startsWith("pressure escalation"))) return "pressure escalation";
  if (sig.hasVolatile && sig.hasDrift)        return "volatility-driven drift";
  if (sig.hasVolatile)                        return "volatility spike";
  if (sig.hasCrit)                            return "CZ instability";
  if (sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
    return "pressure escalation";
  }
  return "diffuse cause";
}

function buildRunCausality(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string {
  if (signatures.length === 0) return `[Run-Level Causality]\n(no runs)`;

  const diffByDest = new Map<number, EngineV1StructuralSignatureDiff>();
  for (const d of diffs) diffByDest.set(d.toIndex, d);

  const blocks: string[] = [];
  for (const sig of signatures) {
    if (riskScore(sig) === 0) continue;
    const factors: string[] = [];
    if (sig.hasCrit)     factors.push("critical-zone");
    if (sig.hasUpper)    factors.push("upper-branch emergence");
    if (sig.hasVolatile) factors.push("volatility spike");
    if (sig.hasDrift)    factors.push("drift onset");
    if (sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
      factors.push(`${sig.pressureLabel}-pressure`);
    }
    const root = rootCauseForRun(sig, diffByDest.get(sig.runIndex));
    blocks.push(
      `R${sig.runIndex}:\n` +
      `  Causes:\n` +
      (factors.length === 0 ? `    - (none)` : factors.map((f) => `    - ${f}`).join("\n")) + "\n" +
      `  Root Cause: ${root}`,
    );
  }
  if (blocks.length === 0) return `[Run-Level Causality]\n(no non-LOW runs)`;
  return `[Run-Level Causality]\n${blocks.join("\n\n")}`;
}

interface DimensionInputs {
  vol:   number[];
  drift: number[];
  crit:  number[];
  upper: number[];
}

function buildDimensionCausality(
  signatures: EngineV1StructuralSignature[],
): string {
  if (signatures.length === 0) return `[Structural-Dimension Causality]\n(no runs)`;

  const counts: DimensionInputs = {
    vol:   signatures.map((s) => s.volatilityCount),
    drift: signatures.map((s) => s.driftCount),
    crit:  signatures.map((s) => s.critCount),
    upper: signatures.map((s) => s.upperCount),
  };
  const pressureRising = pressureTrendDirection(signatures.map((s) => s.pressureLabel)) === "rising";

  function dimBlock(label: string, chain: number[], rootCause: string): string {
    return (
      `${label}:\n` +
      `  Cause Chain: ${chain.join(" → ")}\n` +
      `  Root Cause: ${rootCause}`
    );
  }

  const volRising   = trendDirection(counts.vol)   === "rising";
  const driftRising = trendDirection(counts.drift) === "rising";
  const critRising  = trendDirection(counts.crit)  === "rising";
  const upperRising = trendDirection(counts.upper) === "rising";

  const volRoot = volRising
    ? "compounding volatility feedback"
    : (Math.max(...counts.vol) === 0 ? "no volatility detected" : "stable volatility");
  const driftRoot = driftRising
    ? (volRising ? "volatility-induced drift" : "drift accumulation")
    : (Math.max(...counts.drift) === 0 ? "no drift detected" : "stable drift");
  const critRoot = critRising
    ? (pressureRising ? "pressure-driven CZ saturation" : "CZ accumulation")
    : (Math.max(...counts.crit) === 0 ? "no CZ activity" : "stable CZ load");
  const upperRoot = upperRising
    ? (critRising ? "CZ instability" : "structural overload")
    : (Math.max(...counts.upper) === 0 ? "no upper-branch activity" : "stable upper-branch");

  const blocks: string[] = [];
  blocks.push(dimBlock("Volatility",     counts.vol,   volRoot));
  blocks.push(dimBlock("Drift",          counts.drift, driftRoot));
  blocks.push(dimBlock("Critical-Zone",  counts.crit,  critRoot));
  blocks.push(dimBlock("Upper-Branch",   counts.upper, upperRoot));

  return `[Structural-Dimension Causality]\n${blocks.join("\n\n")}`;
}

function buildIdentityCausality(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Identity-Shift Causality]\n(no runs)`;
  const states = signatures.map(identityState);
  const STATE_RANK: Record<IdentityState, number> = {
    stable: 0, transitional: 1, escalated: 2, "escalated+": 3,
  };
  const first = STATE_RANK[states[0]];
  const last  = STATE_RANK[states[states.length - 1]];

  let root: string;
  if (last > first && last - first >= 2)       root = "multi-dimensional escalation";
  else if (last > first)                       root = "structural escalation";
  else if (last < first)                       root = "structural relaxation";
  else if (states.length >= 3 &&
           states[states.length - 2] !== states[states.length - 1]) {
    root = "structural oscillation";
  }
  else                                         root = "stable identity";

  return (
    `[Identity-Shift Causality]\n` +
    `${states.join(" → ")}\n` +
    `Root Cause: ${root}`
  );
}

function buildSummary(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string {
  if (signatures.length === 0) return "(no data)";

  const links: string[] = [];
  if (pressureTrendDirection(signatures.map((s) => s.pressureLabel)) === "rising") {
    links.push("pressure escalation");
  }
  if (trendDirection(signatures.map((s) => s.critCount))  === "rising") {
    links.push("CZ instability");
  }
  if (trendDirection(signatures.map((s) => s.volatilityCount)) === "rising") {
    links.push("volatility spike");
  }
  if (trendDirection(signatures.map((s) => s.driftCount)) === "rising") {
    links.push("drift onset");
  }
  if (trendDirection(signatures.map((s) => s.upperCount)) === "rising") {
    links.push("upper-branch emergence");
  }

  const hasVolSpike = diffs.some((d) => d.notes.includes("volatility spike"));
  if (hasVolSpike && !links.includes("volatility spike")) {
    links.push("volatility spike");
  }

  if (links.length === 0) {
    return "Structural causality: no causal chain detected. System is operating in a stable regime.";
  }
  if (links.length === 1) {
    return `Structural instability traces back to ${links[0]}.`;
  }
  return (
    `Structural instability is driven by a compounding chain:\n` +
    `${links.join(" → ")}.`
  );
}

export function buildStructuralCausality(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  hotspots:   string,
): string {
  void hotspots;

  if (signatures.length === 0) {
    return `=== Structural Causality ===\n\n(no data)`;
  }

  const blocks: string[] = [];
  blocks.push("=== Structural Causality ===");
  blocks.push(
    `[Primitive-Level Causality]\n` +
    `(per-primitive causal chains require lineage + overlay context — see Structural Matrix)`,
  );
  blocks.push(buildRunCausality(signatures, diffs));
  blocks.push(buildDimensionCausality(signatures));
  blocks.push(buildIdentityCausality(signatures));
  blocks.push(`[System-Level Causal Summary]\n${buildSummary(signatures, diffs)}`);

  return blocks.join("\n\n");
}
