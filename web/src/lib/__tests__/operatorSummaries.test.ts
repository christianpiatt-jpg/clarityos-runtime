// Card 42 — Operator semantic summaries unit tests.
//
// Builds a minimal lineage map + hydraulic evolution + system overlay
// + regression diff by hand (deterministic, no fetch), then asserts
// each summarizer returns the expected plain-text shape. Substring
// checks rather than whole-string equality so cosmetic formatting can
// evolve without breaking the test.

import { describe, expect, it } from "vitest";

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1PrimitiveLineage,
  EngineV1PrimitiveLineageDiff,
  EngineV1SystemOverlay,
  EngineV1SystemRegressionDiff,
} from "../api";
import {
  summarizeHydraulicEvolution,
  summarizeLineageMap,
  summarizeRegression,
  summarizeSystemOverlay,
} from "../operatorSummaries";

// Helpers — build small, valid Card 31/32/34/35/36/37 structures.

function makePrimitive(id: string) {
  return {
    metadata: {
      primitive_id:   id,
      primitive_type: "signal" as const,
      timestamp:      "2026-05-28T00:00:00+00:00",
      version:        "1.0.0",
      domain:         "general",
      source:         "Card 42 fixture",
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

function makeOverlay(
  id: string,
  flow_regime: "laminar" | "transitional" | "turbulent",
  in_critical_zone: boolean,
  on_upper_branch:  boolean,
) {
  return {
    primitive_id:     id,
    reynolds_number:  1000,
    flow_regime,
    stability:        0.9,
    in_critical_zone,
    distance_to_fold: 3.0,
    resilience:       4.0,
    curve_position:   2.0,
    on_upper_branch,
    sensitivity:      1.0,
    hysteresis:       3.0,
  };
}

function makeEmptyDiff(id: string): EngineV1PrimitiveLineageDiff {
  return {
    primitive_id:    id,
    appearance:      { added: [], removed: [] },
    metadataChanges:  [],
    hydraulicChanges: [],
    overlayChanges:   [],
  };
}

describe("Card 42 — summarizeLineageMap", () => {
  it("returns a sentinel when no primitives are present", () => {
    const map: EngineV1LineageMap = {
      primitive_ids: [],
      lineages:      {},
      diffs:         {},
      overlays:      {},
    };
    expect(summarizeLineageMap(map)).toBe("(no primitives)");
  });

  it("reports first / last / total appearances for a stable primitive", () => {
    const lineage: EngineV1PrimitiveLineage = {
      primitive_id: "p1",
      runs: [
        { index: 0, primitive: makePrimitive("p1"), overlay: null },
        { index: 1, primitive: makePrimitive("p1"), overlay: null },
        { index: 2, primitive: makePrimitive("p1"), overlay: null },
      ],
    };
    const map: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: lineage },
      diffs:         { p1: makeEmptyDiff("p1") },
      overlays:      { p1: { primitive_id: "p1", lineage, diff: makeEmptyDiff("p1") } },
    };
    const out = summarizeLineageMap(map);
    expect(out).toContain("Primitive: p1");
    expect(out).toContain("First seen: run 0");
    expect(out).toContain("Last seen: run 2");
    expect(out).toContain("Total appearances: 3");
    expect(out).toContain("Changed between runs: (none)");
  });

  it("flags 'never present' when the primitive is absent in every run", () => {
    const lineage: EngineV1PrimitiveLineage = {
      primitive_id: "p1",
      runs: [
        { index: 0, primitive: null, overlay: null },
        { index: 1, primitive: null, overlay: null },
      ],
    };
    const map: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: lineage },
      diffs:         { p1: makeEmptyDiff("p1") },
      overlays:      { p1: { primitive_id: "p1", lineage, diff: makeEmptyDiff("p1") } },
    };
    const out = summarizeLineageMap(map);
    expect(out).toContain("First seen: never present");
    expect(out).toContain("Last seen: never present");
    expect(out).toContain("Total appearances: 0");
  });

  it("collects pairwise change transitions from all diff categories", () => {
    const diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [{ from: null, to: null, indexFrom: 0, indexTo: 1 }],
      hydraulicChanges: [{ from: null, to: null, indexFrom: 1, indexTo: 2 }],
      overlayChanges:   [{ from: null, to: null, indexFrom: 0, indexTo: 1 }],
    };
    const lineage: EngineV1PrimitiveLineage = {
      primitive_id: "p1",
      runs: [
        { index: 0, primitive: makePrimitive("p1"), overlay: null },
        { index: 1, primitive: makePrimitive("p1"), overlay: null },
        { index: 2, primitive: makePrimitive("p1"), overlay: null },
      ],
    };
    const map: EngineV1LineageMap = {
      primitive_ids: ["p1"],
      lineages:      { p1: lineage },
      diffs:         { p1: diff },
      overlays:      { p1: { primitive_id: "p1", lineage, diff } },
    };
    const out = summarizeLineageMap(map);
    // Deduplicated 0→1 (metadata + overlay both reported the same pair)
    // plus the 1→2 hydraulic transition. Order is sorted ascending.
    expect(out).toContain("Changed between runs: [0→1], [1→2]");
  });
});

describe("Card 42 — summarizeHydraulicEvolution", () => {
  it("returns a sentinel when no runs are present", () => {
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: [], perPrimitive: {}, perRun: [],
    };
    expect(summarizeHydraulicEvolution(evo)).toBe("(no runs)");
  });

  it("emits a per-run block with each regime + zone count", () => {
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: [],
      perPrimitive:  {},
      perRun: [
        { index: 0, laminar: 12, transitional: 3, turbulent: 1, critical_zone: 2, upper_branch: 0 },
        { index: 1, laminar: 10, transitional: 4, turbulent: 2, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const out = summarizeHydraulicEvolution(evo);
    expect(out).toContain("Run 0:");
    expect(out).toContain("- laminar: 12");
    expect(out).toContain("- transitional: 3");
    expect(out).toContain("- turbulent: 1");
    expect(out).toContain("- critical-zone primitives: 2");
    expect(out).toContain("- upper-branch primitives: 0");
    expect(out).toContain("Run 1:");
    expect(out).toContain("- upper-branch primitives: 1");
  });
});

describe("Card 42 — summarizeSystemOverlay", () => {
  it("counts total primitives + runs + primitives-with-changes", () => {
    const lineageMap: EngineV1LineageMap = {
      primitive_ids: ["p1", "p2"],
      lineages: {
        p1: {
          primitive_id: "p1",
          runs: [
            { index: 0, primitive: makePrimitive("p1"), overlay: makeOverlay("p1", "laminar", false, false) },
            { index: 1, primitive: makePrimitive("p1"), overlay: makeOverlay("p1", "laminar", true,  false) },
          ],
        },
        p2: {
          primitive_id: "p2",
          runs: [
            { index: 0, primitive: makePrimitive("p2"), overlay: makeOverlay("p2", "laminar", false, false) },
            { index: 1, primitive: makePrimitive("p2"), overlay: makeOverlay("p2", "laminar", false, true) },
          ],
        },
      },
      diffs: {
        // p1 has a recorded overlay change; p2 does not.
        p1: {
          primitive_id:     "p1",
          appearance:       { added: [], removed: [] },
          metadataChanges:  [],
          hydraulicChanges: [],
          overlayChanges:   [{ from: null, to: null, indexFrom: 0, indexTo: 1 }],
        },
        p2: makeEmptyDiff("p2"),
      },
      overlays: {} as never,
    };
    const evo: EngineV1HydraulicEvolutionMap = {
      primitive_ids: ["p1", "p2"],
      perPrimitive: {
        p1: { primitive_id: "p1", runs: lineageMap.lineages.p1.runs.map((r) => ({ index: r.index, hydraulic_state: r.primitive?.hydraulic_state ?? null, overlay: r.overlay })) },
        p2: { primitive_id: "p2", runs: lineageMap.lineages.p2.runs.map((r) => ({ index: r.index, hydraulic_state: r.primitive?.hydraulic_state ?? null, overlay: r.overlay })) },
      },
      perRun: [
        { index: 0, laminar: 2, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 2, transitional: 0, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    };
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: ["p1", "p2"], lineageMap, hydraulicEvolution: evo,
    };
    const out = summarizeSystemOverlay(overlay);
    expect(out).toContain("System Overlay:");
    expect(out).toContain("- total primitives: 2");
    expect(out).toContain("- runs: 2");
    expect(out).toContain("- primitives with changes: 1");
    // p1 went false→true on in_critical_zone; p2 went false→true on on_upper_branch.
    expect(out).toContain("- primitives entering critical zone: [p1]");
    expect(out).toContain("- primitives entering upper branch: [p2]");
  });

  it("shows (none) when nothing enters critical/upper-branch", () => {
    const overlay: EngineV1SystemOverlay = {
      primitive_ids: [],
      lineageMap: { primitive_ids: [], lineages: {}, diffs: {}, overlays: {} },
      hydraulicEvolution: { primitive_ids: [], perPrimitive: {}, perRun: [] },
    };
    const out = summarizeSystemOverlay(overlay);
    expect(out).toContain("- primitives entering critical zone: (none)");
    expect(out).toContain("- primitives entering upper branch: (none)");
  });
});

describe("Card 42 — summarizeRegression", () => {
  it("formats deltas with explicit sign and (none) sentinels", () => {
    const diff: EngineV1SystemRegressionDiff = {
      fromIndex: 0,
      toIndex:   1,
      primitiveChanges: { added: ["a"], removed: [], changed: ["c1", "c2"] },
      hydraulic: {
        laminarDelta:      2,
        transitionalDelta: -1,
        turbulentDelta:    0,
        criticalZoneDelta: 1,
        upperBranchDelta:  0,
      },
    };
    const out = summarizeRegression(diff);
    expect(out).toContain("Regression (0 → 1):");
    expect(out).toContain("- added primitives: [a]");
    expect(out).toContain("- removed primitives: (none)");
    expect(out).toContain("- changed primitives: [c1, c2]");
    expect(out).toContain("  laminar: +2");
    expect(out).toContain("  transitional: -1");
    expect(out).toContain("  turbulent: 0");
    expect(out).toContain("  critical-zone: +1");
    expect(out).toContain("  upper-branch: 0");
  });
});
