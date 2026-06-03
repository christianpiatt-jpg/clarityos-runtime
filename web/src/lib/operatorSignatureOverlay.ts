// Card 52 — Structural signature overlay engine (Phase-2, Tier-2).
//
// First synthesis-layer instrument: stacks every per-run signature and
// every adjacent-pair diff into one unified text snapshot with these
// 11 sections:
//
//   [Run-Level Signatures]
//   [Run-Level Signature Diffs]
//   [Hydraulic Overlay]
//   [Pressure Band Overlay]
//   [Critical-Zone Overlay]
//   [Upper-Branch Overlay]
//   [Volatility Overlay]
//   [Drift Overlay]
//   [Phase-Transition Overlay]
//   [Identity-Shift Overlay]
//   [System-Level Structural Synthesis]
//
// Inputs come pre-computed (Card 50 signatures + Card 51 structured
// diffs) so this helper is purely a synthesis pass — no overlay math
// is duplicated here.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "./operatorSignatureDiff";

// Compress Card 51's "Structural X" labels for the per-pair overlay
// view. "No significant identity shift" maps to "Stabilization" so the
// overlay stays scannable across long sequences.
function shortClassification(type: string): string {
  switch (type) {
    case "Structural Escalation":     return "Escalation";
    case "Structural Relaxation":     return "Relaxation";
    case "Structural Drift":          return "Drift";
    case "Structural Stabilization":  return "Stabilization";
    case "Structural Shift":          return "Shift";
    case "No significant identity shift": return "Stabilization";
    default:                          return type;
  }
}

// Brief synthesis the per-pair overlay puts in parentheses. Empty /
// "no detectable change" notes degrade gracefully to "(stable)".
function briefNotes(notes: string[]): string {
  const meaningful = notes.filter((n) => n !== "no detectable change");
  if (meaningful.length === 0) return "(stable)";
  return `(${meaningful.join(" + ")})`;
}

// Map a per-run signature to a coarse identity state for the system-
// synthesis "identity shift: …" line. Three buckets so the trajectory
// stays compact across long sequences.
function identityState(sig: EngineV1StructuralSignature): "stable" | "transitional" | "escalated" {
  if (sig.regime === "U" || sig.pressureLabel === "high" || sig.pressureLabel === "high+") {
    return "escalated";
  }
  if (sig.regime === "T" || sig.pressureLabel === "medium") {
    return "transitional";
  }
  return "stable";
}

function dedupeChain(parts: string[]): string[] {
  const out: string[] = [];
  for (const p of parts) {
    if (out.length === 0 || out[out.length - 1] !== p) out.push(p);
  }
  return out;
}

function buildRunSignaturesBlock(signatures: EngineV1StructuralSignature[]): string {
  if (signatures.length === 0) return `[Run-Level Signatures]\n(no runs)`;
  return (
    `[Run-Level Signatures]\n` +
    signatures.map((s) => `R${s.runIndex}: ${s.fingerprint}`).join("\n")
  );
}

function buildRunDiffsBlock(diffs: EngineV1StructuralSignatureDiff[]): string {
  if (diffs.length === 0) return `[Run-Level Signature Diffs]\n(no transitions)`;
  return (
    `[Run-Level Signature Diffs]\n` +
    diffs.map((d) =>
      `R${d.fromIndex} → R${d.toIndex}: ${d.fromFingerprint} → ${d.toFingerprint}  ${briefNotes(d.notes)}`,
    ).join("\n")
  );
}

function chainOverlay(label: string, items: string[]): string {
  if (items.length === 0) return `[${label}]\n(empty)`;
  return `[${label}]\n${items.join(" → ")}`;
}

function buildIdentityShiftBlock(diffs: EngineV1StructuralSignatureDiff[]): string {
  if (diffs.length === 0) return `[Identity-Shift Overlay]\n(no transitions)`;
  return (
    `[Identity-Shift Overlay]\n` +
    diffs.map((d) =>
      `R${d.fromIndex} → R${d.toIndex}: ${shortClassification(d.classification)}`,
    ).join("\n")
  );
}

function buildSynthesisBlock(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string {
  if (signatures.length === 0) return `[System-Level Structural Synthesis]\n(no data)`;

  const lines: string[] = [];

  // Aggregate trend detection across all pair diffs.
  const hasHydraulicEsc = diffs.some((d) =>
    d.notes.some((n) => n.startsWith("hydraulic escalation")));
  const hasHydraulicRel = diffs.some((d) =>
    d.notes.some((n) => n.startsWith("hydraulic relaxation")));
  const hasPressUp      = diffs.some((d) =>
    d.notes.some((n) => n.startsWith("pressure escalation")));
  const hasPressDown    = diffs.some((d) =>
    d.notes.some((n) => n.startsWith("pressure relaxation")));
  const hasVolSpike     = diffs.some((d) =>
    d.notes.includes("volatility spike"));
  const hasDriftOnset   = diffs.some((d) =>
    d.notes.includes("drift onset"));
  const hasDriftUp      = diffs.some((d) =>
    d.notes.includes("drift increase"));
  const hasCritExp      = diffs.some((d) =>
    d.notes.includes("critical-zone expansion"));

  // Upper-branch emergence — any 0 → positive transition across runs.
  let hasUpperEmergence = false;
  for (let i = 0; i < signatures.length - 1; i++) {
    if (signatures[i].upperCount === 0 && signatures[i + 1].upperCount > 0) {
      hasUpperEmergence = true;
      break;
    }
  }

  if (hasHydraulicEsc) lines.push("- hydraulic escalation across runs");
  if (hasHydraulicRel) lines.push("- hydraulic relaxation across runs");
  if (hasPressUp)      lines.push("- pressure rising across runs");
  if (hasPressDown)    lines.push("- pressure relaxing across runs");
  if (hasCritExp)      lines.push("- critical-zone expansion");
  if (hasUpperEmergence) lines.push("- upper-branch emergence");
  if (hasVolSpike)     lines.push("- volatility spike");
  if (hasDriftOnset || hasDriftUp) lines.push("- drift onset");

  // Identity-trajectory line — coarse 3-bucket sequence with
  // consecutive duplicates collapsed.
  const trajectory = dedupeChain(signatures.map(identityState));
  lines.push(`- identity shift: ${trajectory.join(" → ")}`);

  return `[System-Level Structural Synthesis]\n${lines.join("\n")}`;
}

export function buildSignatureOverlay(
  signatures: EngineV1StructuralSignature[],
  diffs:      EngineV1StructuralSignatureDiff[],
): string {
  if (signatures.length === 0) {
    return `=== Structural Signature Overlay ===\n\n(no data)`;
  }

  return (
    `=== Structural Signature Overlay ===\n\n` +
    buildRunSignaturesBlock(signatures)                                                   + "\n\n" +
    buildRunDiffsBlock(diffs)                                                             + "\n\n" +
    chainOverlay("Hydraulic Overlay",      signatures.map((s) => s.regime))               + "\n\n" +
    chainOverlay("Pressure Band Overlay",  signatures.map((s) => s.pressureBand))         + "\n\n" +
    chainOverlay("Critical-Zone Overlay",  signatures.map((s) => String(s.critCount)))    + "\n\n" +
    chainOverlay("Upper-Branch Overlay",   signatures.map((s) => String(s.upperCount)))   + "\n\n" +
    chainOverlay("Volatility Overlay",     signatures.map((s) => String(s.volatilityCount))) + "\n\n" +
    chainOverlay("Drift Overlay",          signatures.map((s) => String(s.driftCount)))   + "\n\n" +
    chainOverlay("Phase-Transition Overlay", signatures.map((s) => s.pressureLabel))      + "\n\n" +
    buildIdentityShiftBlock(diffs)                                                        + "\n\n" +
    buildSynthesisBlock(signatures, diffs)
  );
}
