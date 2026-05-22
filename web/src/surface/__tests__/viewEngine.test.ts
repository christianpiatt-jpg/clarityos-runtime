// Card A1 — tests for the v0.2.0 view-engine foundation.
//
// Three modules under test:
//
//   * viewContract.ts          — type-only namespace; locked by
//                                structural tests below (Mode
//                                constants + RenderOutput shape).
//   * viewRegistry.ts          — Map-backed singleton; tested via
//                                register / get / clear cycles.
//   * viewDefaultRenderer.ts   — deterministic HTML/JSON fallback;
//                                tested for both modes + HTML
//                                escaping + JSON shape.
//
// renderer.ts's dispatch behaviour (registry hit vs fallback) is
// tested next door in ``renderer.test.ts``; this file focuses on
// the underlying primitives.
//
// Path: web/src/surface/__tests__/viewEngine.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { defaultRenderer } from "../viewDefaultRenderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  getView,
  ViewRenderer,
  _listRegisteredViewsForTests,
  _clearViewRegistryForTests,
} from "../viewRegistry";


beforeEach(() => _clearViewRegistryForTests());
afterEach(() => _clearViewRegistryForTests());


// ---------------------------------------------------------------------------
// 1. View contract — Mode discriminator constants
// ---------------------------------------------------------------------------
describe("WebSurfaceV0_2_View.Mode — discriminator constants", () => {
  test("Mode constants mirror the union exactly", () => {
    expect(V.Mode.html).toBe("html");
    expect(V.Mode.json).toBe("json");
    expect(Object.keys(V.Mode).sort()).toEqual(["html", "json"]);
  });

  test("Mode constants narrow correctly when used as the discriminator", () => {
    function pickContentType(mode: V.Mode): string {
      switch (mode) {
        case V.Mode.html: return "text/html; charset=utf-8";
        case V.Mode.json: return "application/json";
        default: {
          const _exhaustive: never = mode;
          return _exhaustive;
        }
      }
    }
    expect(pickContentType(V.Mode.html)).toBe("text/html; charset=utf-8");
    expect(pickContentType(V.Mode.json)).toBe("application/json");
  });
});


// ---------------------------------------------------------------------------
// 2. Default renderer — JSON mode
// ---------------------------------------------------------------------------
describe("defaultRenderer — JSON mode", () => {
  test("returns 200 with application/json content-type", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.json });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
  });

  test("body echoes view name + params", async () => {
    const out = await defaultRenderer({
      view:   "dashboard",
      params: { id: "abc", verbose: true },
      mode:   V.Mode.json,
    });
    expect(out.body).toEqual({
      view:   "dashboard",
      params: { id: "abc", verbose: true },
    });
  });

  test("body uses empty params object when params is missing", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.json });
    expect((out.body as Record<string, unknown>).params).toEqual({});
  });

  test("body is JSON-serialisable (round-trips through stringify/parse)", async () => {
    const out = await defaultRenderer({
      view:   "rt",
      params: { nested: { a: [1, 2, 3] } },
      mode:   V.Mode.json,
    });
    const round = JSON.parse(JSON.stringify(out.body));
    expect(round).toEqual(out.body);
  });
});


// ---------------------------------------------------------------------------
// 3. Default renderer — HTML mode
// ---------------------------------------------------------------------------
describe("defaultRenderer — HTML mode", () => {
  test("returns 200 with text/html content-type + charset", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.html });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("body is a string starting with the DOCTYPE", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.html });
    expect(typeof out.body).toBe("string");
    expect((out.body as string).startsWith("<!DOCTYPE html>")).toBe(true);
  });

  test("body contains the view name in <h1> and <title>", async () => {
    const out = await defaultRenderer({
      view: "dashboard",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<h1>dashboard</h1>");
    expect(html).toContain("<title>dashboard</title>");
  });

  test("body contains JSON-serialised params under <pre>", async () => {
    const out = await defaultRenderer({
      view:   "with-params",
      params: { id: "abc" },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<pre>");
    expect(html).toMatch(/&quot;id&quot;/);  // escaped JSON quotes
    expect(html).toMatch(/abc/);
  });

  test("HTML output escapes the view name (XSS regression)", async () => {
    // A view name carrying HTML metacharacters must be entity-
    // escaped before being interpolated into the body. Catches the
    // case where a future caller passes user-influenced view names.
    const out = await defaultRenderer({
      view: '<script>alert("x")</script>',
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // The raw script tag MUST NOT appear in the output.
    expect(html).not.toContain('<script>alert("x")</script>');
    // The escaped form MUST appear.
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("alert(&quot;x&quot;)");
  });

  test("HTML output escapes params (XSS regression)", async () => {
    const out = await defaultRenderer({
      view:   "safe-view",
      params: { evil: '<img src=x onerror="alert(1)">' },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    expect(html).not.toContain('<img src=x onerror="alert(1)">');
    expect(html).toContain("&lt;img");
  });
});


// ---------------------------------------------------------------------------
// 4. Registry — register / get / clear / list
// ---------------------------------------------------------------------------
describe("view registry", () => {
  test("registered view is retrievable by name", () => {
    const renderer: ViewRenderer = async () => ({
      status: 200, headers: {}, body: { hit: true },
    });
    registerView("hello", renderer);
    expect(getView("hello")).toBe(renderer);
  });

  test("unregistered name returns undefined", () => {
    expect(getView("nonexistent")).toBeUndefined();
  });

  test("re-registering the same name overrides", () => {
    const first: ViewRenderer = async () => ({
      status: 100, headers: {}, body: {},
    });
    const second: ViewRenderer = async () => ({
      status: 200, headers: {}, body: {},
    });
    registerView("doubled", first);
    registerView("doubled", second);
    expect(getView("doubled")).toBe(second);
  });

  test("multiple distinct registrations are kept independently", () => {
    const a: ViewRenderer = async () => ({
      status: 200, headers: {}, body: { which: "a" },
    });
    const b: ViewRenderer = async () => ({
      status: 200, headers: {}, body: { which: "b" },
    });
    registerView("a", a);
    registerView("b", b);
    expect(getView("a")).toBe(a);
    expect(getView("b")).toBe(b);
    expect(_listRegisteredViewsForTests().sort()).toEqual(["a", "b"]);
  });

  test("test-helper clears the registry", () => {
    registerView("temp", async () => ({
      status: 200, headers: {}, body: {},
    }));
    expect(_listRegisteredViewsForTests()).toContain("temp");
    _clearViewRegistryForTests();
    expect(_listRegisteredViewsForTests()).toEqual([]);
    expect(getView("temp")).toBeUndefined();
  });
});


// ---------------------------------------------------------------------------
// 5. RenderOutput contract — structural shape locked
// ---------------------------------------------------------------------------
describe("RenderOutput — structural contract", () => {
  test("defaultRenderer JSON output matches the contract", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.json });
    expect(Object.keys(out).sort()).toEqual(["body", "headers", "status"]);
    expect(typeof out.status).toBe("number");
    expect(typeof out.headers).toBe("object");
    // body in JSON mode is an object.
    expect(typeof out.body).toBe("object");
    expect(Array.isArray(out.body)).toBe(false);
  });

  test("defaultRenderer HTML output matches the contract", async () => {
    const out = await defaultRenderer({ view: "x", mode: V.Mode.html });
    expect(Object.keys(out).sort()).toEqual(["body", "headers", "status"]);
    // body in HTML mode is a string.
    expect(typeof out.body).toBe("string");
  });

  test("registered renderer's output may use the full RenderOutput shape", async () => {
    registerView("rich", async () => ({
      status:  418,
      headers: { "x-tea-pot": "yes" },
      body:    { error: "im_a_teapot", detail: { rfc: 2324 } },
    }));
    const renderer = getView("rich")!;
    const out = await renderer({ view: "rich", mode: V.Mode.json });
    expect(out.status).toBe(418);
    expect(out.headers["x-tea-pot"]).toBe("yes");
    expect((out.body as Record<string, unknown>).error).toBe("im_a_teapot");
  });
});


// ---------------------------------------------------------------------------
// 6. No side effects at import
// ---------------------------------------------------------------------------
describe("module purity", () => {
  test("re-importing the contract is idempotent", async () => {
    const first = await import("../viewContract");
    const second = await import("../viewContract");
    expect(first).toBe(second);
  });

  test("re-importing the registry is idempotent", async () => {
    const first = await import("../viewRegistry");
    const second = await import("../viewRegistry");
    expect(first).toBe(second);
  });

  test("re-importing the default renderer is idempotent", async () => {
    const first = await import("../viewDefaultRenderer");
    const second = await import("../viewDefaultRenderer");
    expect(first).toBe(second);
  });
});
