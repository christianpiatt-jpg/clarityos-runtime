// Card 61 — Structural governance engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralGovernance } from "../operatorStructuralGovernance";

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

describe("Card 61 — buildStructuralGovernance", () => {
  it("baseline HIGH short-circuit on a never-active system with all 11 sections in spec order", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralGovernance(sigs, NO_DIFFS, "");

    // Section ordering matches spec.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Governance ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Governance Level]")).toBeGreaterThan(idx("=== Structural Governance ==="));
    expect(idx("[Structural Invariants]")).toBeGreaterThan(idx("[Governance Level]"));
    expect(idx("[Governance Profile]")).toBeGreaterThan(idx("[Structural Invariants]"));
    expect(idx("[Governance Trajectory]")).toBeGreaterThan(idx("[Governance Profile]"));
    expect(idx("[Governance Drivers]")).toBeGreaterThan(idx("[Governance Trajectory]"));
    expect(idx("[Governance Inhibitors]")).toBeGreaterThan(idx("[Governance Drivers]"));
    expect(idx("[Governance Thresholds]")).toBeGreaterThan(idx("[Governance Inhibitors]"));
    expect(idx("[Governance Breach Conditions]")).toBeGreaterThan(idx("[Governance Thresholds]"));
    expect(idx("[Governance Reinforcement]")).toBeGreaterThan(idx("[Governance Breach Conditions]"));
    expect(idx("[Governance Decay]")).toBeGreaterThan(idx("[Governance Reinforcement]"));
    expect(idx("[System-Level Governance Summary]")).toBeGreaterThan(idx("[Governance Decay]"));

    // HIGH baseline + full compliance everywhere.
    expect(out).toContain("[Governance Level]\nHIGH");
    expect(out).toContain("- full invariant compliance");
    expect(out).toContain("- strong threshold adherence");
    expect(out).toContain("- strong upper-branch containment");
    expect(out).toContain("- strong volatility control");
    expect(out).toContain("high → high → high (stable)");
    expect(out).toContain("(none — system has not faced challenges)");
    expect(out).toContain("(none — invariants fully held)");
    expect(out).toContain("Baseline governance is HIGH and invariants are fully held.");

    // Invariants + thresholds always populated.
    expect(out).toContain("- CZ must not exceed 2");
    expect(out).toContain("- volatility must not exceed 2");
    expect(out).toContain("- drift must not exceed 1");
    expect(out).toContain("- upper-branch activation must remain suppressed");
    expect(out).toContain("- CZ < 2");
    expect(out).toContain("- volatility < 2");
    expect(out).toContain("- drift < 1");
  });

  it("scores LOW with all inhibitors firing on an escalating active system", () => {
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
    const out = buildStructuralGovernance(sigs, NO_DIFFS, "");

    expect(out).toContain("[Governance Level]\nLOW");
    // Every inhibitor fires (CZ active, upper active, drift active,
    // volatility >= 2 and not decaying).
    expect(out).toContain("- CZ vulnerability");
    expect(out).toContain("- upper-branch instability");
    expect(out).toContain("- incomplete drift containment");
    expect(out).toContain("- volatility breach");
    // Profile shows weak compliance across the board (all rising).
    expect(out).toContain("- weak invariant compliance");
    expect(out).toContain("- weak threshold adherence");
    expect(out).toContain("- weak upper-branch containment");
    expect(out).toContain("- weak volatility control");
    // Summary reflects deteriorating state.
    expect(out).toContain("Governance is weakening — reinforcement recommended.");
  });

  it("flags threshold violation + dimension-specific breach conditions when any threshold is crossed", () => {
    // CZ=2 (crosses 2-threshold), vol=2 (crosses), drift=1 (crosses),
    // upper=1 (crosses 0-threshold).
    const sigs = [
      makeSig({
        runIndex:        0,
        hasCrit:         true,
        hasVolatile:     true,
        hasDrift:        true,
        hasUpper:        true,
        critCount:       2,
        volatilityCount: 2,
        driftCount:      1,
        upperCount:      1,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
      makeSig({
        runIndex:        1,
        hasCrit:         true,
        hasVolatile:     true,
        hasDrift:        true,
        hasUpper:        true,
        critCount:       2,
        volatilityCount: 2,
        driftCount:      1,
        upperCount:      1,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
    ];
    const out = buildStructuralGovernance(sigs, NO_DIFFS, "");

    // Threshold violation appears in breach conditions.
    expect(out).toContain("- threshold violation");
    // Dimension-specific breach conditions also surface (since any
    // historical load fires the corresponding condition).
    expect(out).toContain("- CZ re-expansion");
    expect(out).toContain("- drift reactivation");
    expect(out).toContain("- upper-branch emergence");
    // Volatility max is 2 (< 3) → no "volatility spike" line.
    expect(out).not.toContain("- volatility spike");
  });

  it("emits projected trajectory + improving summary when drivers outweigh inhibitors", () => {
    // Two runs with volatility actively decaying (2 → 1, last < 2 so
    // no volatility-breach inhibitor). Drivers = immunity stabilization
    // + volatility dampening = 2; inhibitors = 0. Delta = 2 →
    // MEDIUM-HIGH score, projection bumps to HIGH so the trajectory
    // actually moves.
    const sigs = [
      makeSig({
        runIndex:        0,
        hasVolatile:     true,
        volatilityCount: 2,
      }),
      makeSig({
        runIndex:        1,
        hasVolatile:     true,
        volatilityCount: 1,
      }),
    ];
    const out = buildStructuralGovernance(sigs, NO_DIFFS, "");

    // Drivers fire only for the actively-decaying dimension + umbrella.
    expect(out).toContain("- immunity stabilization");
    expect(out).toContain("- volatility dampening");
    expect(out).not.toContain("- drift suppression");
    expect(out).not.toContain("- CZ stabilization");
    expect(out).not.toContain("- upper-branch containment");
    // No inhibitors: vol.last=1 < 2 → no breach; other dims at 0.
    expect(out).toContain("[Governance Inhibitors]\n(none)");
    // MEDIUM-HIGH (delta=2) → HIGH projection → trajectory tail
    // "(projected)" because the level actually moves.
    expect(out).toContain("medium-high → high → high (projected)");
    // No inhibitors → "fully met" summary clause.
    expect(out).toContain("Invariants are fully met.");
    // Drivers > inhibitors → improving direction.
    expect(out).toContain("Governance is improving but not yet robust.");
  });

  it("populates decay + reinforcement + inhibitors with a coherent summary for partial recovery", () => {
    // System had crit + drift + vol + upper at R0; partially recovers
    // by R1 (drift+upper drop to 0, crit drops to 1, vol drops to 1).
    const sigs = [
      makeSig({
        runIndex:        0,
        hasCrit:         true,
        hasVolatile:     true,
        hasDrift:        true,
        hasUpper:        true,
        critCount:       3,
        volatilityCount: 3,
        driftCount:      1,
        upperCount:      1,
        pressureLabel:   "high",
        pressureSum:     45,
        pressureBand:    "##",
      }),
      makeSig({
        runIndex:        1,
        hasCrit:         true,
        hasVolatile:     true,
        critCount:       1,
        volatilityCount: 1,
        driftCount:      0,
        upperCount:      0,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
    ];
    const out = buildStructuralGovernance(sigs, NO_DIFFS, "");

    // Decay: any-historical-load + drift/upper historical fire.
    expect(out).toContain("- thresholds may weaken under pressure");
    expect(out).toContain("- drift may re-activate under volatility");
    expect(out).toContain("- upper-branch may re-emerge under CZ instability");
    // Reinforcement covers every dimension that ever carried load.
    expect(out).toContain("- maintain volatility dampening");
    expect(out).toContain("- maintain drift suppression");
    expect(out).toContain("- maintain CZ stabilization");
    expect(out).toContain("- constrain upper-branch activation");
    // CZ is still > 0 at R1 → CZ vulnerability inhibitor remains;
    // drift cleared (last=0) → no incomplete-drift-containment line.
    expect(out).toContain("- CZ vulnerability");
    expect(out).not.toContain("- incomplete drift containment");
    // Summary mentions remaining vulnerabilities (drivers >= inhibitors
    // case).
    expect(out).toContain("Invariants are partially met, but CZ and upper-branch vulnerabilities remain.");
  });
});
