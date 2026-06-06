// Card 25 — normalizeEngineResponse pure-function test.
//
// Asserts that the Engine V1 output normalizer:
//   1. preserves primitives / overlays / diagnostics verbatim on a
//      well-formed response
//   2. produces correct counts
//   3. defensively defaults each field when a malformed payload
//      arrives at runtime (fields cast as undefined via `as any`)
//   4. uses the principled EMPTY_ENGINE_DIAGNOSTICS shape (all 7
//      EngineDiagnostics fields present) when diagnostics is missing
//
// No mocking, no fetch, no session. Pure unit test.

import { describe, expect, it } from "vitest";

import {
  normalizeEngineResponse,
  type EngineDiagnostics,
  type EngineHydraulicState,
  type EngineOverlayResult,
  type EnginePrimitive,
  type EngineResponseV1,
  type NormalizedEngineV1,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_test_25_001",
    observer_notes:    "Card 25 fixture",
    confidence_level:  0.7,
    validation_status: "unvalidated",
    early_warnings:    { mean_reynolds: 4000 },
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
      source:         "Card 25 fixture",
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

describe("Card 25 — normalizeEngineResponse", () => {
  it("preserves a well-formed response verbatim with correct counts", () => {
    const prim1 = fakePrimitive("prim_001");
    const prim2 = fakePrimitive("prim_002");
    const overlay1 = fakeOverlay("prim_001");
    const diagnostics = fakeDiagnostics();

    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [prim1, prim2],
      overlays:    [overlay1],
      regression:  null,
      projection:  null,
      diagnostics,
    };

    const out: NormalizedEngineV1 = normalizeEngineResponse(response);

    expect(out.primitives).toEqual([prim1, prim2]);
    expect(out.overlays).toEqual([overlay1]);
    expect(out.diagnostics).toBe(diagnostics);
    expect(out.primitiveCount).toBe(2);
    expect(out.overlayCount).toBe(1);
  });

  it("returns zero counts + empty arrays when primitives/overlays are empty", () => {
    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [],
      overlays:    [],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };

    const out = normalizeEngineResponse(response);

    expect(out.primitives).toEqual([]);
    expect(out.overlays).toEqual([]);
    expect(out.primitiveCount).toBe(0);
    expect(out.overlayCount).toBe(0);
  });

  it("defends against undefined primitives / overlays at runtime", () => {
    // Simulate a malformed payload that violates the EngineResponseV1
    // type contract (e.g. backend bug / proxy mangling). The
    // normalizer's `??` fallbacks should produce empty arrays instead
    // of letting undefined drift through to downstream consumers.
    const malformed = {
      ok: true,
      // primitives + overlays deliberately omitted
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    } as unknown as EngineResponseV1;

    const out = normalizeEngineResponse(malformed);

    expect(out.primitives).toEqual([]);
    expect(out.overlays).toEqual([]);
    expect(out.primitiveCount).toBe(0);
    expect(out.overlayCount).toBe(0);
  });

  it("supplies a fully-typed EngineDiagnostics default when diagnostics is missing", () => {
    // Card spec's `?? {}` doesn't type-check against the strict
    // EngineDiagnostics shape; the normalizer falls back to
    // EMPTY_ENGINE_DIAGNOSTICS (all 7 fields present, zero-valued).
    const malformed = {
      ok: true,
      primitives:  [],
      overlays:    [],
      regression:  null,
      projection:  null,
      // diagnostics deliberately omitted
    } as unknown as EngineResponseV1;

    const out = normalizeEngineResponse(malformed);

    expect(out.diagnostics.observation_id).toBe("");
    expect(out.diagnostics.observer_notes).toBe("");
    expect(out.diagnostics.confidence_level).toBe(0);
    expect(out.diagnostics.validation_status).toBe("unvalidated");
    expect(out.diagnostics.early_warnings).toEqual({});
    expect(out.diagnostics.errors).toEqual([]);
    expect(out.diagnostics.interventions).toEqual([]);
  });

  it("Card 26A — carries regression + projection through to the normalized view", () => {
    // Card 26A extended NormalizedEngineV1 to include the top-level
    // analytical outputs so downstream consumers (classifier, operator
    // tools, future UI) don't need to keep the raw EngineResponseV1
    // alongside the normalized view.
    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [],
      overlays:    [],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };

    const out = normalizeEngineResponse(response);
    expect(out.regression).toBeNull();
    expect(out.projection).toBeNull();

    // When the response has analytical outputs, they pass through.
    const responseWithRegression: EngineResponseV1 = {
      ...response,
      regression: {
        primitive_id:           "prim_001",
        // Minimal-shape regression (other required fields omitted via
        // a defensive cast — this test only pins passthrough identity,
        // not regression-result correctness).
      } as unknown as NonNullable<EngineResponseV1["regression"]>,
    };
    const out2 = normalizeEngineResponse(responseWithRegression);
    expect(out2.regression).toBe(responseWithRegression.regression);
  });

  it("is pure — does not mutate the input response", () => {
    const response: EngineResponseV1 = {
      ok: true,
      primitives:  [fakePrimitive("prim_pure_001")],
      overlays:    [fakeOverlay("prim_pure_001")],
      regression:  null,
      projection:  null,
      diagnostics: fakeDiagnostics(),
    };
    const snapshot = JSON.stringify(response);

    normalizeEngineResponse(response);

    expect(JSON.stringify(response)).toBe(snapshot);
  });
});
