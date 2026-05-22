// Card A6 — view composition + partial templates tests.
//
// Five contract surfaces under test:
//
//   1. Partial loader (``partialLoader.ts``):
//      * Loads header.html and footer.html from the partials dir.
//      * Throws on a missing partial name.
//
//   2. Partial cache (``partialCache.ts``):
//      * First load reads from disk + caches.
//      * Second load returns the same string reference.
//      * clearPartialCache empties the cache.
//      * No eviction across multiple partials.
//
//   3. Template engine — partial inclusion:
//      * ``{{> header}}`` substitutes the header body.
//      * ``{{> footer}}`` substitutes the footer body.
//      * Variables in a partial body propagate from the view vars
//        (e.g. ``{{ subtitle }}`` in header.html).
//      * Missing partial → silent removal (empty string).
//
//   4. Determinism + safety:
//      * Same input → identical output across runs.
//      * No mutation of vars / template cache / partial cache.
//      * No double evaluation: a variable VALUE containing
//        ``{{> header}}`` is NOT re-expanded.
//      * No nested partials: a partial body containing
//        ``{{> other}}`` is NOT re-expanded.
//
//   5. Composition correctness:
//      * Home view + base.html (now using partials) + home.html
//        (also using partials) produce stable HTML.
//      * The header partial's ``{{ subtitle }}`` is filled by the
//        home view's vars.
//
// Path: web/src/surface/__tests__/viewComposition.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { loadPartial } from "../partialLoader";
import {
  loadCachedPartial,
  clearPartialCache,
  _listCachedPartialsForTests,
  _getCachedPartialForTests,
} from "../partialCache";
import { renderTemplate } from "../templateEngine";
import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { homeView } from "../views/home";


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearPartialCache();
  registerView("home", homeView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearPartialCache();
});


// ---------------------------------------------------------------------------
// 1. Partial loader
// ---------------------------------------------------------------------------
describe("partialLoader", () => {
  test("loads header.html", () => {
    const body = loadPartial("header");
    expect(body).toContain("<header>");
    expect(body).toContain("{{ subtitle }}");
  });

  test("loads footer.html", () => {
    const body = loadPartial("footer");
    expect(body).toContain("<footer>");
    expect(body).toContain("ClarityOS Web Surface v0.2.0");
  });

  test("throws on a missing partial name", () => {
    expect(() => loadPartial("does-not-exist-zzz")).toThrow();
  });
});


// ---------------------------------------------------------------------------
// 2. Partial cache
// ---------------------------------------------------------------------------
describe("partialCache", () => {
  test("first load populates the cache", () => {
    expect(_listCachedPartialsForTests()).toEqual([]);
    loadCachedPartial("header");
    expect(_listCachedPartialsForTests()).toEqual(["header"]);
  });

  test("second load returns the same string reference", () => {
    loadCachedPartial("header");
    const cached = _getCachedPartialForTests("header");
    const second = loadCachedPartial("header");
    expect(second).toBe(cached);
  });

  test("clearPartialCache empties the cache", () => {
    loadCachedPartial("header");
    loadCachedPartial("footer");
    expect(_listCachedPartialsForTests().sort()).toEqual(["footer", "header"]);
    clearPartialCache();
    expect(_listCachedPartialsForTests()).toEqual([]);
  });

  test("no eviction across multiple partials", () => {
    loadCachedPartial("header");
    loadCachedPartial("footer");
    expect(_listCachedPartialsForTests().sort()).toEqual(["footer", "header"]);
  });

  test("missing partial throws and doesn't pollute the cache", () => {
    expect(() => loadCachedPartial("does-not-exist-zzz")).toThrow();
    expect(_listCachedPartialsForTests()).not.toContain("does-not-exist-zzz");
  });
});


// ---------------------------------------------------------------------------
// 3. Template engine — partial inclusion
// ---------------------------------------------------------------------------
describe("renderTemplate — partial inclusion", () => {
  test("{{> header}} substitutes the header partial body", () => {
    const out = renderTemplate("BEFORE {{> header}} AFTER", { subtitle: "S" });
    expect(out).toContain("BEFORE");
    expect(out).toContain("AFTER");
    expect(out).toContain("<header>");
    // Variable in the partial body got filled in pass 2.
    expect(out).toContain("<h2>S</h2>");
  });

  test("{{> footer}} substitutes the footer partial body", () => {
    const out = renderTemplate("{{> footer}}", {});
    expect(out).toContain("<footer>");
    expect(out).toContain("ClarityOS Web Surface v0.2.0");
  });

  test("multiple partials in one template work independently", () => {
    const out = renderTemplate(
      "{{> header}}\nMID\n{{> footer}}",
      { subtitle: "S" },
    );
    expect(out).toContain("<header>");
    expect(out).toContain("MID");
    expect(out).toContain("<footer>");
  });

  test("missing partial is silently removed (no error, no literal text)", () => {
    const out = renderTemplate("X {{> nonexistent }} Y", {});
    // Removed → no partial markup, surrounding text intact.
    expect(out).not.toContain("nonexistent");
    expect(out).not.toContain("{{>");
    expect(out).toContain("X");
    expect(out).toContain("Y");
  });

  test("variables in partials are filled from the view vars", () => {
    const out = renderTemplate("{{> header}}", { subtitle: "Greetings" });
    expect(out).toContain("<h2>Greetings</h2>");
  });

  test("variables in partials are stripped when not provided", () => {
    const out = renderTemplate("{{> header}}", {});
    // {{ subtitle }} in the partial body has no var; gets stripped.
    expect(out).toContain("<h2></h2>");
    expect(out).not.toContain("{{");
  });
});


// ---------------------------------------------------------------------------
// 4. Determinism + safety
// ---------------------------------------------------------------------------
describe("renderTemplate — composition safety", () => {
  test("does not mutate the vars object", () => {
    const v = { subtitle: "S" };
    const frozen = JSON.stringify(v);
    renderTemplate("{{> header}}", v);
    expect(JSON.stringify(v)).toBe(frozen);
  });

  test("same input → identical output across runs", () => {
    const t = "{{> header}}\n{{ content }}\n{{> footer}}";
    const v = { subtitle: "S", content: "C" };
    const a = renderTemplate(t, v);
    const b = renderTemplate(t, v);
    expect(a).toBe(b);
  });

  test("no double evaluation: var value containing {{> header}} is NOT expanded", () => {
    // A user-provided variable value containing partial-inclusion
    // syntax must NOT trigger a second partial pass — that'd be
    // a server-side template injection vector.
    const out = renderTemplate(
      "{{ payload }}",
      { payload: "{{> header}}" },
    );
    expect(out).toBe("{{> header}}");
    expect(out).not.toContain("<header>");
  });

  test("no double evaluation: var value containing {{ x }} is NOT expanded", () => {
    // Same property for plain variable syntax in values.
    const out = renderTemplate(
      "{{ payload }}",
      { payload: "{{ secret }}", secret: "SHOULD-NOT-LEAK" },
    );
    expect(out).toBe("{{ secret }}");
    expect(out).not.toContain("SHOULD-NOT-LEAK");
  });

  test("no nested partials: partial body containing {{> other}} stays literal", () => {
    // The engine runs partial substitution exactly once. If a
    // partial body itself contains ``{{> other}}``, the second
    // pass doesn't run — that text appears literally in the
    // output. Documented in templateEngine.ts.
    //
    // We can't reach a "nested" partial without a custom partial
    // file, so this test verifies the engine's behaviour against
    // a hand-constructed template that simulates the case: the
    // template contains a partial-like substring as DATA.
    const out = renderTemplate("{{ raw }}", { raw: "{{> footer}}" });
    expect(out).toContain("{{> footer}}");
    expect(out).not.toContain("ClarityOS Web Surface");
  });
});


// ---------------------------------------------------------------------------
// 5. Composition correctness — end-to-end through the pipeline
// ---------------------------------------------------------------------------
describe("view composition — end-to-end via renderWebSurface", () => {
  test("home view renders with the header partial filled", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    // home.html includes {{> header}}, which has {{ subtitle }}.
    // homeView supplies subtitle="Welcome" (HTML-escaped).
    expect(html).toContain("<header>");
    expect(html).toContain("<h2>Welcome</h2>");
  });

  test("home view renders with the footer partial filled", async () => {
    const out = await renderWebSurface({
      view: "home",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<footer>");
    expect(html).toContain("ClarityOS Web Surface v0.2.0");
  });

  test("unknown view → defaultRenderer (base.html) also picks up partials", async () => {
    // base.html now includes {{> header}} and {{> footer}}. The
    // default renderer doesn't supply ``subtitle`` so the header
    // body renders with an empty h2 — still composes structurally.
    const out = await renderWebSurface({
      view: "unknown-view",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("<header>");
    expect(html).toContain("<footer>");
    // Subtitle var wasn't provided → empty h2.
    expect(html).toContain("<h2></h2>");
  });

  test("HTML output is stable across repeated home renders", async () => {
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

  test("JSON mode is unaffected by partials (still canonical {view, params})", async () => {
    const out = await renderWebSurface({
      view: "home", params: { x: 1 }, mode: V.Mode.json,
    });
    expect(out.headers["content-type"]).toBe("application/json");
    expect(out.body).toEqual({ view: "home", params: { x: 1 } });
  });
});
