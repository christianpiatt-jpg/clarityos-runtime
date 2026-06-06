// Card 59 — Structural resilience engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralResilience } from "../operatorStructuralResilience";

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

describe("Card 59 — buildStructuralResilience", () => {
  it("emits the 9 sections in spec order for an active system", () => {
    const sigs = [
      makeSig({ runIndex: 0, hasCrit: true, hasVolatile: true,
                critCount: 2, volatilityCount: 2,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
      makeSig({ runIndex: 1, hasCrit: true, hasVolatile: true,
                critCount: 1, volatilityCount: 1,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
    ];
    const out = buildStructuralResilience(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Resilience ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Resilience Score]")).toBeGreaterThan(idx("=== Structural Resilience ==="));
    expect(idx("[Resilience Profile]")).toBeGreaterThan(idx("[Resilience Score]"));
    expect(idx("[Resilience Trajectory]")).toBeGreaterThan(idx("[Resilience Profile]"));
    expect(idx("[Resilience Drivers]")).toBeGreaterThan(idx("[Resilience Trajectory]"));
    expect(idx("[Resilience Inhibitors]")).toBeGreaterThan(idx("[Resilience Drivers]"));
    expect(idx("[Resilience Decay]")).toBeGreaterThan(idx("[Resilience Inhibitors]"));
    expect(idx("[Resilience Reinforcement]")).toBeGreaterThan(idx("[Resilience Decay]"));
    expect(idx("[Post-Stabilization Resistance]")).toBeGreaterThan(idx("[Resilience Reinforcement]"));
    expect(idx("[System-Level Resilience Summary]")).toBeGreaterThan(idx("[Post-Stabilization Resistance]"));
  });

  it("short-circuits to HIGH baseline resilience for a never-active system", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralResilience(sigs, NO_DIFFS, "");

    expect(out).toContain("[Resilience Score]\nHIGH");
    expect(out).toContain("- strong resistance to volatility resurgence");
    expect(out).toContain("- strong resistance to drift reactivation");
    expect(out).toContain("- strong resistance to CZ re-expansion");
    expect(out).toContain("- strong resistance to upper-branch reactivation");
    expect(out).toContain("high → high (stable)");
    expect(out).toContain("(none — system has not faced challenges)");
    expect(out).toContain("Volatility: strong");
    expect(out).toContain("Baseline resilience is HIGH and unchallenged.");
  });

  it("scores LOW when active dimensions still carry inhibitors and few drivers", () => {
    // High structural load with rising trends: many inhibitors, only
    // pressure plateau as a single driver.
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
        critCount:       4,
        upperCount:      2,
        volatilityCount: 4,
        driftCount:      2,
        pressureLabel:   "high+",
        pressureSum:     70,
        pressureBand:    "###",
      }),
    ];
    const out = buildStructuralResilience(sigs, NO_DIFFS, "");

    expect(out).toContain("[Resilience Score]\nLOW");
    // Inhibitors active.
    expect(out).toContain("- residual drift pressure");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- incomplete CZ stabilization");
    expect(out).toContain("- volatility persistence");
    // Per-dimension resistance low across the board.
    expect(out).toContain("- low resistance to volatility resurgence");
    expect(out).toContain("- low resistance to CZ re-expansion");
    expect(out).toContain("- low resistance to upper-branch reactivation");
    // Summary uses "deteriorating".
    expect(out).toContain("deteriorating trajectory");
  });

  it("flags decay risks + reinforcement actions when dimensions are decaying", () => {
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
        critCount:       2,
        upperCount:      1,
        volatilityCount: 1,
        driftCount:      1,
        pressureLabel:   "high",
        pressureSum:     45,
        pressureBand:    "##",
      }),
    ];
    const out = buildStructuralResilience(sigs, NO_DIFFS, "");

    // Reinforcement actions for every decaying dimension.
    expect(out).toContain("- maintain volatility dampening");
    expect(out).toContain("- maintain CZ stabilization");
    expect(out).toContain("- maintain pressure relief");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain upper-branch constraint");
    // Decay risks identified by cross-dimensional coupling.
    expect(out).toContain("- CZ may re-expand under pressure");
    expect(out).toContain("- drift may re-activate under volatility");
    expect(out).toContain("- upper-branch may re-emerge under CZ saturation");
  });

  it("maps decaying dimensions to moderate post-stabilization resistance + improving trajectory", () => {
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
        critCount:       1,
        volatilityCount: 1,
        pressureLabel:   "medium",
        pressureSum:     30,
        pressureBand:    "==",
      }),
    ];
    const out = buildStructuralResilience(sigs, NO_DIFFS, "");

    // Drivers: vol decay + CZ relaxation + pressure plateau + drift
    // flattening (drift=0 throughout means "flat AND max>0" is false,
    // so drift flattening does NOT fire — confirms dormant ≠ flattening)
    // + hydraulic stabilization. That gives 4 drivers, 0 inhibitors →
    // MEDIUM-HIGH or HIGH.
    expect(out).toMatch(/\[Resilience Score\]\nHIGH|MEDIUM-HIGH/);
    expect(out).toContain("- volatility decay");
    expect(out).toContain("- CZ relaxation");
    // Volatility + CZ moderate (decaying, not zero).
    expect(out).toContain("Volatility: moderate");
    expect(out).toContain("CZ: moderate");
    // Drift + Upper-Branch strong (never active).
    expect(out).toContain("Drift: strong");
    expect(out).toContain("Upper-Branch: strong");
    // Trajectory improving since drivers > inhibitors.
    expect(out).toContain("improving trajectory");
  });
});
