// Card 54 — Structural risk engine (Phase-3 start).
//
// First diagnostic-layer instrument: assigns LOW / MEDIUM / HIGH /
// CRITICAL risk levels to runs and the system as a whole, then chains
// per-component risk sequences with qualitative annotations.
//
// Twelve sections:
//
//   [Primitive-Level Risk]      Phase-1 sentinel — the inputs are
//                               aggregate-level only; primitive-level
//                               risk requires the lineage + overlay
//                               context the Structural Matrix exposes.
//   [Run-Level Risk]            per-run LOW/MEDIUM/HIGH/CRITICAL with
//                               contributing-factor lists
//   [System-Level Risk]         overall = max run-level
//   [Hydraulic Risk]            regime sequence + escalation note
//   [Pressure Risk]             pressure-band sequence + rising note
//   [Critical-Zone Risk]        crit-count sequence + saturation note
//   [Upper-Branch Risk]         upper-count sequence + emergence note
//   [Volatility Risk]           volatility sequence + lock-in note
//   [Drift Risk]                drift sequence + acceleration note
//   [Identity-Shift Risk]       identity-bucket sequence
//   [Risk Classification]       rule-based bullet list
//   [System-Level Risk Summary] short synthesis paragraph
//
// Risk scoring is deliberately simple: each per-run signature is
// scored by summing weighted flags + pressure-level, then bucketed.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

const PRESSURE_RANK: Record<string, number> = {
  low:     0,
  medium:  1,
  high:    2,
  "high+": 3,
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
  if (sig.hasUpper)    s += 2;  // upper-branch carries more weight
  if (sig.hasVolatile) s += 1;
  if (sig.hasDrift)    s += 2;  // drift carries more weight
  s += PRESSURE_RANK[sig.pressureLabel] ?? 0;
  return s;
}

function riskLevel(score: number): RiskLevel {
  if (score === 0) return "LOW";
  if (score <= 2)  return "MEDIUM";
  if (score <= 4)  return "HIGH";
  return "CRITICAL";
}

function levelRank(level: RiskLevel): number {
  switch (level) {
    case "LOW":      return 0;
    case "MEDIUM":   return 1;
    case "HIGH":     return 2;
    case "CRITICAL": return 3;
  }
}

function contributingFactors(sig: EngineV1StructuralSignature): string[] {
  const out: string[] = [];
  if (sig.hasCrit)     out.push("critical-zone");
  if (sig.hasUpper)    out.push("upper-branch");
  if (sig.hasVolatile) out.push("volatility");
  if (sig.hasDrift)    out.push("drift");
  if (sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
    out.push(`${sig.pressureLabel}-pressure`);
  }
  return out;
}

function buildRunLevelBlock(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Run-Level Risk]\n(no runs)`;
  const lines = signatures.map((sig) => {
    const score   = riskScore(sig);
    const level   = riskLevel(score);
    const factors = contributingFactors(sig);
    const tail    = factors.length === 0 ? "" : `  (${factors.join(" + ")})`;
    return `R${sig.runIndex}: ${level}${tail}`;
  });
  return `[Run-Level Risk]\n${lines.join("\n")}`;
}

function systemRiskLevel(signatures: EngineV1StructuralSignature[]): RiskLevel {
  if (signatures.length === 0) return "LOW";
  let best: RiskLevel = "LOW";
  for (const sig of signatures) {
    const l = riskLevel(riskScore(sig));
    if (levelRank(l) > levelRank(best)) best = l;
  }
  return best;
}

function trendDirection(values: number[]): "rising" | "falling" | "stable" {
  if (values.length < 2) return "stable";
  const last  = values[values.length - 1];
  const first = values[0];
  if (last > first) return "rising";
  if (last < first) return "falling";
  return "stable";
}

function regimeRisk(regimes: ("L" | "T" | "U")[]): string {
  if (regimes.length === 0) return "[Hydraulic Risk]\n(no runs)";
  const RANK: Record<string, number> = { L: 0, T: 1, U: 2 };
  const first = RANK[regimes[0]];
  const last  = RANK[regimes[regimes.length - 1]];
  let note: string;
  if (last > first) note = "escalation";
  else if (last < first) note = "relaxation";
  else if (last === 0) note = "stable laminar";
  else if (last === 2) note = "stable turbulent";
  else note = "stable transitional";
  return `[Hydraulic Risk]\n${regimes.join(" → ")} (${note})`;
}

function pressureBandRisk(bands: string[]): string {
  if (bands.length === 0) return "[Pressure Risk]\n(no runs)";
  const RANK: Record<string, number> = { "--": 0, "-=": 1, "==": 2, "##": 3, "###": 4 };
  const first = RANK[bands[0]]                  ?? 0;
  const last  = RANK[bands[bands.length - 1]]  ?? 0;
  let note: string;
  if (last > first) note = "rising";
  else if (last < first) note = "falling";
  else note = "stable";
  return `[Pressure Risk]\n${bands.join(" → ")} (${note})`;
}

function countRisk(label: string, counts: number[], rising: string, stable: string): string {
  if (counts.length === 0) return `[${label}]\n(no runs)`;
  const last = counts[counts.length - 1];
  const dir  = trendDirection(counts);
  let note: string;
  if (last === 0 && dir === "stable")        note = "no activity";
  else if (dir === "rising")                 note = rising;
  else if (dir === "falling")                note = "decreasing";
  else                                       note = stable;
  return `[${label}]\n${counts.join(" → ")} (${note})`;
}

function identityShiftRisk(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return "[Identity-Shift Risk]\n(no runs)";
  const states = signatures.map(identityState);
  return `[Identity-Shift Risk]\n${states.join(" → ")}`;
}

function classify(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string[] {
  const out: string[] = [];
  if (signatures.length === 0) return out;
  const last = signatures[signatures.length - 1];

  // Volatility lock-in: high (≥ 3) and either rising or stable for the
  // last two runs.
  if (last.volatilityCount >= 3) {
    if (signatures.length >= 2) {
      const prev = signatures[signatures.length - 2];
      if (last.volatilityCount >= prev.volatilityCount) out.push("volatility lock-in");
    } else {
      out.push("volatility lock-in");
    }
  }

  // Drift amplification: drift active AND increasing.
  if (
    last.driftCount > 0 &&
    signatures.length >= 2 &&
    last.driftCount > signatures[signatures.length - 2].driftCount
  ) {
    out.push("drift amplification");
  }

  // Critical-zone saturation: high counts (≥ 3) AND non-decreasing.
  if (
    last.critCount >= 3 &&
    (signatures.length < 2 || last.critCount >= signatures[signatures.length - 2].critCount)
  ) {
    out.push("critical-zone saturation");
  }

  // Upper-branch overextension: upper > 0 AND grew at last transition.
  if (
    last.upperCount > 0 &&
    signatures.length >= 2 &&
    last.upperCount > signatures[signatures.length - 2].upperCount
  ) {
    out.push("upper-branch overextension");
  }

  // Surface any classification labels carried by the most recent diff
  // that don't otherwise appear, so the classification block stays in
  // sync with Card 51's reasoning.
  const lastDiff = diffs[diffs.length - 1];
  if (lastDiff) {
    for (const note of lastDiff.notes) {
      if (note === "volatility spike" && !out.includes("volatility lock-in")) {
        out.push("volatility spike");
      }
    }
  }

  return out;
}

function buildSummary(
  signatures: EngineV1StructuralSignature[],
  overall:    RiskLevel,
  classes:    string[],
): string {
  if (signatures.length === 0) return "(no data)";
  const last = signatures[signatures.length - 1];

  const traits: string[] = [];
  if (last.pressureLabel === "high" || last.pressureLabel === "high+") {
    traits.push(`${last.pressureLabel}-pressure`);
  }
  if (last.volatilityCount >= 3) traits.push("high-volatility");
  if (last.upperCount > 0)       traits.push("upper-branch-emergent");

  const parts: string[] = [];
  const traitsClause = traits.length > 0
    ? `a ${traits.join(", ")} regime`
    : `a stable regime`;
  parts.push(`The system is operating in ${traitsClause}.`);

  if (classes.length > 0) {
    parts.push(`Risk classifications: ${classes.join(", ")}.`);
  }

  parts.push(`Structural risk level: ${overall}.`);
  return parts.join(" ");
}

export function buildStructuralRisk(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  trajectory: string,
): string {
  // `trajectory` kept for spec parity; Phase-1 risk derives from the
  // structured signature sequence + diff notes directly.
  void trajectory;

  if (signatures.length === 0) {
    return `=== Structural Risk Assessment ===\n\n(no data)`;
  }

  const overall = systemRiskLevel(signatures);
  const classes = classify(signatures, diffs);

  const primitiveBlock =
    `[Primitive-Level Risk]\n` +
    `(per-primitive risk requires lineage + overlay context — see Structural Matrix)`;

  const blocks: string[] = [];
  blocks.push("=== Structural Risk Assessment ===");
  blocks.push(primitiveBlock);
  blocks.push(buildRunLevelBlock(signatures));
  blocks.push(`[System-Level Risk]\nOverall: ${overall}`);
  blocks.push(regimeRisk(signatures.map((s) => s.regime)));
  blocks.push(pressureBandRisk(signatures.map((s) => s.pressureBand)));
  blocks.push(countRisk(
    "Critical-Zone Risk",
    signatures.map((s) => s.critCount),
    "saturation approaching", "saturation",
  ));
  blocks.push(countRisk(
    "Upper-Branch Risk",
    signatures.map((s) => s.upperCount),
    "emergence", "stable",
  ));
  blocks.push(countRisk(
    "Volatility Risk",
    signatures.map((s) => s.volatilityCount),
    "lock-in approaching", "lock-in",
  ));
  blocks.push(countRisk(
    "Drift Risk",
    signatures.map((s) => s.driftCount),
    "acceleration", "stable",
  ));
  blocks.push(identityShiftRisk(signatures));
  blocks.push(
    classes.length === 0
      ? `[Risk Classification]\n(none)`
      : `[Risk Classification]\n${classes.map((c) => `- ${c}`).join("\n")}`,
  );
  blocks.push(`[System-Level Risk Summary]\n${buildSummary(signatures, overall, classes)}`);

  return blocks.join("\n\n");
}
