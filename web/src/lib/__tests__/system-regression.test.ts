// Card 37 — computeSystemRegressionDiff test.
//
// Asserts the system-level regression analytic correctly:
//   - identifies primitive additions / removals across a run pair
//   - lists `changed` primitives via Card 32 lineage diff lookups
//   - computes hydraulic regime deltas (laminar / transitional /
//     turbulent / critical_zone / upper_branch)
//   - rejects out-of-bounds indices with RangeError (hardening)
//   - is pure + deterministic
//
// Pure unit test — no fetch, no session. Contexts built via fixture
// factories + buildSystemOverlay.

import { describe, expect, it } from "vitest";

import {
  buildSystemOverlay,
  computeSystemRegressionDiff,
  createMultiRunContext,
  type EngineDiagnostics,
  type EngineFlowRegime,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1OperatorContext,
  type EngineV1SystemRegressionDiff,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_37_001",
    observer_notes:    "Card 37 fixture",
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
      source:         "Card 37 fixture",
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

describe("Card 37 — computeSystemRegressionDiff", () => {
  it("identifies primitive additions and removals across adjacent runs", () => {
    // Run 0: p1, p2.   Run 1: p2, p3.   p1 removed, p3 added.
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], []),
      fakeContext([fakePrimitive("p2"), fakePrimitive("p3")], []),
    ]));

    const diff: EngineV1SystemRegressionDiff = computeSystemRegressionDiff(overlay, 0, 1);

    expect(diff.fromIndex).toBe(0);
    expect(diff.toIndex).toBe(1);
    expect(diff.primitiveChanges.added).toEqual(["p3"]);
    expect(diff.primitiveChanges.removed).toEqual(["p1"]);
  });

  it("populates `changed` for primitives whose lineage diff matches the index pair", () => {
    // p1 has hydraulic change between run 0 and run 1; p2 unchanged.
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1", { pressure: 5 }), fakePrimitive("p2")],
        [fakeOverlay("p1"), fakeOverlay("p2")],
      ),
      fakeContext(
        [fakePrimitive("p1", { pressure: 8 }), fakePrimitive("p2")],
        [fakeOverlay("p1"), fakeOverlay("p2")],
      ),
    ]));

    const diff = computeSystemRegressionDiff(overlay, 0, 1);

    expect(diff.primitiveChanges.changed).toEqual(["p1"]);
  });

  it("computes hydraulic deltas with correct signs (positive and negative)", () => {
    // Run 0: 2 laminar, 0 turbulent.   Run 1: 0 laminar, 2 turbulent.
    // → laminarDelta = -2, turbulentDelta = +2.
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "laminar" }), fakeOverlay("p2", { flow_regime: "laminar" })],
      ),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "turbulent" }), fakeOverlay("p2", { flow_regime: "turbulent" })],
      ),
    ]));

    const diff = computeSystemRegressionDiff(overlay, 0, 1);

    expect(diff.hydraulic.laminarDelta).toBe(-2);
    expect(diff.hydraulic.transitionalDelta).toBe(0);
    expect(diff.hydraulic.turbulentDelta).toBe(2);
    expect(diff.hydraulic.criticalZoneDelta).toBe(0);
    expect(diff.hydraulic.upperBranchDelta).toBe(0);
  });

  it("tracks critical_zone + upper_branch deltas", () => {
    // Run 0: nothing.   Run 1: p1 critical, p2 upper.
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1"), fakeOverlay("p2")],
      ),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [
          fakeOverlay("p1", { in_critical_zone: true }),
          fakeOverlay("p2", { on_upper_branch:  true }),
        ],
      ),
    ]));

    const diff = computeSystemRegressionDiff(overlay, 0, 1);
    expect(diff.hydraulic.criticalZoneDelta).toBe(1);
    expect(diff.hydraulic.upperBranchDelta).toBe(1);
  });

  it("returns empty added/removed/changed + zero hydraulic deltas for identical runs", () => {
    const buildRun = () =>
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "laminar" }), fakeOverlay("p2", { flow_regime: "laminar" })],
      );
    const overlay = buildSystemOverlay(createMultiRunContext([buildRun(), buildRun()]));

    const diff = computeSystemRegressionDiff(overlay, 0, 1);

    expect(diff.primitiveChanges.added).toEqual([]);
    expect(diff.primitiveChanges.removed).toEqual([]);
    expect(diff.primitiveChanges.changed).toEqual([]);
    expect(diff.hydraulic).toEqual({
      laminarDelta: 0, transitionalDelta: 0, turbulentDelta: 0,
      criticalZoneDelta: 0, upperBranchDelta: 0,
    });
  });

  it("supports the full 3-run scenario (0→1 AND 1→2 transitions)", () => {
    // Run 0: p1 laminar.   Run 1: p1 transitional + p2 laminar (p2 added).
    // Run 2: p1 turbulent  (p2 removed).
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "laminar" })]),
      fakeContext(
        [fakePrimitive("p1"), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "transitional" }), fakeOverlay("p2", { flow_regime: "laminar" })],
      ),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "turbulent" })]),
    ]));

    const d01 = computeSystemRegressionDiff(overlay, 0, 1);
    expect(d01.primitiveChanges.added).toEqual(["p2"]);
    expect(d01.primitiveChanges.removed).toEqual([]);
    expect(d01.primitiveChanges.changed).toContain("p1");   // overlay regime changed laminar→transitional
    expect(d01.hydraulic.laminarDelta).toBe(0);              // 1 → 1 (p1 left, p2 entered laminar)
    expect(d01.hydraulic.transitionalDelta).toBe(1);
    expect(d01.hydraulic.turbulentDelta).toBe(0);

    const d12 = computeSystemRegressionDiff(overlay, 1, 2);
    expect(d12.primitiveChanges.added).toEqual([]);
    expect(d12.primitiveChanges.removed).toEqual(["p2"]);
    expect(d12.primitiveChanges.changed).toContain("p1");
    expect(d12.hydraulic.laminarDelta).toBe(-1);
    expect(d12.hydraulic.transitionalDelta).toBe(-1);
    expect(d12.hydraulic.turbulentDelta).toBe(1);
  });

  it("hardening: throws RangeError on out-of-bounds indices", () => {
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
    ]));

    expect(() => computeSystemRegressionDiff(overlay, -1, 0)).toThrow(RangeError);
    expect(() => computeSystemRegressionDiff(overlay,  0, 5)).toThrow(RangeError);
    expect(() => computeSystemRegressionDiff(overlay,  0, 2)).toThrow(RangeError); // runCount=2 → max idx 1
    expect(() => computeSystemRegressionDiff(overlay,  0.5, 1)).toThrow(RangeError); // non-integer
  });

  it("documented constraint: non-adjacent indices give empty `changed` but valid hydraulic deltas", () => {
    // Run 0 → Run 2 skips the middle. Hydraulic deltas should still
    // be correct (perRun lookup is direct), but `changed` is empty
    // because Card 32 only stores (0→1) and (1→2) diff entries.
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext([fakePrimitive("p1", { pressure: 1 })], [fakeOverlay("p1", { flow_regime: "laminar" })]),
      fakeContext([fakePrimitive("p1", { pressure: 5 })], [fakeOverlay("p1", { flow_regime: "transitional" })]),
      fakeContext([fakePrimitive("p1", { pressure: 9 })], [fakeOverlay("p1", { flow_regime: "turbulent" })]),
    ]));

    const d02 = computeSystemRegressionDiff(overlay, 0, 2);
    // Hydraulic delta correct: laminar 1 → 0, turbulent 0 → 1.
    expect(d02.hydraulic.laminarDelta).toBe(-1);
    expect(d02.hydraulic.turbulentDelta).toBe(1);
    // `changed` empty by Card 32 constraint (no (0→2) diff entry).
    expect(d02.primitiveChanges.changed).toEqual([]);
  });

  it("does not mutate the input system overlay (purity)", () => {
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "laminar" })]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1", { flow_regime: "turbulent" })]),
    ]));
    const snapshot = JSON.stringify(overlay);

    computeSystemRegressionDiff(overlay, 0, 1);

    expect(JSON.stringify(overlay)).toBe(snapshot);
  });

  it("is deterministic — same inputs produce structurally identical diffs", () => {
    const overlay = buildSystemOverlay(createMultiRunContext([
      fakeContext(
        [fakePrimitive("p1", { pressure: 5 }), fakePrimitive("p2")],
        [fakeOverlay("p1", { flow_regime: "laminar" }), fakeOverlay("p2", { flow_regime: "transitional" })],
      ),
      fakeContext(
        [fakePrimitive("p1", { pressure: 8 })],
        [fakeOverlay("p1", { flow_regime: "turbulent", in_critical_zone: true })],
      ),
    ]));

    const r1 = computeSystemRegressionDiff(overlay, 0, 1);
    const r2 = computeSystemRegressionDiff(overlay, 0, 1);
    expect(JSON.stringify(r1)).toBe(JSON.stringify(r2));
  });
});
