// Card 30 — computeEngineV1Delta composition test.
//
// Asserts the unified delta object equals the three Card 29 helper
// results stitched into one structure, with no mutation or drift.
//
// Pure unit test — no fetch, no session, no module-init dance.
// Contexts built via fixture factories (same approach as multi-run.test.ts).

import { describe, expect, it } from "vitest";

import {
  computeEngineV1Delta,
  diffDiagnostics,
  diffOverlays,
  diffPrimitives,
  type EngineDiagnostics,
  type EngineFlowRegime,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1Delta,
  type EngineV1OperatorContext,
} from "../api";

function fakeDiagnostics(overrides: Partial<EngineDiagnostics> = {}): EngineDiagnostics {
  return {
    observation_id:    "obs_30_001",
    observer_notes:    "Card 30 fixture",
    confidence_level:  0.7,
    validation_status: "unvalidated",
    early_warnings:    {},
    errors:            [],
    interventions:     [],
    ...overrides,
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

function fakePrimitive(id: string, type: EnginePrimitiveType = "signal"): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: type,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 30 fixture",
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

interface OverlayOverrides {
  flow_regime?:      EngineFlowRegime;
  in_critical_zone?: boolean;
  on_upper_branch?:  boolean;
  hysteresis?:       number;
}

function fakeOverlay(primitiveId: string, o: OverlayOverrides = {}): EngineOverlayResult {
  return {
    primitive_id:     primitiveId,
    reynolds_number:  o.flow_regime === "turbulent" ? 5000 : o.flow_regime === "transitional" ? 3000 : 1000,
    flow_regime:      o.flow_regime      ?? "laminar",
    stability:        o.flow_regime === "laminar" ? 0.9 : o.flow_regime === "transitional" ? 0.5 : 0.2,
    in_critical_zone: o.in_critical_zone ?? false,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch:  o.on_upper_branch  ?? false,
    sensitivity:      1.0,
    hysteresis:       o.hysteresis       ?? 3.0,
  };
}

function fakeContext(
  primitives:  EnginePrimitive[],
  overlays:    EngineOverlayResult[],
  diagnostics: EngineDiagnostics = fakeDiagnostics(),
): EngineV1OperatorContext {
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

describe("Card 30 — computeEngineV1Delta", () => {
  it("composes the three Card 29 helpers into a single typed delta", () => {
    const a = fakeContext(
      [fakePrimitive("p1"), fakePrimitive("p2")],
      [fakeOverlay("p1", { flow_regime: "laminar" })],
      fakeDiagnostics({ confidence_level: 0.5 }),
    );
    const b = fakeContext(
      [fakePrimitive("p2"), fakePrimitive("p3")],
      [fakeOverlay("p1", { flow_regime: "turbulent" })],
      fakeDiagnostics({ confidence_level: 0.9 }),
    );

    const delta: EngineV1Delta = computeEngineV1Delta(a, b);

    // Each sub-field equals the direct helper result.
    expect(delta.primitives).toEqual(diffPrimitives(a, b));
    expect(delta.overlays).toEqual(diffOverlays(a, b));
    expect(delta.diagnostics).toEqual(diffDiagnostics(a, b));

    // Concrete shape — confirms the expected entries land in the right slots.
    expect(delta.primitives.added.map((p) => p.metadata.primitive_id)).toEqual(["p3"]);
    expect(delta.primitives.removed.map((p) => p.metadata.primitive_id)).toEqual(["p1"]);
    expect(delta.overlays.changed.map((o) => o.primitive_id)).toEqual(["p1"]);
    expect(delta.diagnostics.confidence_level).toBe(0.9);
  });

  it("returns an all-empty delta when the two contexts are identical", () => {
    const primitives = [fakePrimitive("p1"), fakePrimitive("p2")];
    const overlays   = [fakeOverlay("p1")];
    const diagnostics = fakeDiagnostics();
    const a = fakeContext(primitives, overlays, diagnostics);
    const b = fakeContext(primitives, overlays, diagnostics);

    const delta = computeEngineV1Delta(a, b);

    expect(delta.primitives.added).toEqual([]);
    expect(delta.primitives.removed).toEqual([]);
    expect(delta.overlays.changed).toEqual([]);
    expect(delta.diagnostics).toEqual({});
  });

  it("produces the exact { primitives, overlays, diagnostics } top-level shape", () => {
    const a = fakeContext([], [], fakeDiagnostics());
    const b = fakeContext([], [], fakeDiagnostics());

    const delta = computeEngineV1Delta(a, b);

    expect(Object.keys(delta).sort()).toEqual(
      ["diagnostics", "overlays", "primitives"].sort(),
    );
    expect(Object.keys(delta.primitives).sort()).toEqual(["added", "removed"].sort());
    expect(Object.keys(delta.overlays)).toEqual(["changed"]);
  });

  it("does not mutate the input contexts (purity)", () => {
    const a = fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")], fakeDiagnostics());
    const b = fakeContext(
      [fakePrimitive("p2")],
      [fakeOverlay("p2", { flow_regime: "turbulent" })],
      fakeDiagnostics({ observation_id: "obs_b" }),
    );
    const snapshotA = JSON.stringify(a);
    const snapshotB = JSON.stringify(b);

    computeEngineV1Delta(a, b);

    expect(JSON.stringify(a)).toBe(snapshotA);
    expect(JSON.stringify(b)).toBe(snapshotB);
  });

  it("is deterministic — same inputs produce structurally identical deltas", () => {
    const a = fakeContext(
      [fakePrimitive("p1"), fakePrimitive("p2")],
      [fakeOverlay("p1", { flow_regime: "laminar" })],
      fakeDiagnostics({ confidence_level: 0.5 }),
    );
    const b = fakeContext(
      [fakePrimitive("p2"), fakePrimitive("p3")],
      [fakeOverlay("p1", { flow_regime: "turbulent" })],
      fakeDiagnostics({ confidence_level: 0.9 }),
    );

    const d1 = computeEngineV1Delta(a, b);
    const d2 = computeEngineV1Delta(a, b);

    // Structural equality via JSON-stringify — separate runs, same shape.
    expect(JSON.stringify(d1)).toBe(JSON.stringify(d2));
  });
});
