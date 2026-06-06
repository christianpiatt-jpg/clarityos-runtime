// Card 26A — classifyEngineV1 contract-faithful test.
//
// Asserts the Engine V1 classifier categorises primitives by
// metadata.primitive_type, overlays by flow_regime + in_critical_zone
// + on_upper_branch, and passes regression / projection / diagnostics
// through unchanged.
//
// No mocking, no fetch. Pure unit test.

import { describe, expect, it } from "vitest";

import {
  classifyEngineV1,
  normalizeEngineResponse,
  type EngineDiagnostics,
  type EngineFlowRegime,
  type EngineHydraulicState,
  type EngineOverlayResult,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineResponseV1,
  type EngineV1Classification,
  type NormalizedEngineV1,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_test_26A_001",
    observer_notes:    "Card 26A fixture",
    confidence_level:  0.7,
    validation_status: "unvalidated",
    early_warnings:    {},
    errors:            [],
    interventions:     [],
  };
}

function fakeHydraulicState(): EngineHydraulicState {
  return {
    pressure:   5.0,
    gradient:   0.0,
    flow:       4.0,
    resistance: 2.0,
    timestamp:  "2026-05-28T00:00:00+00:00",
  };
}

function fakePrimitive(id: string, type: EnginePrimitiveType): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: type,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 26A fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:           { note: id },
    hydraulic_state:   fakeHydraulicState(),
    origin_state:      null,
    historical_states: [],
  };
}

function fakeOverlay(
  primitiveId: string,
  flowRegime: EngineFlowRegime,
  opts: { critical?: boolean; upper?: boolean } = {},
): EngineOverlayResult {
  return {
    primitive_id:     primitiveId,
    reynolds_number:  flowRegime === "turbulent" ? 5000 : flowRegime === "transitional" ? 3000 : 1000,
    flow_regime:      flowRegime,
    stability:        flowRegime === "laminar" ? 0.9 : flowRegime === "transitional" ? 0.5 : 0.2,
    in_critical_zone: opts.critical ?? false,
    distance_to_fold: opts.critical ? 0.5 : 3.0,
    resilience:       opts.critical ? 9.0 : 4.0,
    curve_position:   opts.upper ? 7.0 : 3.0,
    on_upper_branch:  opts.upper ?? false,
    sensitivity:      opts.critical ? 4.0 : 1.0,
    hysteresis:       3.0,
  };
}

function normalizedFrom(
  primitives: EnginePrimitive[],
  overlays:   EngineOverlayResult[],
  extras: Partial<Pick<EngineResponseV1, "regression" | "projection">> = {},
): NormalizedEngineV1 {
  const response: EngineResponseV1 = {
    ok: true,
    primitives,
    overlays,
    regression:  extras.regression ?? null,
    projection:  extras.projection ?? null,
    diagnostics: fakeDiagnostics(),
  };
  return normalizeEngineResponse(response);
}

describe("Card 26A — classifyEngineV1", () => {
  it("partitions primitives by metadata.primitive_type", () => {
    const normalized = normalizedFrom(
      [
        fakePrimitive("p_sig",  "signal"),
        fakePrimitive("p_ent",  "entity"),
        fakePrimitive("p_att",  "attitude"),
        fakePrimitive("p_rel",  "relationship"),
        fakePrimitive("p_evt",  "event"),
        fakePrimitive("p_tmp",  "temperature"),
        fakePrimitive("p_sig2", "signal"),
      ],
      [],
    );

    const out: EngineV1Classification = classifyEngineV1(normalized);

    expect(out.signals.map((p) => p.metadata.primitive_id)).toEqual(["p_sig", "p_sig2"]);
    expect(out.entities.map((p) => p.metadata.primitive_id)).toEqual(["p_ent"]);
    expect(out.attitudes.map((p) => p.metadata.primitive_id)).toEqual(["p_att"]);
    expect(out.relationships.map((p) => p.metadata.primitive_id)).toEqual(["p_rel"]);
    expect(out.events.map((p) => p.metadata.primitive_id)).toEqual(["p_evt"]);
    expect(out.temperatures.map((p) => p.metadata.primitive_id)).toEqual(["p_tmp"]);
  });

  it("partitions overlays by flow_regime", () => {
    const normalized = normalizedFrom(
      [],
      [
        fakeOverlay("o1", "laminar"),
        fakeOverlay("o2", "transitional"),
        fakeOverlay("o3", "turbulent"),
        fakeOverlay("o4", "laminar"),
      ],
    );

    const out = classifyEngineV1(normalized);

    expect(out.laminarOverlays.map((o) => o.primitive_id)).toEqual(["o1", "o4"]);
    expect(out.transitionalOverlays.map((o) => o.primitive_id)).toEqual(["o2"]);
    expect(out.turbulentOverlays.map((o) => o.primitive_id)).toEqual(["o3"]);
  });

  it("subsets overlays by in_critical_zone + on_upper_branch", () => {
    const normalized = normalizedFrom(
      [],
      [
        fakeOverlay("o_low_safe",     "laminar",      { critical: false, upper: false }),
        fakeOverlay("o_mid_critical", "transitional", { critical: true,  upper: false }),
        fakeOverlay("o_high_upper",   "turbulent",    { critical: false, upper: true  }),
        fakeOverlay("o_both",         "transitional", { critical: true,  upper: true  }),
      ],
    );

    const out = classifyEngineV1(normalized);

    // Both subsets include "o_both" since it satisfies each predicate.
    expect(out.criticalZoneOverlays.map((o) => o.primitive_id))
      .toEqual(["o_mid_critical", "o_both"]);
    expect(out.upperBranchOverlays.map((o) => o.primitive_id))
      .toEqual(["o_high_upper", "o_both"]);
  });

  it("passes regression + projection + diagnostics through unchanged", () => {
    const normalized = normalizedFrom(
      [fakePrimitive("p1", "signal")],
      [fakeOverlay("o1", "laminar")],
    );

    const out = classifyEngineV1(normalized);

    expect(out.regression).toBe(normalized.regression);
    expect(out.projection).toBe(normalized.projection);
    expect(out.diagnostics).toBe(normalized.diagnostics);
    expect(out.diagnostics.observation_id).toBe("obs_test_26A_001");
  });

  it("returns empty arrays for every category when input is empty", () => {
    const normalized = normalizedFrom([], []);
    const out = classifyEngineV1(normalized);

    for (const k of [
      "signals", "entities", "attitudes", "relationships", "events", "temperatures",
      "laminarOverlays", "transitionalOverlays", "turbulentOverlays",
      "criticalZoneOverlays", "upperBranchOverlays",
    ] as const) {
      expect(out[k]).toEqual([]);
    }
  });

  it("is pure — does not mutate the input normalized view", () => {
    const normalized = normalizedFrom(
      [fakePrimitive("p1", "signal"), fakePrimitive("p2", "entity")],
      [fakeOverlay("o1", "laminar", { critical: true }), fakeOverlay("o2", "turbulent")],
    );
    const snapshot = JSON.stringify(normalized);

    classifyEngineV1(normalized);

    expect(JSON.stringify(normalized)).toBe(snapshot);
  });
});
