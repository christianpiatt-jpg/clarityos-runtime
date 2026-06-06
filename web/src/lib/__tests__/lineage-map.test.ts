// Card 34 — buildLineageMap test.
//
// Asserts the multi-primitive lineage map correctly enumerates every
// primitive id across runs, sorts them deterministically, and
// produces the lineage / diff / overlay for each by delegating to
// the Card 31 / 32 / 33 helpers.
//
// Pure unit test — no fetch, no session. Contexts built via fixture
// factories.

import { describe, expect, it } from "vitest";

import {
  buildLineageMap,
  buildPrimitiveLineageOverlay,
  createMultiRunContext,
  diffPrimitiveLineage,
  extractPrimitiveLineage,
  type EngineDiagnostics,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1LineageMap,
  type EngineV1OperatorContext,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_34_001",
    observer_notes:    "Card 34 fixture",
    confidence_level:  0.7,
    validation_status: "unvalidated",
    early_warnings:    {},
    errors:            [],
    interventions:     [],
  };
}

function fakeHydraulicState(p: Partial<EngineHydraulicState> = {}): EngineHydraulicState {
  return {
    pressure:   5.0,
    gradient:   0.0,
    flow:       4.0,
    resistance: 2.0,
    timestamp:  "2026-05-28T00:00:00+00:00",
    ...p,
  };
}

function fakePrimitive(
  id: string,
  opts: { type?: EnginePrimitiveType; hydraulic?: Partial<EngineHydraulicState> } = {},
): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: opts.type ?? "signal",
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 34 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:           { note: id },
    hydraulic_state:   fakeHydraulicState(opts.hydraulic),
    origin_state:      null,
    historical_states: [],
  };
}

function fakeOverlay(primitiveId: string, opts: Partial<EngineOverlayResult> = {}): EngineOverlayResult {
  return {
    primitive_id:     primitiveId,
    reynolds_number:  1000,
    flow_regime:      "laminar",
    stability:        0.9,
    in_critical_zone: false,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch:  false,
    sensitivity:      1.0,
    hysteresis:       3.0,
    ...opts,
  };
}

function fakeContext(
  primitives: EnginePrimitive[],
  overlays:   EngineOverlayResult[],
): EngineV1OperatorContext {
  const diagnostics = fakeDiagnostics();
  const raw: EngineResponseV1 = {
    ok: true,
    primitives,
    overlays,
    regression:  null,
    projection:  null,
    diagnostics,
  };
  return {
    primitives:     [],
    projectionDays: 7,
    raw,
    normalized: {
      primitives, overlays,
      regression: null, projection: null, diagnostics,
      primitiveCount: primitives.length, overlayCount: overlays.length,
    },
    classified: {
      signals: [], entities: [], attitudes: [], relationships: [], events: [], temperatures: [],
      laminarOverlays: [], transitionalOverlays: [], turbulentOverlays: [],
      criticalZoneOverlays: [], upperBranchOverlays: [],
      regression: null, projection: null, diagnostics,
    },
  };
}

describe("Card 34 — buildLineageMap", () => {
  it("enumerates every primitive id across runs and sorts them lexicographically", () => {
    // Run 0: p_c, p_a   |   Run 1: p_b, p_a   |   Run 2: p_c, p_d
    // Union (sorted) → p_a, p_b, p_c, p_d
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p_c"), fakePrimitive("p_a")], []),
      fakeContext([fakePrimitive("p_b"), fakePrimitive("p_a")], []),
      fakeContext([fakePrimitive("p_c"), fakePrimitive("p_d")], []),
    ]);

    const map = buildLineageMap(multi);

    expect(map.primitive_ids).toEqual(["p_a", "p_b", "p_c", "p_d"]);
    // Records cover the exact same id set.
    expect(Object.keys(map.lineages).sort()).toEqual(["p_a", "p_b", "p_c", "p_d"]);
    expect(Object.keys(map.diffs).sort()).toEqual(["p_a", "p_b", "p_c", "p_d"]);
    expect(Object.keys(map.overlays).sort()).toEqual(["p_a", "p_b", "p_c", "p_d"]);
  });

  it("each lineage matches a direct extractPrimitiveLineage call", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], []),
      fakeContext([fakePrimitive("p1")],                    []),
    ]);

    const map = buildLineageMap(multi);

    for (const id of map.primitive_ids) {
      expect(map.lineages[id]).toEqual(extractPrimitiveLineage(multi, id));
    }
  });

  it("each diff matches diffPrimitiveLineage applied to the same lineage", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1", { hydraulic: { pressure: 5 } })], []),
      fakeContext([fakePrimitive("p1", { hydraulic: { pressure: 8 } })], []),
    ]);

    const map = buildLineageMap(multi);

    for (const id of map.primitive_ids) {
      expect(map.diffs[id]).toEqual(diffPrimitiveLineage(map.lineages[id]));
    }
  });

  it("each overlay matches buildPrimitiveLineageOverlay applied to the same lineage", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "turbulent" })]),
    ]);

    const map = buildLineageMap(multi);

    for (const id of map.primitive_ids) {
      expect(map.overlays[id]).toEqual(buildPrimitiveLineageOverlay(map.lineages[id]));
    }
  });

  it("handles primitives that appear in only one run (partial coverage)", () => {
    // p_unique appears only in run 1; p_shared in both.
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p_shared")],                                  []),
      fakeContext([fakePrimitive("p_shared"), fakePrimitive("p_unique")],       []),
    ]);

    const map = buildLineageMap(multi);

    expect(map.primitive_ids).toEqual(["p_shared", "p_unique"]);
    // p_unique lineage: run 0 = null (absent), run 1 = present.
    expect(map.lineages["p_unique"].runs[0].primitive).toBeNull();
    expect(map.lineages["p_unique"].runs[1].primitive).not.toBeNull();
    // → diff records its appearance.
    expect(map.diffs["p_unique"].appearance.added).toEqual([1]);
  });

  it("returns an empty map for an empty multi-run context", () => {
    const empty = buildLineageMap(createMultiRunContext([]));
    expect(empty.primitive_ids).toEqual([]);
    expect(empty.lineages).toEqual({});
    expect(empty.diffs).toEqual({});
    expect(empty.overlays).toEqual({});
  });

  it("returns an empty map when runs contain no primitives", () => {
    const multi = createMultiRunContext([fakeContext([], []), fakeContext([], [])]);
    const map = buildLineageMap(multi);
    expect(map.primitive_ids).toEqual([]);
    expect(map.lineages).toEqual({});
  });

  it("does not mutate the input multi-run context (purity)", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")],                       []),
    ]);
    const snapshot = JSON.stringify(multi);

    buildLineageMap(multi);

    expect(JSON.stringify(multi)).toBe(snapshot);
  });

  it("is deterministic — same input produces structurally identical maps", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p2")],                       []),
    ]);

    const m1 = buildLineageMap(multi);
    const m2 = buildLineageMap(multi);

    expect(JSON.stringify(m1)).toBe(JSON.stringify(m2));
  });

  it("top-level shape pin — { primitive_ids, lineages, diffs, overlays } only", () => {
    const map: EngineV1LineageMap = buildLineageMap(createMultiRunContext([]));
    expect(Object.keys(map).sort())
      .toEqual(["diffs", "lineages", "overlays", "primitive_ids"].sort());
  });
});
