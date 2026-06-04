// Card 52 — Structural signature overlay engine unit tests.
//
// Hand-constructed signature + diff arrays so each overlay section
// and synthesis rule is pinned to a deterministic example.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildSignatureOverlay } from "../operatorSignatureOverlay";

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

describe("Card 52 — buildSignatureOverlay", () => {
  it("emits the 11 sections in spec order", () => {
    const sigs  = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const diffs = [makeDiff()];
    const out   = buildSignatureOverlay(sigs, diffs);

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Signature Overlay ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Run-Level Signatures]")).toBeGreaterThan(idx("=== Structural Signature Overlay ==="));
    expect(idx("[Run-Level Signature Diffs]")).toBeGreaterThan(idx("[Run-Level Signatures]"));
    expect(idx("[Hydraulic Overlay]")).toBeGreaterThan(idx("[Run-Level Signature Diffs]"));
    expect(idx("[Pressure Band Overlay]")).toBeGreaterThan(idx("[Hydraulic Overlay]"));
    expect(idx("[Critical-Zone Overlay]")).toBeGreaterThan(idx("[Pressure Band Overlay]"));
    expect(idx("[Upper-Branch Overlay]")).toBeGreaterThan(idx("[Critical-Zone Overlay]"));
    expect(idx("[Volatility Overlay]")).toBeGreaterThan(idx("[Upper-Branch Overlay]"));
    expect(idx("[Drift Overlay]")).toBeGreaterThan(idx("[Volatility Overlay]"));
    expect(idx("[Phase-Transition Overlay]")).toBeGreaterThan(idx("[Drift Overlay]"));
    expect(idx("[Identity-Shift Overlay]")).toBeGreaterThan(idx("[Phase-Transition Overlay]"));
    expect(idx("[System-Level Structural Synthesis]")).toBeGreaterThan(idx("[Identity-Shift Overlay]"));
  });

  it("renders run signatures + briefly-labelled adjacent diffs", () => {
    const sigs = [
      makeSig({ runIndex: 0, regime: "L", pressureBand: "--",  pressureLabel: "low",    fingerprint: "L--" }),
      makeSig({ runIndex: 1, regime: "T", pressureBand: "==",  pressureLabel: "medium", fingerprint: "T=C!",
                hasCrit: true, hasVolatile: true, critCount: 3, volatilityCount: 3 }),
    ];
    const diffs = [
      makeDiff({
        fromIndex: 0, toIndex: 1,
        fromFingerprint: "L--", toFingerprint: "T=C!",
        classification:  "Structural Escalation",
        notes: ["hydraulic escalation (L → T)", "volatility spike", "critical-zone expansion"],
      }),
    ];
    const out = buildSignatureOverlay(sigs, diffs);

    expect(out).toContain("R0: L--");
    expect(out).toContain("R1: T=C!");
    // Brief notes joined with " + " in parens.
    expect(out).toContain("R0 → R1: L-- → T=C!  (hydraulic escalation (L → T) + volatility spike + critical-zone expansion)");
  });

  it("emits chain overlays as → joined sequences for every component", () => {
    const sigs = [
      makeSig({ runIndex: 0, regime: "L", pressureBand: "--", pressureLabel: "low",     critCount: 0, upperCount: 0, volatilityCount: 0, driftCount: 0 }),
      makeSig({ runIndex: 1, regime: "T", pressureBand: "==", pressureLabel: "medium",  critCount: 3, upperCount: 0, volatilityCount: 3, driftCount: 0 }),
      makeSig({ runIndex: 2, regime: "U", pressureBand: "##", pressureLabel: "high",    critCount: 5, upperCount: 2, volatilityCount: 4, driftCount: 1 }),
    ];
    const diffs = [makeDiff(), makeDiff({ fromIndex: 1, toIndex: 2 })];
    const out = buildSignatureOverlay(sigs, diffs);

    expect(out).toContain("[Hydraulic Overlay]\nL → T → U");
    expect(out).toContain("[Pressure Band Overlay]\n-- → == → ##");
    expect(out).toContain("[Critical-Zone Overlay]\n0 → 3 → 5");
    expect(out).toContain("[Upper-Branch Overlay]\n0 → 0 → 2");
    expect(out).toContain("[Volatility Overlay]\n0 → 3 → 4");
    expect(out).toContain("[Drift Overlay]\n0 → 0 → 1");
    expect(out).toContain("[Phase-Transition Overlay]\nlow → medium → high");
  });

  it("compresses Card 51 classifications into short identity-shift labels", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1 }),
      makeSig({ runIndex: 2 }),
      makeSig({ runIndex: 3 }),
    ];
    const diffs = [
      makeDiff({ fromIndex: 0, toIndex: 1, classification: "Structural Escalation",   notes: ["hydraulic escalation (L → T)"] }),
      makeDiff({ fromIndex: 1, toIndex: 2, classification: "Structural Relaxation",   notes: ["pressure relaxation (medium → low)"] }),
      makeDiff({ fromIndex: 2, toIndex: 3, classification: "Structural Drift",        notes: ["drift onset"] }),
    ];
    const out = buildSignatureOverlay(sigs, diffs);

    expect(out).toContain("R0 → R1: Escalation");
    expect(out).toContain("R1 → R2: Relaxation");
    expect(out).toContain("R2 → R3: Drift");
  });

  it("synthesises system-level rules + identity trajectory", () => {
    const sigs = [
      makeSig({ runIndex: 0, regime: "L", pressureLabel: "low",     critCount: 0, upperCount: 0, volatilityCount: 0, driftCount: 0 }),
      makeSig({ runIndex: 1, regime: "T", pressureLabel: "medium",  critCount: 3, upperCount: 0, volatilityCount: 3, driftCount: 0 }),
      makeSig({ runIndex: 2, regime: "U", pressureLabel: "high+",   critCount: 5, upperCount: 2, volatilityCount: 5, driftCount: 1 }),
    ];
    const diffs = [
      makeDiff({
        fromIndex: 0, toIndex: 1,
        classification: "Structural Escalation",
        notes: ["hydraulic escalation (L → T)", "pressure escalation (low → medium)", "volatility spike", "critical-zone expansion"],
      }),
      makeDiff({
        fromIndex: 1, toIndex: 2,
        classification: "Structural Drift",
        notes: ["hydraulic escalation (T → U)", "pressure escalation (medium → high+)", "volatility spike", "drift onset"],
      }),
    ];
    const out = buildSignatureOverlay(sigs, diffs);

    expect(out).toContain("- hydraulic escalation across runs");
    expect(out).toContain("- pressure rising across runs");
    expect(out).toContain("- critical-zone expansion");
    expect(out).toContain("- upper-branch emergence");
    expect(out).toContain("- volatility spike");
    expect(out).toContain("- drift onset");
    // Three runs map to stable → transitional → escalated.
    expect(out).toContain("- identity shift: stable → transitional → escalated");
  });
});
