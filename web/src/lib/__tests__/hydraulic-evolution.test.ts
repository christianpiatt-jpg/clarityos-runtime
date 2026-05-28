// Card 35 — buildHydraulicEvolutionMap test.
//
// Asserts the hydraulic evolution map:
//   - captures per-primitive hydraulic state + overlay across runs
//   - rolls up per-run system-wide counts (laminar / transitional /
//     turbulent / critical_zone / upper_branch)
//   - handles primitives appearing and disappearing across runs
//   - is pure + deterministic
//
// Pure unit test — no fetch, no session. Lineage maps built via
// fixture factories + buildLineageMap.

import { describe, expect, it } from "vitest";

import {
  buildHydraulicEvolutionMap,
  buildLineageMap,
  createMultiRunContext,
  type EngineDiagnostics,
  type EngineFlowRegime,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1HydraulicEvolutionMap,
  type EngineV1OperatorContext,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_35_001",
    observer_notes:    "Card 35 fixture",
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
      source:         "Card 35 fixture",
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

interface OverlayOverrides {
  flow_regime?:      EngineFlowRegime;
  in_critical_zone?: boolean;
  on_upper_branch?:  boolean;
}

function fakeOverlay(id: string, o: OverlayOverrides = {}): EngineOverlayResult {
  return {
    primitive_id:     id,
    reynolds_number:  o.flow_regime === "turbulent" ? 5000 : o.flow_regime === "transitional" ? 3000 : 1000,
    flow_regime:      o.flow_regime      ?? "laminar",
    stability:        o.flow_regime === "laminar" ? 0.9 : o.flow_regime === "transitional" ? 0.5 : 0.2,
    in_critical_zone: o.in_critical_zone ?? false,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch:  o.on_upper_branch  ?? false,
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

describe("Card 35 — buildHydraulicEvolutionMap", () => {
  it("captures per-primitive hydraulic state + overlay across runs", () => {
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1", { pressure: 5 })],
        [fakeOverlay("p1", { flow_regime: "laminar" })],
      ),
      fakeContext(
        [fakePrimitive("p1", { pressure: 8 })],
        [fakeOverlay("p1", { flow_regime: "turbulent" })],
      ),
    ]));

    const evo: EngineV1HydraulicEvolutionMap = buildHydraulicEvolutionMap(lineageMap);

    expect(evo.primitive_ids).toEqual(["p1"]);
    const p1 = evo.perPrimitive["p1"];
    expect(p1.runs).toHaveLength(2);
    expect(p1.runs[0].hydraulic_state?.pressure).toBe(5);
    expect(p1.runs[1].hydraulic_state?.pressure).toBe(8);
    expect(p1.runs[0].overlay?.flow_regime).toBe("laminar");
    expect(p1.runs[1].overlay?.flow_regime).toBe("turbulent");
  });

  it("rolls up per-run regime counts correctly across primitives", () => {
    // Run 0: laminar, transitional.   Run 1: turbulent, laminar.
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "laminar" }), fakeOverlay("p2", { flow_regime: "transitional" })],
      ),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "turbulent" }), fakeOverlay("p2", { flow_regime: "laminar" })],
      ),
    ]));

    const evo = buildHydraulicEvolutionMap(lineageMap);

    expect(evo.perRun).toHaveLength(2);
    expect(evo.perRun[0]).toEqual({
      index: 0, laminar: 1, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0,
    });
    expect(evo.perRun[1]).toEqual({
      index: 1, laminar: 1, transitional: 0, turbulent: 1, critical_zone: 0, upper_branch: 0,
    });
  });

  it("counts critical_zone and upper_branch transitions correctly", () => {
    // Run 0: nothing critical.   Run 1: p1 critical, p2 upper.   Run 2: both critical AND upper.
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1"), fakeOverlay("p2")],
      ),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [
          fakeOverlay("p1", { in_critical_zone: true }),
          fakeOverlay("p2", { on_upper_branch: true }),
        ],
      ),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [
          fakeOverlay("p1", { in_critical_zone: true, on_upper_branch: true }),
          fakeOverlay("p2", { in_critical_zone: true, on_upper_branch: true }),
        ],
      ),
    ]));

    const evo = buildHydraulicEvolutionMap(lineageMap);

    expect(evo.perRun[0].critical_zone).toBe(0);
    expect(evo.perRun[0].upper_branch).toBe(0);
    expect(evo.perRun[1].critical_zone).toBe(1);
    expect(evo.perRun[1].upper_branch).toBe(1);
    expect(evo.perRun[2].critical_zone).toBe(2);
    expect(evo.perRun[2].upper_branch).toBe(2);
  });

  it("returns hydraulic_state=null and skips overlay-less runs in counts", () => {
    // p1 appears only in run 1. perRun[0] should see 0 of everything for p1.
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext([fakePrimitive("p_other")], [fakeOverlay("p_other", { flow_regime: "laminar" })]),
      fakeContext(
        [fakePrimitive("p_other"), fakePrimitive("p1")],
        [
          fakeOverlay("p_other", { flow_regime: "laminar" }),
          fakeOverlay("p1",      { flow_regime: "turbulent" }),
        ],
      ),
    ]));

    const evo = buildHydraulicEvolutionMap(lineageMap);

    // p1 absent in run 0 → hydraulic_state null + no overlay contribution.
    const p1 = evo.perPrimitive["p1"];
    expect(p1.runs[0].hydraulic_state).toBeNull();
    expect(p1.runs[0].overlay).toBeNull();
    expect(p1.runs[1].hydraulic_state?.pressure).toBe(5);

    // Counts for run 0: only p_other (laminar). Run 1: p_other laminar + p1 turbulent.
    expect(evo.perRun[0].laminar).toBe(1);
    expect(evo.perRun[0].turbulent).toBe(0);
    expect(evo.perRun[1].laminar).toBe(1);
    expect(evo.perRun[1].turbulent).toBe(1);
  });

  it("handles an empty lineage map (zero primitives, zero runs)", () => {
    const evo = buildHydraulicEvolutionMap(
      buildLineageMap(createMultiRunContext([])),
    );
    expect(evo.primitive_ids).toEqual([]);
    expect(evo.perPrimitive).toEqual({});
    expect(evo.perRun).toEqual([]);
  });

  it("handles a lineage map with runs but no primitives", () => {
    const evo = buildHydraulicEvolutionMap(
      buildLineageMap(createMultiRunContext([fakeContext([], []), fakeContext([], [])])),
    );
    expect(evo.primitive_ids).toEqual([]);
    expect(evo.perPrimitive).toEqual({});
    // No primitives → runCount is 0 by the helper's derivation rule.
    expect(evo.perRun).toEqual([]);
  });

  it("covers the full card scenario: regime + critical + branch transitions across 3 runs", () => {
    // p_a:  laminar → transitional → turbulent
    // p_b:  transitional → turbulent → laminar
    // p_c:  enters critical zone in run 1, exits in run 2
    // p_d:  enters upper branch in run 1, exits in run 2
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p_a"), fakePrimitive("p_b"), fakePrimitive("p_c"), fakePrimitive("p_d")],
        [
          fakeOverlay("p_a", { flow_regime: "laminar" }),
          fakeOverlay("p_b", { flow_regime: "transitional" }),
          fakeOverlay("p_c", { flow_regime: "laminar", in_critical_zone: false }),
          fakeOverlay("p_d", { flow_regime: "laminar", on_upper_branch:  false }),
        ],
      ),
      fakeContext(
        [fakePrimitive("p_a"), fakePrimitive("p_b"), fakePrimitive("p_c"), fakePrimitive("p_d")],
        [
          fakeOverlay("p_a", { flow_regime: "transitional" }),
          fakeOverlay("p_b", { flow_regime: "turbulent" }),
          fakeOverlay("p_c", { flow_regime: "laminar", in_critical_zone: true }),
          fakeOverlay("p_d", { flow_regime: "laminar", on_upper_branch:  true }),
        ],
      ),
      fakeContext(
        [fakePrimitive("p_a"), fakePrimitive("p_b"), fakePrimitive("p_c"), fakePrimitive("p_d")],
        [
          fakeOverlay("p_a", { flow_regime: "turbulent" }),
          fakeOverlay("p_b", { flow_regime: "laminar" }),
          fakeOverlay("p_c", { flow_regime: "laminar", in_critical_zone: false }),
          fakeOverlay("p_d", { flow_regime: "laminar", on_upper_branch:  false }),
        ],
      ),
    ]));

    const evo = buildHydraulicEvolutionMap(lineageMap);

    // Run 0: lam=p_a,p_c,p_d  trans=p_b  turb=0  crit=0  upper=0
    expect(evo.perRun[0]).toEqual({
      index: 0, laminar: 3, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0,
    });
    // Run 1: lam=p_c,p_d  trans=p_a  turb=p_b  crit=p_c  upper=p_d
    expect(evo.perRun[1]).toEqual({
      index: 1, laminar: 2, transitional: 1, turbulent: 1, critical_zone: 1, upper_branch: 1,
    });
    // Run 2: lam=p_b,p_c,p_d  trans=0  turb=p_a  crit=0  upper=0
    expect(evo.perRun[2]).toEqual({
      index: 2, laminar: 3, transitional: 0, turbulent: 1, critical_zone: 0, upper_branch: 0,
    });
  });

  it("does not mutate the input lineage map (purity)", () => {
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "turbulent" })]),
    ]));
    const snapshot = JSON.stringify(lineageMap);

    buildHydraulicEvolutionMap(lineageMap);

    expect(JSON.stringify(lineageMap)).toBe(snapshot);
  });

  it("is deterministic — same input produces structurally identical maps", () => {
    const lineageMap = buildLineageMap(createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [
        fakeOverlay("p1", { flow_regime: "laminar" }),
        fakeOverlay("p2", { flow_regime: "transitional" }),
      ]),
      fakeContext([fakePrimitive("p1")], [
        fakeOverlay("p1", { flow_regime: "turbulent", in_critical_zone: true }),
      ]),
    ]));

    const e1 = buildHydraulicEvolutionMap(lineageMap);
    const e2 = buildHydraulicEvolutionMap(lineageMap);
    expect(JSON.stringify(e1)).toBe(JSON.stringify(e2));
  });
});
