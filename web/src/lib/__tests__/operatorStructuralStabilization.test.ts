// Card 58 — Structural stabilization engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralStabilization } from "../operatorStructuralStabilization";

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

describe("Card 58 — buildStructuralStabilization", () => {
  it("emits the 8 sections in spec order for an active system", () => {
    const sigs = [
      makeSig({ runIndex: 0, hasCrit: true, hasVolatile: true,
                critCount: 2, volatilityCount: 2,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
      makeSig({ runIndex: 1, hasCrit: true, hasVolatile: true,
                critCount: 1, volatilityCount: 1,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
    ];
    const out = buildStructuralStabilization(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Stabilization ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Stabilization Indicators]")).toBeGreaterThan(idx("=== Structural Stabilization ==="));
    expect(idx("[Stabilization Window]")).toBeGreaterThan(idx("[Stabilization Indicators]"));
    expect(idx("[Stabilization Probability]")).toBeGreaterThan(idx("[Stabilization Window]"));
    expect(idx("[Stabilization Trajectory]")).toBeGreaterThan(idx("[Stabilization Probability]"));
    expect(idx("[Stabilization Blockers]")).toBeGreaterThan(idx("[Stabilization Trajectory]"));
    expect(idx("[Stabilization Accelerators]")).toBeGreaterThan(idx("[Stabilization Blockers]"));
    expect(idx("[Post-Intervention Effects]")).toBeGreaterThan(idx("[Stabilization Accelerators]"));
    expect(idx("[System-Level Stabilization Summary]")).toBeGreaterThan(idx("[Post-Intervention Effects]"));
  });

  it("short-circuits with 'already stable' when the system has never carried risk", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralStabilization(sigs, NO_DIFFS, "");

    expect(out).toContain("(none — system has not shown structural risk)");
    expect(out).toContain("[Stabilization Window]\nnot needed");
    expect(out).toContain("[Stabilization Probability]\nN/A");
    expect(out).toContain("(already stable)");
    expect(out).toContain("Volatility: no activity");
    expect(out).toContain("No stabilization assessment needed. System is operating within stable bounds.");
  });

  it("fires stabilization indicators for decaying / flat / plateau dimensions", () => {
    // Run 0: heavy load. Run 1: dimensions decaying (volatility 3 → 2,
    // crit 3 → 2, pressure medium → medium plateau, regime T → T flat).
    const sigs = [
      makeSig({
        runIndex:        0,
        regime:          "T",
        hasCrit:         true,
        hasVolatile:     true,
        critCount:       3,
        volatilityCount: 3,
        pressureLabel:   "medium",
        pressureSum:     30,
        pressureBand:    "==",
      }),
      makeSig({
        runIndex:        1,
        regime:          "T",
        hasCrit:         true,
        hasVolatile:     true,
        critCount:       2,
        volatilityCount: 2,
        pressureLabel:   "medium",
        pressureSum:     30,
        pressureBand:    "==",
      }),
    ];
    const out = buildStructuralStabilization(sigs, NO_DIFFS, "");

    expect(out).toContain("- volatility decay detected");
    expect(out).toContain("- CZ relaxation beginning");
    expect(out).toContain("- pressure plateau forming");
    expect(out).toContain("- hydraulic stabilization");
    // Drift was never active (0 → 0) so the "flattening" indicator
    // intentionally does not fire — a dormant dimension is not
    // recovering, it just isn't engaged.
    expect(out).not.toContain("- drift slope flattening");
    // 4 indicators → HIGH probability + 1–2 run window.
    expect(out).toContain("[Stabilization Probability]\nHIGH");
    expect(out).toContain("[Stabilization Window]\nProjected: next 1–2 runs");
    // Identity sequence + projected → stabilized.
    expect(out).toContain("transitional → transitional → stabilized (projected)");
  });

  it("flags remaining blockers + accelerators in progress", () => {
    const sigs = [
      makeSig({
        runIndex:        0,
        regime:          "U",
        hasCrit:         true,
        hasUpper:        true,
        hasDrift:        true,
        hasVolatile:     true,
        critCount:       4,
        upperCount:      2,
        volatilityCount: 4,
        driftCount:      2,
        pressureLabel:   "high+",
        pressureSum:     70,
        pressureBand:    "###",
      }),
      makeSig({
        runIndex:        1,
        regime:          "U",
        hasCrit:         true,
        hasUpper:        true,
        hasDrift:        true,
        hasVolatile:     true,
        critCount:       4,
        upperCount:      1,
        volatilityCount: 3,
        driftCount:      1,
        pressureLabel:   "high",
        pressureSum:     45,
        pressureBand:    "##",
      }),
    ];
    const out = buildStructuralStabilization(sigs, NO_DIFFS, "");

    // Blockers — last drift / upper / crit / vol all still ≥ thresholds.
    expect(out).toContain("- residual drift pressure");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- critical-zone saturation");
    // Accelerators — volatility / drift / upper / pressure all decayed.
    expect(out).toContain("- volatility dampening");
    expect(out).toContain("- pressure relief");
    expect(out).toContain("- drift suppression");
    expect(out).toContain("- upper-branch constraint");
  });

  it("captures decreasing / rising dimension status in the post-intervention block", () => {
    const sigs = [
      makeSig({
        runIndex:        0,
        regime:          "T",
        hasCrit:         true,
        hasVolatile:     true,
        critCount:       2,
        volatilityCount: 2,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
      makeSig({
        runIndex:        1,
        regime:          "U",
        hasCrit:         true,
        hasUpper:        true,
        hasDrift:        true,
        hasVolatile:     true,
        critCount:       4,        // rising
        upperCount:      2,        // rising (was 0)
        volatilityCount: 1,        // decreasing
        driftCount:      1,        // rising (was 0)
        pressureLabel:   "high",
        pressureSum:     45,
        pressureBand:    "##",
      }),
    ];
    const out = buildStructuralStabilization(sigs, NO_DIFFS, "");

    // Volatility went 2 → 1 → decreasing.
    expect(out).toContain("Volatility: decreasing");
    // CZ went 2 → 4 → rising.
    expect(out).toContain("CZ: rising");
    // Drift went 0 → 1 → rising.
    expect(out).toContain("Drift: rising");
    // Upper-Branch went 0 → 2 → rising.
    expect(out).toContain("Upper-Branch: rising");
  });
});
