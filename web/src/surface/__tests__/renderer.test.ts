// Tests for the v0.2.0 Web Surface render dispatcher.
//
// Card 9 introduced the renderer as a 501 stub. Card A1 promoted it
// to a real dispatcher that routes through the view registry +
// default renderer. This file's assertions reflect the Card A1
// behaviour:
//
//   1. The renderer accepts a ``WebSurfaceV0_2_View.RenderContext``
//      and returns a ``RenderOutput`` whose shape is structurally
//      compatible with ``WebSurfaceV0_2.Response``.
//   2. Without a registered view, the request falls through to
//      ``defaultRenderer`` — 200 + JSON or HTML body keyed on
//      ``ctx.mode``.
//   3. With a registered view, ``getView`` resolves and the
//      registered renderer is called instead of the default.
//   4. The renderer is side-effect-free for any given input.
//
// The full view-engine test surface lives in
// ``viewEngine.test.ts`` next door; this file pins the renderer
// dispatcher's contract specifically.
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
// 2. Falls through to defaultRenderer when no view is registered
// ---------------------------------------------------------------------------
describe("renderWebSurface — default fallback", () => {
  test("unknown view + json mode → 200 + JSON body via defaultRenderer", async () => {
    const out = await renderWebSurface({
      view:   "unregistered-view",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({
      view:   "unregistered-view",
      params: { id: "abc" },
    });
  });

  test("unknown view + html mode → 200 + HTML body via defaultRenderer", async () => {
    const out = await renderWebSurface({
      view:   "unregistered-view",
      mode:   V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    expect(typeof out.body).toBe("string");
    expect(out.body as string).toContain("unregistered-view");
  });

  test("missing params fall back to empty object", async () => {
    const out = await renderWebSurface({
      view: "no-params",
      mode: V.Mode.json,
    });
    expect((out.body as Record<string, unknown>).params).toEqual({});
  });
});


// ---------------------------------------------------------------------------
// 3. Registered view overrides the default
// ---------------------------------------------------------------------------
describe("renderWebSurface — registered view dispatch", () => {
  test("registered view's renderer is called instead of defaultRenderer", async () => {
    registerView("custom", async (ctx) => ({
      status:  201,
      headers: { "x-custom": "yes" },
      body:    { customMarker: "hit", echoView: ctx.view },
    }));

    const out = await renderWebSurface({
      view: "custom",
      mode: V.Mode.json,
    });
    expect(out.status).toBe(201);
    expect(out.headers["x-custom"]).toBe("yes");
    expect((out.body as Record<string, unknown>).customMarker).toBe("hit");
    expect((out.body as Record<string, unknown>).echoView).toBe("custom");
  });

  test("renderer is awaited (async function is supported)", async () => {
    registerView("async-view", async (ctx) => {
      await new Promise((r) => setTimeout(r, 1));
      return {
        status:  202,
        headers: {},
        body:    { view: ctx.view },
      };
    });

    const out = await renderWebSurface({
      view: "async-view",
      mode: V.Mode.json,
    });
    expect(out.status).toBe(202);
  });

  test("re-registering the same name overrides the previous renderer", async () => {
    registerView("rename", async () => ({
      status: 100, headers: {}, body: { v: 1 },
    }));
    registerView("rename", async () => ({
      status: 200, headers: {}, body: { v: 2 },
    }));
    const out = await renderWebSurface({
      view: "rename", mode: V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect((out.body as Record<string, unknown>).v).toBe(2);
  });
});


// ---------------------------------------------------------------------------
// 4. Purity
// ---------------------------------------------------------------------------
describe("renderWebSurface — purity for the default-fallback path", () => {
  test("does not mutate the input RenderContext", async () => {
    const ctx: RenderContext = {
      view:   "no-mutate",
      params: { id: "abc", count: 3 },
      mode:   V.Mode.json,
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("two calls with the same ctx produce equivalent outputs", async () => {
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
