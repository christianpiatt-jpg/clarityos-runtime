// Card 33 — buildPrimitiveLineageOverlay composition test.
//
// Asserts the overlay correctly pairs the Card 31 lineage with the
// Card 32 diff, with identity-preserving pass-through for lineage
// and structural equality with diffPrimitiveLineage for diff.
//
// Pure unit test — no fetch, no session. Lineages built directly
// via fixture factories.

import { describe, expect, it } from "vitest";

import {
  buildPrimitiveLineageOverlay,
  diffPrimitiveLineage,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineOverlayResult,
  type EngineV1PrimitiveLineage,
  type EngineV1PrimitiveLineageOverlay,
} from "../api";

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
      source:         "Card 33 fixture",
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

function fakeOverlay(
  primitiveId: string,
  opts: Partial<EngineOverlayResult> = {},
): EngineOverlayResult {
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

function lineage(
  primitive_id: string,
  runs: Array<{
    index:     number;
    primitive: EnginePrimitive     | null;
    overlay:   EngineOverlayResult | null;
  }>,
): EngineV1PrimitiveLineage {
  return { primitive_id, runs };
}

describe("Card 33 — buildPrimitiveLineageOverlay", () => {
  it("pairs the Card 31 lineage with the Card 32 diff", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1", { hydraulic: { pressure: 5.0 } }), overlay: fakeOverlay("p1", { flow_regime: "laminar" }) },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 8.0 } }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
      { index: 2, primitive: null, overlay: null },
    ]);

    const out: EngineV1PrimitiveLineageOverlay = buildPrimitiveLineageOverlay(l);

    expect(out.primitive_id).toBe("p1");
    expect(out.lineage).toBe(l);  // pass-through by reference
    expect(out.diff).toEqual(diffPrimitiveLineage(l));  // structural equality
  });

  it("matches the canonical { primitive_id, lineage, diff } top-level shape", () => {
    const l = lineage("p1", []);
    const out = buildPrimitiveLineageOverlay(l);
    expect(Object.keys(out).sort()).toEqual(["diff", "lineage", "primitive_id"].sort());
  });

  it("forwards lineage with zero runs and produces an empty diff", () => {
    const l = lineage("p1", []);
    const out = buildPrimitiveLineageOverlay(l);
    expect(out.lineage.runs).toEqual([]);
    expect(out.diff.appearance.added).toEqual([]);
    expect(out.diff.appearance.removed).toEqual([]);
    expect(out.diff.metadataChanges).toEqual([]);
    expect(out.diff.hydraulicChanges).toEqual([]);
    expect(out.diff.overlayChanges).toEqual([]);
  });

  it("does not mutate the input lineage (purity)", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1") },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 9 } }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
    ]);
    const snapshot = JSON.stringify(l);

    buildPrimitiveLineageOverlay(l);

    expect(JSON.stringify(l)).toBe(snapshot);
  });

  it("is deterministic — same input produces structurally identical overlays", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1") },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 9 } }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
    ]);
    const o1 = buildPrimitiveLineageOverlay(l);
    const o2 = buildPrimitiveLineageOverlay(l);
    expect(JSON.stringify(o1)).toBe(JSON.stringify(o2));
  });
});
