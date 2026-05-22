// Tests for the v0.2.0 Web Surface render dispatcher.
//
// Card history pinned by this file:
//   * Card 9   — 501 stub
//   * Card A1  — dispatch via registry, default fallback
//   * Card A3  — defaultRenderer uses the template engine
//   * Card A4  — registry registrations are ``ViewDefinition``s
//                (template + render-to-vars), not callable
//                renderers. JSON mode bypasses view definitions.
//
// These tests lock the renderer dispatcher's post-A4 contract:
//
//   1. Output shape always conforms to ``RenderOutput`` and is
//      structurally compatible with ``WebSurfaceV0_2.Response``.
//   2. JSON mode always uses ``defaultRenderer`` (canonical
//      ``{view, params}`` shape) regardless of view registration.
//   3. HTML mode + unknown view → ``defaultRenderer`` (template-
//      based base.html).
//   4. HTML mode + registered view → template-bound render.
//   5. The dispatcher is side-effect-free for any given input.
//
// Path: web/src/surface/__tests__/renderer.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { renderWebSurface, RenderContext } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";


beforeEach(() => _clearViewRegistryForTests());
afterEach(() => _clearViewRegistryForTests());


// ---------------------------------------------------------------------------
// 1. Output shape conforms to RenderOutput
// ---------------------------------------------------------------------------
describe("renderWebSurface — output shape", () => {
  test("returns the documented RenderOutput keys", async () => {
    const out = await renderWebSurface({
      view: "any", mode: V.Mode.json,
    });
    expect(Object.keys(out).sort()).toEqual(["body", "headers", "status"]);
  });

  test("status is a number", async () => {
    const out = await renderWebSurface({
      view: "any", mode: V.Mode.json,
    });
    expect(typeof out.status).toBe("number");
  });

  test("headers is a string-keyed string map", async () => {
    const out = await renderWebSurface({
      view: "any", mode: V.Mode.json,
    });
    expect(typeof out.headers).toBe("object");
    for (const v of Object.values(out.headers)) {
      expect(typeof v).toBe("string");
    }
  });
});


// ---------------------------------------------------------------------------
// 2. JSON mode always uses defaultRenderer (canonical shape)
// ---------------------------------------------------------------------------
describe("renderWebSurface — JSON mode dispatch", () => {
  test("JSON mode + unknown view → defaultRenderer body shape", async () => {
    const out = await renderWebSurface({
      view:   "anything-unknown",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({
      view:   "anything-unknown",
      params: { id: "abc" },
    });
  });

  test("JSON mode + REGISTERED view → defaultRenderer body shape (bypass)", async () => {
    // Post-A4 invariant: the view's render() is NEVER called for
    // JSON mode. The canonical {view, params} shape is the JSON
    // contract; per-view JSON shaping is a future card.
    let viewRenderCalled = false;
    registerView("custom", {
      template: "base",
      async render(ctx) {
        viewRenderCalled = true;
        return { title: "Custom", content: ctx.view };
      },
    });

    const out = await renderWebSurface({
      view:   "custom",
      params: { id: "xyz" },
      mode:   V.Mode.json,
    });
    expect(viewRenderCalled).toBe(false);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "custom", params: { id: "xyz" } });
  });

  test("JSON mode params fall back to empty object", async () => {
    const out = await renderWebSurface({
      view: "no-params",
      mode: V.Mode.json,
    });
    expect((out.body as Record<string, unknown>).params).toEqual({});
  });
});


// ---------------------------------------------------------------------------
// 3. HTML mode + unknown view → defaultRenderer (template-based)
// ---------------------------------------------------------------------------
describe("renderWebSurface — HTML mode fallback to defaultRenderer", () => {
  test("HTML mode + unknown view → 200 + HTML via base template", async () => {
    const out = await renderWebSurface({
      view:   "unregistered-view",
      mode:   V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    expect(typeof out.body).toBe("string");
    const html = out.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<h1>unregistered-view</h1>");
  });
});


// ---------------------------------------------------------------------------
// 4. HTML mode + registered view → template-bound render
// ---------------------------------------------------------------------------
describe("renderWebSurface — HTML mode template binding", () => {
  test("registered view's render() is called and vars substitute into the template", async () => {
    registerView("custom", {
      template: "base",
      async render() {
        return {
          title:   "Custom Title",
          content: "custom content body",
        };
      },
    });

    const out = await renderWebSurface({
      view: "custom",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = out.body as string;
    expect(html).toContain("<title>Custom Title</title>");
    expect(html).toContain("<h1>Custom Title</h1>");
    expect(html).toContain("custom content body");
  });

  test("render() may be async (awaited)", async () => {
    registerView("async-view", {
      template: "base",
      async render() {
        await new Promise((r) => setTimeout(r, 1));
        return { title: "Async", content: "ok" };
      },
    });

    const out = await renderWebSurface({
      view: "async-view",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.body as string).toContain("<h1>Async</h1>");
  });

  test("re-registering the same name overrides the previous definition", async () => {
    registerView("rename", {
      template: "base",
      async render() { return { title: "first", content: "" }; },
    });
    registerView("rename", {
      template: "base",
      async render() { return { title: "second", content: "" }; },
    });
    const out = await renderWebSurface({
      view: "rename", mode: V.Mode.html,
    });
    expect(out.body as string).toContain("<h1>second</h1>");
  });

  test("view + ctx are passed through to render()", async () => {
    let receivedCtx: V.RenderContext | null = null;
    registerView("pass-through", {
      template: "base",
      async render(ctx) {
        receivedCtx = ctx;
        return { title: "x", content: "y" };
      },
    });

    await renderWebSurface({
      view:   "pass-through",
      params: { a: "1" },
      mode:   V.Mode.html,
    });
    expect(receivedCtx).not.toBeNull();
    expect(receivedCtx!.view).toBe("pass-through");
    expect(receivedCtx!.params).toEqual({ a: "1" });
    expect(receivedCtx!.mode).toBe(V.Mode.html);
  });
});


// ---------------------------------------------------------------------------
// 5. Purity
// ---------------------------------------------------------------------------
describe("renderWebSurface — purity", () => {
  test("does not mutate the input RenderContext (fallback path)", async () => {
    const ctx: RenderContext = {
      view:   "no-mutate",
      params: { id: "abc", count: 3 },
      mode:   V.Mode.json,
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("two calls with the same ctx produce equivalent outputs (fallback path)", async () => {
    const ctx: RenderContext = {
      view: "same", params: { a: 1 }, mode: V.Mode.json,
    };
    const a = await renderWebSurface(ctx);
    const b = await renderWebSurface(ctx);
    expect(a).toEqual(b);
  });

  test("module re-import is idempotent", async () => {
    const first = await import("../renderer");
    const second = await import("../renderer");
    expect(first).toBe(second);
  });
});
