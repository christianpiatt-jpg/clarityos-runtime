// Card A7 — layout system tests (base → layout → view composition).
//
// Five contract surfaces under test:
//
//   1. Layout loader (``layoutLoader.ts``):
//      * Loads standard.html from the layouts directory.
//      * Throws on a missing layout.
//
//   2. Layout cache (``layoutCache.ts``):
//      * First load reads from disk + caches.
//      * Second load returns the same string reference.
//      * clearLayoutCache empties the cache.
//      * No eviction across multiple layouts.
//
//   3. Pipeline layout wrapping:
//      * View template renders first.
//      * Layout wraps view HTML via ``{{ yield }}``.
//      * Layout has access to the view's vars (title, subtitle…).
//      * View WITHOUT a layout renders unwrapped.
//
//   4. Partial + layout interaction:
//      * Partials inside layouts render correctly.
//      * Partials inside views render correctly (when no layout).
//      * View vars propagate into layout-included partials.
//
//   5. Determinism + safety:
//      * Same input → identical output.
//      * Pipeline does not mutate view vars (layout substitution
//        builds a fresh context, doesn't mutate in place).
//      * Pipeline does not double-evaluate ``yield`` content
//        (HTML inside yield isn't re-scanned for template syntax).
//
// Path: web/src/surface/__tests__/layoutEngine.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { loadLayout } from "../layoutLoader";
import {
  loadCachedLayout,
  clearLayoutCache,
  _listCachedLayoutsForTests,
  _getCachedLayoutForTests,
} from "../layoutCache";
import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearPartialCache } from "../partialCache";
import { homeView } from "../views/home";


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearPartialCache();
  clearLayoutCache();
  registerView("home", homeView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearPartialCache();
  clearLayoutCache();
});


// ---------------------------------------------------------------------------
// 1. Layout loader
// ---------------------------------------------------------------------------
describe("layoutLoader", () => {
  test("loads standard.html", () => {
    const body = loadLayout("standard");
    expect(body).toContain("<!DOCTYPE html>");
    expect(body).toContain("{{ yield }}");
  });

  test("standard layout includes header + footer partials", () => {
    const body = loadLayout("standard");
    expect(body).toContain("{{> header}}");
    expect(body).toContain("{{> footer}}");
  });

  test("throws on a missing layout name", () => {
    expect(() => loadLayout("does-not-exist-zzz")).toThrow();
  });
});


// ---------------------------------------------------------------------------
// 2. Layout cache
// ---------------------------------------------------------------------------
describe("layoutCache", () => {
  test("first load populates the cache", () => {
    expect(_listCachedLayoutsForTests()).toEqual([]);
    loadCachedLayout("standard");
    expect(_listCachedLayoutsForTests()).toEqual(["standard"]);
  });

  test("second load returns the same string reference", () => {
    loadCachedLayout("standard");
    const cached = _getCachedLayoutForTests("standard");
    const second = loadCachedLayout("standard");
    expect(second).toBe(cached);
  });

  test("clearLayoutCache empties the cache", () => {
    loadCachedLayout("standard");
    expect(_listCachedLayoutsForTests()).toContain("standard");
    clearLayoutCache();
    expect(_listCachedLayoutsForTests()).toEqual([]);
  });

  test("missing layout throws and doesn't pollute the cache", () => {
    expect(() => loadCachedLayout("does-not-exist-zzz")).toThrow();
    expect(_listCachedLayoutsForTests()).not.toContain("does-not-exist-zzz");
  });
});


// ---------------------------------------------------------------------------
// 3. Pipeline layout wrapping
// ---------------------------------------------------------------------------
describe("pipeline — layout wrapping", () => {
  test("home view renders inside the standard layout", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // Layout owns the document chrome.
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
    // View body is inside the layout's yield slot.
    expect(html).toContain("<h1>Home</h1>");
    expect(html).toContain("Welcome to the Web Surface v0.2.0");
  });

  test("layout's <title> is filled from the view's title var", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<title>Home</title>");
  });

  test("view content nests inside the layout's yield slot (correct ordering)", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // The yield-wrapped view body sits between the opening div and
    // the closing div. Confirm via index ordering.
    const layoutOpenIdx = html.indexOf('<div id="layout">');
    const viewBodyIdx = html.indexOf("<h1>Home</h1>");
    const layoutCloseIdx = html.indexOf("</div>", layoutOpenIdx);
    expect(layoutOpenIdx).toBeGreaterThan(-1);
    expect(viewBodyIdx).toBeGreaterThan(layoutOpenIdx);
    expect(layoutCloseIdx).toBeGreaterThan(viewBodyIdx);
  });

  test("view WITHOUT a layout renders unwrapped (template-only)", async () => {
    registerView("standalone", {
      template: "base",  // base.html — no layout
      async render() {
        return { title: "Standalone", content: "no wrapper" };
      },
    });
    const out = await renderWebSurface({
      view: "standalone",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // base.html is a full document; no layout means no
    // <div id="layout"> wrapper.
    expect(html).toContain("<title>Standalone</title>");
    expect(html).toContain("<h1>Standalone</h1>");
    expect(html).not.toContain('<div id="layout">');
  });

  test("view with custom layout (registered + cached) renders correctly", async () => {
    // Custom views can opt into the same standard layout.
    registerView("custom-with-layout", {
      template: "base",
      layout:   "standard",
      async render() {
        return { title: "Custom", subtitle: "Sub", content: "x" };
      },
    });
    const out = await renderWebSurface({
      view: "custom-with-layout",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // Standard layout wraps base.html's full document output.
    expect(html).toContain('<div id="layout">');
    expect(html).toContain("<title>Custom</title>");
    // The header partial inside the layout fills with subtitle="Sub".
    expect(html).toContain("<h2>Sub</h2>");
  });
});


// ---------------------------------------------------------------------------
// 4. Partial + layout interaction
// ---------------------------------------------------------------------------
describe("partial + layout interaction", () => {
  test("standard layout's header partial fills with view's subtitle", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // home view supplies subtitle="Welcome"; standard layout
    // includes {{> header}} which contains {{ subtitle }}.
    expect(html).toContain("<header>");
    expect(html).toContain("<h2>Welcome</h2>");
  });

  test("standard layout's footer partial renders", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<footer>");
    expect(html).toContain("ClarityOS Web Surface v0.2.0");
  });

  test("partials in a view template still render (no layout)", async () => {
    // base.html includes {{> header}} {{> footer}} directly — when
    // used without a layout, partials still substitute through the
    // template-engine pass 1.
    registerView("base-direct", {
      template: "base",
      async render() {
        return { title: "T", subtitle: "Sub", content: "C" };
      },
    });
    const out = await renderWebSurface({
      view: "base-direct",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<header>");
    expect(html).toContain("<h2>Sub</h2>");
    expect(html).toContain("<footer>");
  });
});


// ---------------------------------------------------------------------------
// 5. Determinism + safety
// ---------------------------------------------------------------------------
describe("layout — determinism + safety", () => {
  test("same request → byte-identical HTML across runs", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await renderWebSurface({
        view: "home", mode: V.Mode.html,
      });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("pipeline does not mutate the view's returned vars", async () => {
    // Verify by capturing the vars object reference inside render()
    // and comparing before/after the pipeline runs.
    let capturedVars: Record<string, unknown> | null = null;
    registerView("vars-check", {
      template: "base",
      layout:   "standard",
      async render() {
        capturedVars = { title: "T", subtitle: "S", content: "C" };
        return capturedVars;
      },
    });
    await renderWebSurface({
      view: "vars-check",
      mode: V.Mode.html,
    });
    // The pipeline adds ``yield`` to a SPREAD copy for the layout
    // call — the original vars object must not gain a yield key.
    expect(capturedVars).not.toBeNull();
    expect("yield" in capturedVars!).toBe(false);
    // Original keys still present.
    expect(Object.keys(capturedVars!).sort()).toEqual(
      ["content", "subtitle", "title"],
    );
  });

  test("yield content is not re-scanned (no double evaluation)", async () => {
    // If a view's rendered HTML happens to contain template-engine
    // syntax (e.g. literal "{{ title }}" text), it must NOT be
    // re-evaluated when the layout substitutes ``{{ yield }}``.
    // The single-pass engine (Card A6 fix) guarantees this.
    registerView("yield-payload", {
      template: "base",
      layout:   "standard",
      async render() {
        return {
          title:    "Real Title",
          subtitle: "S",
          content:  "{{ title }} should appear literally",
        };
      },
    });
    const out = await renderWebSurface({
      view: "yield-payload",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // The literal "{{ title }}" string in the content survives
    // BOTH the view-template pass AND the layout pass.
    expect(html).toContain("{{ title }} should appear literally");
    // The real ``Real Title`` value DOES appear (as the layout
    // <title> + view <h1>), but the literal {{ title }} in
    // content is preserved.
  });

  test("layout caches additively (one entry per used layout)", async () => {
    expect(_listCachedLayoutsForTests()).toEqual([]);
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    expect(_listCachedLayoutsForTests()).toEqual(["standard"]);
    // Second render reuses the cached layout.
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    expect(_listCachedLayoutsForTests()).toEqual(["standard"]);
  });
});


// ---------------------------------------------------------------------------
// 6. Fallback behaviour — JSON mode + unknown view
// ---------------------------------------------------------------------------
describe("layout — fallback behaviour", () => {
  test("JSON mode bypasses the layout (canonical {view, params})", async () => {
    const out = await renderWebSurface({
      view:   "home",
      params: { id: "abc" },
      mode:   V.Mode.json,
    });
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "home", params: { id: "abc" } });
    // No layout cache entry was added in JSON mode.
    expect(_listCachedLayoutsForTests()).toEqual([]);
  });

  test("unknown view does not trigger layout loading", async () => {
    const out = await renderWebSurface({
      view: "definitely-unknown",
      mode: V.Mode.html,
    });
    expect(out.status).toBe(200);
    expect(_listCachedLayoutsForTests()).toEqual([]);
    // Default renderer's base.html is what produced this.
    const html = out.body as string;
    expect(html).toContain("<h1>definitely-unknown</h1>");
    expect(html).not.toContain('<div id="layout">');
  });
});
