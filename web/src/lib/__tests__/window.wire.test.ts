/**
 * #139 -- what the four doors put on the wire.
 *
 * ★ WHAT THESE PIN. The api.ts doors (the cockpit's personal run and
 * /personal-elins) send surface "personal" without their callers changing
 * a line; the typed thread doors (lib/emotionalPhysics, lib/elinsV2) send
 * surface + message_boundaries as given and default to "thread". The
 * kernel sizes its window from that one word.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const SESSION_STORAGE_KEY = "clarityos_session";

const PHYSICS = {
  field_curvature: {}, edge_pressure: {}, relational_primitives: {}, external_expression: {},
  _meta: { model_id: "m", ts_ms: 1, parse_error: null, window_chars: 6000, total_chars: 9000, window_anchor: "tail" },
};
const ENVELOPE = {
  elins_version: "elins.v2.0", region: null, input: {}, pipeline: {},
  outputs: { collapse_state: "none", attractor: "S1", state_distribution: {}, P0_P8: {}, geography_tier: null, timeline: {}, multiplier: 1 },
  meta: { engine: "x", view_kind: "y", warnings: [], notes: [] },
  _meta: { window_chars: 6000, total_chars: 9000, window_anchor: "tail" },
};

function lastBody() {
  const f = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
  const [url, init] = f.mock.calls[f.mock.calls.length - 1] as [unknown, RequestInit];
  return { url: String(url), body: JSON.parse(String(init.body)) as Record<string, unknown> };
}

describe("the window on the wire", () => {
  beforeEach(() => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_window");
    vi.resetModules();
  });
  afterEach(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    vi.unstubAllGlobals();
  });

  function stub(response: unknown) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => response,
      headers: new Headers({ "content-type": "application/json" }),
    }));
  }

  it("★ api.runEmotionalPhysics is the personal door: surface personal, callers unchanged", async () => {
    stub(PHYSICS);
    const api = await import("../api");
    const r = await api.runEmotionalPhysics("seed text", "r1");
    expect(r._meta.window_chars).toBe(6000);
    const { url, body } = lastBody();
    expect(url.endsWith("/me/emotional_physics/analyze")).toBe(true);
    expect(body).toEqual({ text: "seed text", thread_id: "r1", surface: "personal" });
    await api.runEmotionalPhysics("seed text");
    expect(lastBody().body).toEqual({ text: "seed text", surface: "personal" });
  });

  it("★ api.runElinsV2 is the personal door too", async () => {
    stub(ENVELOPE);
    const api = await import("../api");
    await api.runElinsV2("seed text", null, "r1");
    expect(lastBody().body).toEqual({ region: null, input: { raw_text: "seed text" }, thread_id: "r1", surface: "personal" });
    await api.runElinsV2("seed text");
    expect(lastBody().body).toEqual({ region: null, input: { raw_text: "seed text" }, surface: "personal" });
  });

  it("the typed physics door sends surface + boundaries as given, thread by default", async () => {
    stub(PHYSICS);
    const lib = await import("../emotionalPhysics");
    await lib.analyzeEmotionalPhysics({ text: "user: a\nassistant: b", surface: "thread", message_boundaries: [7, 20] });
    expect(lastBody().body).toEqual({ text: "user: a\nassistant: b", surface: "thread", message_boundaries: [7, 20] });
    await lib.analyzeEmotionalPhysics({ text: "just text" });
    expect(lastBody().body).toEqual({ text: "just text", surface: "thread", message_boundaries: null });
  });

  it("the typed ELINS door sends surface + boundaries as given, thread by default", async () => {
    stub(ENVELOPE);
    const lib = await import("../elinsV2");
    await lib.runElinsV2({ input: { raw_text: "user: a\nassistant: b" }, surface: "personal", message_boundaries: [7, 20] });
    const { body } = lastBody();
    expect(body.surface).toBe("personal");
    expect(body.message_boundaries).toEqual([7, 20]);
    await lib.runElinsV2({ input: { raw_text: "just text" } });
    expect(lastBody().body.surface).toBe("thread");
    expect(lastBody().body.message_boundaries).toBeNull();
  });
});
