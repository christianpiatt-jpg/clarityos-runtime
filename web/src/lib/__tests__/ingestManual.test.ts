/**
 * ingestManual — the corpus front door binding.
 *
 * ★ WHAT THESE PIN. The binding POSTs /ingest/manual through the same
 * request() path as every other binding (session header, JSON body) with
 * the server's real contract -- exactly {raw_text, source, region} -- and
 * returns the created item id as `library_id`. When no source is given the
 * SERVER's own default ("manual") goes on the wire, never a surface label.
 * The brief's title/tags are not on the input type at all: the request
 * model has no field for them, so tsc refuses them at the call site.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// api.ts reads the session from localStorage at module load and request()
// refuses with missing_session without one; there is no public setter. Seed
// the key, then force a fresh module load (same approach as api.test.ts).
const SESSION_STORAGE_KEY = "clarityos_session";

const RESPONSE = { ok: true, library_id: "l_abc123", envelope: { outputs: {} } };

function lastCall() {
  const f = globalThis.fetch as unknown as { mock: { calls: unknown[][] } };
  const [url, init] = f.mock.calls[f.mock.calls.length - 1] as [unknown, RequestInit];
  const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
  return { url: String(url), init, body: body as Record<string, unknown> };
}

describe("ingestManual", () => {
  beforeEach(() => {
    localStorage.setItem(SESSION_STORAGE_KEY, "test_session_ingest");
    vi.resetModules();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => RESPONSE,
        headers: new Headers({ "content-type": "application/json" }),
      }),
    );
  });

  afterEach(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    vi.unstubAllGlobals();
  });

  it("POSTs /ingest/manual with the real contract and returns library_id", async () => {
    const api = await import("../api");
    const r = await api.ingestManual({ text: "one. two. three." });
    expect(r.library_id).toBe("l_abc123");

    const { url, init, body } = lastCall();
    expect(url.endsWith("/ingest/manual")).toBe(true);
    expect(init.method).toBe("POST");
    // the member's session rides the request, as on every other binding
    expect((init.headers as Record<string, string>)["X-Session-ID"]).toBe("test_session_ingest");
    // ★ the server's own default source, not a surface label
    expect(body).toEqual({ raw_text: "one. two. three.", source: "manual", region: null });
  });

  it("forwards a caller's source and region", async () => {
    const api = await import("../api");
    await api.ingestManual({ text: "t", source: "elins_v2_view", region: "us" });
    expect(lastCall().body).toEqual({ raw_text: "t", source: "elins_v2_view", region: "us" });
  });

  it("★ exactly the contract's keys go on the wire -- nothing the server would drop", async () => {
    const api = await import("../api");
    await api.ingestManual({ text: "t", source: "cockpit" });
    expect(Object.keys(lastCall().body).sort()).toEqual(["raw_text", "region", "source"]);
  });

  it("a server refusal surfaces as an ApiError carrying the server's code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ ok: false, error: "bad_input", message: "raw_text is empty" }),
        headers: new Headers({ "content-type": "application/json" }),
      }),
    );
    const api = await import("../api");
    await expect(api.ingestManual({ text: "   " })).rejects.toMatchObject({
      code: "bad_input",
      status: 400,
    });
  });
});
