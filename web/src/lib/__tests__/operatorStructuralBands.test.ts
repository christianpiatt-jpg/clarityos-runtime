// Card 49 — Structural bands unit tests.
//
// Hand-rolled lineageMap + hydraulic-evolution fixtures so each
// section's output is pinned to a deterministic example. Section
// ordering, band-symbol thresholds, phase-detection rules, and
// primitive bucket categorization are the unit under test.

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
import { buildStructuralBands } from "../operatorStructuralBands";

function makePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 49 fixture",
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

describe("Card 49 — buildStructuralBands", () => {
  it("emits the legend + 3 section headers in spec order", () => {
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
    const out = buildStructuralBands(overlay, lineageMap, evo, "stub-heatmap");

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Bands ===")).toBeGreaterThanOrEqual(0);
    expect(idx("Legend:")).toBeGreaterThan(idx("=== Structural Bands ==="));
    expect(idx("[Run-Level Bands]")).toBeGreaterThan(idx("Legend:"));
    expect(idx("[System-Level Phase Bands]")).toBeGreaterThan(idx("[Run-Level Bands]"));
    expect(idx("[Primitive-Level Band Summary]")).toBeGreaterThan(idx("[System-Level Phase Bands]"));
  });

  it("renders '--' bands for a fully stable laminar system + (no phase transitions)", () => {
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
    const out = buildStructuralBands(overlay, lineageMap, evo, "");

    expect(out).toContain("R0: --");
    expect(out).toContain("R1: --");
    expect(out).toContain("(no phase transitions)");
    // p1 has 0 changes → stable bucket; no critical-zone, no upper-branch.
    expect(out).toContain("Stable primitives: [p1]");
    expect(out).toContain("Volatile primitives: (none)");
    expect(out).toContain("Critical-zone cluster: (none)");
    expect(out).toContain("Drift cluster: (none)");
  });

  it("appends C/!/B overlays to the run band when at least one primitive triggers them", () => {
    // p2: laminar → transitional + critical-zone + upper-branch at R1
    //     (regime change at 0→1 transition → volatility).
    const p2Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p2",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: makeOverlay("p2", "laminar"),
        to:   makeOverlay("p2", "transitional", true, true),
      }],
    };
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p2"],
      lineages:      { p2: makeLineage("p2", [true, true]) },
      diffs:         { p2: p2Diff },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p2"],
      perPrimitive: {
        p2: makeOverlayRuns("p2", [
          makeOverlay("p2", "laminar"),
          makeOverlay("p2", "transitional", true, true),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p2"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralBands(overlay, lineageMap, evo, "");

    // R0 is laminar with no overlays → "--".
    expect(out).toMatch(/R0:\s+--/);
    // R1 cell has C + B + ! flags.
    const r1Line = out.split("\n").find((l) => l.startsWith("R1:")) ?? "";
    expect(r1Line).toContain("C");
    expect(r1Line).toContain("B");
    expect(r1Line).toContain("!");
  });

  it("detects phase transitions (rising volatility, critical-zone expansion, upper-branch emergence)", () => {
    const p3Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p3",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: makeOverlay("p3", "laminar"),
        to:   makeOverlay("p3", "transitional", true, true),
      }],
    };
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p3"],
      lineages:      { p3: makeLineage("p3", [true, true]) },
      diffs:         { p3: p3Diff },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p3"],
      perPrimitive: {
        p3: makeOverlayRuns("p3", [
          makeOverlay("p3", "laminar"),
          makeOverlay("p3", "transitional", true, true),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p3"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralBands(overlay, lineageMap, evo, "");

    expect(out).toContain("Phase 1 (R0–R1):");
    expect(out).toContain("rising volatility");
    expect(out).toContain("critical-zone expansion");
    expect(out).toContain("upper-branch emergence");
  });

  it("buckets primitives into stable / volatile / crit-zone / upper-branch / drift", () => {
    // p1: 0 changes, laminar everywhere → stable.
    // p2: 2 overlay changes → volatile.
    // p4: enters critical-zone → crit-zone bucket.
    // p5: enters upper-branch + drifts across 3 runs → drift + upper-branch + critzone hits.
    const p1Diff = emptyPrimDiff("p1");
    const p2Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p2",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [
        { indexFrom: 0, indexTo: 1, from: makeOverlay("p2", "laminar"),     to: makeOverlay("p2", "transitional") },
        { indexFrom: 1, indexTo: 2, from: makeOverlay("p2", "transitional"), to: makeOverlay("p2", "laminar")    },
      ],
    };
    const p4Diff = emptyPrimDiff("p4");
    const p5Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p5",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 1, indexTo: 2,
        from: makeOverlay("p5", "laminar"),
        to:   makeOverlay("p5", "turbulent", false, true),
      }],
    };

    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1", "p2", "p4", "p5"],
      lineages: {
        p1: makeLineage("p1", [true, true, true]),
        p2: makeLineage("p2", [true, true, true]),
        p4: makeLineage("p4", [true, true, true]),
        p5: makeLineage("p5", [true, true, true]),
      },
      diffs: { p1: p1Diff, p2: p2Diff, p4: p4Diff, p5: p5Diff },
      overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1", "p2", "p4", "p5"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
        ]),
        p2: makeOverlayRuns("p2", [
          makeOverlay("p2", "laminar"),
          makeOverlay("p2", "transitional"),
          makeOverlay("p2", "laminar"),
        ]),
        p4: makeOverlayRuns("p4", [
          makeOverlay("p4", "laminar"),
          makeOverlay("p4", "laminar", true, false),
          makeOverlay("p4", "laminar", true, false),
        ]),
        p5: makeOverlayRuns("p5", [
          makeOverlay("p5", "laminar"),
          makeOverlay("p5", "laminar"),
          makeOverlay("p5", "turbulent", false, true),
        ]),
      },
      perRun: [
        { index: 0, laminar: 4, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 3, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 0 },
        { index: 2, laminar: 2, transitional: 0, turbulent: 1, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1", "p2", "p4", "p5"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildStructuralBands(overlay, lineageMap, evo, "");

    expect(out).toContain("Stable primitives: [p1, p4]"); // 0 changes
    expect(out).toContain("Volatile primitives: [p2]");   // 2 overlay changes
    expect(out).toContain("Critical-zone cluster: [p4]");
    expect(out).toContain("Upper-branch cluster: [p5]");
    expect(out).toContain("Drift cluster: [p5]");         // first laminar, last turbulent, 3 active runs
  });
});
