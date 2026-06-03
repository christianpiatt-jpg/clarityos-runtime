// Card 47 — Structural matrix unit tests.
//
// Hand-rolled lineageMap + hydraulic-evolution fixtures so each cell
// pattern is pinned to a deterministic example. Token layout, marker
// rules, and absent-cell handling are the unit under test.

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
import { buildStructuralMatrix } from "../operatorStructuralMatrix";

function makePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 47 fixture",
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

describe("Card 47 — buildStructuralMatrix", () => {
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
    const out = buildStructuralMatrix(overlay, lineageMap, evo);
    expect(out).toContain("=== Structural Matrix ===");
    expect(out).toContain("Legend:");
    expect(out).toContain("L = laminar");
    expect(out).toContain("T = transitional");
    expect(out).toContain("U = turbulent");
    expect(out).toContain("C = critical-zone");
    expect(out).toContain("B = upper-branch");
    expect(out).toContain("* = structural change");
    expect(out).toContain("! = volatility marker");
    expect(out).toContain("~ = drift marker");
    expect(out).toContain("(no primitives)");
  });

  it("renders header row + per-cell regime / zone tokens with no markers when stable", () => {
    // p1 in 2 runs, both laminar, no changes.
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
    const out = buildStructuralMatrix(overlay, lineageMap, evo);

    // Header
    expect(out).toContain("Primitive");
    expect(out).toContain("R0");
    expect(out).toContain("R1");
    // Stable p1 → "L" cells, no markers. Inspect the p1 data row in
    // isolation so the assertion doesn't trip on the legend (which
    // intentionally mentions *, !, ~).
    expect(out).toMatch(/p1\s+\|\s+L\s+\|\s+L/);
    const p1Row = out.split("\n").find((l) => l.startsWith("p1")) ?? "";
    expect(p1Row).not.toContain("*");
    expect(p1Row).not.toContain("!");
    expect(p1Row).not.toContain("~");
  });

  it("adds * for structural change and ! for regime change at the transition", () => {
    // p1 has overlay change from laminar → transitional at the 0→1 pair.
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: makeOverlay("p1", "laminar"),
        to:   makeOverlay("p1", "transitional"),
      }],
    };
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: makeLineage("p1", [true, true]) },
      diffs:         { p1: p1Diff },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "transitional"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralMatrix(overlay, lineageMap, evo);
    // R1 cell should be "T * !" (transitional + structural change + regime change).
    expect(out).toMatch(/T \* !/);
  });

  it("renders (absent) for runs where the primitive is not present", () => {
    // p4 only in runs 1+2; absent in run 0.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p4"],
      lineages:      { p4: makeLineage("p4", [false, true, true]) },
      diffs:         {
        p4: {
          primitive_id: "p4",
          appearance:   { added: [1], removed: [] },
          metadataChanges:  [],
          hydraulicChanges: [],
          overlayChanges:   [],
        },
      },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p4"],
      perPrimitive: {
        p4: makeOverlayRuns("p4", [
          null,
          makeOverlay("p4", "transitional", true, false),
          makeOverlay("p4", "transitional", true, false),
        ]),
      },
      perRun: [
        { index: 0, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p4"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralMatrix(overlay, lineageMap, evo);
    expect(out).toContain("(absent)");
    // R1 cell should contain "T C" (and "*" because appearance added at 1).
    expect(out).toMatch(/T C \*/);
    // R2 cell should be just "T C" — no change from R1.
    expect(out).toMatch(/T C\s+$/m);
  });

  it("marks the last active run with ~ when the primitive shows long-range drift", () => {
    // p1 spans 4 runs: laminar → laminar → transitional → turbulent.
    // First overlay = laminar, last = turbulent → drift, with ≥ 3 active runs.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: makeLineage("p1", [true, true, true, true]) },
      diffs:         { p1: emptyPrimDiff("p1") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "transitional"),
          makeOverlay("p1", "turbulent"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 3, laminar: 0, transitional: 0, turbulent: 1, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralMatrix(overlay, lineageMap, evo);
    // ~ should appear on R3 (last active run).
    expect(out).toContain("~");
    // R3 cell should contain "U" (turbulent) and "~".
    expect(out).toMatch(/U.*~/);
  });
});
