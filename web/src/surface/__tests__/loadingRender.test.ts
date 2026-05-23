// Card A24-R — server-side loading surface tests.
//
// Four contract surfaces under test:
//
//   1. Constants — DEFAULT_LOADING_MESSAGE, LOADING_TEMPLATE_NAME,
//      LOADING_PATH literal values.
//   2. escapeHtml — five HTML-sensitive characters; & first.
//   3. renderLoadingSurface — default-message fallback (no
//      payload / undefined / missing message / non-string
//      message / empty string), custom message injection,
//      HTML escaping, static chrome (spinner div + status
//      slot), determinism + non-mutation.
//   4. handleLoading + _coercePayload — lenient body parsing,
//      always 200 + text/html, never throws.
//
// Path: web/src/surface/__tests__/loadingRender.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  renderLoadingSurface,
  DEFAULT_LOADING_MESSAGE,
  LOADING_TEMPLATE_NAME,
  escapeHtml,
  type LoadingPayload,
} from "../loading";
import {
  LOADING_PATH,
  handleLoading,
  _coercePayload,
} from "../../server/routes/loading";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";


function req(opts: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/__loading",
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
  test("DEFAULT_LOADING_MESSAGE is the literal 'Loading…'", () => {
    expect(DEFAULT_LOADING_MESSAGE).toBe("Loading…");
    expect(DEFAULT_LOADING_MESSAGE).toBe("Loading…");
  });

  test("LOADING_TEMPLATE_NAME is the literal 'loadingFragment'", () => {
    expect(LOADING_TEMPLATE_NAME).toBe("loadingFragment");
  });

  test("LOADING_PATH is the literal /__loading", () => {
    expect(LOADING_PATH).toBe("/__loading");
  });
});


// ---------------------------------------------------------------------------
// 2. escapeHtml — boundary escape
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

  test("empty string passes through unchanged", () => {
    expect(escapeHtml("")).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 3. renderLoadingSurface — default-message fallback
// ---------------------------------------------------------------------------
describe("renderLoadingSurface — default-message fallback", () => {
  test("no payload → renders default message", async () => {
    const html = await renderLoadingSurface();
    expect(html).toContain('<p data-loading-message>Loading…</p>');
  });

  test("undefined payload → renders default message", async () => {
    const html = await renderLoadingSurface(undefined);
    expect(html).toContain('<p data-loading-message>Loading…</p>');
  });

  test("empty object → renders default message", async () => {
    const html = await renderLoadingSurface({});
    expect(html).toContain('<p data-loading-message>Loading…</p>');
  });

  test("payload.message=undefined → renders default message", async () => {
    const html = await renderLoadingSurface({ message: undefined });
    expect(html).toContain('<p data-loading-message>Loading…</p>');
  });

  test("payload.message='' (empty string) → renders default message", async () => {
    const html = await renderLoadingSurface({ message: "" });
    expect(html).toContain('<p data-loading-message>Loading…</p>');
  });
});


// ---------------------------------------------------------------------------
// 4. renderLoadingSurface — custom message
// ---------------------------------------------------------------------------
describe("renderLoadingSurface — custom message", () => {
  test("custom message replaces the default", async () => {
    const html = await renderLoadingSurface({ message: "Working on it…" });
    expect(html).toContain('<p data-loading-message>Working on it…</p>');
    expect(html).not.toContain(">Loading…<");
  });

  test("HTML-escapes the message (defence-in-depth)", async () => {
    const html = await renderLoadingSurface({
      message: '"><script>alert(1)</script>',
    });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).toContain("&quot;");
  });

  test("static chrome present (spinner + wrapper + data-attr)", async () => {
    const html = await renderLoadingSurface();
    expect(html).toContain('class="loading-surface"');
    expect(html).toContain('data-loading-surface');
    expect(html).toContain('<div class="spinner"></div>');
  });
});


describe("renderLoadingSurface — determinism + non-mutation", () => {
  test("same payload → byte-identical HTML across 5 renders", async () => {
    const payload: LoadingPayload = { message: "Hold on" };
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      outs.push(await renderLoadingSurface(payload));
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("default-message renders are byte-identical", async () => {
    const a = await renderLoadingSurface();
    const b = await renderLoadingSurface({});
    const c = await renderLoadingSurface({ message: "" });
    expect(b).toBe(a);
    expect(c).toBe(a);
  });

  test("does not mutate the input payload", async () => {
    const payload: LoadingPayload = { message: "x" };
    const frozen = JSON.stringify(payload);
    await renderLoadingSurface(payload);
    expect(JSON.stringify(payload)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 5. _coercePayload — lenient parsing table
// ---------------------------------------------------------------------------
describe("_coercePayload — lenient parsing", () => {
  test("well-formed JSON with message → returned as-is", () => {
    expect(_coercePayload('{"message":"go"}')).toEqual({ message: "go" });
  });

  test("empty JSON object → empty payload", () => {
    expect(_coercePayload('{}')).toEqual({});
  });

  test("non-string body → empty payload", () => {
    expect(_coercePayload(null)).toEqual({});
    expect(_coercePayload(undefined)).toEqual({});
    expect(_coercePayload(Buffer.from("anything"))).toEqual({});
  });

  test("empty string body → empty payload", () => {
    expect(_coercePayload("")).toEqual({});
  });

  test("unparseable JSON → empty payload", () => {
    expect(_coercePayload("not-json{")).toEqual({});
  });

  test("JSON that's not an object → empty payload", () => {
    expect(_coercePayload('"a string"')).toEqual({});
    expect(_coercePayload('42')).toEqual({});
    expect(_coercePayload('null')).toEqual({});
    expect(_coercePayload('["x"]')).toEqual({});
  });

  test("JSON object without message → empty payload", () => {
    expect(_coercePayload('{"other":"x"}')).toEqual({});
  });

  test("JSON with non-string message → empty payload", () => {
    expect(_coercePayload('{"message":1}')).toEqual({});
    expect(_coercePayload('{"message":true}')).toEqual({});
    expect(_coercePayload('{"message":null}')).toEqual({});
  });
});


// ---------------------------------------------------------------------------
// 6. handleLoading — route behaviour
// ---------------------------------------------------------------------------
describe("handleLoading — always 200 + text/html", () => {
  test("POST + valid body → 200 + text/html + custom message", async () => {
    const response = await handleLoading(req({
      body: JSON.stringify({ message: "Working…" }),
    }));
    expect(response.status).toBe(200);
    expect(response.headers["content-type"]).toBe(
      "text/html; charset=utf-8",
    );
    expect(response.body as string).toContain(
      '<p data-loading-message>Working…</p>',
    );
  });

  test("POST + no body → 200 + default-message fragment", async () => {
    const response = await handleLoading(req({ body: "" }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      '<p data-loading-message>Loading…</p>',
    );
  });

  test("POST + null body → 200 + default-message fragment", async () => {
    const response = await handleLoading(req({ body: null }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      '<p data-loading-message>Loading…</p>',
    );
  });

  test("POST + unparseable JSON → 200 + default-message fragment", async () => {
    const response = await handleLoading(req({ body: "not-json" }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      '<p data-loading-message>Loading…</p>',
    );
  });

  test("POST + JSON without message → 200 + default-message fragment", async () => {
    const response = await handleLoading(req({
      body: JSON.stringify({ unrelated: "x" }),
    }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      '<p data-loading-message>Loading…</p>',
    );
  });

  test("non-POST method still returns 200 + default fragment (lenient)", async () => {
    const response = await handleLoading(req({
      method: "GET",
      body:   null,
    }));
    expect(response.status).toBe(200);
    expect(response.body as string).toContain(
      '<p data-loading-message>Loading…</p>',
    );
  });

  test("content-type is always text/html (never JSON)", async () => {
    const cases = [
      req({ body: "" }),
      req({ body: null }),
      req({ body: "not-json" }),
      req({ body: JSON.stringify({ message: "x" }) }),
      req({ body: JSON.stringify({}) }),
      req({ method: "GET", body: null }),
    ];
    for (const r of cases) {
      const response = await handleLoading(r);
      expect(response.headers["content-type"]).toBe(
        "text/html; charset=utf-8",
      );
      expect(typeof response.body).toBe("string");
      // The body is always an HTML fragment, never a JSON object.
      expect((response.body as string).startsWith("{")).toBe(false);
    }
  });
});


describe("handleLoading — determinism + non-mutation", () => {
  test("same request → byte-identical body across calls", async () => {
    const r = req({ body: JSON.stringify({ message: "x" }) });
    const a = await handleLoading(r);
    const b = await handleLoading(r);
    expect(b.body).toBe(a.body);
  });

  test("default-message calls produce byte-identical bodies", async () => {
    const a = await handleLoading(req({ body: "" }));
    const b = await handleLoading(req({ body: null }));
    const c = await handleLoading(req({ body: "not-json" }));
    expect(b.body).toBe(a.body);
    expect(c.body).toBe(a.body);
  });

  test("does not mutate the request", async () => {
    const r = req({ body: JSON.stringify({ message: "x" }) });
    const frozen = JSON.stringify(r);
    await handleLoading(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });

  test("XSS payload in message is escaped on the wire", async () => {
    const response = await handleLoading(req({
      body: JSON.stringify({ message: '<img src=x>' }),
    }));
    expect(response.body as string).not.toContain('<img src=x>');
    expect(response.body as string).toContain('&lt;img src=x&gt;');
  });
});
