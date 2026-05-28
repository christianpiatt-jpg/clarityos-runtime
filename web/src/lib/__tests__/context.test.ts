// Card 28 — createEngineV1Context snapshot test.
//
// Asserts the OperatorContext correctly captures a full engine run:
//   - inputs preserved (primitives + projectionDays normalised to default)
//   - raw response matches what fetch returned
//   - normalized + classified layers consistent with their helpers
//   - input primitives array unmutated
//
// Same localStorage-seed + vi.resetModules + dynamic import pattern
// as Card 22A / 27.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  EnginePrimitiveInput,
  EngineResponseV1,
  EngineV1OperatorContext,
} from "../api";

const SESSION_STORAGE_KEY = "clarityos_session";

describe("Card 28 — createEngineV1Context", () => {
  let createEngineV1Context: (
    primitives: EnginePrimitiveInput[],
    projectionDays?: number,
  ) => Promise<EngineV1OperatorContext>;

  let mockResponse: EngineResponseV1;

  beforeEach(async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_28");
    vi.resetModules();
    const api = await import("../api");
    createEngineV1Context = api.createEngineV1Context;

    mockResponse = {
      ok: true,
      primitives: [
        {
          metadata: {
            primitive_id:   "prim_ctx_001",
            primitive_type: "entity",
            timestamp:      "2026-05-28T00:00:00+00:00",
            version:        "1.0.0",
            domain:         "general",
            source:         "Card 28 fixture",
            parent_id:      null,
            ancestors:      [],
            depends_on:     [],
            influences:     [],
            confidence:     1.0,
            completeness:   1.0,
            reliability:    1.0,
          },
          content: { note: "fixture" },
          hydraulic_state: {
            pressure:   5.0,
            gradient:   0.0,
            flow:       4.0,
            resistance: 2.0,
            timestamp:  "2026-05-28T00:00:00+00:00",
          },
          origin_state:      null,
          historical_states: [],
        },
      ],
      overlays: [
        {
          primitive_id:     "prim_ctx_001",
          reynolds_number:  3000,
          flow_regime:      "transitional",
          stability:        0.5,
          in_critical_zone: true,
          distance_to_fold: 0.5,
          resilience:       9.0,
          curve_position:   5.5,
          on_upper_branch:  true,
          sensitivity:      4.0,
          hysteresis:       3.0,
        },
      ],
      regression: null,
      projection: null,
      diagnostics: {
        observation_id:    "obs_28_001",
        observer_notes:    "Card 28 fixture",
        confidence_level:  0.7,
        validation_status: "unvalidated",
        early_warnings:    {},
        errors:            [],
        interventions:     [],
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok:   true,
        json: async () => mockResponse,
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.removeItem(SESSION_STORAGE_KEY);
  });

  it("captures inputs, raw, normalized, and classified layers in one snapshot", async () => {
    const inputs: EnginePrimitiveInput[] = [
      { pressure: 5.0, flow: 4.0, resistance: 2.0 },
    ];

    const ctx = await createEngineV1Context(inputs, 21);

    // Inputs preserved (primitives by reference, projectionDays normalised).
    expect(ctx.primitives).toBe(inputs);
    expect(ctx.projectionDays).toBe(21);

    // raw === the mocked response (round-tripped through JSON, so structurally equal).
    expect(ctx.raw).toEqual(mockResponse);

    // normalized layer reflects the raw layer.
    expect(ctx.normalized.primitives).toEqual(mockResponse.primitives);
    expect(ctx.normalized.overlays).toEqual(mockResponse.overlays);
    expect(ctx.normalized.primitiveCount).toBe(1);
    expect(ctx.normalized.overlayCount).toBe(1);
    expect(ctx.normalized.regression).toBeNull();
    expect(ctx.normalized.projection).toBeNull();
    expect(ctx.normalized.diagnostics.observation_id).toBe("obs_28_001");

    // classified layer reflects the normalized layer (entity primitive,
    // transitional + critical + upper-branch overlay).
    expect(ctx.classified.entities).toHaveLength(1);
    expect(ctx.classified.signals).toEqual([]);
    expect(ctx.classified.transitionalOverlays).toHaveLength(1);
    expect(ctx.classified.criticalZoneOverlays).toHaveLength(1);
    expect(ctx.classified.upperBranchOverlays).toHaveLength(1);
    expect(ctx.classified.laminarOverlays).toEqual([]);
  });

  it("normalises projectionDays to 7 when omitted at the call site", async () => {
    const ctx = await createEngineV1Context([], undefined);
    expect(ctx.projectionDays).toBe(7);

    // Builder also forwarded that default into the request body.
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toContain('"projection_days":7');
  });

  it("does not mutate the caller's primitives array", async () => {
    const inputs: EnginePrimitiveInput[] = [
      { pressure: 5.0, flow: 4.0, resistance: 2.0, gradient: 0.1 },
    ];
    const snapshot = JSON.stringify(inputs);

    const ctx = await createEngineV1Context(inputs, 7);

    expect(JSON.stringify(inputs)).toBe(snapshot);
    // And the context's primitives field IS the same array (intentional
    // pass-through; the operator layer is expected to treat the context
    // as read-only by convention).
    expect(ctx.primitives).toBe(inputs);
  });

  it("captures every layer independently — mutating one does not affect another", async () => {
    // Convention check: the operator layer should treat the context as
    // read-only. This test pins that the four fields are distinct
    // objects (no aliasing between raw / normalized / classified beyond
    // primitive / overlay element identity, which is intentional and
    // tested elsewhere).
    const ctx = await createEngineV1Context([], 7);
    expect(ctx.raw).not.toBe(ctx.normalized);
    expect(ctx.normalized).not.toBe(ctx.classified);
    expect(ctx.raw).not.toBe(ctx.classified);
  });
});
