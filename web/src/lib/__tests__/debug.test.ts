// Card 23 — debugEngineV1 introspection helper test.
//
// Pure-function unit test for the Phase-1 minimal debug surface.
// No fetch, no session, no module-init dance — just construct a
// fixture EngineResponseV1 and verify the debug shape.

import { describe, expect, it } from "vitest";

import {
  debugEngineV1,
  type EngineDiagnostics,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1DebugSnapshot,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_test_23_001",
    observer_notes:    "Card 23 fixture",
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

function fakePrimitive(id: string): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal",
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 23 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:         { note: id },
    hydraulic_state: fakeHydraulicState(),
    origin_state:       null,
    historical_states:  [],
  };
}

function fakeOverlay(primitiveId: string): EngineOverlayResult {
  return {
    primitive_id:     primitiveId,
    reynolds_number:  4000.0,
    flow_regime:      "transitional",
    stability:        0.5,
    in_critical_zone: true,
    distance_to_fold: 0.0,
    resilience:       10.0,
    curve_position:   5.0,
    on_upper_branch:  false,
    sensitivity:      4.0,
    hysteresis:       3.0,
  };
}

describe("Card 23 — debugEngineV1", () => {
  it("returns counts + diagnostics + first primitive + first overlay", () => {
    const prim1 = fakePrimitive("prim_001");
    const prim2 = fakePrimitive("prim_002");
    const overlay1 = fakeOverlay("prim_001");
    const overlay2 = fakeOverlay("prim_002");

    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [prim1, prim2],
      overlays:    [overlay1, overlay2],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };

    const snapshot: EngineV1DebugSnapshot = debugEngineV1(response);

    expect(snapshot.primitiveCount).toBe(2);
    expect(snapshot.overlayCount).toBe(2);
    expect(snapshot.firstPrimitive).toBe(prim1);
    expect(snapshot.firstOverlay).toBe(overlay1);
    expect(snapshot.diagnostics).toBe(response.diagnostics);
    expect(snapshot.diagnostics.observation_id).toBe("obs_test_23_001");
  });

  it("returns nulls for first primitive / first overlay when empty", () => {
    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [],
      overlays:    [],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };

    const snapshot = debugEngineV1(response);

    expect(snapshot.primitiveCount).toBe(0);
    expect(snapshot.overlayCount).toBe(0);
    expect(snapshot.firstPrimitive).toBeNull();
    expect(snapshot.firstOverlay).toBeNull();
    expect(snapshot.diagnostics.observation_id).toBe("obs_test_23_001");
  });

  it("is pure — does not mutate the input response", () => {
    const original: EngineResponseV1 = {
      ok: true,
      primitives:  [fakePrimitive("prim_pure_001")],
      overlays:    [fakeOverlay("prim_pure_001")],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };
    const snapshot = JSON.stringify(original);

    debugEngineV1(original);

    // Untouched: same JSON representation post-call.
    expect(JSON.stringify(original)).toBe(snapshot);
  });
});
