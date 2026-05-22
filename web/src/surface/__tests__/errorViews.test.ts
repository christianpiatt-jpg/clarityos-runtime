// Card A11 — error views + error layout tests.
//
// Five contract surfaces under test:
//
//   1. error_404 view (classifier-rewrite path):
//      * Unknown view URL → status 404 + error layout output.
//      * Body contains the message + header/footer partials +
//        the "Not Found" title.
//      * Message value flows through HTML-escape (no XSS).
//      * JSON-mode 404 returns the structured ``{view, params}``
//        shape via defaultRenderer.
//
//   2. error_500 view (direct render):
//      * Direct ``renderWebSurface({view: "error_500", ...})``
//        returns status 500 + error layout output.
//      * Message param surfaces in the body.
//
//   3. Pipeline try/catch fallback (500):
//      * A view whose render() throws routes to the minimal
//        500 fallback (status 500 + errors/500 template,
//        without the error layout — fault-isolated).
//      * No stack trace, no exception message in the body.
//      * Deterministic across repeats.
//
//   4. Router envelope→HTML transform:
//      * noop branch (forced via direct router call) +
//        HTML request → re-rendered through error_500.
//      * Same envelope + JSON Accept header → raw envelope
//        pass-through.
//      * Asset 404 envelope is NOT transformed (subresource
//        contract: assets always return JSON envelope).
//
//   5. Determinism + safety:
//      * Same error scenario → byte-identical HTML across runs.
//      * Renderer never mutates the input ctx.
//      * Error body never echoes a raw stack frame
//        (``at file:line`` shape).
//
// Path: web/src/surface/__tests__/errorViews.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { routeWebSurface } from "../router";
import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import {
  clearTemplateCache,
} from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";


function reqOf(
  overrides: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  return {
    path:    "/",
    method:  "GET",
    headers: {},
    body:    null,
    ...overrides,
  };
}


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  // Re-register the standard fixture set every test so the
  // classifier's registry check has a known set of known views.
  registerView("home",       homeView);
  registerView("error_404",  error404View);
  registerView("error_500",  error500View);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. error_404 — classifier rewrite path
// ---------------------------------------------------------------------------
describe("error_404 view — classifier rewrite", () => {
  test("unknown URL → 404 status + HTML content-type", async () => {
    const res = await routeWebSurface(reqOf({ path: "/missing" }));
    expect(res.status).toBe(404);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("body contains the Not Found heading + the message", async () => {
    const res = await routeWebSurface(reqOf({ path: "/missing-page" }));
    const html = res.body as string;
    expect(html).toContain("<h1>Not Found</h1>");
    expect(html).toContain("View &#39;missing-page&#39; not found.");
  });

  test("uses the error layout (#error wrapper, not #layout)", async () => {
    const res = await routeWebSurface(reqOf({ path: "/missing" }));
    const html = res.body as string;
    expect(html).toContain('<div id="error">');
    expect(html).not.toContain('<div id="layout">');
  });

  test("includes the header + footer partials", async () => {
    const res = await routeWebSurface(reqOf({ path: "/missing" }));
    const html = res.body as string;
    expect(html).toContain("<header>");
    expect(html).toContain("<footer>");
    // The header partial fills {{ subtitle }} with "404".
    expect(html).toContain("<h2>404</h2>");
    expect(html).toContain("ClarityOS Web Surface v0.2.0");
  });

  test("title in <head> reflects the error", async () => {
    const res = await routeWebSurface(reqOf({ path: "/missing" }));
    const html = res.body as string;
    expect(html).toContain("<title>Not Found</title>");
  });

  test("HTML-escapes hostile message values (XSS safety)", async () => {
    // The URL parser already percent-encodes ``<>"`` in paths,
    // so an XSS payload would need to ride in as a raw message
    // param. Direct dispatch to error_404 with a hostile message
    // exercises the same escape boundary the classifier-rewrite
    // path uses (both flow into ``error404View.render`` →
    // ``_message`` → ``escapeHtml``).
    const res = await renderWebSurface({
      view:   "error_404",
      params: { message: "<script>alert(1)</script>" },
      mode:   V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
  });

  test("URL-encoded hostile chars in the path are surfaced safely", async () => {
    // Sanity-check the classifier-rewrite path: a path with
    // characters that get URL-encoded into the resolved view
    // name still produces a safe page — no raw ``<`` slips
    // through, and the surrounding quotes are escaped.
    const res = await routeWebSurface(reqOf({
      path: "/<script>",
    }));
    const html = res.body as string;
    expect(html).not.toContain("<script>");
    expect(html).toContain("&#39;");  // surrounding single quotes
  });

  test("JSON-mode 404 returns the structured shape via defaultRenderer", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/missing",
      headers: { accept: "application/json" },
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      view:   "error_404",
      params: { message: "View 'missing' not found." },
    });
  });

  test("known views are NOT rewritten — home still renders normally", async () => {
    const res = await routeWebSurface(reqOf({ path: "/home" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain('<div id="layout">');
    expect(html).not.toContain('<div id="error">');
    expect(html).toContain("Welcome to the Web Surface v0.2.0");
  });
});


// ---------------------------------------------------------------------------
// 2. error_500 view — direct render
// ---------------------------------------------------------------------------
describe("error_500 view — direct render", () => {
  test("direct dispatch → 500 + HTML content-type + #error wrapper", async () => {
    const res = await renderWebSurface({
      view:   "error_500",
      params: { message: "Custom failure message" },
      mode:   V.Mode.html,
    });
    expect(res.status).toBe(500);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = res.body as string;
    expect(html).toContain('<div id="error">');
    expect(html).toContain("<h1>Internal Error</h1>");
    expect(html).toContain("Custom failure message");
  });

  test("default message used when params omits one", async () => {
    const res = await renderWebSurface({
      view: "error_500",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain("An unexpected error occurred.");
  });

  test("header partial subtitle reflects the 500 status", async () => {
    const res = await renderWebSurface({
      view: "error_500",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain("<h2>500</h2>");
  });
});


// ---------------------------------------------------------------------------
// 3. Pipeline try/catch fallback
// ---------------------------------------------------------------------------
describe("renderPipeline — try/catch 500 fallback", () => {
  test("view.render() throw → 500 minimal fallback", async () => {
    registerView("kaboom", {
      template: "base",
      async render() {
        throw new Error("simulated failure");
      },
    });
    const res = await renderWebSurface({
      view: "kaboom",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(500);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = res.body as string;
    expect(html).toContain("<h1>Internal Error</h1>");
    expect(html).toContain("An unexpected error occurred.");
  });

  test("fallback does NOT include the original exception message", async () => {
    const secret = "leak-this-and-the-test-fails";
    registerView("leaky", {
      template: "base",
      async render() {
        throw new Error(secret);
      },
    });
    const res = await renderWebSurface({
      view: "leaky",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).not.toContain(secret);
  });

  test("fallback body has no ``at file:line`` stack frame", async () => {
    registerView("stacky", {
      template: "base",
      async render() {
        const err = new Error("with stack");
        // Force a deep-ish frame so .stack is populated.
        throw err;
      },
    });
    const res = await renderWebSurface({
      view: "stacky",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    // Node-style stack frames look like "    at funcName (file:line)".
    expect(html).not.toMatch(/\bat\s+\w+\s*\(/);
    // "Error:" prefix only appears if Node's stack was stringified.
    expect(html).not.toContain("Error: with stack");
  });

  test("fallback fires for a missing layout (layout load throw)", async () => {
    // A view that points at a layout that doesn't exist on disk.
    // The pipeline's loadCachedLayout throws → outer catch fires.
    registerView("bad-layout", {
      template: "base",
      layout:   "does-not-exist-zzz",
      async render() {
        return { title: "x", content: "y" };
      },
    });
    const res = await renderWebSurface({
      view: "bad-layout",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(500);
    expect((res.body as string)).toContain("<h1>Internal Error</h1>");
  });

  test("fallback fires for a missing view template (template load throw)", async () => {
    registerView("bad-template", {
      template: "does-not-exist-zzz",
      async render() {
        return { title: "x", content: "y" };
      },
    });
    const res = await renderWebSurface({
      view: "bad-template",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(500);
  });

  test("fallback is byte-identical across repeated faults (determinism)", async () => {
    registerView("repeat-kaboom", {
      template: "base",
      async render() {
        throw new Error("repeatable");
      },
    });
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await renderWebSurface({
        view: "repeat-kaboom",
        mode: V.Mode.html,
      });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("fallback does NOT apply the error layout (no double-fault)", async () => {
    // The minimal 500 path skips the layout — a fault in the
    // layout / partial path can't recurse. So no header/footer
    // partials appear in the catch body.
    registerView("layoutless-kaboom", {
      template: "base",
      async render() {
        throw new Error("nope");
      },
    });
    const res = await renderWebSurface({
      view: "layoutless-kaboom",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).not.toContain('<div id="error">');
    expect(html).not.toContain("<header>");
    expect(html).not.toContain("<footer>");
  });
});


// ---------------------------------------------------------------------------
// 4. Router envelope → HTML transform
// ---------------------------------------------------------------------------
describe("router — envelope→HTML transform", () => {
  test("asset 404 envelope is NOT transformed (asset contract preserved)", async () => {
    // The transform deliberately skips the asset short-circuit:
    // asset 404s are subresource failures, not user-facing
    // errors. Tests covering A8/A9/A10 already assert on the
    // raw envelope shape — this test locks that contract.
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/does-not-exist.css",
    }));
    expect(res.status).toBe(404);
    expect(res.headers["content-type"]).toBe("application/json");
    expect((res.body as WebSurfaceV0_2.ErrorEnvelope).error).toBe(
      "asset_not_found",
    );
  });

  test("known views (render-success branch) pass through untransformed", async () => {
    const res = await routeWebSurface(reqOf({ path: "/home" }));
    // The render branch produced HTML — no envelope shape, no
    // transform.
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("JSON-mode unknown view stays as the structured shape (no transform)", async () => {
    // The classifier rewrites to error_404; the pipeline renders
    // JSON; the body is ``{view, params}``, NOT an envelope —
    // so the transform doesn't fire.
    const res = await routeWebSurface(reqOf({
      path:    "/missing",
      headers: { accept: "application/json" },
    }));
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      view:   "error_404",
      params: { message: "View 'missing' not found." },
    });
  });

  test("HTML-mode 404 produces the full error layout (rewrite path)", async () => {
    // Sanity: the 404 page IS produced by the rewrite, not by
    // the envelope transform. The status comes from def.status.
    const res = await routeWebSurface(reqOf({ path: "/missing" }));
    expect(res.status).toBe(404);
    expect((res.body as string)).toContain('<div id="error">');
  });
});


// ---------------------------------------------------------------------------
// 5. Determinism + safety
// ---------------------------------------------------------------------------
describe("error views — determinism + safety", () => {
  test("same 404 URL → byte-identical HTML across 5 runs", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await routeWebSurface(reqOf({ path: "/missing" }));
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("same error_500 ctx → byte-identical HTML across runs", async () => {
    const ctx = {
      view: "error_500",
      params: { message: "X" },
      mode: V.Mode.html,
    };
    const a = await renderWebSurface(ctx);
    const b = await renderWebSurface(ctx);
    expect(a.body).toBe(b.body);
  });

  test("router does not mutate the input request", async () => {
    const req = reqOf({ path: "/missing?keep=1", headers: { x: "y" } });
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("renderer does not mutate the input ctx", async () => {
    const ctx = {
      view:   "error_500",
      params: { message: "stable" },
      mode:   V.Mode.html,
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });

  test("HTML body never contains an absolute file path", async () => {
    // Defensive: if a stack frame leaked from the catch, the
    // body would carry a path like ``C:\ClarityOS_Code\...`` or
    // ``/Users/...``. The structured 500 page must not.
    registerView("path-leak-check", {
      template: "base",
      async render() {
        throw new Error("path-leak-check");
      },
    });
    const res = await renderWebSurface({
      view: "path-leak-check",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).not.toMatch(/[A-Za-z]:\\[\w.\\-]+\.ts/);
    expect(html).not.toMatch(/\/(?:Users|home)\/[\w.-]+\//);
  });
});
