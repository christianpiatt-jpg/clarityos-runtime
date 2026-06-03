// Card 56 — Structural causality engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralCausality } from "../operatorStructuralCausality";

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

function makeDiff(overrides: Partial<EngineV1StructuralSignatureDiff> = {}): EngineV1StructuralSignatureDiff {
  return {
    fromIndex:       0,
    toIndex:         1,
    fromFingerprint: "L--",
    toFingerprint:   "L--",
    classification:  "No significant identity shift",
    notes:           ["no detectable change"],
    ...overrides,
  };
}

describe("Card 56 — buildStructuralCausality", () => {
  it("emits the 5 sections in spec order with the per-primitive sentinel", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralCausality(sigs, [makeDiff()], "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Causality ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Primitive-Level Causality]")).toBeGreaterThan(idx("=== Structural Causality ==="));
    expect(idx("[Run-Level Causality]")).toBeGreaterThan(idx("[Primitive-Level Causality]"));
    expect(idx("[Structural-Dimension Causality]")).toBeGreaterThan(idx("[Run-Level Causality]"));
    expect(idx("[Identity-Shift Causality]")).toBeGreaterThan(idx("[Structural-Dimension Causality]"));
    expect(idx("[System-Level Causal Summary]")).toBeGreaterThan(idx("[Identity-Shift Causality]"));
    expect(out).toContain("(per-primitive causal chains require lineage + overlay context — see Structural Matrix)");
  });

  it("reports a stable causality for a fully laminar baseline", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralCausality(sigs, [makeDiff()], "");

    // No non-LOW runs → run section sentinel.
    expect(out).toContain("[Run-Level Causality]\n(no non-LOW runs)");
    // All dimensions show their "no X detected" cause.
    expect(out).toContain("Root Cause: no volatility detected");
    expect(out).toContain("Root Cause: no drift detected");
    expect(out).toContain("Root Cause: no CZ activity");
    expect(out).toContain("Root Cause: no upper-branch activity");
    // Identity is stable → stable identity root.
    expect(out).toContain("stable → stable");
    expect(out).toContain("Root Cause: stable identity");
    // System-level summary collapses to the stable-regime line.
    expect(out).toContain("Structural causality: no causal chain detected. System is operating in a stable regime.");
  });

  it("emits per-run cause chains for non-LOW runs with derived root causes", () => {
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
    const out = buildStructuralCausality(sigs, [], "");

    // R0 (LOW) is skipped, R1 + R2 appear.
    expect(out).not.toMatch(/R0:\s*\n\s+Causes:/);
    expect(out).toContain("R1:");
    expect(out).toContain("    - critical-zone");
    expect(out).toContain("    - volatility spike");
    // R1 root cause: volatility (no drift, no upper).
    expect(out).toMatch(/R1:[\s\S]*?Root Cause: volatility spike/);
    // R2 has both upper-branch + drift → "structural overload".
    expect(out).toMatch(/R2:[\s\S]*?Root Cause: structural overload/);
    expect(out).toContain("    - upper-branch emergence");
    expect(out).toContain("    - drift onset");
    expect(out).toContain("    - high+-pressure");
  });

  it("links dimension causes through cross-dimensional patterns", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1, critCount: 1, volatilityCount: 1,
                pressureLabel: "medium", pressureSum: 12, pressureBand: "-=" }),
      makeSig({ runIndex: 2, critCount: 3, volatilityCount: 3, driftCount: 1, upperCount: 1,
                pressureLabel: "high", pressureSum: 45, pressureBand: "##" }),
      makeSig({ runIndex: 3, critCount: 4, volatilityCount: 4, driftCount: 2, upperCount: 2,
                pressureLabel: "high+", pressureSum: 70, pressureBand: "###" }),
    ];
    const out = buildStructuralCausality(sigs, [], "");

    // Volatility rising → compounding feedback.
    expect(out).toContain("Volatility:");
    expect(out).toContain("  Cause Chain: 0 → 1 → 3 → 4");
    expect(out).toContain("Root Cause: compounding volatility feedback");
    // Drift rising AND volatility rising → volatility-induced drift.
    expect(out).toContain("Drift:");
    expect(out).toContain("Root Cause: volatility-induced drift");
    // CZ rising AND pressure rising → pressure-driven CZ saturation.
    expect(out).toContain("Critical-Zone:");
    expect(out).toContain("Root Cause: pressure-driven CZ saturation");
    // Upper-branch rising AND CZ rising → CZ instability.
    expect(out).toContain("Upper-Branch:");
    expect(out).toContain("Root Cause: CZ instability");
  });

  it("synthesizes a compounding causal chain when multiple dimensions are rising", () => {
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
    const out = buildStructuralCausality(sigs, [], "");

    // Identity sequence spans stable → escalated → multi-dimensional escalation root.
    expect(out).toContain("stable → transitional → escalated → escalated");
    expect(out).toContain("Root Cause: multi-dimensional escalation");
    // System-level causal chain in operational order.
    expect(out).toContain("Structural instability is driven by a compounding chain:");
    expect(out).toContain("pressure escalation → CZ instability → volatility spike → drift onset → upper-branch emergence");
  });
});
