// Card 9 — tests for the v0.2.0 Web Surface render pipeline skeleton.
//
// The renderer is a pure stub today. These tests lock:
//
//   1. ``renderWebSurface(ctx)`` resolves to a 501 Response.
//   2. The Response shape conforms to ``WebSurfaceV0_2.Response``
//      (status, headers, body) and the body conforms to
//      ``WebSurfaceV0_2.ErrorEnvelope`` (top-level keys = error +
//      detail; nothing else).
//   3. The renderer is side-effect-free (no mutation of the input
//      RenderContext; idempotent re-import).
//
// When real rendering replaces the stub, assertions 1-2 will need
// to expand (per-view status, per-view body schema) but 3 must
// continue to hold.
//
// Path: web/src/surface/__tests__/renderer.test.ts
import { describe, expect, test } from "vitest";

import { renderWebSurface, RenderContext } from "../renderer";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";


// ---------------------------------------------------------------------------
// 1. Renderer returns the 501 stub
// ---------------------------------------------------------------------------
describe("renderWebSurface — v0.2.0 stub behaviour", () => {
  test("returns a Response with status 501", async () => {
    const res = await renderWebSurface({ view: "any" });
    expect(res.status).toBe(501);
  });

  test("sets content-type: application/json", async () => {
    const res = await renderWebSurface({ view: "x" });
    expect(res.headers["content-type"]).toBe("application/json");
  });

  test("body carries the documented error code", async () => {
    const res = await renderWebSurface({ view: "dashboard" });
    const body = res.body as WebSurfaceV0_2.ErrorEnvelope;
    expect(body.error).toBe("web_surface_renderer_not_implemented");
  });

  test("body.detail echoes the requested view", async () => {
    const res = await renderWebSurface({ view: "operator" });
    const body = res.body as WebSurfaceV0_2.ErrorEnvelope;
    expect((body.detail as any).view).toBe("operator");
  });

  test("body.detail.param_count is set when params is present", async () => {
    const res = await renderWebSurface({
      view:   "with-params",
      params: { id: "abc", verbose: true, depth: 2 },
    });
    const body = res.body as WebSurfaceV0_2.ErrorEnvelope;
    expect((body.detail as any).param_count).toBe(3);
  });

  test("body.detail.param_count is absent when params is undefined", async () => {
    const res = await renderWebSurface({ view: "no-params" });
    const body = res.body as WebSurfaceV0_2.ErrorEnvelope;
    expect((body.detail as any).param_count).toBeUndefined();
  });
});


// ---------------------------------------------------------------------------
// 2. Response + body shape conformance with the v0.2.0 contract
// ---------------------------------------------------------------------------
describe("renderWebSurface — contract shape conformance", () => {
  test("Response top-level keys match WebSurfaceV0_2.Response", async () => {
    const res = await renderWebSurface({ view: "x" });
    expect(Object.keys(res).sort()).toEqual(
      ["body", "headers", "status"],
    );
  });

  test("Body top-level keys match WebSurfaceV0_2.ErrorEnvelope (error + detail only)", async () => {
    const res = await renderWebSurface({ view: "x" });
    const body = res.body as Record<string, unknown>;
    // The envelope forbids additional properties on the wire; the
    // renderer must not slip extra top-level fields in. Routing /
    // diagnostic context goes under ``detail`` instead.
    expect(Object.keys(body).sort()).toEqual(["detail", "error"]);
  });

  test("body carries the contract VERSION pin under detail", async () => {
    const res = await renderWebSurface({ view: "x" });
    const body = res.body as WebSurfaceV0_2.ErrorEnvelope;
    expect((body.detail as any).version).toBe(WebSurfaceV0_2.VERSION);
    expect((body.detail as any).version).toBe("v0.2.0");
  });

  test("Response body is JSON-serialisable", async () => {
    const res = await renderWebSurface({
      view:   "json-roundtrip",
      params: { k: "v" },
    });
    const round = JSON.parse(JSON.stringify(res.body));
    expect(round).toEqual(res.body);
  });
});


// ---------------------------------------------------------------------------
// 3. Purity / determinism / no side effects
// ---------------------------------------------------------------------------
describe("renderWebSurface — purity", () => {
  test("does not mutate the input RenderContext", async () => {
    const ctx: RenderContext = {
      view:   "no-mutate",
      params: { id: "abc", count: 3 },
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("two calls with the same ctx produce equivalent responses", async () => {
    const ctx: RenderContext = { view: "same", params: { a: 1 } };
    const a = await renderWebSurface(ctx);
    const b = await renderWebSurface(ctx);
    // Structural equality (the renderer always builds a fresh
    // response object, so referential identity is not asserted).
    expect(a).toEqual(b);
  });

  test("module re-import is idempotent (no side effects at import time)", async () => {
    const first = await import("../renderer");
    const second = await import("../renderer");
    expect(first).toBe(second);
  });
});
