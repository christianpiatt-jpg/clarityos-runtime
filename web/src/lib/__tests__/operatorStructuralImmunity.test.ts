// Card 60 — Structural immunity engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralImmunity } from "../operatorStructuralImmunity";

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

describe("Card 60 — buildStructuralImmunity", () => {
  it("emits the 11 sections in spec order for an active system", () => {
    const sigs = [
      makeSig({ runIndex: 0, hasCrit: true, hasVolatile: true,
                critCount: 2, volatilityCount: 2,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
      makeSig({ runIndex: 1, hasCrit: true, hasVolatile: true,
                critCount: 1, volatilityCount: 1,
                pressureLabel: "medium", pressureSum: 14, pressureBand: "-=" }),
    ];
    const out = buildStructuralImmunity(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Immunity ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Immunity Score]")).toBeGreaterThan(idx("=== Structural Immunity ==="));
    expect(idx("[Immunity Profile]")).toBeGreaterThan(idx("[Immunity Score]"));
    expect(idx("[Immunity Trajectory]")).toBeGreaterThan(idx("[Immunity Profile]"));
    expect(idx("[Immunity Drivers]")).toBeGreaterThan(idx("[Immunity Trajectory]"));
    expect(idx("[Immunity Inhibitors]")).toBeGreaterThan(idx("[Immunity Drivers]"));
    expect(idx("[Immunity Thresholds]")).toBeGreaterThan(idx("[Immunity Inhibitors]"));
    expect(idx("[Immunity Breach Conditions]")).toBeGreaterThan(idx("[Immunity Thresholds]"));
    expect(idx("[Immunity Reinforcement]")).toBeGreaterThan(idx("[Immunity Breach Conditions]"));
    expect(idx("[Immunity Decay]")).toBeGreaterThan(idx("[Immunity Reinforcement]"));
    expect(idx("[Early-Warning Signals]")).toBeGreaterThan(idx("[Immunity Decay]"));
    expect(idx("[System-Level Immunity Summary]")).toBeGreaterThan(idx("[Early-Warning Signals]"));
  });

  it("short-circuits to HIGH baseline immunity for a never-active system", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralImmunity(sigs, NO_DIFFS, "");

    expect(out).toContain("[Immunity Score]\nHIGH");
    expect(out).toContain("- strong CZ immunity");
    expect(out).toContain("- strong volatility immunity");
    expect(out).toContain("- strong drift immunity");
    expect(out).toContain("- strong upper-branch immunity");
    expect(out).toContain("high → high → high (stable)");
    expect(out).toContain("(none — system has not faced challenges)");
    expect(out).toContain("(none — system is not under structural load)");
    // Thresholds always show baseline operating bounds.
    expect(out).toContain("- CZ must remain below 2");
    expect(out).toContain("- volatility must remain below 2");
    expect(out).toContain("- drift must remain below 1");
    expect(out).toContain("- upper-branch must remain at 0");
    expect(out).toContain("Baseline immunity is HIGH and well-positioned to prevent future instability.");
  });

  it("scores LOW with multiple inhibitors and rising warnings for an active escalation", () => {
    // Escalating load: crit/vol/drift/upper all rise.
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
    const out = buildStructuralImmunity(sigs, NO_DIFFS, "");

    expect(out).toContain("[Immunity Score]\nLOW");
    // Inhibitors: every residual fires.
    expect(out).toContain("- residual CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- incomplete drift containment");
    expect(out).toContain("- volatility persistence");
    // Early-warning: every dimension uptick fires.
    expect(out).toContain("- rising volatility slope");
    expect(out).toContain("- CZ uptick");
    expect(out).toContain("- drift acceleration");
    expect(out).toContain("- pressure climb");
    expect(out).toContain("- upper-branch tick");
    // Profile shows weak across the board (rising counts → weak).
    expect(out).toContain("- weak CZ immunity");
    expect(out).toContain("- weak volatility immunity");
    expect(out).toContain("- weak drift immunity");
    expect(out).toContain("- weak upper-branch immunity");
    // Summary uses deteriorating + reinforcement-recommended tail.
    expect(out).toContain("deteriorating trajectory");
    expect(out).toContain("Immunity is weakening — reinforcement recommended.");
  });

  it("populates breach + reinforcement when ANY structural load was ever present", () => {
    // System had crit + vol load at R0, fully recovered by R1.
    const sigs = [
      makeSig({
        runIndex:        0,
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
        critCount:       0,
        volatilityCount: 0,
        pressureLabel:   "low",
        pressureSum:     0,
        pressureBand:    "--",
      }),
    ];
    const out = buildStructuralImmunity(sigs, NO_DIFFS, "");

    // Breach conditions surface the failure modes the system has seen.
    expect(out).toContain("- pressure escalation");
    expect(out).toContain("- volatility resurgence");
    expect(out).toContain("- CZ re-expansion");
    // Reinforcement actions stay in effect for any dimension that
    // ever carried load.
    expect(out).toContain("- maintain volatility dampening");
    expect(out).toContain("- maintain CZ stabilization");
    // Decay surfaces forward-looking risks for dimensions with history.
    expect(out).toContain("- CZ may re-expand under pressure");
  });

  it("scores HIGH with improving trajectory when many drivers fire and inhibitors clear", () => {
    // System had high load at R0/R1; by R2 vol/crit/drift/upper all
    // decay to 0. Lots of drivers, no inhibitors, no warnings.
    const sigs = [
      makeSig({
        runIndex:        0,
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
        hasCrit:         true,
        hasUpper:        true,
        hasDrift:        true,
        hasVolatile:     true,
        critCount:       2,
        upperCount:      1,
        volatilityCount: 2,
        driftCount:      1,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
      makeSig({
        runIndex:        2,
        critCount:       0,
        upperCount:      0,
        volatilityCount: 0,
        driftCount:      0,
        pressureLabel:   "low",
        pressureSum:     0,
        pressureBand:    "--",
      }),
    ];
    const out = buildStructuralImmunity(sigs, NO_DIFFS, "");

    // 5 drivers (vol/crit/drift/upper all decaying + pressure
    // decaying), 0 inhibitors, 0 warnings → delta = 5 → HIGH.
    expect(out).toContain("[Immunity Score]\nHIGH");
    expect(out).toContain("- volatility decay");
    expect(out).toContain("- drift suppression");
    expect(out).toContain("- CZ relaxation");
    expect(out).toContain("- pressure plateau");
    expect(out).toContain("- upper-branch normalization");
    expect(out).toContain("improving trajectory");
    expect(out).toContain("No primary vulnerabilities detected.");
    expect(out).toContain("Immunity is well-positioned and reinforcing.");
  });
});
