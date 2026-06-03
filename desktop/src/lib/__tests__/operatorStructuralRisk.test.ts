// Card 54 — Structural risk engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralRisk } from "../operatorStructuralRisk";

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

describe("Card 54 — buildStructuralRisk", () => {
  it("emits the 12 sections in spec order", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralRisk(sigs, NO_DIFFS, "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Risk Assessment ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Primitive-Level Risk]")).toBeGreaterThan(idx("=== Structural Risk Assessment ==="));
    expect(idx("[Run-Level Risk]")).toBeGreaterThan(idx("[Primitive-Level Risk]"));
    expect(idx("[System-Level Risk]")).toBeGreaterThan(idx("[Run-Level Risk]"));
    expect(idx("[Hydraulic Risk]")).toBeGreaterThan(idx("[System-Level Risk]"));
    expect(idx("[Pressure Risk]")).toBeGreaterThan(idx("[Hydraulic Risk]"));
    expect(idx("[Critical-Zone Risk]")).toBeGreaterThan(idx("[Pressure Risk]"));
    expect(idx("[Upper-Branch Risk]")).toBeGreaterThan(idx("[Critical-Zone Risk]"));
    expect(idx("[Volatility Risk]")).toBeGreaterThan(idx("[Upper-Branch Risk]"));
    expect(idx("[Drift Risk]")).toBeGreaterThan(idx("[Volatility Risk]"));
    expect(idx("[Identity-Shift Risk]")).toBeGreaterThan(idx("[Drift Risk]"));
    expect(idx("[Risk Classification]")).toBeGreaterThan(idx("[Identity-Shift Risk]"));
    expect(idx("[System-Level Risk Summary]")).toBeGreaterThan(idx("[Risk Classification]"));
  });

  it("grades a stable laminar baseline as LOW with no classifications", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralRisk(sigs, NO_DIFFS, "");

    expect(out).toContain("R0: LOW");
    expect(out).toContain("R1: LOW");
    expect(out).toContain("[System-Level Risk]\nOverall: LOW");
    expect(out).toContain("L → L (stable laminar)");
    expect(out).toContain("0 → 0 (no activity)");
    expect(out).toContain("stable → stable");
    expect(out).toContain("[Risk Classification]\n(none)");
    expect(out).toContain("Structural risk level: LOW.");
    // The per-primitive sentinel always shows up.
    expect(out).toContain("(per-primitive risk requires lineage + overlay context — see Structural Matrix)");
  });

  it("escalates an active high-pressure run to CRITICAL with contributing factors", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({
        runIndex:        1,
        regime:          "U",
        pressureSum:     70,
        pressureBand:    "###",
        pressureLabel:   "high+",
        hasCrit:         true,
        hasUpper:        true,
        hasVolatile:     true,
        hasDrift:        true,
        critCount:       4,
        upperCount:      2,
        volatilityCount: 4,
        driftCount:      2,
      }),
    ];
    const out = buildStructuralRisk(sigs, NO_DIFFS, "");
    // R1 score = 1+2+1+2 + 3 (high+) = 9 → CRITICAL.
    expect(out).toContain("R1: CRITICAL");
    expect(out).toContain("(critical-zone + upper-branch + volatility + drift + high+-pressure)");
    expect(out).toContain("[System-Level Risk]\nOverall: CRITICAL");
    // Summary should mention the headline traits + level.
    expect(out).toContain("high+-pressure");
    expect(out).toContain("high-volatility");
    expect(out).toContain("upper-branch-emergent");
    expect(out).toContain("Structural risk level: CRITICAL.");
  });

  it("flags volatility lock-in + critical-zone saturation + drift amplification + upper-branch overextension", () => {
    const sigs = [
      makeSig({ runIndex: 0, critCount: 2, volatilityCount: 2, driftCount: 0, upperCount: 0 }),
      makeSig({
        runIndex:        1,
        regime:          "T",
        pressureSum:     30,
        pressureBand:    "==",
        pressureLabel:   "medium",
        hasCrit:         true,
        hasUpper:        true,
        hasVolatile:     true,
        hasDrift:        true,
        critCount:       4,
        upperCount:      2,
        volatilityCount: 5,
        driftCount:      2,
      }),
    ];
    const out = buildStructuralRisk(sigs, NO_DIFFS, "");
    expect(out).toContain("- volatility lock-in");
    expect(out).toContain("- drift amplification");
    expect(out).toContain("- critical-zone saturation");
    expect(out).toContain("- upper-branch overextension");
  });

  it("renders chain risk lines with rising annotations", () => {
    const sigs = [
      makeSig({ runIndex: 0, regime: "L", pressureBand: "--", critCount: 0, upperCount: 0, volatilityCount: 0, driftCount: 0 }),
      makeSig({ runIndex: 1, regime: "T", pressureBand: "==", critCount: 1, upperCount: 0, volatilityCount: 1, driftCount: 0 }),
      makeSig({ runIndex: 2, regime: "U", pressureBand: "##", critCount: 3, upperCount: 2, volatilityCount: 3, driftCount: 1 }),
    ];
    const out = buildStructuralRisk(sigs, NO_DIFFS, "");

    expect(out).toContain("[Hydraulic Risk]\nL → T → U (escalation)");
    expect(out).toContain("[Pressure Risk]\n-- → == → ## (rising)");
    expect(out).toContain("[Critical-Zone Risk]\n0 → 1 → 3 (saturation approaching)");
    expect(out).toContain("[Upper-Branch Risk]\n0 → 0 → 2 (emergence)");
    expect(out).toContain("[Volatility Risk]\n0 → 1 → 3 (lock-in approaching)");
    expect(out).toContain("[Drift Risk]\n0 → 0 → 1 (acceleration)");
  });
});
