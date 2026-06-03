// Card 53 — Structural trajectory engine unit tests.
//
// Hand-constructed signature arrays so each projection rule + risk +
// opportunity is pinned to a deterministic example. The diff + overlay
// inputs are stubbed because Phase-1 projections derive from
// signatures directly.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralTrajectory } from "../operatorStructuralTrajectory";

function makeSig(overrides: Partial<EngineV1StructuralSignature> = {}): EngineV1StructuralSignature {
  return {
    runIndex:        0,
    regime:          "L",
    pressureSum:     0,
    fingerprint:     "L--",
    signatureToken:  "L-",
    pressureBand:    "--",
    pressureLabel:   "low",
    hasCrit:         false,
    hasUpper:        false,
    hasVolatile:     false,
    hasDrift:        false,
    critCount:       0,
    upperCount:      0,
    volatilityCount: 0,
    driftCount:      0,
    ...overrides,
  };
}

const NO_DIFFS: EngineV1StructuralSignatureDiff[] = [];

describe("Card 53 — buildStructuralTrajectory", () => {
  it("emits the 11 sections in spec order", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralTrajectory(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Trajectory ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Hydraulic Trajectory]")).toBeGreaterThan(idx("=== Structural Trajectory ==="));
    expect(idx("[Pressure Trajectory]")).toBeGreaterThan(idx("[Hydraulic Trajectory]"));
    expect(idx("[Critical-Zone Trajectory]")).toBeGreaterThan(idx("[Pressure Trajectory]"));
    expect(idx("[Upper-Branch Trajectory]")).toBeGreaterThan(idx("[Critical-Zone Trajectory]"));
    expect(idx("[Volatility Trajectory]")).toBeGreaterThan(idx("[Upper-Branch Trajectory]"));
    expect(idx("[Drift Trajectory]")).toBeGreaterThan(idx("[Volatility Trajectory]"));
    expect(idx("[Phase Trajectory]")).toBeGreaterThan(idx("[Drift Trajectory]"));
    expect(idx("[Identity-Shift Trajectory]")).toBeGreaterThan(idx("[Phase Trajectory]"));
    expect(idx("[Projected Structural Risks]")).toBeGreaterThan(idx("[Identity-Shift Trajectory]"));
    expect(idx("[Projected Structural Opportunities]")).toBeGreaterThan(idx("[Projected Structural Risks]"));
    expect(idx("[System-Level Trajectory Summary]")).toBeGreaterThan(idx("[Projected Structural Opportunities]"));
  });

  it("projects continuation + flags stabilization opportunities for a stable laminar baseline", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralTrajectory(sigs, NO_DIFFS, "");

    expect(out).toContain("[Hydraulic Trajectory]\nL → L → L (stable laminar regime)");
    expect(out).toContain("[Pressure Trajectory]\n-- → -- → -- (stable pressure)");
    expect(out).toContain("[Critical-Zone Trajectory]\n0 → 0 → 0 (no critical-zone activity)");
    expect(out).toContain("[Phase Trajectory]\nlow → low → low (phase lock)");
    expect(out).toContain("[Identity-Shift Trajectory]\nstable → stable → stable (identity stable)");
    expect(out).toContain("(no critical-zone activity)");
    // Stabilization opportunities should fire when regime + pressure + drift all stay stable.
    expect(out).toContain("- hydraulic stabilization");
    expect(out).toContain("- pressure plateau");
    expect(out).toContain("- drift normalization");
    // No risks for a fully stable system.
    expect(out).toContain("[Projected Structural Risks]\n(none)");
  });

  it("linearly extrapolates count sequences forward by one step", () => {
    const sigs = [
      makeSig({ runIndex: 0, critCount: 0 }),
      makeSig({ runIndex: 1, critCount: 1 }),
      makeSig({ runIndex: 2, critCount: 3 }),
    ];
    const out = buildStructuralTrajectory(sigs, NO_DIFFS, "");
    // Last increment was +2 → projected = 3 + 2 = 5; trailing increment ≥
    // previous increment (+2 ≥ +1) → "continued critical-zone expansion".
    expect(out).toContain("[Critical-Zone Trajectory]\n0 → 1 → 3 → 5 (continued critical-zone expansion)");
  });

  it("projects hydraulic escalation when the last transition was L → T", () => {
    const sigs = [
      makeSig({ runIndex: 0, regime: "L" }),
      makeSig({ runIndex: 1, regime: "T", pressureSum: 12, pressureBand: "-=", pressureLabel: "medium" }),
    ];
    const out = buildStructuralTrajectory(sigs, NO_DIFFS, "");
    expect(out).toContain("[Hydraulic Trajectory]\nL → T → U (continued hydraulic escalation)");
    // Pressure rose 0 → 12 → projected ≈ 24, still in medium band ==.
    expect(out).toContain("Pressure Trajectory");
    expect(out).toContain("rising pressure");
  });

  it("flags drift amplification + upper-branch overextension as risks", () => {
    const sigs = [
      makeSig({ runIndex: 0, driftCount: 0, upperCount: 0 }),
      makeSig({ runIndex: 1, driftCount: 1, upperCount: 1 }),
      makeSig({ runIndex: 2, driftCount: 2, upperCount: 2 }),
    ];
    const out = buildStructuralTrajectory(sigs, NO_DIFFS, "");
    expect(out).toContain("- drift amplification");
    expect(out).toContain("- upper-branch overextension");
    // Drift projected to grow → drift NOT in opportunities ("drift normalization").
    expect(out).not.toContain("- drift normalization");
  });
});
