// Card 46 — Multi-run structural overlay unit tests.
//
// Hand-rolled lineageMap + hydraulic-evolution fixtures so each
// section's output is pinned to a deterministic example. Section
// ordering, sentinel handling, and rule-based clustering are the
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
import { buildMultiRunStructuralOverlay } from "../operatorStructuralOverlay";

function makePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 46 fixture",
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
  id:         string,
  presence:   boolean[],
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

describe("Card 46 — buildMultiRunStructuralOverlay", () => {
  it("emits the 4 sections in spec order with empty-input sentinels", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: [], lineages: {}, diffs: {}, overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: [], perPrimitive: {}, perRun: [],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: [], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildMultiRunStructuralOverlay(overlay, lineageMap, evo);

    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Multi-Run Structural Overlay ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[Primitive Structural Evolution]")).toBeGreaterThan(idx("=== Multi-Run Structural Overlay ==="));
    expect(idx("[System Structural Map]")).toBeGreaterThan(idx("[Primitive Structural Evolution]"));
    expect(idx("[Cross-Run Structural Deltas]")).toBeGreaterThan(idx("[System Structural Map]"));
    expect(idx("[Structural Clusters]")).toBeGreaterThan(idx("[Cross-Run Structural Deltas]"));
    expect(out).toContain("(no primitives)");
    expect(out).toContain("(no transitions)");
    expect(out).toContain("- Cluster A (stable laminar): (none)");
  });

  it("renders per-primitive runs / hydraulic / zone sequences only for active runs", () => {
    // p1: present in all 3 runs, laminar throughout.
    // p4: present in runs 1+2 only, regime transitional → turbulent,
    //     enters critical-zone at run 2.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1", "p4"],
      lineages: {
        p1: makeLineage("p1", [true,  true, true]),
        p4: makeLineage("p4", [false, true, true]),
      },
      diffs: {
        p1: emptyPrimDiff("p1"),
        p4: {
          primitive_id: "p4",
          appearance:   { added: [1], removed: [] },
          metadataChanges:  [],
          hydraulicChanges: [],
          overlayChanges:   [{
            indexFrom: 1, indexTo: 2,
            from: makeOverlay("p4", "transitional", false, false),
            to:   makeOverlay("p4", "turbulent",    true,  false),
          }],
        },
      },
      overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1", "p4"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
          makeOverlay("p1", "laminar"),
        ]),
        p4: makeOverlayRuns("p4", [
          null,
          makeOverlay("p4", "transitional", false, false),
          makeOverlay("p4", "turbulent",    true,  false),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 1, transitional: 0, turbulent: 1, critical_zone: 1, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1", "p4"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildMultiRunStructuralOverlay(overlay, lineageMap, evo);

    expect(out).toContain("p1:");
    expect(out).toContain("  runs: [0,1,2]");
    expect(out).toContain("  hydraulic: laminar → laminar → laminar");
    expect(out).toContain("p4:");
    // p4 has 2 active runs (indices 1, 2), so the sequence has 2 entries.
    expect(out).toContain("  runs: [1,2]");
    expect(out).toContain("  hydraulic: transitional → turbulent");
    expect(out).toContain("  critical-zone: false → true");
    expect(out).toContain("  upper-branch: false → false");
  });

  it("tallies system map: total / stable / volatile / critical-zone / upper-branch", () => {
    // p1: 0 changes (stable) AND all overlays laminar → cluster A.
    // p2: 2 changes (volatile) — overlay regime flip + critical-zone entry.
    // p3: no overlay anywhere, 0 changes (stable but unclassified).
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1", "p2", "p3"],
      lineages: {
        p1: makeLineage("p1", [true, true]),
        p2: makeLineage("p2", [true, true]),
        p3: makeLineage("p3", [true, true]),
      },
      diffs: {
        p1: emptyPrimDiff("p1"),
        p2: {
          primitive_id: "p2",
          appearance:   { added: [], removed: [] },
          metadataChanges:  [],
          hydraulicChanges: [],
          overlayChanges:   [
            { indexFrom: 0, indexTo: 1,
              from: makeOverlay("p2", "laminar"),
              to:   makeOverlay("p2", "transitional", true, true) },
            { indexFrom: 0, indexTo: 1,
              from: makeOverlay("p2", "laminar"),
              to:   makeOverlay("p2", "transitional", true, true) },
          ],
        },
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
        ]),
        p2: makeOverlayRuns("p2", [
          makeOverlay("p2", "laminar"),
          makeOverlay("p2", "transitional", true, true),
        ]),
        p3: makeOverlayRuns("p3", [null, null]),
      },
      perRun: [
        { index: 0, laminar: 2, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 1, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1", "p2", "p3"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildMultiRunStructuralOverlay(overlay, lineageMap, evo);

    expect(out).toContain("- total primitives: 3");
    // p1 (0 changes) + p3 (0 changes) → 2 stable.
    expect(out).toContain("- stable primitives: 2");
    // p2 has 2 overlayChanges → volatile.
    expect(out).toContain("- volatile primitives: 1");
    // Only p2 has in_critical_zone=true at any point.
    expect(out).toContain("- critical-zone primitives: 1");
    expect(out).toContain("- upper-branch primitives: 1");
    // Cluster A: p1 only (p3 has no overlays present).
    expect(out).toContain("- Cluster A (stable laminar): [p1]");
    // Cluster C: p2 entered critical-zone.
    expect(out).toContain("- Cluster C (critical-zone entrants): [p2]");
    expect(out).toContain("- Cluster D (upper-branch entrants): [p2]");
  });

  it("counts cross-run structural deltas per adjacent pair", () => {
    // p1 has metadata change at 0→1 (1 change) and appearance.removed at run 2 (1 change).
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id: "p1",
      appearance:   { added: [], removed: [2] },
      metadataChanges:  [{
        indexFrom: 0, indexTo: 1,
        from: { metadata: { primitive_id: "p1" } as never,
                content: {}, hydraulic_state: {} as never,
                origin_state: null, historical_states: [] },
        to:   { metadata: { primitive_id: "p1" } as never,
                content: {}, hydraulic_state: {} as never,
                origin_state: null, historical_states: [] },
      }],
      hydraulicChanges: [],
      overlayChanges:   [],
    };
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: makeLineage("p1", [true, true, false]) },
      diffs:         { p1: p1Diff },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1"],
      perPrimitive: {
        p1: makeOverlayRuns("p1", [null, null, null]),
      },
      perRun: [
        { index: 0, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildMultiRunStructuralOverlay(overlay, lineageMap, evo);

    // Two adjacent pairs (0→1, 1→2). 0→1 sees 1 metadata change; 1→2
    // sees 1 appearance.removed entry.
    expect(out).toContain("Run 0 → 1:\n  structural changes: 1");
    expect(out).toContain("Run 1 → 2:\n  structural changes: 1");
  });

  it("classifies transitional oscillators into Cluster B", () => {
    // p7 oscillates: laminar → transitional → laminar → transitional
    // → 3 regime flips, has transitional runs → cluster B.
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p7"],
      lineages:      { p7: makeLineage("p7", [true, true, true, true]) },
      diffs:         { p7: emptyPrimDiff("p7") },
      overlays:      {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p7"],
      perPrimitive: {
        p7: makeOverlayRuns("p7", [
          makeOverlay("p7", "laminar"),
          makeOverlay("p7", "transitional"),
          makeOverlay("p7", "laminar"),
          makeOverlay("p7", "transitional"),
        ]),
      },
      perRun: [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 3, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p7"], lineageMap, hydraulicEvolution: evo,
    };
    const out = buildMultiRunStructuralOverlay(overlay, lineageMap, evo);
    expect(out).toContain("- Cluster B (transitional oscillators): [p7]");
  });
});
