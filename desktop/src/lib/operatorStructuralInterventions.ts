// Card 57 — Structural intervention engine (Phase-3, Tier-4).
//
// Desktop mirror of web/src/lib/operatorStructuralInterventions.ts.

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

function regimeTrend(sigs: EngineV1StructuralSignature[]): "rising" | "falling" | "stable" {
  if (sigs.length < 2) return "stable";
  const RANK: Record<string, number> = { L: 0, T: 1, U: 2 };
  const first = RANK[sigs[0].regime];
  const last  = RANK[sigs[sigs.length - 1].regime];
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

function buildRunInterventions(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Run-Level Interventions]\n(no runs)`;

  const blocks: string[] = [];
  for (const sig of signatures) {
    if (riskScore(sig) === 0) continue;
    const actions: string[] = [];
    if (sig.hasVolatile) actions.push("volatility dampening");
    if (sig.hasCrit)     actions.push("CZ containment");
    if (sig.hasDrift)    actions.push("drift suppression");
    if (sig.hasUpper)    actions.push("upper-branch stabilization");
    if (sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
      actions.push("pressure relief");
    }
    if (actions.length === 0) continue;
    blocks.push(
      `R${sig.runIndex}:\n` +
      actions.map((a) => `  - ${a}`).join("\n"),
    );
  }
  if (blocks.length === 0) return `[Run-Level Interventions]\n(no non-LOW runs)`;
  return `[Run-Level Interventions]\n${blocks.join("\n\n")}`;
}

interface DimRecommendation {
  label:   string;
  actions: string[];
}

function dimensionInterventions(
  signatures: EngineV1StructuralSignature[],
): DimRecommendation[] {
  const volCounts   = signatures.map((s) => s.volatilityCount);
  const driftCounts = signatures.map((s) => s.driftCount);
  const critCounts  = signatures.map((s) => s.critCount);
  const upperCounts = signatures.map((s) => s.upperCount);

  const volMax    = Math.max(...volCounts);
  const driftMax  = Math.max(...driftCounts);
  const critMax   = Math.max(...critCounts);
  const upperMax  = Math.max(...upperCounts);

  const volRising   = trendDirection(volCounts)   === "rising";
  const critRising  = trendDirection(critCounts)  === "rising";
  const pressureRising = pressureTrendDirection(signatures.map((s) => s.pressureLabel)) === "rising";
  const regimeRising   = regimeTrend(signatures) === "rising";

  const out: DimRecommendation[] = [];

  if (volMax > 0) {
    const actions = ["apply volatility dampening"];
    if (volRising) actions.push("reduce feedback loops");
    out.push({ label: "Volatility", actions });
  } else {
    out.push({ label: "Volatility", actions: ["(none — no volatility detected)"] });
  }

  if (driftMax > 0) {
    const actions = ["apply drift suppression"];
    if (volRising) actions.push("stabilize upstream volatility");
    out.push({ label: "Drift", actions });
  } else {
    out.push({ label: "Drift", actions: ["(none — no drift detected)"] });
  }

  if (critMax > 0) {
    const actions: string[] = [];
    if (pressureRising) actions.push("reduce pressure");
    actions.push("apply CZ stabilization");
    out.push({ label: "Critical-Zone", actions });
  } else {
    out.push({ label: "Critical-Zone", actions: ["(none — no CZ activity)"] });
  }

  if (upperMax > 0) {
    const actions = ["constrain branching"];
    if (critRising) actions.push("reduce CZ instability");
    out.push({ label: "Upper-Branch", actions });
  } else {
    out.push({ label: "Upper-Branch", actions: ["(none — no upper-branch activity)"] });
  }

  if (pressureRising) {
    out.push({ label: "Pressure", actions: ["apply pressure relief"] });
  } else {
    out.push({ label: "Pressure", actions: ["(none — pressure stable)"] });
  }

  if (regimeRising) {
    out.push({ label: "Hydraulic", actions: ["stabilize regime transitions"] });
  } else {
    out.push({ label: "Hydraulic", actions: ["(none — regime stable)"] });
  }

  return out;
}

function buildDimensionInterventions(
  signatures: EngineV1StructuralSignature[],
): string {
  if (signatures.length === 0) return `[Structural-Dimension Interventions]\n(no runs)`;
  const recs = dimensionInterventions(signatures);
  const blocks = recs.map((r) =>
    `${r.label}:\n${r.actions.map((a) => `  - ${a}`).join("\n")}`,
  );
  return `[Structural-Dimension Interventions]\n${blocks.join("\n\n")}`;
}

function buildIdentityInterventions(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Identity-Shift Interventions]\n(no runs)`;
  const states = signatures.map(identityState);
  const STATE_RANK: Record<IdentityState, number> = {
    stable: 0, transitional: 1, escalated: 2, "escalated+": 3,
  };
  const first = STATE_RANK[states[0]];
  const last  = STATE_RANK[states[states.length - 1]];

  const actions: string[] = [];
  if (last > first) {
    actions.push("reduce escalation drivers");
    actions.push("stabilize structural dimensions");
    actions.push("dampen volatility and drift");
  } else if (last < first) {
    actions.push("monitor for re-escalation");
  } else if (
    states.length >= 3 &&
    states[states.length - 2] !== states[states.length - 1]
  ) {
    actions.push("stabilize identity transitions");
  }

  if (actions.length === 0) {
    return `[Identity-Shift Interventions]\n(none — identity is stable)`;
  }
  return (
    `[Identity-Shift Interventions]\n` +
    actions.map((a) => `- ${a}`).join("\n")
  );
}

function buildSummary(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string {
  if (signatures.length === 0) return "(no data)";

  const actions: string[] = [];
  if (pressureTrendDirection(signatures.map((s) => s.pressureLabel)) === "rising") {
    actions.push("reduce pressure escalation");
  }
  if (trendDirection(signatures.map((s) => s.critCount)) === "rising") {
    actions.push("stabilize CZ");
  }
  if (trendDirection(signatures.map((s) => s.volatilityCount)) === "rising") {
    actions.push("dampen volatility");
  }
  if (trendDirection(signatures.map((s) => s.driftCount)) === "rising") {
    actions.push("suppress drift");
  }
  if (trendDirection(signatures.map((s) => s.upperCount)) === "rising") {
    actions.push("constrain upper-branch emergence");
  }

  const hasVolSpike = diffs.some((d) => d.notes.includes("volatility spike"));
  if (hasVolSpike && !actions.includes("dampen volatility")) {
    actions.push("dampen volatility");
  }

  if (actions.length === 0) {
    return "No interventions required. System is operating within stable bounds.";
  }
  return (
    `Recommended actions:\n` +
    actions.map((a) => `- ${a}`).join("\n")
  );
}

export function buildStructuralInterventions(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  causality:  string,
): string {
  void causality;

  if (signatures.length === 0) {
    return `=== Structural Interventions ===\n\n(no data)`;
  }

  const blocks: string[] = [];
  blocks.push("=== Structural Interventions ===");
  blocks.push(
    `[Primitive-Level Interventions]\n` +
    `(per-primitive interventions require lineage + overlay context — see Structural Matrix)`,
  );
  blocks.push(buildRunInterventions(signatures));
  blocks.push(buildDimensionInterventions(signatures));
  blocks.push(buildIdentityInterventions(signatures));
  blocks.push(`[System-Level Intervention Summary]\n${buildSummary(signatures, diffs)}`);

  return blocks.join("\n\n");
}
