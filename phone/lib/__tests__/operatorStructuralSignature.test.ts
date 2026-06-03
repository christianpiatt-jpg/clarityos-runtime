// Card 50 — Structural signature unit tests.
//
// Hand-rolled lineageMap + hydraulic-evolution fixtures so each
// section's output is pinned to a deterministic example. Section
// ordering, fingerprint composition, signature-string concatenation,
// count derivation, and phase-label mapping are the unit under test.

import { describe, expect, it } from "vitest";

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1PrimitiveLineage,
  EngineV1PrimitiveLineageDiff,
  EngineV1SystemOverlay,
  EngineOverlayResult,
  EnginePrimitive,
} from "../api";
import { buildStructuralSignature } from "../operatorStructuralSignature";

function makePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 50 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:           {},
    hydraulic_state:   {
      pressure: 5, gradient: 0, flow: 4, resistance: 2,
      timestamp: "2026-05-28T00:00:00+00:00",
    },
    origin_state:      null,
    historical_states: [],
  };
}

function makeOverlay(
  id: string,
  flow_regime: "laminar" | "transitional" | "turbulent",
  in_critical_zone = false,
  on_upper_branch  = false,
): EngineOverlayResult {
  return {
    primitive_id:     id,
    reynolds_number:  1000,
    flow_regime,
    stability:        0.9,
    in_critical_zone,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch,
    sensitivity:      1.0,
    hysteresis:       3.0,
  };
}

function emptyPrimDiff(id: string): EngineV1PrimitiveLineageDiff {
  return {
    primitive_id:     id,
    appearance:       { added: [], removed: [] },
    metadataChanges:  [],
    hydraulicChanges: [],
    overlayChanges:   [],
  };
}

function makeLineage(
  id: string,
  presence: boolean[],
): EngineV1PrimitiveLineage {
  return {
    primitive_id: id,
    runs: presence.map((present, ix) => ({
      index:     ix,
      primitive: present ? makePrimitive(id) : null,
      overlay:   null,
    })),
  };
}

function makeOverlayRuns(
  id: string,
  overlays: (EngineOverlayResult | null)[],
): EngineV1HydraulicEvolutionMap["perPrimitive"][string] {
  return {
    primitive_id: id,
    runs: overlays.map((ov, ix) => ({
      index:           ix,
      hydraulic_state: null,
      overlay:         ov,
    })),
  };
}

describe("Card 50 — buildStructuralSignature", () => {
  it("emits the 8 sections in spec order", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: makeLineage("p1", [true, true]) },
      diffs:         { p1: emptyPrimDiff("p1") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralSignature(overlay, lineageMap, evo, "", "");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Signature ===")).toBeGreaterThanOrEqual(0);
    expect(idx("Legend:")).toBeGreaterThan(idx("=== Structural Signature ==="));
    expect(idx("[Run-Level Structural Fingerprints]")).toBeGreaterThan(idx("Legend:"));
    expect(idx("[System-Level Signature String]")).toBeGreaterThan(idx("[Run-Level Structural Fingerprints]"));
    expect(idx("[Hydraulic Signature]")).toBeGreaterThan(idx("[System-Level Signature String]"));
    expect(idx("[Critical-Zone Signature]")).toBeGreaterThan(idx("[Hydraulic Signature]"));
    expect(idx("[Upper-Branch Signature]")).toBeGreaterThan(idx("[Critical-Zone Signature]"));
    expect(idx("[Volatility Signature]")).toBeGreaterThan(idx("[Upper-Branch Signature]"));
    expect(idx("[Drift Signature]")).toBeGreaterThan(idx("[Volatility Signature]"));
    expect(idx("[Phase-Transition Signature]")).toBeGreaterThan(idx("[Drift Signature]"));
  });

  it("renders stable laminar fingerprints with zero count signatures", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: makeLineage("p1", [true, true]) },
      diffs:         { p1: emptyPrimDiff("p1") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralSignature(overlay, lineageMap, evo, "", "");

    expect(out).toContain("R0: L--");
    expect(out).toContain("R1: L--");
    // Stable laminar in both runs → hydraulic signature "L → L".
    expect(out).toContain("L → L");
    // No critical-zone, upper-branch, volatility, or drift → all zeros.
    expect(out).toMatch(/\[Critical-Zone Signature\]\s*\n0 → 0/);
    expect(out).toMatch(/\[Upper-Branch Signature\]\s*\n0 → 0/);
    expect(out).toMatch(/\[Volatility Signature\]\s*\n0 → 0/);
    expect(out).toMatch(/\[Drift Signature\]\s*\n0 → 0/);
    // Phase-transition signature → both low.
    expect(out).toMatch(/\[Phase-Transition Signature\]\s*\nlow → low/);
  });

  it("composes the system signature string as regime+single-char-pressure tokens", () => {
    // 50 primitives across 3 runs — enough population to push the
    // per-run pressure sum past the 40-threshold so the signature
    // string includes the "#" high-pressure token.
    const manyIds: string[] = [];
    const manyLineages: Record<string, EngineV1PrimitiveLineage> = {};
    const manyDiffs:    Record<string, EngineV1PrimitiveLineageDiff> = {};
    const manyEvoRuns:  Record<string, EngineV1HydraulicEvolutionMap["perPrimitive"][string]> = {};
    for (let i = 0; i < 50; i++) {
      const id = `q${i}`;
      manyIds.push(id);
      manyLineages[id] = makeLineage(id, [true, true, true]);
      manyDiffs[id]    = emptyPrimDiff(id);
      manyEvoRuns[id]  = makeOverlayRuns(id, [
        makeOverlay(id, "laminar"),
        makeOverlay(id, "transitional", true),
        makeOverlay(id, "turbulent",    true, true),
      ]);
    }
    const fullLineageMap: EngineV1LineageMap = {
      primitive_ids: manyIds,
      lineages:      manyLineages,
      diffs:         manyDiffs,
      overlays:      {} as never,
    };
    const fullEvo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: manyIds,
      perPrimitive:  manyEvoRuns,
      perRun: [
        { index: 0, laminar: 50, transitional: 0,  turbulent: 0,  critical_zone: 0,  upper_branch: 0 },
        { index: 1, laminar: 0,  transitional: 50, turbulent: 0,  critical_zone: 50, upper_branch: 0 },
        { index: 2, laminar: 0,  transitional: 0,  turbulent: 50, critical_zone: 50, upper_branch: 50 },
      ],
    };
    const fullOverlay: EngineV1SystemOverlay = {
      primitive_ids: manyIds, lineageMap: fullLineageMap, hydraulicEvolution: fullEvo,
    };
    const out = buildStructuralSignature(fullOverlay, fullLineageMap, fullEvo, "", "");

    // Expected per-run pressure (sums across 50 primitives at each run):
    //   R0: regime=0 each → 0 (low)            → "L-"
    //   R1: regime=1 + crit=1 + volatility=1 each → 50×3=150 (high) → "T#"
    //   R2: regime=2 + crit=1 + upper=1 + volatility=1 each → 50×5=250 (high) → "U#"
    // Concatenated: "L-T#U#".
    expect(out).toContain("L-T#U#");
    // Hydraulic signature line.
    expect(out).toContain("L → T → U");
  });

  it("derives critical-zone / upper-branch / volatility / drift count signatures per run", () => {
    // p1: appears in 3 runs, laminar laminar transitional → drift active at R2.
    // p2: appears in 3 runs, laminar in crit always → crit at R0/R1/R2 = 1.
    // p3: laminar → laminar → upper-branch → upper at R2 only.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1", "p2", "p3"],
      lineages: {
        p1: makeLineage("p1", [true, true, true]),
        p2: makeLineage("p2", [true, true, true]),
        p3: makeLineage("p3", [true, true, true]),
      },
      diffs: {
        p1: emptyPrimDiff("p1"),
        p2: emptyPrimDiff("p2"),
        p3: emptyPrimDiff("p3"),
      },
      overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1", "p2", "p3"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "transitional"),
        ]),
        p2: makeOverlayRuns("p2", [
          makeOverlay("p2", "laminar", true),
          makeOverlay("p2", "laminar", true),
          makeOverlay("p2", "laminar", true),
        ]),
        p3: makeOverlayRuns("p3", [
          makeOverlay("p3", "laminar"),
          makeOverlay("p3", "laminar"),
          makeOverlay("p3", "laminar", false, true),
        ]),
      },
      perRun: [
        { index: 0, laminar: 3, transitional: 0, turbulent: 0, critical_zone: 1, upper_branch: 0 },
        { index: 1, laminar: 3, transitional: 0, turbulent: 0, critical_zone: 1, upper_branch: 0 },
        { index: 2, laminar: 2, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1", "p2", "p3"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralSignature(overlay, lineageMap, evo, "", "");

    // Critical-zone: 1 → 1 → 1 (p2 always).
    expect(out).toMatch(/\[Critical-Zone Signature\]\s*\n1 → 1 → 1/);
    // Upper-branch: 0 → 0 → 1 (p3 at R2).
    expect(out).toMatch(/\[Upper-Branch Signature\]\s*\n0 → 0 → 1/);
    // Volatility: 0 → 0 → 1 (p1 regime change L→T at R2).
    expect(out).toMatch(/\[Volatility Signature\]\s*\n0 → 0 → 1/);
    // Drift: p1 first L, last T, 3 active runs → drifts at last active run (R2).
    //        p2 / p3 don't drift (no regime change).
    expect(out).toMatch(/\[Drift Signature\]\s*\n0 → 0 → 1/);
  });

  it("emits phase-transition labels (low / medium / high / high+)", () => {
    // Build a 4-run system covering all 4 phase labels.
    // R0: empty → low
    // R1: 20 transitional → 20 medium
    // R2: 40 turbulent + 10 crit = 90 (>60) → high+
    //     We'll do regime sum = 40 + crit sum = 10 = 50 (high range).
    //     Actually, want one run in "high" (41-60) and one in "high+" (>60).
    const manyIds: string[] = [];
    const manyLineages: Record<string, EngineV1PrimitiveLineage> = {};
    const manyDiffs:    Record<string, EngineV1PrimitiveLineageDiff> = {};
    const manyEvoRuns:  Record<string, EngineV1HydraulicEvolutionMap["perPrimitive"][string]> = {};

    // 30 primitives present in all 4 runs.
    for (let i = 0; i < 30; i++) {
      const id = `q${i}`;
      manyIds.push(id);
      manyLineages[id] = makeLineage(id, [true, true, true, true]);
      manyDiffs[id]    = emptyPrimDiff(id);
      manyEvoRuns[id]  = makeOverlayRuns(id, [
        // R0: nothing → no overlay → pressure 0
        null,
        // R1: transitional, no crit → pressure 1 each
        makeOverlay(id, "transitional"),
        // R2: turbulent + crit → pressure 3 each. Plus volatility (regime change T→U). → 4
        makeOverlay(id, "turbulent", true),
        // R3: turbulent + crit + upper → pressure 4. Plus drift on last active. → 5
        makeOverlay(id, "turbulent", true, true),
      ]);
    }
    const fullLineageMap: EngineV1LineageMap = {
      primitive_ids: manyIds,
      lineages:      manyLineages,
      diffs:         manyDiffs,
      overlays:      {} as never,
    };
    const fullEvo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: manyIds,
      perPrimitive:  manyEvoRuns,
      perRun: [
        { index: 0, laminar: 0, transitional: 0,  turbulent: 0,  critical_zone: 0,  upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 30, turbulent: 0,  critical_zone: 0,  upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 0,  turbulent: 30, critical_zone: 30, upper_branch: 0 },
        { index: 3, laminar: 0, transitional: 0,  turbulent: 30, critical_zone: 30, upper_branch: 30 },
      ],
    };
    const fullOverlay: EngineV1SystemOverlay = {
      primitive_ids: manyIds, lineageMap: fullLineageMap, hydraulicEvolution: fullEvo,
    };
    const out = buildStructuralSignature(fullOverlay, fullLineageMap, fullEvo, "", "");

    // R0 sum = 0 → low.
    // R1 sum = 30 × 1 = 30 → medium.
    // R2 sum = 30 × (2 turbulent + 1 crit + 1 volatility) = 30 × 4 = 120 → high+ (>60).
    // R3 sum = 30 × (2 + 1 + 1 + 1 drift) = 30 × 5 = 150 → high+.
    // So we'll see low → medium → high+ → high+.
    expect(out).toMatch(/\[Phase-Transition Signature\]\s*\nlow → medium → high\+ → high\+/);
  });
});
