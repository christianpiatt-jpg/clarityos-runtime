// Card 51 — Structural signature diff engine (Phase-2 start).
//
// Phone mirror of web/src/lib/operatorSignatureDiff.ts.

import type { EngineV1StructuralSignature } from "./operatorStructuralSignature";

const REGIME_RANK: Record<"L" | "T" | "U", number> = { L: 0, T: 1, U: 2 };
const PRESSURE_RANK: Record<string, number> = {
  low:     0,
  medium:  1,
  high:    2,
  "high+": 3,
};

function countLabel(from: number, to: number): string {
  if (to > from)  return "(increase)";
  if (to < from)  return "(decrease)";
  return "(no change)";
}

function driftLabel(from: number, to: number): string {
  if (from === 0 && to > 0) return "(onset)";
  if (to > from)            return "(increase)";
  if (to < from)            return "(decrease)";
  return "(no change)";
}

interface Classification {
  type:  string;
  notes: string[];
}

function classify(
  from: EngineV1StructuralSignature,
  to:   EngineV1StructuralSignature,
): Classification {
  const notes: string[] = [];

  const regimeUp   = REGIME_RANK[to.regime] > REGIME_RANK[from.regime];
  const regimeDown = REGIME_RANK[to.regime] < REGIME_RANK[from.regime];
  const pressUp    = PRESSURE_RANK[to.pressureLabel] > PRESSURE_RANK[from.pressureLabel];
  const pressDown  = PRESSURE_RANK[to.pressureLabel] < PRESSURE_RANK[from.pressureLabel];
  const volSpike   = to.volatilityCount > from.volatilityCount && to.volatilityCount > 0;
  const volDrop    = to.volatilityCount < from.volatilityCount;
  const driftOnset = from.driftCount === 0 && to.driftCount > 0;
  const driftUp    = to.driftCount > from.driftCount;
  const critUp     = to.critCount > from.critCount;

  if (regimeUp)   notes.push(`hydraulic escalation (${from.regime} → ${to.regime})`);
  if (regimeDown) notes.push(`hydraulic relaxation (${from.regime} → ${to.regime})`);
  if (pressUp)    notes.push(`pressure escalation (${from.pressureLabel} → ${to.pressureLabel})`);
  if (pressDown)  notes.push(`pressure relaxation (${from.pressureLabel} → ${to.pressureLabel})`);
  if (volSpike)   notes.push("volatility spike");
  if (volDrop && !volSpike) notes.push("volatility decrease");
  if (critUp)     notes.push("critical-zone expansion");
  if (driftOnset) notes.push("drift onset");
  else if (driftUp) notes.push("drift increase");

  let type: string;
  if (driftOnset || driftUp) {
    type = "Structural Drift";
  } else if (regimeUp || pressUp || volSpike) {
    type = "Structural Escalation";
  } else if (regimeDown || pressDown) {
    type = "Structural Relaxation";
  } else if (volDrop && pressDown) {
    type = "Structural Stabilization";
  } else if (notes.length === 0) {
    type = "No significant identity shift";
  } else {
    type = "Structural Shift";
  }

  if (notes.length === 0) notes.push("no detectable change");
  return { type, notes };
}

// Card 52 — structured per-pair diff.
export interface EngineV1StructuralSignatureDiff {
  fromIndex:       number;
  toIndex:         number;
  fromFingerprint: string;
  toFingerprint:   string;
  classification:  string;
  notes:           string[];
}

export function computeSignatureDiff(
  from: EngineV1StructuralSignature,
  to:   EngineV1StructuralSignature,
): EngineV1StructuralSignatureDiff {
  const cls = classify(from, to);
  return {
    fromIndex:       from.runIndex,
    toIndex:         to.runIndex,
    fromFingerprint: from.fingerprint,
    toFingerprint:   to.fingerprint,
    classification:  cls.type,
    notes:           cls.notes,
  };
}

export function buildSignatureDiff(
  fromSig: EngineV1StructuralSignature,
  toSig:   EngineV1StructuralSignature,
): string {
  const cls = classify(fromSig, toSig);

  return (
    `=== Structural Signature Diff ===\n` +
    `Run ${fromSig.runIndex} → Run ${toSig.runIndex}\n\n` +
    `[Fingerprint Diff]\n${fromSig.fingerprint}  →  ${toSig.fingerprint}\n\n` +
    `[Hydraulic Diff]\n${fromSig.regime} → ${toSig.regime}\n\n` +
    `[Pressure Band Diff]\n${fromSig.pressureBand}  →  ${toSig.pressureBand}\n\n` +
    `[Critical-Zone Diff]\n${fromSig.critCount} → ${toSig.critCount}  ${countLabel(fromSig.critCount, toSig.critCount)}\n\n` +
    `[Upper-Branch Diff]\n${fromSig.upperCount} → ${toSig.upperCount}  ${countLabel(fromSig.upperCount, toSig.upperCount)}\n\n` +
    `[Volatility Diff]\n${fromSig.volatilityCount} → ${toSig.volatilityCount}  ${countLabel(fromSig.volatilityCount, toSig.volatilityCount)}\n\n` +
    `[Drift Diff]\n${fromSig.driftCount} → ${toSig.driftCount}  ${driftLabel(fromSig.driftCount, toSig.driftCount)}\n\n` +
    `[Phase-Transition Diff]\n${fromSig.pressureLabel} → ${toSig.pressureLabel}\n\n` +
    `[Identity Shift Classification]\n` +
    `Type: ${cls.type}\n` +
    `Notes:\n` +
    cls.notes.map((n) => `- ${n}`).join("\n")
  );
}
