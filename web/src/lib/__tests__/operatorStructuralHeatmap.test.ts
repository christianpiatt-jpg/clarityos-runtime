// Card 48 — Structural heatmap unit tests.
//
// Hand-rolled lineageMap + hydraulic-evolution fixtures so each cell's
// pressure score + flag overlay can be pinned to a deterministic
// example. Score-to-symbol mapping and the flag-append rules are the
// unit under test.

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
import { buildStructuralHeatmap } from "../operatorStructuralHeatmap";

function makePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 48 fixture",
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

describe("Card 48 — buildStructuralHeatmap", () => {
  it("emits the legend + (no primitives) sentinel when empty", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: [], lineages: {}, diffs: {}, overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: [], perPrimitive: {}, perRun: [],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: [], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralHeatmap(overlay, lineageMap, evo);
    expect(out).toContain("=== Structural Heatmap ===");
    expect(out).toContain("Legend:");
    expect(out).toContain(". = no structural pressure");
    expect(out).toContain("+ = low pressure");
    expect(out).toContain("* = medium pressure");
    expect(out).toContain("# = high pressure");
    expect(out).toContain("(no primitives)");
  });

  it("renders '.' cells for a stable laminar primitive across all runs", () => {
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
    const out = buildStructuralHeatmap(overlay, lineageMap, evo);

    // Find p1 row; both cells should be ".".
    const p1Row = out.split("\n").find((l) => l.startsWith("p1")) ?? "";
    expect(p1Row).toContain(".");
    expect(p1Row).not.toContain("+");
    expect(p1Row).not.toContain("*");
    expect(p1Row).not.toContain("#");
  });

  it("scores transitional + critical-zone as '*C' (regime 1 + zone 1 = pressure 2)", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p2"],
      lineages:      { p2: makeLineage("p2", [true]) },
      diffs:         { p2: emptyPrimDiff("p2") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p2"],
      perPrimitive: {
        p2: makeOverlayRuns("p2", [
          makeOverlay("p2", "transitional", true, false),
        ]),
      },
      perRun: [
        { index: 0, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p2"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralHeatmap(overlay, lineageMap, evo);
    const p2Row = out.split("\n").find((l) => l.startsWith("p2")) ?? "";
    // "*C" — pressure 2 (transitional 1 + crit 1), with C overlay flag.
    expect(p2Row).toContain("*C");
  });

  it("scores turbulent + crit-zone + upper-branch as '#CB' (regime 2 + zone 1 + branch 1 = pressure 4)", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p4"],
      lineages:      { p4: makeLineage("p4", [true]) },
      diffs:         { p4: emptyPrimDiff("p4") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p4"],
      perPrimitive: {
        p4: makeOverlayRuns("p4", [
          makeOverlay("p4", "turbulent", true, true),
        ]),
      },
      perRun: [
        { index: 0, laminar: 0, transitional: 0, turbulent: 1, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p4"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralHeatmap(overlay, lineageMap, evo);
    const p4Row = out.split("\n").find((l) => l.startsWith("p4")) ?? "";
    expect(p4Row).toContain("#CB");
  });

  it("appends '!' for a regime change at a transition and shows blank cells for absent runs", () => {
    // p17 in 2 runs: laminar → transitional (regime flipped).
    // p18 only present in R1, absent in R0.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p17", "p18"],
      lineages: {
        p17: makeLineage("p17", [true,  true]),
        p18: makeLineage("p18", [false, true]),
      },
      diffs: {
        p17: emptyPrimDiff("p17"),
        p18: {
          primitive_id: "p18",
          appearance:   { added: [1], removed: [] },
          metadataChanges:  [],
          hydraulicChanges: [],
          overlayChanges:   [],
        },
      },
      overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p17", "p18"],
      perPrimitive: {
        p17: makeOverlayRuns("p17", [
          makeOverlay("p17", "laminar"),
          makeOverlay("p17", "transitional"),
        ]),
        p18: makeOverlayRuns("p18", [
          null,
          makeOverlay("p18", "laminar"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p17", "p18"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralHeatmap(overlay, lineageMap, evo);

    const p17Row = out.split("\n").find((l) => l.startsWith("p17")) ?? "";
    // R1 cell should contain "*!" — pressure 2 (transitional 1 + volatility 1).
    expect(p17Row).toContain("*!");
    // p18 row exists; R0 cell should NOT contain a pressure symbol
    // (blank for absent), R1 should be ".".
    const p18Row = out.split("\n").find((l) => l.startsWith("p18")) ?? "";
    expect(p18Row).toContain(".");
  });
});
