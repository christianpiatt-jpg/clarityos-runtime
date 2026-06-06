// Card 36 — buildSystemOverlay composition test.
//
// Asserts the top-level system overlay artifact stitches the Card 34
// lineage map and the Card 35 hydraulic evolution map into one
// deterministic structure.
//
// Pure unit test — no fetch, no session. Contexts built via fixture
// factories.

import { describe, expect, it } from "vitest";

import {
  buildHydraulicEvolutionMap,
  buildLineageMap,
  buildSystemOverlay,
  createMultiRunContext,
  type EngineDiagnostics,
  type EngineFlowRegime,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1OperatorContext,
  type EngineV1SystemOverlay,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_36_001",
    observer_notes:    "Card 36 fixture",
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

function fakePrimitive(id: string, hydraulic: Partial<EngineHydraulicState> = {}): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal",
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 36 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:           { note: id },
    hydraulic_state:   fakeHydraulicState(hydraulic),
    origin_state:      null,
    historical_states: [],
  };
}

function fakeOverlay(id: string, regime: EngineFlowRegime = "laminar"): EngineOverlayResult {
  return {
    primitive_id:     id,
    reynolds_number:  regime === "turbulent" ? 5000 : regime === "transitional" ? 3000 : 1000,
    flow_regime:      regime,
    stability:        regime === "laminar" ? 0.9 : regime === "transitional" ? 0.5 : 0.2,
    in_critical_zone: false,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch:  false,
    sensitivity:      1.0,
    hysteresis:       3.0,
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

describe("Card 36 — buildSystemOverlay", () => {
  it("composes the Card 34 lineage map + Card 35 hydraulic evolution map", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [
        fakeOverlay("p1", "laminar"),
        fakeOverlay("p2", "transitional"),
      ]),
      fakeContext([fakePrimitive("p1")], [
        fakeOverlay("p1", "turbulent"),
      ]),
    ]);

    const out: EngineV1SystemOverlay = buildSystemOverlay(multi);

    const expectedLineageMap = buildLineageMap(multi);
    const expectedHydraulic  = buildHydraulicEvolutionMap(expectedLineageMap);

    expect(out.primitive_ids).toEqual(expectedLineageMap.primitive_ids);
    expect(out.lineageMap).toEqual(expectedLineageMap);
    expect(out.hydraulicEvolution).toEqual(expectedHydraulic);
  });

  it("primitive_ids on the overlay matches lineageMap.primitive_ids (single source of truth)", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p_z"), fakePrimitive("p_a")], []),
      fakeContext([fakePrimitive("p_m")],                       []),
    ]);

    const out = buildSystemOverlay(multi);

    expect(out.primitive_ids).toBe(out.lineageMap.primitive_ids);
    expect(out.primitive_ids).toEqual(["p_a", "p_m", "p_z"]);  // lex sort per Card 34
  });

  it("returns an all-empty overlay for an empty multi-run context", () => {
    const out = buildSystemOverlay(createMultiRunContext([]));
    expect(out.primitive_ids).toEqual([]);
    expect(out.lineageMap.lineages).toEqual({});
    expect(out.lineageMap.diffs).toEqual({});
    expect(out.lineageMap.overlays).toEqual({});
    expect(out.hydraulicEvolution.perPrimitive).toEqual({});
    expect(out.hydraulicEvolution.perRun).toEqual([]);
  });

  it("top-level shape pin — exactly { primitive_ids, lineageMap, hydraulicEvolution }", () => {
    const out = buildSystemOverlay(createMultiRunContext([]));
    expect(Object.keys(out).sort()).toEqual(
      ["hydraulicEvolution", "lineageMap", "primitive_ids"].sort(),
    );
  });

  it("does not mutate the input multi-run context (purity)", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", "laminar")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", "turbulent")]),
    ]);
    const snapshot = JSON.stringify(multi);

    buildSystemOverlay(multi);

    expect(JSON.stringify(multi)).toBe(snapshot);
  });

  it("is deterministic — same input produces structurally identical overlays", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [
        fakeOverlay("p1", "laminar"),
        fakeOverlay("p2", "transitional"),
      ]),
      fakeContext([fakePrimitive("p1")], [
        fakeOverlay("p1", "turbulent"),
      ]),
    ]);

    const o1 = buildSystemOverlay(multi);
    const o2 = buildSystemOverlay(multi);
    expect(JSON.stringify(o1)).toBe(JSON.stringify(o2));
  });
});
