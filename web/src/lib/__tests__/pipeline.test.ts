// Card 27 — runEngineV1Pipeline composition test.
//
// Asserts the one-shot pipeline correctly chains:
//   builder (Card 24) → request (Card 22A) → normalizer (Card 25)
//   → classifier (Card 26A)
//
// Uses the same localStorage-seed + vi.resetModules + dynamic import
// pattern as Card 22A's api.test.ts because web's api.ts initialises
// memorySession at module load and exposes no public session setter.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  EnginePrimitiveInput,
  EngineResponseV1,
  EngineV1Classification,
} from "../api";

const SESSION_STORAGE_KEY = "clarityos_session";

describe("Card 27 — runEngineV1Pipeline", () => {
  let runEngineV1Pipeline: (
    primitives: EnginePrimitiveInput[],
    projectionDays?: number,
  ) => Promise<EngineV1Classification>;

  beforeEach(async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_27");
    vi.resetModules();
    const api = await import("../api");
    runEngineV1Pipeline = api.runEngineV1Pipeline;

    const mockResponse: EngineResponseV1 = {
      ok: true,
      primitives: [
        {
          metadata: {
            primitive_id:   "prim_pipe_001",
            primitive_type: "signal",
            timestamp:      "2026-05-28T00:00:00+00:00",
            version:        "1.0.0",
            domain:         "general",
            source:         "Card 27 fixture",
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
          primitive_id:     "prim_pipe_001",
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
        },
      ],
      regression: null,
      projection: null,
      diagnostics: {
        observation_id:    "obs_27_001",
        observer_notes:    "Card 27 fixture",
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

  it("chains builder + request + normalizer + classifier into a single call", async () => {
    const inputs: EnginePrimitiveInput[] = [
      { pressure: 5.0, flow: 4.0, resistance: 2.0 },
    ];

    const result: EngineV1Classification = await runEngineV1Pipeline(inputs, 14);

    // Card 24 builder → Card 22A request: projection_days override
    // and primitives forwarded to /engine/v1/run.
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/engine/v1/run");
    expect(init.method).toBe("POST");
    expect(init.body).toContain('"projection_days":14');
    expect(init.body).toContain('"primitives"');

    // Card 26A classifier output reflects the mocked response. The
    // single mocked primitive is a signal, the single overlay is
    // laminar — every other category should be empty.
    expect(result.signals).toHaveLength(1);
    expect(result.signals[0].metadata.primitive_id).toBe("prim_pipe_001");
    expect(result.entities).toEqual([]);
    expect(result.attitudes).toEqual([]);
    expect(result.relationships).toEqual([]);
    expect(result.events).toEqual([]);
    expect(result.temperatures).toEqual([]);

    expect(result.laminarOverlays).toHaveLength(1);
    expect(result.laminarOverlays[0].primitive_id).toBe("prim_pipe_001");
    expect(result.transitionalOverlays).toEqual([]);
    expect(result.turbulentOverlays).toEqual([]);
    expect(result.criticalZoneOverlays).toEqual([]);
    expect(result.upperBranchOverlays).toEqual([]);

    // Card 26A pass-throughs.
    expect(result.regression).toBeNull();
    expect(result.projection).toBeNull();
    expect(result.diagnostics.observation_id).toBe("obs_27_001");
  });

  it("defaults projection_days to 7 when omitted (Card 24 builder default)", async () => {
    await runEngineV1Pipeline([], undefined);

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toContain('"projection_days":7');
  });

  it("does not mutate the caller's primitives array", async () => {
    const inputs: EnginePrimitiveInput[] = [
      { pressure: 5.0, flow: 4.0, resistance: 2.0, gradient: 0.1 },
    ];
    const snapshot = JSON.stringify(inputs);

    await runEngineV1Pipeline(inputs, 7);

    expect(JSON.stringify(inputs)).toBe(snapshot);
  });
});
