// Card 31 — extractPrimitiveLineage test.
//
// Asserts:
//   - lineage length matches the multi-run context's run count
//   - primitives present in only some runs are correctly null in
//     absent runs
//   - overlays present/absent track per-run state
//   - run indices preserved
//   - purity (no mutation of contexts)
//   - determinism (same inputs → same outputs)
//
// Pure unit test — no fetch, no session. Contexts built via fixture
// factories (same approach as multi-run / delta tests).

import { describe, expect, it } from "vitest";

import {
  createMultiRunContext,
  extractPrimitiveLineage,
  type EngineDiagnostics,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineOverlayResult,
  type EngineResponseV1,
  type EngineV1OperatorContext,
} from "../api";

function fakeDiagnostics(): EngineDiagnostics {
  return {
    observation_id:    "obs_31_001",
    observer_notes:    "Card 31 fixture",
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

function fakePrimitive(id: string, type: EnginePrimitiveType = "signal"): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: type,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 31 fixture",
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

function fakeOverlay(primitiveId: string): EngineOverlayResult {
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

describe("Card 31 — extractPrimitiveLineage", () => {
  it("returns one entry per run with indices preserved", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
    ]);

    const lineage = extractPrimitiveLineage(multi, "p1");

    expect(lineage.primitive_id).toBe("p1");
    expect(lineage.runs).toHaveLength(3);
    expect(lineage.runs.map((r) => r.index)).toEqual([0, 1, 2]);
  });

  it("returns the primitive + overlay where present, null where absent", () => {
    // p1 present in runs 0 and 2, absent in run 1.
    const r0_p1 = fakePrimitive("p1");
    const r0_o1 = fakeOverlay("p1");
    const r2_p1 = fakePrimitive("p1");
    const r2_o1 = fakeOverlay("p1");

    const multi = createMultiRunContext([
      fakeContext([r0_p1, fakePrimitive("p_other")], [r0_o1]),
      fakeContext([fakePrimitive("p_other")], []),
      fakeContext([r2_p1], [r2_o1]),
    ]);

    const lineage = extractPrimitiveLineage(multi, "p1");

    expect(lineage.runs[0].primitive).toBe(r0_p1);
    expect(lineage.runs[0].overlay).toBe(r0_o1);

    expect(lineage.runs[1].primitive).toBeNull();
    expect(lineage.runs[1].overlay).toBeNull();

    expect(lineage.runs[2].primitive).toBe(r2_p1);
    expect(lineage.runs[2].overlay).toBe(r2_o1);
  });

  it("returns overlay=null when the primitive exists but no matching overlay does", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [/* no overlay for p1 */]),
    ]);

    const lineage = extractPrimitiveLineage(multi, "p1");

    expect(lineage.runs[0].primitive).not.toBeNull();
    expect(lineage.runs[0].overlay).toBeNull();
  });

  it("returns null in every entry when the primitive is absent from every run", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p_other")], []),
      fakeContext([fakePrimitive("p_other2")], []),
    ]);

    const lineage = extractPrimitiveLineage(multi, "p_missing");

    expect(lineage.runs).toHaveLength(2);
    for (const entry of lineage.runs) {
      expect(entry.primitive).toBeNull();
      expect(entry.overlay).toBeNull();
    }
  });

  it("handles an empty multi-run context", () => {
    const multi = createMultiRunContext([]);
    const lineage = extractPrimitiveLineage(multi, "anything");
    expect(lineage.primitive_id).toBe("anything");
    expect(lineage.runs).toEqual([]);
  });

  it("does not mutate the input multi-run context (purity)", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p2")], [fakeOverlay("p2")]),
    ]);
    const snapshot = JSON.stringify(multi);

    extractPrimitiveLineage(multi, "p1");
    extractPrimitiveLineage(multi, "p_missing");

    expect(JSON.stringify(multi)).toBe(snapshot);
  });

  it("is deterministic — same inputs produce structurally identical lineages", () => {
    const multi = createMultiRunContext([
      fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [fakeOverlay("p1")]),
      fakeContext([fakePrimitive("p2")], [fakeOverlay("p2")]),
    ]);

    const l1 = extractPrimitiveLineage(multi, "p1");
    const l2 = extractPrimitiveLineage(multi, "p1");

    expect(JSON.stringify(l1)).toBe(JSON.stringify(l2));
  });
});
