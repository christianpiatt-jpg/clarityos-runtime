// Card 55 — Structural hotspot engine unit tests.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import type { EngineV1StructuralSignatureDiff } from "../operatorSignatureDiff";
import { buildStructuralHotspots } from "../operatorStructuralHotspots";

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

describe("Card 55 — buildStructuralHotspots", () => {
  it("emits the 7 sections in spec order with primitive sentinels", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralHotspots(sigs, [makeDiff()], "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Hotspots ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Top Primitive Hotspots]")).toBeGreaterThan(idx("=== Structural Hotspots ==="));
    expect(idx("[Top Run Hotspots]")).toBeGreaterThan(idx("[Top Primitive Hotspots]"));
    expect(idx("[Structural-Dimension Hotspots]")).toBeGreaterThan(idx("[Top Run Hotspots]"));
    expect(idx("[Hotspot Clusters]")).toBeGreaterThan(idx("[Structural-Dimension Hotspots]"));
    expect(idx("[Hotspot Evolution]")).toBeGreaterThan(idx("[Hotspot Clusters]"));
    expect(idx("[Hotspot Trajectory]")).toBeGreaterThan(idx("[Hotspot Evolution]"));
    expect(idx("[System-Level Hotspot Summary]")).toBeGreaterThan(idx("[Hotspot Trajectory]"));
    // Primitive-level sentinels always show up.
    expect(out).toContain("(per-primitive ranking requires lineage + overlay context — see Structural Matrix)");
    expect(out).toContain("(primitive clusters require lineage + overlay context — see Structural Matrix)");
  });

  it("reports no hotspots for a stable laminar baseline", () => {
    const sigs = [makeSig({ runIndex: 0 }), makeSig({ runIndex: 1 })];
    const out  = buildStructuralHotspots(sigs, [makeDiff()], "");

    expect(out).toContain("R0 — LOW");
    expect(out).toContain("R1 — LOW");
    expect(out).toContain("R0 → R1: (stable)");
    expect(out).toContain("- Volatility: stable");
    expect(out).toContain("- Pressure: stable");
    expect(out).toContain("Structural hotspots: none detected. System is operating without elevated risk concentrations.");
  });

  it("ranks top-3 runs by descending risk score with contributing factors", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1, pressureLabel: "medium", pressureSum: 12, pressureBand: "-=",
                hasCrit: true, critCount: 1 }),
      makeSig({ runIndex: 2, pressureLabel: "high", pressureSum: 45, pressureBand: "##",
                hasCrit: true, hasVolatile: true, critCount: 3, volatilityCount: 3 }),
      makeSig({ runIndex: 3, regime: "U", pressureLabel: "high+", pressureSum: 70, pressureBand: "###",
                hasCrit: true, hasUpper: true, hasVolatile: true, hasDrift: true,
                critCount: 4, upperCount: 2, volatilityCount: 4, driftCount: 2 }),
    ];
    const out = buildStructuralHotspots(sigs, [], "");

    // R3 is the highest (CRITICAL), then R2 (HIGH), then R1 (MEDIUM).
    expect(out).toMatch(/\[Top Run Hotspots\]\s*\n1\. R3 — CRITICAL/);
    expect(out).toMatch(/\n2\. R2 — HIGH/);
    expect(out).toMatch(/\n3\. R1 — MEDIUM/);
    expect(out).toContain("critical-zone + upper-branch + volatility + drift + high+-pressure");
  });

  it("ranks dimensions by severity (HIGH first) using maximum counts", () => {
    const sigs = [
      makeSig({ runIndex: 0 }),
      makeSig({ runIndex: 1, critCount: 1, volatilityCount: 1 }),
      makeSig({ runIndex: 2, critCount: 3, volatilityCount: 3, upperCount: 1 }),
      makeSig({ runIndex: 3, critCount: 4, volatilityCount: 4, upperCount: 2, driftCount: 1,
                pressureLabel: "high", pressureSum: 45, pressureBand: "##" }),
    ];
    const out = buildStructuralHotspots(sigs, [], "");

    // HIGH dimensions: Volatility (max 4), Critical-Zone (max 4), Upper-Branch (max 2),
    // Pressure (max high), then MEDIUM: Drift (max 1). All rendered with sequence + severity.
    expect(out).toContain("Volatility — HIGH (0 → 1 → 3 → 4)");
    expect(out).toContain("Critical-Zone — HIGH (0 → 1 → 3 → 4)");
    expect(out).toContain("Upper-Branch — HIGH (0 → 0 → 1 → 2)");
    expect(out).toContain("Pressure — HIGH (low → low → low → high)");
    expect(out).toContain("Drift — MEDIUM (0 → 0 → 0 → 1)");
    // Within the dimension section, MEDIUM should sort after HIGH.
    const dimStart   = out.indexOf("[Structural-Dimension Hotspots]");
    const dimSection = out.slice(dimStart);
    expect(dimSection.indexOf("Drift — MEDIUM"))
      .toBeGreaterThan(dimSection.indexOf("Volatility — HIGH"));
  });

  it("synthesizes a hotspot summary citing top runs + rising dimensions", () => {
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
    const out = buildStructuralHotspots(sigs, [], "");

    expect(out).toContain("Structural hotspots are concentrated in R3, R2");
    expect(out).toContain("volatility escalation");
    expect(out).toContain("drift onset");
    expect(out).toContain("critical-zone saturation");
    expect(out).toContain("upper-branch emergence");
    expect(out).toContain("pressure escalation");
  });
});
