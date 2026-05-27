// v0.2.1 — runtime view tests.
//
// Surfaces under test:
//
//   1. Resolution: GET /runtime → 200 + text/html.
//   2. Layout: response uses the standard layout (#layout, not #error).
//   3. Heading: body contains ``<h1>Runtime Panel</h1>``.
//   4. Env rendering: process.env values appear in the body when set
//      (K_SERVICE + K_REVISION as the canonical Cloud Run-supplied
//      pair).
//   5. Env fallback: missing env vars render as ``(not set)`` so the
//      page is always usable outside Cloud Run.
//   6. XSS safety: env values are HTML-escaped at the view boundary.
//
// Determinism: each test snapshots + restores ``process.env`` for the
// keys it touches, so the order of tests does not matter and no
// mutation leaks across files.
//
// Path: web/src/surface/__tests__/runtime.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { routeWebSurface } from "../router";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import { runtimeView } from "../views/runtime";


function reqOf(
  overrides: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  return {
    path:    "/runtime",
    method:  "GET",
    headers: {},
    body:    null,
    ...overrides,
  };
}


const ENV_KEYS = [
  "K_SERVICE",
  "K_REVISION",
  "K_CONFIGURATION",
  "ENVIRONMENT",
  "PORT",
  "COMMIT_SHA",
  "BUILD_VERSION",
] as const;


// Snapshot of every relevant env var taken in ``beforeEach`` and
// restored in ``afterEach``. Keeps tests deterministic even when
// the host shell has any of these pre-set.
const savedEnv: Record<string, string | undefined> = {};


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  // Fixture set the classifier expects to find in the registry.
  registerView("home",      homeView);
  registerView("error_404", error404View);
  registerView("error_500", error500View);
  registerView("runtime",   runtimeView);
  // Snapshot + scrub env so each test starts from a known-empty state.
  for (const k of ENV_KEYS) {
    savedEnv[k] = process.env[k];
    delete process.env[k];
  }
});


afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) {
      delete process.env[k];
    } else {
      process.env[k] = savedEnv[k];
    }
  }
});


// ---------------------------------------------------------------------------
// 1. Resolution + transport
// ---------------------------------------------------------------------------
describe("runtime view — resolution", () => {
  test("GET /runtime → 200 + text/html", async () => {
    process.env.K_SERVICE  = "clarityos-web-v0-2";
    process.env.K_REVISION = "clarityos-web-v0-2-00099-test";
    process.env.ENVIRONMENT = "test";
    process.env.PORT       = "8080";

    const res = await routeWebSurface(reqOf());
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("body contains the Runtime Panel heading", async () => {
    const res = await routeWebSurface(reqOf());
    const html = res.body as string;
    expect(html).toContain("<h1>Runtime Panel</h1>");
  });

  test("response uses the standard layout (#layout, not #error)", async () => {
    const res = await routeWebSurface(reqOf());
    const html = res.body as string;
    expect(html).toContain('<div id="layout">');
    expect(html).not.toContain('<div id="error">');
  });
});


// ---------------------------------------------------------------------------
// 2. Env value rendering
// ---------------------------------------------------------------------------
describe("runtime view — env values", () => {
  test("K_SERVICE + K_REVISION values appear in body when set", async () => {
    process.env.K_SERVICE  = "clarityos-web-v0-2";
    process.env.K_REVISION = "clarityos-web-v0-2-00042-abc";

    const res = await routeWebSurface(reqOf());
    const html = res.body as string;
    expect(html).toContain("clarityos-web-v0-2");
    expect(html).toContain("clarityos-web-v0-2-00042-abc");
  });

  test("missing env vars render as (not set)", async () => {
    // beforeEach already scrubbed every key — render now produces
    // the fallback for all of them.
    const res = await routeWebSurface(reqOf());
    const html = res.body as string;
    expect(html).toContain("(not set)");
  });

  test("env values are HTML-escaped (no XSS)", async () => {
    process.env.COMMIT_SHA = "<script>alert(1)</script>";
    const res = await routeWebSurface(reqOf());
    const html = res.body as string;
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });
});
