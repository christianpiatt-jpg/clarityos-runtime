// Card 22A — runEngineV1 alias test.
//
// Asserts that the Card 22-named ``runEngineV1`` helper:
//   1. hits POST /engine/v1/run on the backend
//   2. forwards the request body verbatim
//   3. parses the response as EngineResponseV1
//   4. accepts EngineRequestV1 (alias of the deployed EngineRunRequest)
//
// The original Card 22 draft proposed a {text, mode, includeHistorical}
// request shape that does not exist on the backend. Card 22A's
// EngineRequestV1 is a type alias to the deployed EngineRunRequest
// (primitives + projection_days). This test pins that alias so the
// stale shape can't sneak back in later.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EngineRequestV1, EngineResponseV1 } from "../api";

// api.ts initialises memorySession at module load by reading from
// localStorage. Web doesn't export a public session setter, so the
// test seeds localStorage and forces a fresh module load via
// vi.resetModules() before each test.
const SESSION_STORAGE_KEY = "clarityos_session";

describe("Card 22A — runEngineV1 alias", () => {
  let runEngineV1: (i: EngineRequestV1) => Promise<EngineResponseV1>;

  beforeEach(async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_22A");
    vi.resetModules();
    const api = await import("../api");
    runEngineV1 = api.runEngineV1;

    const mockResponse: EngineResponseV1 = {
      ok: true,
      primitives: [],
      overlays: [],
      regression: null,
      projection: null,
      diagnostics: {
        observation_id:    "obs_test_001",
        observer_notes:    "test",
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

  it("hits /engine/v1/run with POST and forwards the body verbatim", async () => {
    const input: EngineRequestV1 = {
      primitives: [],
      projection_days: 7,
    };

    const res = await runEngineV1(input);

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(typeof url).toBe("string");
    expect(url).toContain("/engine/v1/run");
    expect(init).toMatchObject({ method: "POST" });
    expect(init.body).toBe(JSON.stringify(input));

    // Response parses to the deployed EngineResponseV1 shape.
    expect(res.ok).toBe(true);
    expect(res.primitives).toEqual([]);
    expect(res.diagnostics.observation_id).toBe("obs_test_001");
    expect(res.diagnostics.interventions).toEqual([]);
  });

  it("EngineRequestV1 accepts the deployed EngineRunRequest shape", async () => {
    // The card draft's {text, mode, includeHistorical} shape was
    // rejected. This test pins the alias to the real backend body so
    // any future redefinition that drops `primitives` or
    // `projection_days` will fail compilation.
    const input: EngineRequestV1 = {
      primitives: [
        {
          primitive_id:   "prim_22A_001",
          primitive_type: "signal",
          domain:         "general",
          source:         "Card 22A test",
          pressure:       5.0,
          flow:           4.0,
          resistance:     2.0,
        },
      ],
      projection_days: 30,
    };

    await runEngineV1(input);
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
