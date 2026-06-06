// Card 55 — Structural hotspot engine (Phase-3, Tier-2).
//
// Phone mirror of web/src/lib/operatorStructuralHotspots.ts.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

const SEVERITY_RANK: Record<Severity, number> = {
  LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3,
};

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

function riskLevel(score: number): Severity {
  if (score === 0) return "LOW";
  if (score <= 2)  return "MEDIUM";
  if (score <= 4)  return "HIGH";
  return "CRITICAL";
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

function buildRunHotspots(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Top Run Hotspots]\n(no runs)`;
  const ranked = signatures
    .map((sig) => ({
      sig,
      score:   riskScore(sig),
      level:   riskLevel(riskScore(sig)),
      factors: contributingFactors(sig),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
  const lines = ranked.map((r, i) => {
    const tail = r.factors.length === 0 ? "" : ` (${r.factors.join(" + ")})`;
    return `${i + 1}. R${r.sig.runIndex} — ${r.level}${tail}`;
  });
  return `[Top Run Hotspots]\n${lines.join("\n")}`;
}

interface DimRanking {
  label:      string;
  severity:   Severity;
  sortValue:  number;
  sequence:   string;
}

function dimensionSeverity(
  max: number,
  thresholds: { high: number; medium: number },
): Severity {
  if (max >= thresholds.high)   return "HIGH";
  if (max >= thresholds.medium) return "MEDIUM";
  return "LOW";
}

function pressureSeverity(labels: string[]): { severity: Severity; sortValue: number; sequence: string } {
  if (labels.length === 0) return { severity: "LOW", sortValue: 0, sequence: "(no runs)" };
  const ranks = labels.map((l) => PRESSURE_RANK[l] ?? 0);
  const maxR  = Math.max(...ranks);
  let severity: Severity = "LOW";
  if (maxR >= 2) severity = "HIGH";
  else if (maxR >= 1) severity = "MEDIUM";
  return { severity, sortValue: maxR, sequence: labels.join(" → ") };
}

function buildDimensionHotspots(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Structural-Dimension Hotspots]\n(no runs)`;
  const volCounts   = signatures.map((s) => s.volatilityCount);
  const driftCounts = signatures.map((s) => s.driftCount);
  const critCounts  = signatures.map((s) => s.critCount);
  const upperCounts = signatures.map((s) => s.upperCount);
  const pressureLs  = signatures.map((s) => s.pressureLabel);

  const dims: DimRanking[] = [
    {
      label:    "Volatility",
      severity: dimensionSeverity(Math.max(...volCounts),   { high: 3, medium: 1 }),
      sortValue: Math.max(...volCounts),
      sequence: volCounts.join(" → "),
    },
    {
      label:    "Drift",
      severity: dimensionSeverity(Math.max(...driftCounts), { high: 2, medium: 1 }),
      sortValue: Math.max(...driftCounts),
      sequence: driftCounts.join(" → "),
    },
    {
      label:    "Critical-Zone",
      severity: dimensionSeverity(Math.max(...critCounts),  { high: 3, medium: 1 }),
      sortValue: Math.max(...critCounts),
      sequence: critCounts.join(" → "),
    },
    {
      label:    "Upper-Branch",
      severity: dimensionSeverity(Math.max(...upperCounts), { high: 2, medium: 1 }),
      sortValue: Math.max(...upperCounts),
      sequence: upperCounts.join(" → "),
    },
    (() => {
      const p = pressureSeverity(pressureLs);
      return { label: "Pressure", severity: p.severity, sortValue: p.sortValue, sequence: p.sequence };
    })(),
  ];
  dims.sort((a, b) => {
    const r = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
    if (r !== 0) return r;
    return b.sortValue - a.sortValue;
  });
  const lines = dims.map((d, i) =>
    `${i + 1}. ${d.label} — ${d.severity} (${d.sequence})`,
  );
  return `[Structural-Dimension Hotspots]\n${lines.join("\n")}`;
}

function briefNotes(notes: string[]): string {
  const meaningful = notes.filter((n) => n !== "no detectable change");
  if (meaningful.length === 0) return "(stable)";
  return meaningful.join(" + ");
}

function buildEvolution(diffs: EngineV1StructuralSignatureDiff[]): string {
  if (diffs.length === 0) return `[Hotspot Evolution]\n(no transitions)`;
  const lines = diffs.map((d) =>
    `R${d.fromIndex} → R${d.toIndex}: ${briefNotes(d.notes)}`,
  );
  return `[Hotspot Evolution]\n${lines.join("\n")}`;
}

function buildTrajectory(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Hotspot Trajectory]\n(no runs)`;
  const lines = [
    `- Volatility: ${trendDirection(signatures.map((s) => s.volatilityCount))}`,
    `- Drift: ${trendDirection(signatures.map((s) => s.driftCount))}`,
    `- Critical-Zone: ${trendDirection(signatures.map((s) => s.critCount))}`,
    `- Upper-Branch: ${trendDirection(signatures.map((s) => s.upperCount))}`,
    `- Pressure: ${pressureTrendDirection(signatures.map((s) => s.pressureLabel))}`,
  ];
  return `[Hotspot Trajectory]\n${lines.join("\n")}`;
}

function buildSummary(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return "(no data)";

  const topRuns = signatures
    .map((s) => ({ index: s.runIndex, score: riskScore(s) }))
    .sort((a, b) => b.score - a.score)
    .filter((r) => r.score > 0)
    .slice(0, 2);

  const rising: string[] = [];
  if (trendDirection(signatures.map((s) => s.volatilityCount)) === "rising") rising.push("volatility escalation");
  if (trendDirection(signatures.map((s) => s.driftCount))      === "rising") rising.push("drift onset");
  if (trendDirection(signatures.map((s) => s.critCount))       === "rising") rising.push("critical-zone saturation");
  if (trendDirection(signatures.map((s) => s.upperCount))      === "rising") rising.push("upper-branch emergence");
  if (pressureTrendDirection(signatures.map((s) => s.pressureLabel)) === "rising") rising.push("pressure escalation");

  if (topRuns.length === 0 && rising.length === 0) {
    return "Structural hotspots: none detected. System is operating without elevated risk concentrations.";
  }

  const parts: string[] = [];
  if (topRuns.length > 0) {
    const runIds = topRuns.map((r) => `R${r.index}`).join(", ");
    parts.push(`Structural hotspots are concentrated in ${runIds}`);
  } else {
    parts.push("Structural hotspots are diffuse");
  }
  if (rising.length > 0) {
    parts.push(`driven by ${rising.join(", ")}`);
  }
  return parts.join(", ") + ".";
}

export function buildStructuralHotspots(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
  risk:       string,
): string {
  void risk;

  if (signatures.length === 0) {
    return `=== Structural Hotspots ===\n\n(no data)`;
  }

  const blocks: string[] = [];
  blocks.push("=== Structural Hotspots ===");
  blocks.push(
    `[Top Primitive Hotspots]\n` +
    `(per-primitive ranking requires lineage + overlay context — see Structural Matrix)`,
  );
  blocks.push(buildRunHotspots(signatures));
  blocks.push(buildDimensionHotspots(signatures));
  blocks.push(
    `[Hotspot Clusters]\n` +
    `(primitive clusters require lineage + overlay context — see Structural Matrix)`,
  );
  blocks.push(buildEvolution(diffs));
  blocks.push(buildTrajectory(signatures));
  blocks.push(`[System-Level Hotspot Summary]\n${buildSummary(signatures)}`);

  return blocks.join("\n\n");
}
