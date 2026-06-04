// Card 44 — Operator diff viewer unit tests.
//
// Hand-rolled regression-diff + lineage-map fixtures so we can pin
// the exact text format the helper emits. Field-level diff comparison
// is the unit under test — Card 32 / Card 37 themselves are covered
// by their own suites.

import { describe, expect, it } from "vitest";

import type {
  EngineV1LineageMap,
  EngineV1PrimitiveLineageDiff,
  EngineV1SystemRegressionDiff,
} from "../api";
import { buildDiffView } from "../operatorDiff";

function emptyPrimDiff(id: string): EngineV1PrimitiveLineageDiff {
  return {
    primitive_id:     id,
    appearance:       { added: [], removed: [] },
    metadataChanges:  [],
    hydraulicChanges: [],
    overlayChanges:   [],
  };
}

// Builds the minimum lineage-map skeleton the diff viewer needs:
// .diffs[id] is consulted; everything else is unused.
function makeLineageMap(
  diffs: Record<string, EngineV1PrimitiveLineageDiff>,
): EngineV1LineageMap {
  return {
    primitive_ids: Object.keys(diffs),
    lineages:      {} as never,
    diffs,
    overlays:      {} as never,
  };
}

describe("Card 44 — buildDiffView", () => {
  it("emits the header + sections in the right order for an empty diff", () => {
    const diff: EngineV1SystemRegressionDiff = {
      fromIndex: 0,
      toIndex:   1,
      primitiveChanges: { added: [], removed: [], changed: [] },
      hydraulic: {
        laminarDelta: 0, transitionalDelta: 0, turbulentDelta: 0,
        criticalZoneDelta: 0, upperBranchDelta: 0,
      },
    };
    const out = buildDiffView(diff, makeLineageMap({}));
    // Sections appear in spec order.
    const headerIdx     = out.indexOf("=== Diff: Run 0 → Run 1 ===");
    const primitivesIdx = out.indexOf("[Primitives]");
    const hydraulicIdx  = out.indexOf("[Hydraulic]");
    const detailsIdx    = out.indexOf("[Primitive Details]");
    expect(headerIdx).toBeGreaterThanOrEqual(0);
    expect(primitivesIdx).toBeGreaterThan(headerIdx);
    expect(hydraulicIdx).toBeGreaterThan(primitivesIdx);
    expect(detailsIdx).toBeGreaterThan(hydraulicIdx);
    // Empty changed set → sentinel under details.
    expect(out).toContain("(no per-primitive field changes)");
    expect(out).toContain("+ Added: (none)");
    expect(out).toContain("- Removed: (none)");
    expect(out).toContain("~ Changed: (none)");
  });

  it("renders added / removed / changed lists + hydraulic deltas with explicit sign", () => {
    const diff: EngineV1SystemRegressionDiff = {
      fromIndex: 0,
      toIndex:   1,
      primitiveChanges: {
        added:   ["p3"],
        removed: ["p2"],
        changed: ["p1"],
      },
      hydraulic: {
        laminarDelta: 1, transitionalDelta: -1, turbulentDelta: 0,
        criticalZoneDelta: 1, upperBranchDelta: 0,
      },
    };
    // p1's hydraulic_state.pressure went 5→7; nothing else changed.
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [{
        indexFrom: 0, indexTo: 1,
        from: { metadata: { primitive_id: "p1" } as never,
                content:           {},
                hydraulic_state:   { pressure: 5, gradient: 0, flow: 4, resistance: 2, timestamp: "t0" },
                origin_state:      null,
                historical_states: [] },
        to:   { metadata: { primitive_id: "p1" } as never,
                content:           {},
                hydraulic_state:   { pressure: 7, gradient: 0, flow: 4, resistance: 2, timestamp: "t1" },
                origin_state:      null,
                historical_states: [] },
      }],
      overlayChanges:   [],
    };
    const out = buildDiffView(diff, makeLineageMap({
      p1: p1Diff,
      p2: emptyPrimDiff("p2"),
      p3: emptyPrimDiff("p3"),
    }));

    expect(out).toContain("+ Added: [p3]");
    expect(out).toContain("- Removed: [p2]");
    expect(out).toContain("~ Changed: [p1]");
    expect(out).toContain("laminar: +1");
    expect(out).toContain("transitional: -1");
    expect(out).toContain("turbulent: 0");
    expect(out).toContain("critical-zone: +1");
    expect(out).toContain("upper-branch: 0");
    expect(out).toContain("p1:");
    expect(out).toContain("hydraulic changes:");
    // Pressure changed; timestamp changed (both shown). Untouched
    // fields are filtered out.
    expect(out).toContain("- pressure: 5 → 7");
    expect(out).not.toContain("- gradient:");
    expect(out).not.toContain("- flow:");
  });

  it("renders metadata, hydraulic, and overlay subsections under a single changed primitive", () => {
    const diff: EngineV1SystemRegressionDiff = {
      fromIndex: 0,
      toIndex:   1,
      primitiveChanges: { added: [], removed: [], changed: ["p1"] },
      hydraulic: {
        laminarDelta: 0, transitionalDelta: 0, turbulentDelta: 0,
        criticalZoneDelta: 0, upperBranchDelta: 0,
      },
    };
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id: "p1",
      appearance:   { added: [], removed: [] },
      metadataChanges:  [{
        indexFrom: 0, indexTo: 1,
        from: { metadata: { primitive_id: "p1", domain: "general" } as never,
                content: {}, hydraulic_state: {} as never,
                origin_state: null, historical_states: [] },
        to:   { metadata: { primitive_id: "p1", domain: "advanced" } as never,
                content: {}, hydraulic_state: {} as never,
                origin_state: null, historical_states: [] },
      }],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: { primitive_id: "p1", in_critical_zone: false } as never,
        to:   { primitive_id: "p1", in_critical_zone: true  } as never,
      }],
    };
    const out = buildDiffView(diff, makeLineageMap({ p1: p1Diff }));
    expect(out).toContain("p1:");
    expect(out).toContain("  metadata changes:");
    expect(out).toContain(`- domain: "general" → "advanced"`);
    expect(out).toContain("  overlay changes:");
    expect(out).toContain("- in_critical_zone: false → true");
    // No hydraulic block because the changes array is empty.
    expect(out).not.toContain("  hydraulic changes:");
  });

  it("ignores diff entries whose (indexFrom, indexTo) does not match the regression's selection", () => {
    const diff: EngineV1SystemRegressionDiff = {
      fromIndex: 1,
      toIndex:   2,
      primitiveChanges: { added: [], removed: [], changed: ["p1"] },
      hydraulic: {
        laminarDelta: 0, transitionalDelta: 0, turbulentDelta: 0,
        criticalZoneDelta: 0, upperBranchDelta: 0,
      },
    };
    // The primitive's only diff entry belongs to the 0→1 transition,
    // which doesn't match the 1→2 selection — must not surface.
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id: "p1",
      appearance:   { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [{
        indexFrom: 0, indexTo: 1,
        from: { metadata: {} as never, content: {},
                hydraulic_state: { pressure: 5 } as never,
                origin_state: null, historical_states: [] },
        to:   { metadata: {} as never, content: {},
                hydraulic_state: { pressure: 9 } as never,
                origin_state: null, historical_states: [] },
      }],
      overlayChanges:   [],
    };
    const out = buildDiffView(diff, makeLineageMap({ p1: p1Diff }));
    // p1 is listed under Changed but has no matching field diff at this pair.
    expect(out).toContain("~ Changed: [p1]");
    expect(out).not.toContain("- pressure: 5 → 9");
    expect(out).toContain("(no per-primitive field changes)");
  });
});
