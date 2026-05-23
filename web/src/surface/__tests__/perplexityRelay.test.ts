// Card A30-R — server-side Perplexity relay tests.
//
// All tests run against MOCK mode (the upstream's default).
// REAL-mode behaviour requires a live API key + outbound
// network access and is verified cloud-side, not here.
//
// Five contract surfaces under test:
//
//   1. Constants — PERPLEXITY_PATH + PERPLEXITY_TEMPLATE_NAME
//      literal values.
//   2. escapeHtml — five HTML-sensitive characters; & first.
//   3. _coerceQuery — pulls query field; rejects missing /
//      empty / non-string / non-object.
//   4. handlePerplexity happy path — POST + valid body →
//      200 + text/html + fragment containing the mock answer
//      and tokensUsed=0.
//   5. handlePerplexity error paths — non-POST / non-string
//      body / unparseable JSON / missing query / upstream
//      throws (via trigger_error mock); each returns an HTML
//      failure fragment (never JSON), with a diagnostic
//      message and a 4xx / 502 status.
//
// Path: web/src/surface/__tests__/perplexityRelay.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  PERPLEXITY_PATH,
  PERPLEXITY_TEMPLATE_NAME,
  handlePerplexity,
  escapeHtml,
  _coerceQuery,
} from "../../server/routes/perplexity";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/__perplexity",
    method:  "POST",
    headers: { "content-type": "application/json" },
    body:    "",
    ...opts,
  };
}


beforeEach(() => {
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  // Force MOCK mode for these tests. The upstream defaults to
  // MOCK when PERPLEXITY_MODE is unset, but be explicit so a
  // stray env var from a parent shell can't flip us into REAL
  // and fire outbound HTTPS during test runs.
  delete process.env.PERPLEXITY_MODE;
  delete process.env.PERPLEXITY_API_KEY;
});

afterEach(() => {
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Constants
// ---------------------------------------------------------------------------
describe("constants", () => {
  test("PERPLEXITY_PATH is the literal /__perplexity", () => {
    expect(PERPLEXITY_PATH).toBe("/__perplexity");
  });

  test("PERPLEXITY_TEMPLATE_NAME is the literal 'perplexityFragment'", () => {
    expect(PERPLEXITY_TEMPLATE_NAME).toBe("perplexityFragment");
  });
});


// ---------------------------------------------------------------------------
// 2. escapeHtml
// ---------------------------------------------------------------------------
describe("escapeHtml", () => {
  test("escapes the five HTML-sensitive characters", () => {
    expect(escapeHtml("<")).toBe("&lt;");
    expect(escapeHtml(">")).toBe("&gt;");
    expect(escapeHtml("&")).toBe("&amp;");
    expect(escapeHtml('"')).toBe("&quot;");
    expect(escapeHtml("'")).toBe("&#39;");
  });

  test("escapes & first so existing entities don't double-encode", () => {
    expect(escapeHtml("a & b < c")).toBe("a &amp; b &lt; c");
  });
});


// ---------------------------------------------------------------------------
// 3. _coerceQuery
// ---------------------------------------------------------------------------
describe("_coerceQuery", () => {
  test("well-formed payload → returns the query string", () => {
    expect(_coerceQuery({ query: "weather" })).toBe("weather");
  });

  test("missing query → null", () => {
    expect(_coerceQuery({})).toBeNull();
  });

  test("non-string query → null", () => {
    expect(_coerceQuery({ query: 1 })).toBeNull();
    expect(_coerceQuery({ query: null })).toBeNull();
    expect(_coerceQuery({ query: ["x"] })).toBeNull();
  });

  test("empty-string query → null", () => {
    expect(_coerceQuery({ query: "" })).toBeNull();
  });

  test("null / non-object → null", () => {
    expect(_coerceQuery(null)).toBeNull();
    expect(_coerceQuery("string")).toBeNull();
    expect(_coerceQuery(42)).toBeNull();
    expect(_coerceQuery(["x"])).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// 4. handlePerplexity — happy path (MOCK)
// ---------------------------------------------------------------------------
describe("handlePerplexity — MOCK happy path", () => {
  test("POST + valid body → 200 + text/html + mock-shaped fragment", async () => {
    const response = await handlePerplexity(req({
      body: JSON.stringify({ query: "weather" }),
    }));
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
    const html = response.body as string;
    expect(html).toContain('data-perplexity-answer');
    expect(html).toContain('<pre data-answer>');
    expect(html).toContain('MOCK_RESPONSE: weather');
    expect(html).toContain('tokens: 0');
  });

  test("query is HTML-escaped on the wire (defence-in-depth)", async () => {
    const response = await handlePerplexity(req({
      body: JSON.stringify({ query: '<script>alert(1)</script>' }),
    }));
    const html = response.body as string;
    // The mock echoes the query into the response text, so a
    // dangerous query would land in the body unescaped if the
    // renderer didn't escape it. Confirm the entities ARE
    // applied.
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });

  test("byte-identical body across repeated calls (MOCK determinism)", async () => {
    const r = req({ body: JSON.stringify({ query: "deterministic" }) });
    const a = await handlePerplexity(r);
    const b = await handlePerplexity(r);
    expect(b.body).toBe(a.body);
  });

  test("does not mutate the request", async () => {
    const r = req({ body: JSON.stringify({ query: "x" }) });
    const frozen = JSON.stringify(r);
    await handlePerplexity(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 5. handlePerplexity — error paths (always HTML)
// ---------------------------------------------------------------------------
describe("handlePerplexity — error paths (always HTML)", () => {
  test("non-POST method → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({ method: "GET" }));
    expect(response.status).toBe(400);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
    const html = response.body as string;
    expect(html).toContain("method_not_allowed");
    expect(html).toContain("data-perplexity-answer");
    expect(html).toContain("tokens: 0");
  });

  test("non-string body → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({ body: null }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain("missing JSON body");
  });

  test("empty body → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({ body: "" }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain("missing JSON body");
  });

  test("unparseable JSON → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({ body: "not-json{" }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain("not valid JSON");
  });

  test("missing query → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({
      body: JSON.stringify({ unrelated: "x" }),
    }));
    expect(response.status).toBe(400);
    expect(response.body as string).toContain("non-empty string");
  });

  test("empty query string → 400 + failure fragment", async () => {
    const response = await handlePerplexity(req({
      body: JSON.stringify({ query: "" }),
    }));
    expect(response.status).toBe(400);
  });

  test("upstream throws (MOCK trigger_error path) → 502 + failure fragment", async () => {
    const response = await handlePerplexity(req({
      body: JSON.stringify({ query: "please trigger_error now" }),
    }));
    expect(response.status).toBe(502);
    expect(response.body as string).toContain("upstream_error");
    expect(response.body as string).toContain("MOCK_PERPLEXITY_ERROR");
    expect(response.body as string).toContain("data-perplexity-answer");
  });

  test("every error path carries text/html (never JSON)", async () => {
    const cases = [
      req({ method: "GET" }),
      req({ body: null }),
      req({ body: "" }),
      req({ body: "not-json" }),
      req({ body: JSON.stringify({}) }),
      req({ body: JSON.stringify({ query: "trigger_error" }) }),
    ];
    for (const r of cases) {
      const response = await handlePerplexity(r);
      expect(response.headers["content-type"]).toBe(
        "text/html; charset=utf-8",
      );
      expect(typeof response.body).toBe("string");
      expect((response.body as string).startsWith("{")).toBe(false);
    }
  });
});


// ---------------------------------------------------------------------------
// REAL-mode behaviour: NOT exercised here.
// REAL requires PERPLEXITY_MODE=REAL + a live PERPLEXITY_API_KEY
// and one outbound HTTPS call. Verified cloud-side per the
// A30-R card.
// ---------------------------------------------------------------------------
describe("REAL mode (cloud-side verification only)", () => {
  test("MOCK is the default when PERPLEXITY_MODE is unset", async () => {
    // Sanity-check: confirm we are NOT silently in REAL mode
    // — if we were, the assertion below would either time out
    // (no API key → config error, which we catch as 502) or
    // hit the real endpoint.
    delete process.env.PERPLEXITY_MODE;
    const response = await handlePerplexity(req({
      body: JSON.stringify({ query: "sanity" }),
    }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain("MOCK_RESPONSE: sanity");
  });
});
