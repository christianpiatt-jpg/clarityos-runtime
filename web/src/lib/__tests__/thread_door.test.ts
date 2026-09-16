/**
 * #113 -- the two thread doors carry the thread they belong to.
 *
 * ★ WHAT THESE PIN. lib/emotionalPhysics and lib/elinsV2 send `thread_id`
 * when the caller gives one and send NOTHING under that key otherwise (the
 * #139 wire pins stay exact); the backend records a turn on the thread and
 * counts its scored turns into _meta.n_points.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const SESSION_STORAGE_KEY = "clarityos_session";

const PHYSICS = {
  field_curvature: {}, edge_pressure: {}, relational_primitives: {}, external_expression: {},
  _meta: { model_id: "m", ts_ms: 1, parse_error: null },
};
const ENVELOPE = {
  elins_version: "elins.v2.0", region: null, input: {}, pipeline: {},
  outputs: { collapse_state: "none", attractor: "S1", state_distribution: {}, P0_P8: {}, geography_tier: null, timeline: {}, multiplier: 1 },
  meta: { engine: "x", view_kind: "y", warnings: [], notes: [] },
  _meta: { n_points: 3 },
};

function lastBody() {
  const f = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
  const [, init] = f.mock.calls[f.mock.calls.length - 1] as [unknown, RequestInit];
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

function stub(response: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => response,
    headers: new Headers({ "content-type": "application/json" }),
  }));
}

describe("#113 -- the thread on the wire", () => {
  beforeEach(() => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_113");
    vi.resetModules();
  });
  afterEach(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    vi.unstubAllGlobals();
  });

  it("★ the physics door sends thread_id when given, and no key otherwise", async () => {
    stub(PHYSICS);
    const { analyzeEmotionalPhysics } = await import("../emotionalPhysics");
    await analyzeEmotionalPhysics({ text: "t", surface: "thread", message_boundaries: [1], thread_id: "t1" });
    expect(lastBody()).toEqual({ text: "t", surface: "thread", message_boundaries: [1], thread_id: "t1" });
    await analyzeEmotionalPhysics({ text: "t", surface: "thread", message_boundaries: [1], thread_id: null });
    expect(lastBody()).toEqual({ text: "t", surface: "thread", message_boundaries: [1] });
  });

  it("★ the ELINS door sends thread_id when given, and no key otherwise", async () => {
    stub(ENVELOPE);
    const { runElinsV2 } = await import("../elinsV2");
    await runElinsV2({ input: { raw_text: "t" }, surface: "thread", message_boundaries: [1], thread_id: "t1" });
    expect(lastBody().thread_id).toBe("t1");
    await runElinsV2({ input: { raw_text: "t" }, surface: "thread", message_boundaries: [1] });
    expect("thread_id" in lastBody()).toBe(false);
  });
});
