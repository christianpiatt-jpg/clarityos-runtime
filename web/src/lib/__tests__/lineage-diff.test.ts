// Card 32 — diffPrimitiveLineage test.
//
// Asserts pairwise-adjacent run comparison correctly surfaces:
//   - appearance.added / .removed indices
//   - metadata changes (and ONLY when metadata differs)
//   - hydraulic_state changes (and ONLY when hydraulic_state differs)
//   - overlay changes (including null↔non-null transitions)
//   - purity (input lineage unchanged)
//   - determinism (same input → same output)
//
// Pure unit test — no fetch, no session. Lineages built directly
// via fixture factories.

import { describe, expect, it } from "vitest";

import {
  diffPrimitiveLineage,
  type EngineHydraulicState,
  type EnginePrimitive,
  type EnginePrimitiveType,
  type EngineOverlayResult,
  type EngineV1PrimitiveLineage,
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
  opts: { type?: EnginePrimitiveType; hydraulic?: Partial<EngineHydraulicState>; confidence?: number } = {},
): EnginePrimitive {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: opts.type ?? "signal",
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 32 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     opts.confidence ?? 1.0,
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

describe("Card 32 — diffPrimitiveLineage", () => {
  it("flags appearance.added on null → non-null transitions", () => {
    const l = lineage("p1", [
      { index: 0, primitive: null,                  overlay: null },
      { index: 1, primitive: fakePrimitive("p1"),   overlay: fakeOverlay("p1") },
    ]);
    const d = diffPrimitiveLineage(l);
    expect(d.appearance.added).toEqual([1]);
    expect(d.appearance.removed).toEqual([]);
  });

  it("flags appearance.removed on non-null → null transitions", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"),   overlay: fakeOverlay("p1") },
      { index: 1, primitive: null,                  overlay: null },
    ]);
    const d = diffPrimitiveLineage(l);
    expect(d.appearance.added).toEqual([]);
    expect(d.appearance.removed).toEqual([1]);
  });

  it("detects metadata changes only when metadata fields differ", () => {
    // run0/run1 differ on metadata.confidence; hydraulic unchanged.
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1", { confidence: 1.0 }), overlay: null },
      { index: 1, primitive: fakePrimitive("p1", { confidence: 0.5 }), overlay: null },
    ]);
    const d = diffPrimitiveLineage(l);
    expect(d.metadataChanges).toHaveLength(1);
    expect(d.metadataChanges[0].indexFrom).toBe(0);
    expect(d.metadataChanges[0].indexTo).toBe(1);
    expect(d.hydraulicChanges).toEqual([]);
  });

  it("detects hydraulic changes only when hydraulic_state fields differ", () => {
    // run0/run1 differ on hydraulic.pressure; metadata unchanged.
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1", { hydraulic: { pressure: 5.0 } }), overlay: null },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 7.0 } }), overlay: null },
    ]);
    const d = diffPrimitiveLineage(l);
    expect(d.hydraulicChanges).toHaveLength(1);
    expect(d.hydraulicChanges[0].indexFrom).toBe(0);
    expect(d.hydraulicChanges[0].indexTo).toBe(1);
    expect(d.metadataChanges).toEqual([]);
  });

  it("detects overlay changes including null ↔ non-null transitions", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"), overlay: null },
      { index: 1, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1", { flow_regime: "laminar" }) },
      { index: 2, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
      { index: 3, primitive: fakePrimitive("p1"), overlay: null },
    ]);
    const d = diffPrimitiveLineage(l);
    // 3 transitions: null→laminar, laminar→turbulent, turbulent→null.
    expect(d.overlayChanges).toHaveLength(3);
    expect(d.overlayChanges.map((c) => [c.indexFrom, c.indexTo]))
      .toEqual([[0, 1], [1, 2], [2, 3]]);
  });

  it("produces an empty diff when adjacent runs are byte-identical", () => {
    const shared_p = fakePrimitive("p1");
    const shared_o = fakeOverlay("p1");
    const l = lineage("p1", [
      { index: 0, primitive: shared_p, overlay: shared_o },
      { index: 1, primitive: shared_p, overlay: shared_o },
      { index: 2, primitive: shared_p, overlay: shared_o },
    ]);
    const d = diffPrimitiveLineage(l);
    expect(d.appearance.added).toEqual([]);
    expect(d.appearance.removed).toEqual([]);
    expect(d.metadataChanges).toEqual([]);
    expect(d.hydraulicChanges).toEqual([]);
    expect(d.overlayChanges).toEqual([]);
  });

  it("returns empty everything for a zero-run or single-run lineage", () => {
    const empty = diffPrimitiveLineage(lineage("p1", []));
    expect(empty.appearance.added).toEqual([]);
    expect(empty.metadataChanges).toEqual([]);
    expect(empty.hydraulicChanges).toEqual([]);
    expect(empty.overlayChanges).toEqual([]);

    const single = diffPrimitiveLineage(lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1") },
    ]));
    expect(single.appearance.added).toEqual([]);
    expect(single.metadataChanges).toEqual([]);
    expect(single.hydraulicChanges).toEqual([]);
    expect(single.overlayChanges).toEqual([]);
  });

  it("captures the full 3-run scenario described in the card spec", () => {
    // Run 0: present.  Run 1: hydraulic + overlay both changed.  Run 2: gone.
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1", { hydraulic: { pressure: 5.0 } }), overlay: fakeOverlay("p1", { flow_regime: "laminar" }) },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 8.0 } }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
      { index: 2, primitive: null, overlay: null },
    ]);
    const d = diffPrimitiveLineage(l);

    expect(d.appearance.added).toEqual([]);
    expect(d.appearance.removed).toEqual([2]);
    expect(d.hydraulicChanges).toHaveLength(1);
    expect(d.hydraulicChanges[0].indexFrom).toBe(0);
    expect(d.hydraulicChanges[0].indexTo).toBe(1);
    expect(d.overlayChanges).toHaveLength(2);  // 0→1 (laminar→turbulent), 1→2 (turbulent→null)
    expect(d.metadataChanges).toEqual([]);     // metadata unchanged
  });

  it("does not mutate the input lineage (purity)", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1"), overlay: fakeOverlay("p1") },
      { index: 1, primitive: fakePrimitive("p1", { hydraulic: { pressure: 9 } }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
    ]);
    const snapshot = JSON.stringify(l);

    diffPrimitiveLineage(l);

    expect(JSON.stringify(l)).toBe(snapshot);
  });

  it("is deterministic — same input produces structurally identical diffs", () => {
    const l = lineage("p1", [
      { index: 0, primitive: fakePrimitive("p1", { confidence: 1.0 }), overlay: fakeOverlay("p1") },
      { index: 1, primitive: fakePrimitive("p1", { confidence: 0.5 }), overlay: fakeOverlay("p1", { flow_regime: "turbulent" }) },
    ]);
    const d1 = diffPrimitiveLineage(l);
    const d2 = diffPrimitiveLineage(l);
    expect(JSON.stringify(d1)).toBe(JSON.stringify(d2));
  });
});
