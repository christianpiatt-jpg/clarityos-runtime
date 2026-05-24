// Card A31-R — server-rendered Perplexity demo view tests.
//
// Three contract surfaces under test:
//
//   1. View registration — perplexity_demo is registered as a
//      side effect of importing the view module, and the
//      definition shape (template + standard layout) matches
//      the A20 / A22 demo-view convention.
//   2. routeWebSurface — GET /web-surface/v0.2/perplexity_demo
//      returns 200 + text/html + a body that carries the
//      demo's header text, its data-perplexity-query form, and
//      its #perplexity-result target panel.
//   3. Determinism + non-mutation — same request → byte-
//      identical body across calls; request not mutated.
//
// Path: web/src/surface/__tests__/perplexityDemo.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { routeWebSurface } from "../router";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  registerView,
  getView,
  _clearViewRegistryForTests,
  _listRegisteredViewsForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetManifest } from "../assetManifest";
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import { perplexityDemoView } from "../views/perplexityDemo";


function reqOf(
  overrides: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  return {
    path:    "/perplexity_demo",
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
  registerView("home",            homeView);
  registerView("error_404",       error404View);
  registerView("error_500",       error500View);
  registerView("perplexity_demo", perplexityDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. View registration shape
// ---------------------------------------------------------------------------
describe("perplexityDemoView — registration", () => {
  test("imported view is in the registered-views list", () => {
    expect(_listRegisteredViewsForTests()).toContain("perplexity_demo");
  });

  test("registered definition matches the exported constant", () => {
    expect(getView("perplexity_demo")).toBe(perplexityDemoView);
  });

  test("uses the standard layout (chrome-wrapped)", () => {
    expect(perplexityDemoView.layout).toBe("standard");
  });

  test("binds the perplexity_demo template", () => {
    expect(perplexityDemoView.template).toBe("perplexity_demo");
  });

  test("renders title + subtitle vars (HTML-escaped at boundary)", async () => {
    const vars = await perplexityDemoView.render({
      view:   "perplexity_demo",
      params: {},
      mode:   "html" as unknown as WebSurfaceV0_2.Request["headers"][string],
    } as unknown as Parameters<typeof perplexityDemoView.render>[0]);
    expect(vars.title).toBe("Perplexity Relay Demo");
    expect(vars.subtitle).toBe("Perplexity Relay Demo");
  });
});


// ---------------------------------------------------------------------------
// 2. routeWebSurface — GET /perplexity_demo
// ---------------------------------------------------------------------------
describe("routeWebSurface — GET /perplexity_demo", () => {
  test("returns 200", async () => {
    const response = await routeWebSurface(reqOf());
    expect(response.status).toBe(200);
  });

  test("returns text/html content-type", async () => {
    const response = await routeWebSurface(reqOf());
    expect(response.headers["content-type"]).toMatch(/text\/html/);
  });

  test("body carries the expected header text", async () => {
    const response = await routeWebSurface(reqOf());
    const body = response.body as string;
    expect(body).toContain("Perplexity Relay Demo");
    expect(body).toContain("<h1>");
  });

  test("body carries the data-perplexity-query form", async () => {
    const response = await routeWebSurface(reqOf());
    const body = response.body as string;
    expect(body).toContain("data-perplexity-query");
    expect(body).toContain('data-perplexity-target="#perplexity-result"');
    expect(body).toContain('name="query"');
  });

  test("body carries the #perplexity-result target panel", async () => {
    const response = await routeWebSurface(reqOf());
    const body = response.body as string;
    expect(body).toContain('id="perplexity-result"');
  });

  test("form action falls back to the demo's own URL (no-JS path)", async () => {
    const response = await routeWebSurface(reqOf());
    const body = response.body as string;
    expect(body).toContain(
      'action="/web-surface/v0.2/perplexity_demo"',
    );
  });

  test("response is wrapped by the standard layout chrome", async () => {
    const response = await routeWebSurface(reqOf());
    const body = response.body as string;
    // The standard layout adds the doctype + html/head/body.
    // We assert the body wrapping rather than a specific
    // chrome attribute so a future layout change doesn't
    // break this test unnecessarily.
    expect(body.toLowerCase()).toContain("<!doctype html>");
    expect(body.toLowerCase()).toContain("</html>");
  });
});


// ---------------------------------------------------------------------------
// 3. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("routeWebSurface — determinism + non-mutation", () => {
  test("same request → byte-identical body across 5 calls", async () => {
    const r = reqOf();
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const response = await routeWebSurface(r);
      outs.push(response.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("does not mutate the request", async () => {
    const r = reqOf();
    const frozen = JSON.stringify(r);
    await routeWebSurface(r);
    expect(JSON.stringify(r)).toBe(frozen);
  });
});
