// Card 29 — multi-run context + diff helpers test.
//
// Asserts:
//   - createMultiRunContext preserves run order
//   - diffPrimitives matches by metadata.primitive_id (spec said
//     metadata.id; the deployed field is primitive_id)
//   - diffOverlays detects changes in flow_regime, in_critical_zone,
//     on_upper_branch, hysteresis (the 4 watched fields)
//   - diffDiagnostics returns only changed fields
//   - purity: no input mutation
//   - determinism: same inputs → same outputs
//
// Pure unit tests — no fetch, no session, no module-init dance.
// Contexts are built directly via fixture factories.

import { describe, expect, it } from "vitest";

import {
  createMultiRunContext,
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
  type EngineV1OperatorContext,
} from "../api";

function fakeDiagnostics(overrides: Partial<EngineDiagnostics> = {}): EngineDiagnostics {
  return {
    observation_id:    "obs_29_001",
    observer_notes:    "Card 29 fixture",
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
      source:         "Card 29 fixture",
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
  primitives: EnginePrimitive[],
  overlays:   EngineOverlayResult[],
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
  // Other layers populated minimally — diff helpers only read .raw.
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

describe("Card 29 — createMultiRunContext + diff helpers", () => {
  describe("createMultiRunContext", () => {
    it("preserves run order", () => {
      const r1 = fakeContext([fakePrimitive("p1")], []);
      const r2 = fakeContext([fakePrimitive("p2")], []);
      const r3 = fakeContext([fakePrimitive("p3")], []);
      const ctx = createMultiRunContext([r1, r2, r3]);
      expect(ctx.runs).toEqual([r1, r2, r3]);
      expect(ctx.runs[0]).toBe(r1);
      expect(ctx.runs[2]).toBe(r3);
    });
  });

  describe("diffPrimitives", () => {
    it("matches by metadata.primitive_id (the real deployed field)", () => {
      const a = fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], []);
      const b = fakeContext([fakePrimitive("p2"), fakePrimitive("p3")], []);

      const { added, removed } = diffPrimitives(a, b);
      expect(added.map((p) => p.metadata.primitive_id)).toEqual(["p3"]);
      expect(removed.map((p) => p.metadata.primitive_id)).toEqual(["p1"]);
    });

    it("returns empty arrays when the two runs share every primitive", () => {
      const shared = [fakePrimitive("p1"), fakePrimitive("p2")];
      const a = fakeContext(shared, []);
      const b = fakeContext(shared, []);
      const { added, removed } = diffPrimitives(a, b);
      expect(added).toEqual([]);
      expect(removed).toEqual([]);
    });
  });

  describe("diffOverlays", () => {
    it("detects changes in each of the four watched fields", () => {
      const cases: Array<{ a: OverlayOverrides; b: OverlayOverrides; label: string }> = [
        { a: { flow_regime: "laminar" },      b: { flow_regime: "turbulent" },     label: "flow_regime" },
        { a: { in_critical_zone: false },     b: { in_critical_zone: true },        label: "in_critical_zone" },
        { a: { on_upper_branch: false },      b: { on_upper_branch: true },         label: "on_upper_branch" },
        { a: { hysteresis: 3.0 },             b: { hysteresis: 4.5 },               label: "hysteresis" },
      ];
      for (const c of cases) {
        const ctxA = fakeContext([], [fakeOverlay("p1", c.a)]);
        const ctxB = fakeContext([], [fakeOverlay("p1", c.b)]);
        const { changed } = diffOverlays(ctxA, ctxB);
        expect(changed, c.label).toHaveLength(1);
        expect(changed[0].primitive_id).toBe("p1");
      }
    });

    it("does not flag overlays that match across all four watched fields", () => {
      const same = { flow_regime: "laminar" as const, in_critical_zone: false, on_upper_branch: false, hysteresis: 3.0 };
      const a = fakeContext([], [fakeOverlay("p1", same), fakeOverlay("p2", same)]);
      const b = fakeContext([], [fakeOverlay("p1", same), fakeOverlay("p2", same)]);
      expect(diffOverlays(a, b).changed).toEqual([]);
    });

    it("ignores overlays present only in b (those are additions, not changes)", () => {
      const a = fakeContext([], []);
      const b = fakeContext([], [fakeOverlay("p_new")]);
      expect(diffOverlays(a, b).changed).toEqual([]);
    });
  });

  describe("diffDiagnostics", () => {
    it("returns only fields whose values differ", () => {
      const a = fakeContext([], [], fakeDiagnostics({
        observation_id: "obs_A",
        confidence_level: 0.5,
        observer_notes: "same",
      }));
      const b = fakeContext([], [], fakeDiagnostics({
        observation_id: "obs_B",
        confidence_level: 0.9,
        observer_notes: "same",
      }));
      const diff = diffDiagnostics(a, b);
      expect(diff.observation_id).toBe("obs_B");
      expect(diff.confidence_level).toBe(0.9);
      expect(diff).not.toHaveProperty("observer_notes");
    });

    it("detects nested changes in early_warnings / errors / interventions", () => {
      const a = fakeContext([], [], fakeDiagnostics({
        early_warnings: { mean_reynolds: 1000 },
        errors:         [],
        interventions:  ["intv_a"],
      }));
      const b = fakeContext([], [], fakeDiagnostics({
        early_warnings: { mean_reynolds: 5000 },  // changed value
        errors:         ["err_new"],              // grew
        interventions:  ["intv_a"],               // unchanged
      }));
      const diff = diffDiagnostics(a, b);
      expect(diff.early_warnings).toEqual({ mean_reynolds: 5000 });
      expect(diff.errors).toEqual(["err_new"]);
      expect(diff).not.toHaveProperty("interventions");
    });

    it("returns {} when diagnostics are identical", () => {
      const same = fakeDiagnostics();
      const a = fakeContext([], [], same);
      const b = fakeContext([], [], same);
      expect(diffDiagnostics(a, b)).toEqual({});
    });
  });

  describe("purity + determinism", () => {
    it("does not mutate input contexts", () => {
      const a = fakeContext([fakePrimitive("p1")], [fakeOverlay("p1")]);
      const b = fakeContext([fakePrimitive("p2")], [fakeOverlay("p2", { flow_regime: "turbulent" })]);
      const snapshotA = JSON.stringify(a);
      const snapshotB = JSON.stringify(b);

      diffPrimitives(a, b);
      diffOverlays(a, b);
      diffDiagnostics(a, b);

      expect(JSON.stringify(a)).toBe(snapshotA);
      expect(JSON.stringify(b)).toBe(snapshotB);
    });

    it("returns identical results for identical inputs (determinism)", () => {
      const a = fakeContext([fakePrimitive("p1"), fakePrimitive("p2")], [fakeOverlay("p1")]);
      const b = fakeContext([fakePrimitive("p2"), fakePrimitive("p3")], [fakeOverlay("p1", { flow_regime: "turbulent" })]);

      const r1 = diffPrimitives(a, b);
      const r2 = diffPrimitives(a, b);
      expect(r1.added.map((p) => p.metadata.primitive_id)).toEqual(r2.added.map((p) => p.metadata.primitive_id));
      expect(r1.removed.map((p) => p.metadata.primitive_id)).toEqual(r2.removed.map((p) => p.metadata.primitive_id));

      const o1 = diffOverlays(a, b);
      const o2 = diffOverlays(a, b);
      expect(o1.changed.map((o) => o.primitive_id)).toEqual(o2.changed.map((o) => o.primitive_id));
    });
  });
});
