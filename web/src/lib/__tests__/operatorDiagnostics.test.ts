// Card 45 — Operator structural diagnostics unit tests.
//
// Hand-rolled overlay / lineage / hydraulic-evolution fixtures so we
// can pin specific section outputs. The diagnostic computations are
// the unit under test — Cards 32 / 35 / 36 are pinned by their own
// suites.

import { describe, expect, it } from "vitest";

import type {
  EngineV1HydraulicEvolutionMap,
  EngineV1LineageMap,
  EngineV1PrimitiveLineage,
  EngineV1PrimitiveLineageDiff,
  EngineV1SystemOverlay,
  EngineOverlayResult,
} from "../api";
import { buildStructuralDiagnostics } from "../operatorDiagnostics";

function makeOverlay(
  id: string,
  flow_regime: "laminar" | "transitional" | "turbulent",
  in_critical_zone = false,
  on_upper_branch  = false,
): EngineOverlayResult {
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

function makeLineageMap(
  diffs:    Record<string, EngineV1PrimitiveLineageDiff>,
  lineages: Record<string, EngineV1PrimitiveLineage> = {},
): EngineV1LineageMap {
  return {
    primitive_ids: Object.keys(diffs),
    lineages,
    diffs,
    overlays:      {} as never,
  };
}

function makeEvo(
  primitive_ids: string[],
  perPrimitive:  EngineV1HydraulicEvolutionMap["perPrimitive"],
  perRun:        EngineV1HydraulicEvolutionMap["perRun"],
): EngineV1HydraulicEvolutionMap {
  return { primitive_ids, perPrimitive, perRun };
}

function makeSystemOverlay(
  primitive_ids:      string[],
  lineageMap:         EngineV1LineageMap,
  hydraulicEvolution: EngineV1HydraulicEvolutionMap,
): EngineV1SystemOverlay {
  return { primitive_ids, lineageMap, hydraulicEvolution };
}

describe("Card 45 — buildStructuralDiagnostics", () => {
  it("emits the 5 sections in spec order, even when fully empty", () => {
    const lineageMap = makeLineageMap({});
    const evo        = makeEvo([], {}, []);
    const overlay    = makeSystemOverlay([], lineageMap, evo);
    const out        = buildStructuralDiagnostics(overlay, "", lineageMap, evo);

    // Header + 5 section labels in order.
    const idx = (label: string) => out.indexOf(label);
    expect(idx("=== Structural Diagnostics ===")).toBeGreaterThanOrEqual(0);
    expect(idx("[System Stability]")).toBeGreaterThan(idx("=== Structural Diagnostics ==="));
    expect(idx("[Primitive Churn]")).toBeGreaterThan(idx("[System Stability]"));
    expect(idx("[Hydraulic Volatility]")).toBeGreaterThan(idx("[Primitive Churn]"));
    expect(idx("[Structural Anomalies]")).toBeGreaterThan(idx("[Hydraulic Volatility]"));
    expect(idx("[System-Level Outliers]")).toBeGreaterThan(idx("[Structural Anomalies]"));

    // Empty system reads as fully stable.
    expect(out).toContain("- stability score: 1.00");
    expect(out).toContain("- volatility index: 0.00");
    expect(out).toContain("- drift index: 0.00");
    expect(out).toContain("- total primitives: 0");
    expect(out).toContain("- high-churn primitives: (none)");
    expect(out).toContain("(none)"); // outliers
  });

  it("drops stability below 1.00 when overlay changes accumulate", () => {
    // 1 primitive, 2 runs, with one overlay change → observed = 1,
    // possible = 1 * 1 * 3 = 3 → stability = 1 - 1/3 ≈ 0.67.
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: makeOverlay("p1", "laminar"),
        to:   makeOverlay("p1", "transitional"),
      }],
    };
    const lineageMap = makeLineageMap({ p1: p1Diff });
    const evo = makeEvo(
      ["p1"],
      {
        p1: {
          primitive_id: "p1",
          runs: [
            { index: 0, hydraulic_state: null, overlay: makeOverlay("p1", "laminar")      },
            { index: 1, hydraulic_state: null, overlay: makeOverlay("p1", "transitional") },
          ],
        },
      },
      [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    );
    const overlay = makeSystemOverlay(["p1"], lineageMap, evo);
    const out = buildStructuralDiagnostics(overlay, "", lineageMap, evo);
    expect(out).toContain("- stability score: 0.67");
  });

  it("counts laminar→transitional and transitional→turbulent transitions", () => {
    // p1 across 3 runs: laminar → transitional → turbulent.
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [
        { indexFrom: 0, indexTo: 1, from: makeOverlay("p1", "laminar"),      to: makeOverlay("p1", "transitional") },
        { indexFrom: 1, indexTo: 2, from: makeOverlay("p1", "transitional"), to: makeOverlay("p1", "turbulent")    },
      ],
    };
    const lineageMap = makeLineageMap({ p1: p1Diff });
    const evo = makeEvo(
      ["p1"],
      {
        p1: {
          primitive_id: "p1",
          runs: [
            { index: 0, hydraulic_state: null, overlay: makeOverlay("p1", "laminar")      },
            { index: 1, hydraulic_state: null, overlay: makeOverlay("p1", "transitional") },
            { index: 2, hydraulic_state: null, overlay: makeOverlay("p1", "turbulent")    },
          ],
        },
      },
      [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 1, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 0, turbulent: 1, critical_zone: 0, upper_branch: 0 },
      ],
    );
    const overlay = makeSystemOverlay(["p1"], lineageMap, evo);
    const out = buildStructuralDiagnostics(overlay, "", lineageMap, evo);
    expect(out).toContain("- laminar → transitional transitions: 1");
    expect(out).toContain("- transitional → turbulent transitions: 1");
    // Two regime flips out of two pairs → volatility = 1.00.
    expect(out).toContain("- volatility index: 1.00");
    // First (laminar) vs last (turbulent) → drift count 1 of 1 = 1.00.
    expect(out).toContain("- drift index: 1.00");
    // 2 regime transitions → oscillating.
    expect(out).toContain("- primitives with oscillating hydraulic regimes: [p1]");
    // First vs last differ → long-range drift.
    expect(out).toContain("- primitives with long-range drift: [p1]");
  });

  it("flags critical-zone and upper-branch entries", () => {
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [{
        indexFrom: 0, indexTo: 1,
        from: makeOverlay("p1", "laminar", false, false),
        to:   makeOverlay("p1", "laminar", true,  true),
      }],
    };
    const lineageMap = makeLineageMap({ p1: p1Diff });
    const evo = makeEvo(
      ["p1"],
      {
        p1: {
          primitive_id: "p1",
          runs: [
            { index: 0, hydraulic_state: null, overlay: makeOverlay("p1", "laminar", false, false) },
            { index: 1, hydraulic_state: null, overlay: makeOverlay("p1", "laminar", true,  true)  },
          ],
        },
      },
      [
        { index: 0, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 1, transitional: 0, turbulent: 0, critical_zone: 1, upper_branch: 1 },
      ],
    );
    const overlay = makeSystemOverlay(["p1"], lineageMap, evo);
    const out = buildStructuralDiagnostics(overlay, "", lineageMap, evo);
    expect(out).toContain("- critical-zone entries: 1");
    expect(out).toContain("- upper-branch entries: 1");
  });

  it("reports churn totals + high-churn primitives + metadata-anomaly list", () => {
    const p1Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p1",
      appearance:       { added: [], removed: [] },
      // 2 metadata changes → metadata anomaly + high churn.
      metadataChanges:  [
        { indexFrom: 0, indexTo: 1,
          from: { metadata: { primitive_id: "p1", domain: "a" } as never,
                  content: {}, hydraulic_state: {} as never,
                  origin_state: null, historical_states: [] },
          to:   { metadata: { primitive_id: "p1", domain: "b" } as never,
                  content: {}, hydraulic_state: {} as never,
                  origin_state: null, historical_states: [] } },
        { indexFrom: 1, indexTo: 2,
          from: { metadata: { primitive_id: "p1", domain: "b" } as never,
                  content: {}, hydraulic_state: {} as never,
                  origin_state: null, historical_states: [] },
          to:   { metadata: { primitive_id: "p1", domain: "c" } as never,
                  content: {}, hydraulic_state: {} as never,
                  origin_state: null, historical_states: [] } },
      ],
      hydraulicChanges: [],
      overlayChanges:   [],
    };
    // p2 appears in run 1 then is removed in run 2 → 1 added + 1 removed = 2 → high churn.
    const p2Diff: EngineV1PrimitiveLineageDiff = {
      primitive_id:     "p2",
      appearance:       { added: [1], removed: [2] },
      metadataChanges:  [],
      hydraulicChanges: [],
      overlayChanges:   [],
    };
    const lineageMap = makeLineageMap({ p1: p1Diff, p2: p2Diff });
    const evo = makeEvo(
      ["p1", "p2"],
      {
        p1: { primitive_id: "p1", runs: [
          { index: 0, hydraulic_state: null, overlay: null },
          { index: 1, hydraulic_state: null, overlay: null },
          { index: 2, hydraulic_state: null, overlay: null },
        ] },
        p2: { primitive_id: "p2", runs: [
          { index: 0, hydraulic_state: null, overlay: null },
          { index: 1, hydraulic_state: null, overlay: null },
          { index: 2, hydraulic_state: null, overlay: null },
        ] },
      },
      [
        { index: 0, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
      ],
    );
    const overlay = makeSystemOverlay(["p1", "p2"], lineageMap, evo);
    const out = buildStructuralDiagnostics(overlay, "", lineageMap, evo);
    expect(out).toContain("- total primitives: 2");
    expect(out).toContain("- added across runs: 1");
    expect(out).toContain("- removed across runs: 1");
    expect(out).toContain("- high-churn primitives: [p1, p2]");
    expect(out).toContain("- primitives with inconsistent metadata: [p1]");
  });

  it("flags per-run outliers when a value exceeds 1.5 × mean", () => {
    // 3 runs with critical_zone = [0, 0, 5]: mean = 5/3 ≈ 1.67, 5 > 2.5.
    const lineageMap = makeLineageMap({});
    const evo = makeEvo(
      [],
      {},
      [
        { index: 0, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 1, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 0, upper_branch: 0 },
        { index: 2, laminar: 0, transitional: 0, turbulent: 0, critical_zone: 5, upper_branch: 0 },
      ],
    );
    const overlay = makeSystemOverlay([], lineageMap, evo);
    const out = buildStructuralDiagnostics(overlay, "", lineageMap, evo);
    expect(out).toContain("- run 2: unusually high critical-zone pressure");
  });
});
