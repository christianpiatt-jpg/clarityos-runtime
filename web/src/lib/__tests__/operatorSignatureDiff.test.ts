// Card 51 — Structural signature diff engine unit tests.
//
// Hand-constructed EngineV1StructuralSignature objects so each
// classification rule + count-label is pinned to a deterministic
// example. Card 50's signature extraction is exercised in its own
// suite — these tests focus on the diff helper itself.

import { describe, expect, it } from "vitest";

import type { EngineV1StructuralSignature } from "../operatorStructuralSignature";
import { buildSignatureDiff } from "../operatorSignatureDiff";

// Stable baseline signature used as the "from" side for most tests.
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

describe("Card 51 — buildSignatureDiff", () => {
  it("emits the 9 sections in spec order with a Run X → Run Y header", () => {
    const from = makeSig({ runIndex: 1 });
    const to   = makeSig({ runIndex: 2 });
    const out  = buildSignatureDiff(from, to);

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Signature Diff ===")).toBeGreaterThanOrEqual(0);
    expect(out).toContain("Run 1 → Run 2");
    expect(idx("[Fingerprint Diff]")).toBeGreaterThan(idx("Run 1 → Run 2"));
    expect(idx("[Hydraulic Diff]")).toBeGreaterThan(idx("[Fingerprint Diff]"));
    expect(idx("[Pressure Band Diff]")).toBeGreaterThan(idx("[Hydraulic Diff]"));
    expect(idx("[Critical-Zone Diff]")).toBeGreaterThan(idx("[Pressure Band Diff]"));
    expect(idx("[Upper-Branch Diff]")).toBeGreaterThan(idx("[Critical-Zone Diff]"));
    expect(idx("[Volatility Diff]")).toBeGreaterThan(idx("[Upper-Branch Diff]"));
    expect(idx("[Drift Diff]")).toBeGreaterThan(idx("[Volatility Diff]"));
    expect(idx("[Phase-Transition Diff]")).toBeGreaterThan(idx("[Drift Diff]"));
    expect(idx("[Identity Shift Classification]")).toBeGreaterThan(idx("[Phase-Transition Diff]"));
  });

  it("classifies identical signatures as no identity shift", () => {
    const sig = makeSig({ runIndex: 0 });
    const out = buildSignatureDiff(sig, makeSig({ runIndex: 1 }));
    expect(out).toContain("Type: No significant identity shift");
    expect(out).toContain("- no detectable change");
    expect(out).toContain("(no change)");
  });

  it("flags Structural Escalation on hydraulic upshift + volatility spike + crit-zone expansion", () => {
    const from = makeSig({ runIndex: 1, regime: "L", pressureLabel: "medium", pressureSum: 12 });
    const to   = makeSig({
      runIndex:        2,
      regime:          "T",
      pressureSum:     30,
      fingerprint:     "T=C!",
      signatureToken:  "T=",
      pressureBand:    "==",
      pressureLabel:   "medium",
      hasCrit:         true,
      hasVolatile:     true,
      critCount:       3,
      volatilityCount: 3,
    });
    const out = buildSignatureDiff(from, to);
    expect(out).toContain("Type: Structural Escalation");
    expect(out).toContain("hydraulic escalation (L → T)");
    expect(out).toContain("volatility spike");
    expect(out).toContain("critical-zone expansion");
    // Fingerprint diff carries the full token from each signature
    // (default "L--" → "T=C!").
    expect(out).toContain("L--  →  T=C!");
    expect(out).toContain("L → T");      // hydraulic diff
  });

  it("flags Structural Drift on 0 → 1 drift transition (onset)", () => {
    const from = makeSig({ runIndex: 2 });
    const to   = makeSig({
      runIndex:    3,
      hasDrift:    true,
      driftCount:  1,
      fingerprint: "L--~",
    });
    const out = buildSignatureDiff(from, to);
    expect(out).toContain("Type: Structural Drift");
    expect(out).toContain("drift onset");
    // Drift line uses the specialised "(onset)" label.
    expect(out).toMatch(/\[Drift Diff\]\s*\n0 → 1\s+\(onset\)/);
  });

  it("flags Structural Relaxation on hydraulic + pressure downshift", () => {
    const from = makeSig({
      runIndex:      0,
      regime:        "U",
      pressureSum:   45,
      pressureBand:  "##",
      pressureLabel: "high",
      fingerprint:   "U#",
    });
    const to = makeSig({
      runIndex:      1,
      regime:        "T",
      pressureSum:   15,
      pressureBand:  "-=",
      pressureLabel: "medium",
      fingerprint:   "T=",
    });
    const out = buildSignatureDiff(from, to);
    expect(out).toContain("Type: Structural Relaxation");
    expect(out).toContain("hydraulic relaxation (U → T)");
    expect(out).toContain("pressure relaxation (high → medium)");
    expect(out).toContain("##  →  -=");
  });
});
