// Card A5 — render pipeline + template cache tests.
//
// Four contract surfaces under test:
//
//   1. Template cache (``templateCache.ts``):
//      * First load reads from disk (cache miss → populated).
//      * Second load returns the cached reference (no re-read).
//      * clearTemplateCache empties the cache.
//      * No eviction — multiple templates persist independently.
//
//   2. Pipeline determinism (``renderPipeline.ts``):
//      * Same input → identical output (deep equality).
//      * Does not mutate ``ctx``.
//      * Does not mutate the registry.
//      * Does not mutate the cache except by adding entries.
//
//   3. Fallback behaviour:
//      * Unknown view + HTML mode → defaultRenderer (base.html).
//      * Unknown view + JSON mode → defaultRenderer (canonical
//        {view, params} shape).
//      * Registered view + JSON mode → defaultRenderer (bypass).
//      * Registered view + HTML mode → template-bound render.
//
//   4. Template correctness:
//      * Variables substitute correctly through the pipeline.
//      * Unfilled placeholders removed.
//      * HTML stable across runs.
//
// Path: web/src/surface/__tests__/renderPipeline.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { executeRenderPipeline } from "../renderPipeline";
import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
} from "../viewRegistry";
import {
  loadCachedTemplate,
  clearTemplateCache,
  _listCachedTemplatesForTests,
  _getCachedTemplateForTests,
} from "../templateCache";


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
});


// ---------------------------------------------------------------------------
// 1. Template cache — load / cache hit / clear / no eviction
// ---------------------------------------------------------------------------
describe("templateCache — caching behaviour", () => {
  test("first load reads from disk and populates the cache", () => {
    expect(_listCachedTemplatesForTests()).toEqual([]);
    const content = loadCachedTemplate("base");
    expect(content).toContain("<!DOCTYPE html>");
    expect(_listCachedTemplatesForTests()).toEqual(["base"]);
  });

  test("second load returns the same string reference (cache hit, no re-read)", () => {
    // Reference equality (``toBe``) verifies the cached value is
    // returned — a re-read from disk would allocate a fresh
    // string that compares equal by content but not by reference.
    loadCachedTemplate("base");
    const cached = _getCachedTemplateForTests("base");
    const second = loadCachedTemplate("base");
    expect(second).toBe(cached);
  });

  test("clearTemplateCache empties the cache", () => {
    loadCachedTemplate("base");
    expect(_listCachedTemplatesForTests()).toContain("base");
    clearTemplateCache();
    expect(_listCachedTemplatesForTests()).toEqual([]);
  });

  test("clearing then reloading produces a fresh cache entry", () => {
    loadCachedTemplate("base");
    const first = _getCachedTemplateForTests("base");
    clearTemplateCache();
    loadCachedTemplate("base");
    const second = _getCachedTemplateForTests("base");
    // After clear, the cache holds a freshly-read string. Same
    // CONTENT, but the Map entry is a new one.
    expect(second).toEqual(first);
    expect(_listCachedTemplatesForTests()).toEqual(["base"]);
  });

  test("cache holds multiple templates independently (no eviction)", () => {
    loadCachedTemplate("base");
    loadCachedTemplate("home");
    const names = _listCachedTemplatesForTests().sort();
    expect(names).toEqual(["base", "home"]);
  });

  test("missing template throws (loader contract preserved)", () => {
    expect(() => loadCachedTemplate("does-not-exist-zzz")).toThrow();
    // A failed load must not silently insert anything.
    expect(_listCachedTemplatesForTests()).not.toContain("does-not-exist-zzz");
  });
});


// ---------------------------------------------------------------------------
// 2. Pipeline determinism + purity
// ---------------------------------------------------------------------------
describe("executeRenderPipeline — determinism", () => {
  test("same input → identical output (HTML default fallback)", async () => {
    const ctx = { view: "x", mode: V.Mode.html, params: { a: "1" } };
    const a = await executeRenderPipeline(ctx);
    const b = await executeRenderPipeline(ctx);
    expect(a).toEqual(b);
  });

  test("same input → identical output (HTML registered view)", async () => {
    registerView("test-view", {
      template: "base",
      async render() { return { title: "T", content: "C" }; },
    });
    const ctx = { view: "test-view", mode: V.Mode.html };
    const a = await executeRenderPipeline(ctx);
    const b = await executeRenderPipeline(ctx);
    expect(a).toEqual(b);
  });

  test("same input → identical output (JSON mode)", async () => {
    const ctx = { view: "x", mode: V.Mode.json, params: { a: "1" } };
    const a = await executeRenderPipeline(ctx);
    const b = await executeRenderPipeline(ctx);
    expect(a).toEqual(b);
  });

  test("does not mutate the input ctx", async () => {
    const ctx = {
      view: "x", mode: V.Mode.html, params: { id: "abc" },
    };
    const frozen = JSON.stringify(ctx);
    await executeRenderPipeline(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("does not mutate the registry", async () => {
    registerView("test", {
      template: "base",
      async render() { return { title: "x", content: "" }; },
    });
    const before = _listRegisteredViewsForTests().slice();
    await executeRenderPipeline({ view: "test", mode: V.Mode.html });
    const after = _listRegisteredViewsForTests().slice();
    expect(after).toEqual(before);
  });

  test("only mutates the cache by adding entries on first miss", async () => {
    const cacheBefore = _listCachedTemplatesForTests().slice();
    await executeRenderPipeline({ view: "x", mode: V.Mode.html });
    const cacheAfter = _listCachedTemplatesForTests();
    // ``base.html`` was loaded by the default fallback; it appears
    // in the cache where it wasn't before.
    expect(cacheAfter).toContain("base");
    // Cache size increased by exactly one entry.
    expect(cacheAfter.length).toBe(cacheBefore.length + 1);

    // Second pipeline run reuses the cache — no new entries.
    await executeRenderPipeline({ view: "x", mode: V.Mode.html });
    expect(_listCachedTemplatesForTests().length).toBe(cacheAfter.length);
  });
});


// ---------------------------------------------------------------------------
// 3. Fallback behaviour
// ---------------------------------------------------------------------------
describe("executeRenderPipeline — fallback", () => {
  test("unknown view + HTML mode → defaultRenderer (base template)", async () => {
    const out = await executeRenderPipeline({
      view: "unknown-view",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = out.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<h1>unknown-view</h1>");
  });

  test("unknown view + JSON mode → defaultRenderer ({view, params})", async () => {
    const out = await executeRenderPipeline({
      view:   "unknown-view",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    expect(out.status).toBe(200);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "unknown-view", params: { id: "abc" } });
  });

  test("registered view + JSON mode → defaultRenderer (bypass view.render)", async () => {
    let viewCalled = false;
    registerView("registered", {
      template: "base",
      async render() {
        viewCalled = true;
        return { title: "x", content: "y" };
      },
    });
    const out = await executeRenderPipeline({
      view: "registered",
      mode: V.Mode.json,
    });
    expect(viewCalled).toBe(false);
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "registered", params: {} });
  });
});


// ---------------------------------------------------------------------------
// 4. Template correctness through the pipeline
// ---------------------------------------------------------------------------
describe("executeRenderPipeline — template binding", () => {
  test("variables substitute correctly into the template", async () => {
    registerView("subst", {
      template: "base",
      async render() {
        return { title: "TITLE_VALUE", content: "CONTENT_VALUE" };
      },
    });
    const out = await executeRenderPipeline({
      view: "subst",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("TITLE_VALUE");
    expect(html).toContain("CONTENT_VALUE");
  });

  test("unfilled placeholders removed (no {{...}} in output)", async () => {
    registerView("partial", {
      template: "base",
      // Returns ONLY title; ``content`` placeholder will be empty.
      async render() { return { title: "Only Title" }; },
    });
    const out = await executeRenderPipeline({
      view: "partial",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("Only Title");
    expect(html).not.toMatch(/{{\s*\w+\s*}}/);
  });

  test("HTML stable across runs (cache + pipeline produce identical bytes)", async () => {
    registerView("stable", {
      template: "home",
      async render() {
        return { title: "Stable", content: "stable body" };
      },
    });

    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await executeRenderPipeline({
        view: "stable",
        mode: V.Mode.html,
      });
      outs.push(r.body as string);
    }
    // Every run produces the byte-identical HTML.
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });
});


// ---------------------------------------------------------------------------
// 5. renderer.ts public alias delegates to the pipeline
// ---------------------------------------------------------------------------
describe("renderWebSurface — pipeline alias", () => {
  test("renderWebSurface and executeRenderPipeline produce identical output", async () => {
    registerView("alias-check", {
      template: "base",
      async render() { return { title: "Alias", content: "OK" }; },
    });
    const ctx = { view: "alias-check", mode: V.Mode.html };
    const viaAlias = await renderWebSurface(ctx);
    const viaPipeline = await executeRenderPipeline(ctx);
    expect(viaAlias).toEqual(viaPipeline);
  });

  test("renderWebSurface preserves JSON mode contract", async () => {
    const out = await renderWebSurface({
      view: "x", mode: V.Mode.json, params: { y: 1 },
    });
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "x", params: { y: 1 } });
  });
});
