// Card 57 — Structural intervention engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralInterventions } from "../operatorStructuralInterventions";

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

describe("Card 57 — buildStructuralInterventions", () => {
  it("emits the 5 sections in spec order with the per-primitive sentinel", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralInterventions(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Interventions ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Primitive-Level Interventions]")).toBeGreaterThan(idx("=== Structural Interventions ==="));
    expect(idx("[Run-Level Interventions]")).toBeGreaterThan(idx("[Primitive-Level Interventions]"));
    expect(idx("[Structural-Dimension Interventions]")).toBeGreaterThan(idx("[Run-Level Interventions]"));
    expect(idx("[Identity-Shift Interventions]")).toBeGreaterThan(idx("[Structural-Dimension Interventions]"));
    expect(idx("[System-Level Intervention Summary]")).toBeGreaterThan(idx("[Identity-Shift Interventions]"));
    expect(out).toContain("(per-primitive interventions require lineage + overlay context — see Structural Matrix)");
  });

  it("reports no interventions required for a stable laminar baseline", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralInterventions(sigs, NO_DIFFS, "");

    expect(out).toContain("[Run-Level Interventions]\n(no non-LOW runs)");
    expect(out).toContain("(none — no volatility detected)");
    expect(out).toContain("(none — no drift detected)");
    expect(out).toContain("(none — no CZ activity)");
    expect(out).toContain("(none — no upper-branch activity)");
    expect(out).toContain("(none — pressure stable)");
    expect(out).toContain("(none — regime stable)");
    expect(out).toContain("[Identity-Shift Interventions]\n(none — identity is stable)");
    expect(out).toContain("No interventions required. System is operating within stable bounds.");
  });

  it("recommends per-run actions for non-LOW runs based on contributing flags", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({
        runIndex:        1,
        hasCrit:         true,
        hasVolatile:     true,
        critCount:       2,
        volatilityCount: 2,
        pressureLabel:   "medium",
        pressureSum:     14,
        pressureBand:    "-=",
      }),
      makeSig({
        runIndex:        2,
        regime:          "U",
        hasCrit:         true,
        hasUpper:        true,
        hasDrift:        true,
        hasVolatile:     true,
        critCount:       4,
        upperCount:      2,
        volatilityCount: 4,
        driftCount:      1,
        pressureLabel:   "high+",
        pressureSum:     70,
        pressureBand:    "###",
      }),
    ];
    const out = buildStructuralInterventions(sigs, NO_DIFFS, "");

    // R0 (LOW) is skipped, R1 + R2 appear.
    expect(out).not.toMatch(/R0:\s*\n\s+- /);
    expect(out).toMatch(/R1:[\s\S]*?- volatility dampening[\s\S]*?- CZ containment/);
    expect(out).toMatch(/R2:[\s\S]*?- volatility dampening[\s\S]*?- CZ containment[\s\S]*?- drift suppression[\s\S]*?- upper-branch stabilization[\s\S]*?- pressure relief/);
  });

  it("derives dimension interventions from chain trends + cross-dimensional coupling", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1, critCount: 1, volatilityCount: 1, hasCrit: true, hasVolatile: true,
                pressureLabel: "medium", pressureSum: 12, pressureBand: "-=" }),
      makeSig({ runIndex: 2, regime: "T", critCount: 3, volatilityCount: 3, driftCount: 1, upperCount: 1,
                hasCrit: true, hasVolatile: true, hasDrift: true, hasUpper: true,
                pressureLabel: "high", pressureSum: 45, pressureBand: "##" }),
      makeSig({ runIndex: 3, regime: "U", critCount: 4, volatilityCount: 4, driftCount: 2, upperCount: 2,
                hasCrit: true, hasVolatile: true, hasDrift: true, hasUpper: true,
                pressureLabel: "high+", pressureSum: 70, pressureBand: "###" }),
    ];
    const out = buildStructuralInterventions(sigs, NO_DIFFS, "");

    // Volatility rising → both actions fire.
    expect(out).toMatch(/Volatility:[\s\S]*?- apply volatility dampening[\s\S]*?- reduce feedback loops/);
    // Drift active + volatility rising → upstream-stabilization action.
    expect(out).toMatch(/Drift:[\s\S]*?- apply drift suppression[\s\S]*?- stabilize upstream volatility/);
    // CZ active + pressure rising → pressure-reduction action.
    expect(out).toMatch(/Critical-Zone:[\s\S]*?- reduce pressure[\s\S]*?- apply CZ stabilization/);
    // Upper-branch active + CZ rising → CZ-instability action.
    expect(out).toMatch(/Upper-Branch:[\s\S]*?- constrain branching[\s\S]*?- reduce CZ instability/);
    // Pressure + Hydraulic dimensions surface their dedicated actions.
    expect(out).toContain("Pressure:\n  - apply pressure relief");
    expect(out).toContain("Hydraulic:\n  - stabilize regime transitions");
  });

  it("recommends identity-shift + system-level actions on multi-dimensional escalation", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1, critCount: 1, volatilityCount: 1, hasCrit: true, hasVolatile: true,
                pressureLabel: "medium", pressureSum: 12, pressureBand: "-=" }),
      makeSig({ runIndex: 2, regime: "T", critCount: 3, volatilityCount: 3, driftCount: 1,
                hasCrit: true, hasVolatile: true, hasDrift: true,
                pressureLabel: "high", pressureSum: 45, pressureBand: "##" }),
      makeSig({ runIndex: 3, regime: "U", critCount: 4, volatilityCount: 4, driftCount: 2, upperCount: 2,
                hasCrit: true, hasVolatile: true, hasDrift: true, hasUpper: true,
                pressureLabel: "high+", pressureSum: 70, pressureBand: "###" }),
    ];
    const out = buildStructuralInterventions(sigs, NO_DIFFS, "");

    // Identity escalated → 3 prescribed actions.
    expect(out).toContain("- reduce escalation drivers");
    expect(out).toContain("- stabilize structural dimensions");
    expect(out).toContain("- dampen volatility and drift");

    // System-level summary lists every rising dimension's action.
    expect(out).toContain("Recommended actions:");
    expect(out).toContain("- reduce pressure escalation");
    expect(out).toContain("- stabilize CZ");
    expect(out).toContain("- dampen volatility");
    expect(out).toContain("- suppress drift");
    expect(out).toContain("- constrain upper-branch emergence");
  });
});
