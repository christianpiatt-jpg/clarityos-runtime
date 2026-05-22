// Card A12 — redirects + navigation helpers tests.
//
// Six contract surfaces under test:
//
//   1. Classifier redirect detection:
//      * URL with last segment ``"redirect"`` + ?to=/foo →
//        ``{kind: "redirect", to: "/foo", mode}``.
//      * Missing ?to → falls back to DEFAULT_REDIRECT_TARGET.
//      * Non-string ?to (impossible via URL but via param map)
//        → DEFAULT_REDIRECT_TARGET.
//      * Mode is preserved from the resolver.
//      * Interception happens BEFORE the registry check —
//        ``redirect`` doesn't need to be a registered view.
//
//   2. JSON-mode redirect render:
//      * Response body is a ``RedirectEnvelope``: ``{redirect: <to>}``.
//      * Status 200 (never 302), content-type application/json.
//      * ``isRedirectEnvelope`` predicate recognises the shape.
//
//   3. HTML-mode redirect render:
//      * Renders through the standard layout (#layout wrapper).
//      * Body contains ``<h1>Redirecting…</h1>`` + an ``<a>``
//        tag pointing at ``to`` + a ``setTimeout`` script that
//        navigates via ``window.location.href``.
//      * Status 200, content-type text/html; charset=utf-8.
//
//   4. URL allowlist (security):
//      * Hostile ``to`` values (``"><script>``, ``javascript:``,
//        backticks, quotes, newlines, etc.) fall back to the
//        default.
//      * Common valid paths (``/foo``, ``/a/b/c?x=1&y=2``,
//        ``/p%20ath``) pass through unchanged.
//      * Default fallback applies for non-strings, empty
//        strings, and over-length values.
//
//   5. Navigation helper:
//      * ``redirect("/x")`` → ``/web-surface/v0.2/redirect?to=%2Fx``.
//      * URL-encodes special chars (``&``, ``?``, spaces) so they
//        round-trip through the classifier.
//      * Output is consumable by ``routeWebSurface``: feeding it
//        back through the router produces the expected redirect
//        action with the original ``to`` value.
//
//   6. Determinism + safety:
//      * Same redirect → byte-identical HTML across runs.
//      * Router / renderer do not mutate ctx / req / registry.
//      * HTML body never contains raw ``<script>`` from a
//        hostile ``to`` (sanitiser is load-bearing).
//
// Path: web/src/surface/__tests__/redirects.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  classifyWebSurfaceRequest,
  REDIRECT_VIEW_NAME,
  DEFAULT_REDIRECT_TARGET,
  ClassifiedSurfaceAction,
} from "../classifier";
import { renderRedirect } from "../redirectRenderer";
import { renderWebSurface } from "../renderer";
import { routeWebSurface } from "../router";
import { redirect, SURFACE_URL_PREFIX } from "../navigation";
import { isRedirectEnvelope } from "../redirectEnvelope";
import { sanitizeRedirectTarget, redirectView } from "../views/redirect";
import { error404View } from "../views/errors";
import { homeView } from "../views/home";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";


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
  // Register the canonical fixture set every test. Redirect
  // detection in the classifier does NOT depend on
  // ``redirect_view`` being registered (it's intercepted by
  // view-NAME match), but HTML-mode dispatch through the
  // pipeline does — so the view is registered for tests that
  // exercise the full path.
  registerView("home",         homeView);
  registerView("error_404",    error404View);
  registerView("redirect_view", redirectView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Classifier — redirect detection
// ---------------------------------------------------------------------------
describe("classifier — redirect detection", () => {
  test("`/redirect?to=/foo` → {kind: 'redirect', to: '/foo', mode: html}", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/redirect?to=/foo",
    }));
    expect(action).toEqual({
      kind: "redirect",
      to:   "/foo",
      mode: V.Mode.html,
    });
  });

  test("`/redirect` (no ?to=) falls back to DEFAULT_REDIRECT_TARGET", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/redirect",
    }));
    expect(action).toEqual({
      kind: "redirect",
      to:   DEFAULT_REDIRECT_TARGET,
      mode: V.Mode.html,
    });
  });

  test("JSON-mode redirect preserves mode through the action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/redirect?to=/foo",
      headers: { accept: "application/json" },
    }));
    expect(action).toEqual({
      kind: "redirect",
      to:   "/foo",
      mode: V.Mode.json,
    });
  });

  test("redirect interception happens BEFORE the registry check", () => {
    // Sanity: even with the registry empty (no redirect_view
    // registered), the URL still routes as a redirect action.
    _clearViewRegistryForTests();
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/redirect?to=/x",
    }));
    expect(action.kind).toBe("redirect");
    expect(_listRegisteredViewsForTests()).toEqual([]);
  });

  test("redirect URL with query encoding round-trips correctly", () => {
    // ``redirect("/a?x=1&y=2")`` URL-encodes to ``%2Fa%3Fx%3D1%26y%3D2``
    // — the classifier reads it back via URLSearchParams which
    // auto-decodes. The value at action.to is byte-identical to
    // what was originally passed.
    const helperUrl = redirect("/a?x=1&y=2");
    const action = classifyWebSurfaceRequest(reqOf({ path: helperUrl }));
    expect(action).toMatchObject({
      kind: "redirect",
      to:   "/a?x=1&y=2",
    });
  });

  test("does not mutate the request", () => {
    const req = reqOf({ path: "/redirect?to=/foo" });
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 2. JSON-mode redirect render
// ---------------------------------------------------------------------------
describe("renderRedirect — JSON mode", () => {
  test("returns a RedirectEnvelope body", async () => {
    const res = await renderRedirect("/foo", V.Mode.json);
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({ redirect: "/foo" });
  });

  test("body is recognised by isRedirectEnvelope", async () => {
    const res = await renderRedirect("/foo", V.Mode.json);
    expect(isRedirectEnvelope(res.body)).toBe(true);
  });

  test("status is 200, never 302 (no HTTP redirect)", async () => {
    const res = await renderRedirect("/foo", V.Mode.json);
    expect(res.status).toBe(200);
    expect(res.status).not.toBe(302);
  });

  test("via routeWebSurface end-to-end", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/redirect?to=/dashboard",
      headers: { accept: "application/json" },
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({ redirect: "/dashboard" });
  });
});


// ---------------------------------------------------------------------------
// 3. HTML-mode redirect render
// ---------------------------------------------------------------------------
describe("renderRedirect — HTML mode", () => {
  test("returns 200 + text/html", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("body contains the Redirecting… heading", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    const html = res.body as string;
    expect(html).toContain("<h1>Redirecting");
  });

  test("body contains an <a> tag pointing at the target", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    const html = res.body as string;
    expect(html).toContain('<a href="/foo">/foo</a>');
  });

  test("body contains the setTimeout window.location.href script", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    const html = res.body as string;
    expect(html).toContain("window.location.href");
    expect(html).toContain('window.location.href = "/foo"');
    expect(html).toMatch(/setTimeout\(/);
  });

  test("rendered through the standard layout", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
  });

  test("title in <head> reflects the redirect state", async () => {
    const res = await renderRedirect("/foo", V.Mode.html);
    const html = res.body as string;
    expect(html).toContain("<title>Redirecting</title>");
  });

  test("via routeWebSurface end-to-end (HTML default)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/redirect?to=/foo",
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = res.body as string;
    expect(html).toContain("Redirecting");
    expect(html).toContain('<a href="/foo">/foo</a>');
  });
});


// ---------------------------------------------------------------------------
// 4. URL allowlist (security)
// ---------------------------------------------------------------------------
describe("sanitizeRedirectTarget — allowlist", () => {
  test.each([
    ["/foo",                        "/foo"],
    ["/a/b/c",                      "/a/b/c"],
    ["/foo?x=1",                    "/foo?x=1"],
    ["/foo?x=1&y=2",                "/foo?x=1&y=2"],
    ["/p%20ath",                    "/p%20ath"],
    ["/with-dashes_and.dots~tilde", "/with-dashes_and.dots~tilde"],
  ])("safe input %j passes through unchanged", (input, expected) => {
    expect(sanitizeRedirectTarget(input)).toBe(expected);
  });

  test.each([
    ['"><script>alert(1)</script>'],
    ['/foo"><script>'],
    ["/foo'onerror=alert(1)"],
    ["javascript:alert(1)"],
    ["//evil.example.com"],
    ["http://evil.example.com"],
    ["/foo;alert(1)"],
    ["/foo\nnewline"],
    ["/foo`backtick"],
    ["/foo<bracket>"],
    ["/foo\\backslash"],
    ["foo-no-leading-slash"],
    [""],
  ])("hostile input %j falls back to default", (input) => {
    expect(sanitizeRedirectTarget(input)).toBe(DEFAULT_REDIRECT_TARGET);
  });

  test.each([
    [undefined],
    [null],
    [42],
    [{ url: "/foo" }],
    [["/foo"]],
    [true],
  ])("non-string input %j falls back to default", (input) => {
    expect(sanitizeRedirectTarget(input as unknown)).toBe(
      DEFAULT_REDIRECT_TARGET,
    );
  });

  test("over-length input falls back to default", () => {
    const huge = "/" + "x".repeat(3000);
    expect(sanitizeRedirectTarget(huge)).toBe(DEFAULT_REDIRECT_TARGET);
  });

  test("hostile `to` does NOT leak into rendered HTML (XSS safety)", async () => {
    // End-to-end check: route → classifier → renderer → view.
    // The hostile value would be passed through the classifier
    // verbatim (the classifier doesn't validate the URL) and
    // sanitised by the view before substitution. The rendered
    // HTML must show the default target, not the hostile string.
    const res = await routeWebSurface(reqOf({
      path: '/redirect?to=%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E',
    }));
    const html = res.body as string;
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain(DEFAULT_REDIRECT_TARGET);
  });
});


// ---------------------------------------------------------------------------
// 5. Navigation helper
// ---------------------------------------------------------------------------
describe("navigation.redirect — URL builder", () => {
  test("redirect('/x') → /web-surface/v0.2/redirect?to=%2Fx", () => {
    expect(redirect("/x")).toBe(
      `${SURFACE_URL_PREFIX}/${REDIRECT_VIEW_NAME}?to=%2Fx`,
    );
  });

  test("URL-encodes special characters", () => {
    expect(redirect("/a?b=1&c=2")).toBe(
      `${SURFACE_URL_PREFIX}/${REDIRECT_VIEW_NAME}?to=%2Fa%3Fb%3D1%26c%3D2`,
    );
  });

  test("URL-encodes spaces", () => {
    expect(redirect("/with space")).toBe(
      `${SURFACE_URL_PREFIX}/${REDIRECT_VIEW_NAME}?to=%2Fwith%20space`,
    );
  });

  test("output is round-trippable through the classifier", () => {
    const url = redirect("/foo");
    const action = classifyWebSurfaceRequest(reqOf({ path: url }));
    expect(action).toMatchObject({ kind: "redirect", to: "/foo" });
  });

  test("output round-trip preserves complex querystring values", () => {
    const original = "/a?x=1&y=hello world";
    const url = redirect(original);
    const action = classifyWebSurfaceRequest(reqOf({ path: url }));
    expect(action).toMatchObject({ kind: "redirect", to: original });
  });

  test("SURFACE_URL_PREFIX matches the prefix the router claims", () => {
    expect(SURFACE_URL_PREFIX).toBe("/web-surface/v0.2");
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + safety
// ---------------------------------------------------------------------------
describe("redirect — determinism + safety", () => {
  test("same redirect → byte-identical HTML across 5 runs", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await renderRedirect("/foo", V.Mode.html);
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("same JSON redirect → byte-identical body across runs", async () => {
    const a = await renderRedirect("/foo", V.Mode.json);
    const b = await renderRedirect("/foo", V.Mode.json);
    expect(a.body).toEqual(b.body);
  });

  test("classifier output is byte-identical for repeated calls", () => {
    const req = reqOf({ path: "/redirect?to=/foo" });
    const a = classifyWebSurfaceRequest(req);
    const b = classifyWebSurfaceRequest(req);
    expect(a).toEqual(b);
  });

  test("renderer does not mutate ctx-like inputs", async () => {
    const to = "/foo";
    await renderRedirect(to, V.Mode.html);
    expect(to).toBe("/foo");
  });

  test("renderRedirect does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice();
    await renderRedirect("/foo", V.Mode.html);
    await renderRedirect("/foo", V.Mode.json);
    expect(_listRegisteredViewsForTests().slice()).toEqual(before);
  });

  test("HTML body holds exactly the expected script tags (no injection)", async () => {
    // Belt-and-braces — the sanitiser catches injection earlier,
    // but confirm the rendered output stays at the expected
    // baseline script count.
    //
    // Two <script> tags expected:
    //   1. The standard layout's <script src="...app.js" defer>
    //   2. The redirect template's inline setTimeout
    //
    // A hostile ``to`` value (which falls back to the default
    // via the sanitiser) MUST not increase this count.
    const safe = await renderRedirect("/foo", V.Mode.html);
    const safeCount = (safe.body as string).match(/<script\b/g)?.length ?? 0;
    expect(safeCount).toBe(2);

    const hostile = await renderRedirect(
      '"><script>alert(1)</script>',
      V.Mode.html,
    );
    const hostileCount =
      (hostile.body as string).match(/<script\b/g)?.length ?? 0;
    expect(hostileCount).toBe(safeCount);
  });

  test("ClassifiedSurfaceAction redirect variant carries exactly {kind, to, mode}", () => {
    // Shape lock — extra fields would mean the classifier is
    // leaking state through the action envelope.
    const action: ClassifiedSurfaceAction = classifyWebSurfaceRequest(
      reqOf({ path: "/redirect?to=/x" }),
    );
    if (action.kind !== "redirect") {
      throw new Error("expected redirect action");
    }
    expect(Object.keys(action).sort()).toEqual(["kind", "mode", "to"]);
  });
});
