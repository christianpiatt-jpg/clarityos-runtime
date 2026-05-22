// Card A4 — multi-view registry + template binding tests.
//
// Covers the integration surface between:
//   * the ``ViewDefinition``-shaped registry,
//   * the renderer's HTML-mode template-binding dispatch,
//   * the ``home`` view (the first named, registered view),
//   * the renderer's mode-aware fallback to ``defaultRenderer``.
//
// Path: web/src/surface/__tests__/viewRegistryBinding.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  getView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
  ViewDefinition,
} from "../viewRegistry";
import { homeView } from "../views/home";


beforeEach(() => {
  _clearViewRegistryForTests();
  // Side-effect import of ``../views/home`` registers home once;
  // after _clearViewRegistryForTests it's gone. Re-register
  // explicitly so each test that needs ``home`` starts clean.
  registerView("home", homeView);
});

afterEach(() => _clearViewRegistryForTests());


// ---------------------------------------------------------------------------
// 1. Registry stores definitions
// ---------------------------------------------------------------------------
describe("ViewDefinition registry", () => {
  test("registerView stores a ViewDefinition", () => {
    const def: ViewDefinition = {
      template: "base",
      async render() { return { title: "x", content: "y" }; },
    };
    registerView("test-view", def);
    expect(getView("test-view")).toBe(def);
  });

  test("getView retrieves a registered definition", () => {
    const def = getView("home");
    expect(def).toBeDefined();
    expect(def!.template).toBe("home");
  });

  test("getView returns undefined for an unknown view", () => {
    expect(getView("does-not-exist-zzz")).toBeUndefined();
  });

  test("home is in the registered-views list", () => {
    expect(_listRegisteredViewsForTests()).toContain("home");
  });
});


// ---------------------------------------------------------------------------
// 2. Template binding — registered view + HTML mode
// ---------------------------------------------------------------------------
describe("template binding — registered home view + HTML mode", () => {
  test("home view renders via its own template (home.html)", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = out.body as string;
    // home.html is distinguishable from base.html by the
    // welcome paragraph.
    expect(html).toContain("Welcome to the Web Surface v0.2.0");
  });

  test("home view template substitutes the title", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<title>Home</title>");
    expect(html).toContain("<h1>Home</h1>");
  });

  test("home view template substitutes the content", async () => {
    const out = await renderWebSurface({
      view:   "home",
      params: { id: "abc" },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    // Content is JSON-stringified, then HTML-escaped by the view.
    expect(html).toMatch(/&quot;id&quot;/);
    expect(html).toMatch(/abc/);
  });

  test("home view escapes user-controlled params (XSS regression)", async () => {
    const out = await renderWebSurface({
      view:   "home",
      params: { evil: '<script>alert("x")</script>' },
      mode:   V.Mode.html,
    });
    const html = out.body as string;
    // The home view escapes its content via the local escapeHtml.
    expect(html).not.toContain('<script>alert("x")</script>');
    expect(html).toContain("&lt;script&gt;");
  });

  test("HTML output has no unfilled placeholders", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).not.toMatch(/{{\s*\w+\s*}}/);
  });

  test("a custom view bound to base template renders through it", async () => {
    registerView("custom", {
      template: "base",
      async render() {
        return { title: "Custom", content: "custom body" };
      },
    });
    const out = await renderWebSurface({
      view: "custom",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<title>Custom</title>");
    expect(html).toContain("<h1>Custom</h1>");
    expect(html).toContain("custom body");
    // base.html does NOT have the welcome line — confirms we used
    // the right template.
    expect(html).not.toContain("Welcome to the Web Surface");
  });

  test("view render() receives the full RenderContext", async () => {
    let received: V.RenderContext | null = null;
    registerView("introspect", {
      template: "base",
      async render(ctx) {
        received = ctx;
        return { title: "ok", content: "" };
      },
    });
    await renderWebSurface({
      view:   "introspect",
      params: { a: "1", b: "2" },
      mode:   V.Mode.html,
    });
    expect(received).not.toBeNull();
    expect(received!.view).toBe("introspect");
    expect(received!.params).toEqual({ a: "1", b: "2" });
    expect(received!.mode).toBe(V.Mode.html);
  });
});


// ---------------------------------------------------------------------------
// 3. Fallback behaviour — unknown view + JSON mode
// ---------------------------------------------------------------------------
describe("template binding — fallback behaviour", () => {
  test("unknown view + HTML mode → defaultRenderer (base.html)", async () => {
    const out = await renderWebSurface({
      view: "definitely-not-registered",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = out.body as string;
    // defaultRenderer uses base.html, which doesn't carry the
    // home view's welcome line.
    expect(html).toContain("<h1>definitely-not-registered</h1>");
    expect(html).not.toContain("Welcome to the Web Surface");
  });

  test("registered view + JSON mode → defaultRenderer (NOT the view's render fn)", async () => {
    let viewCalled = false;
    registerView("home", {
      template: "home",
      async render() {
        viewCalled = true;
        return { title: "Home", content: "x" };
      },
    });
    const out = await renderWebSurface({
      view:   "home",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    // JSON mode bypasses the view definition entirely.
    expect(viewCalled).toBe(false);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "home", params: { id: "abc" } });
  });

  test("unknown view + JSON mode → defaultRenderer canonical shape", async () => {
    const out = await renderWebSurface({
      view:   "unknown",
      params: { x: 1 },
      mode:   V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "unknown", params: { x: 1 } });
  });
});


// ---------------------------------------------------------------------------
// 4. Determinism / purity
// ---------------------------------------------------------------------------
describe("template binding — determinism", () => {
  test("same request → same HTML body for home view", async () => {
    const a = await renderWebSurface({
      view: "home", mode: V.Mode.html,
    });
    const b = await renderWebSurface({
      view: "home", mode: V.Mode.html,
    });
    expect(a).toEqual(b);
  });

  test("home view module re-import is idempotent", async () => {
    const first = await import("../views/home");
    const second = await import("../views/home");
    expect(first).toBe(second);
    // And homeView is the same object across imports.
    expect(first.homeView).toBe(second.homeView);
  });
});
