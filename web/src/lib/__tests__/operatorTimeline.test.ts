// Card 43 — Operator evolution timeline unit tests.
//
// Builds a small hand-rolled overlay + a stub regression function so
// we can pin the exact text format the helper emits. The regression
// callback is mocked rather than wired to the real Card 37 helper —
// the helper's iteration + formatting is the unit under test, not the
// regression engine itself (covered by Cards 37 tests).

import { describe, expect, it, vi } from "vitest";

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1PrimitiveLineage,
  EngineV1PrimitiveLineageDiff,
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "../api";
import { buildEvolutionTimeline } from "../operatorTimeline";

function makePrimitive(id: string) {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 43 fixture",
      parent_id:      null,
      ancestors:      [],
      depends_on:     [],
      influences:     [],
      confidence:     1.0,
      completeness:   1.0,
      reliability:    1.0,
    },
    content:           {},
    hydraulic_state:   {
      pressure: 5, gradient: 0, flow: 4, resistance: 2,
      timestamp: "2026-05-28T00:00:00+00:00",
    },
    origin_state:      null,
    historical_states: [],
  };
}

function makeEmptyDiff(id: string): EngineV1PrimitiveLineageDiff {
  return {
    primitive_id:     id,
    appearance:       { added: [], removed: [] },
    metadataChanges:  [],
    hydraulicChanges: [],
    overlayChanges:   [],
  };
}

function makeOverlay(
  primitive_ids: string[],
  presenceMatrix: boolean[][],   // [primitive][run] = present?
  perRun: EngineV1HydraulicEvolutionMap["perRun"],
): EngineV1SystemOverlay {
  const lineages: Record<string, EngineV1PrimitiveLineage> = {};
  const diffs:    Record<string, EngineV1PrimitiveLineageDiff> = {};
  primitive_ids.forEach((id, pIdx) => {
    lineages[id] = {
      primitive_id: id,
      runs: presenceMatrix[pIdx].map((present, rIdx) => ({
        index:     rIdx,
        primitive: present ? makePrimitive(id) : null,
        overlay:   null,
      })),
    };
    diffs[id] = makeEmptyDiff(id);
  });
  const lineageMap: EngineV1LineageMap = {
    primitive_ids,
    lineages,
    diffs,
    overlays: {} as never,
  };
  const hydraulicEvolution: EngineV1HydraulicEvolutionMap = {
    primitive_ids,
    perPrimitive: {} as never,
    perRun,
  };
  return { primitive_ids, lineageMap, hydraulicEvolution };
}

describe("Card 43 — buildEvolutionTimeline", () => {
  it("returns a sentinel when no runs are present", () => {
    const overlay = makeOverlay([], [], []);
    const out = buildEvolutionTimeline(overlay, () => {
      throw new Error("regression should not be called when there are 0 runs");
    });
    expect(out).toBe("(no runs)");
  });

  it("emits a single Run block (and no transition block) for a 1-run overlay", () => {
    const overlay = makeOverlay(
      ["p1"],
      [[true]],
      [{ index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 }],
    );
    const regression = vi.fn(() => { throw new Error("never"); });
    const out = buildEvolutionTimeline(overlay, regression);
    expect(out).toContain("=== Run 0 ===");
    expect(out).toContain("Primitives active: [p1]");
    expect(out).toContain("- laminar: 1");
    // No transition block for a single run.
    expect(out).not.toContain("→ Run 1");
    expect(regression).not.toHaveBeenCalled();
  });

  it("interleaves run state and adjacent-pair transitions for a 3-run overlay", () => {
    const overlay = makeOverlay(
      ["p1", "p2"],
      // Run 0: only p1; Run 1: both; Run 2: only p2.
      [
        [true,  true,  false],
        [false, true,  true ],
      ],
      [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 2, transitional: 0, turbulent: 0, critical_zone: 1, upper_branch: 0 },
        { index: 2, laminar: 1, transitional: 0, turbulent: 1, critical_zone: 0, upper_branch: 1 },
      ],
    );
    const regression: (a: number, b: number) => EngineV1SystemRegressionDiff = (a, b) => ({
      fromIndex: a,
      toIndex:   b,
      primitiveChanges: a === 0
        ? { added: ["p2"], removed: [],     changed: ["p1"] }
        : { added: [],     removed: ["p1"], changed: ["p2"] },
      hydraulic: a === 0
        ? { laminarDelta: 1,  transitionalDelta: 0, turbulentDelta: 0, criticalZoneDelta: 1,  upperBranchDelta: 0 }
        : { laminarDelta: -1, transitionalDelta: 0, turbulentDelta: 1, criticalZoneDelta: -1, upperBranchDelta: 1 },
    });
    const out = buildEvolutionTimeline(overlay, regression);

    // Per-run state blocks (one per run).
    expect(out).toContain("=== Run 0 ===");
    expect(out).toContain("Primitives active: [p1]");
    expect(out).toContain("=== Run 1 ===");
    expect(out).toContain("Primitives active: [p1, p2]");
    expect(out).toContain("=== Run 2 ===");
    expect(out).toContain("Primitives active: [p2]");

    // Adjacent-pair transitions (two: 0→1 and 1→2).
    expect(out).toContain("=== Run 0 → Run 1 ===");
    expect(out).toContain("Added: [p2]");
    expect(out).toContain("Changed: [p1]");
    expect(out).toContain("- laminar: +1");
    expect(out).toContain("- critical-zone: +1");

    expect(out).toContain("=== Run 1 → Run 2 ===");
    expect(out).toContain("Removed: [p1]");
    expect(out).toContain("Changed: [p2]");
    expect(out).toContain("- laminar: -1");
    expect(out).toContain("- critical-zone: -1");
    expect(out).toContain("- upper-branch: +1");
  });

  it("shows (none) for empty Primitives active and (none) lists", () => {
    const overlay = makeOverlay(
      ["p1"],
      [[false, false]],
      [
        { index: 0, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    );
    const regression: (a: number, b: number) => EngineV1SystemRegressionDiff = (a, b) => ({
      fromIndex: a, toIndex: b,
      primitiveChanges: { added: [], removed: [], changed: [] },
      hydraulic: { laminarDelta: 0, transitionalDelta: 0, turbulentDelta: 0, criticalZoneDelta: 0, upperBranchDelta: 0 },
    });
    const out = buildEvolutionTimeline(overlay, regression);
    expect(out).toContain("Primitives active: (none)");
    expect(out).toContain("Added: (none)");
    expect(out).toContain("Removed: (none)");
    expect(out).toContain("Changed: (none)");
    expect(out).toContain("- laminar: 0");
  });
});
