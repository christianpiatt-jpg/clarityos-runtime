// Card A13-R — form handling + input binding tests.
//
// Six contract surfaces under test:
//
//   1. parseFormBody:
//      * URL-encoded values are auto-decoded
//        (``name=Alice&email=a%40b.com`` →
//         ``{name: "Alice", email: "a@b.com"}``).
//      * Empty body → empty map.
//      * Empty value (``k=``) → empty-string value.
//      * Duplicate keys → last-write-wins.
//      * Spaces are decoded (``+`` and ``%20`` both work).
//
//   2. Classifier — form detection:
//      * POST + ``application/x-www-form-urlencoded`` → form action.
//      * Mode preserved (HTML default + ``Accept: application/json``).
//      * GET never produces a form action (regardless of body).
//      * POST with non-form content-type (JSON, plain text) is NOT
//        a form action — falls through to render/404.
//      * POST with charset suffix on content-type still detected.
//      * Non-string body → render(error_500), NEVER a form action.
//      * Precedence: redirect URL wins over form detection.
//      * Precedence: form wins over 404 rewrite (unknown view +
//        form body still routes through handleForm).
//
//   3. Form handler:
//      * Parses ``rawBody`` and dispatches via the render
//        pipeline with the parsed fields as ``params``.
//      * The receiving view sees the fields via ``ctx.params``.
//      * No mutation of the input action.
//
//   4. End-to-end (form_demo):
//      * POST round-trip: submitted fields are echoed into the
//        re-rendered form's input ``value`` attributes.
//      * GET renders an empty form.
//      * HTML output goes through the standard layout.
//      * JSON mode stays canonical (``{view, params}``).
//
//   5. XSS safety:
//      * Hostile field values are HTML-escaped at the view
//        boundary; the rendered HTML never carries raw script
//        tags from form input.
//
//   6. Determinism:
//      * Same form body → byte-identical HTML across runs.
//      * No mutation of the request, the registry, or any cache
//        beyond additive cache fills.
//
// Path: web/src/surface/__tests__/formHandling.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { parseFormBody } from "../formParser";
import { handleForm } from "../formHandler";
import {
  classifyWebSurfaceRequest,
  ERROR_500_VIEW,
  FORM_URLENCODED_CONTENT_TYPE,
} from "../classifier";
import { routeWebSurface } from "../router";
import { renderWebSurface } from "../renderer";
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
import { homeView } from "../views/home";
import { error404View, error500View } from "../views/errors";
import { formDemoView } from "../views/formDemo";


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


function formReq(
  path: string,
  body: string,
  extra: Partial<WebSurfaceV0_2.Request> = {},
): WebSurfaceV0_2.Request {
  const { headers: extraHeaders, ...rest } = extra;
  return {
    path,
    method: "POST",
    body,
    ...rest,
    headers: {
      "content-type": FORM_URLENCODED_CONTENT_TYPE,
      ...(extraHeaders ?? {}),
    },
  };
}


beforeEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
  registerView("home",       homeView);
  registerView("error_404",  error404View);
  registerView("error_500",  error500View);
  registerView("form_demo",  formDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. parseFormBody
// ---------------------------------------------------------------------------
describe("parseFormBody", () => {
  test("URL-encoded values are auto-decoded", () => {
    expect(parseFormBody("name=Alice&email=a%40b.com")).toEqual({
      name:  "Alice",
      email: "a@b.com",
    });
  });

  test("empty body → empty map", () => {
    expect(parseFormBody("")).toEqual({});
  });

  test("empty value yields empty string (k= form)", () => {
    expect(parseFormBody("name=&email=")).toEqual({
      name:  "",
      email: "",
    });
  });

  test("missing value (bare key, no =) yields empty string", () => {
    expect(parseFormBody("flag")).toEqual({ flag: "" });
  });

  test("duplicate keys → last-write-wins", () => {
    expect(parseFormBody("k=1&k=2&k=3")).toEqual({ k: "3" });
  });

  test("`+` decodes to a space", () => {
    expect(parseFormBody("greeting=hello+world")).toEqual({
      greeting: "hello world",
    });
  });

  test("`%20` also decodes to a space", () => {
    expect(parseFormBody("greeting=hello%20world")).toEqual({
      greeting: "hello world",
    });
  });

  test("preserves key insertion order semantically (last-key wins)", () => {
    const out = parseFormBody("a=1&b=2&c=3");
    expect(out).toEqual({ a: "1", b: "2", c: "3" });
  });

  test("does not throw on weird-but-legal urlencoded input", () => {
    expect(() => parseFormBody("=")).not.toThrow();
    expect(() => parseFormBody("&&&")).not.toThrow();
    expect(() => parseFormBody("a=%")).not.toThrow();
  });

  test("returns a fresh object each call (no shared mutation surface)", () => {
    const a = parseFormBody("x=1");
    const b = parseFormBody("x=1");
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });
});


// ---------------------------------------------------------------------------
// 2. Classifier — form detection
// ---------------------------------------------------------------------------
describe("classifier — form detection", () => {
  test("POST + form content-type → form action", () => {
    const req = formReq("/form_demo", "name=Alice");
    const action = classifyWebSurfaceRequest(req);
    expect(action).toEqual({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice",
      mode:    V.Mode.html,
    });
  });

  test("mode is preserved (Accept: application/json → mode=json)", () => {
    const req = formReq("/form_demo", "name=A", {
      headers: {
        "content-type": FORM_URLENCODED_CONTENT_TYPE,
        accept:         "application/json",
      },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("form");
    if (action.kind === "form") {
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("content-type with charset suffix still classifies as form", () => {
    const req = formReq("/form_demo", "name=A", {
      headers: {
        "content-type": `${FORM_URLENCODED_CONTENT_TYPE}; charset=utf-8`,
      },
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("form");
  });

  test("GET never produces a form action (even with form body)", () => {
    const req = reqOf({
      path:    "/form_demo",
      method:  "GET",
      headers: { "content-type": FORM_URLENCODED_CONTENT_TYPE },
      body:    "name=Alice",
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).not.toBe("form");
  });

  test("POST with JSON content-type is NOT a form action", () => {
    const req = reqOf({
      path:    "/form_demo",
      method:  "POST",
      headers: { "content-type": "application/json" },
      body:    JSON.stringify({ name: "Alice" }),
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).not.toBe("form");
  });

  test("POST with plain text content-type is NOT a form action", () => {
    const req = reqOf({
      path:    "/form_demo",
      method:  "POST",
      headers: { "content-type": "text/plain" },
      body:    "name=Alice",
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).not.toBe("form");
  });

  test("POST with no content-type header is NOT a form action", () => {
    const req = reqOf({
      path:   "/form_demo",
      method: "POST",
      body:   "name=Alice",
    });
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).not.toBe("form");
  });

  test("non-string body → render(error_500), never form", () => {
    const cases: Array<WebSurfaceV0_2.Request["body"]> = [
      null,
      undefined,
      42,
      true,
      { name: "Alice" },
      ["name=Alice"],
    ];
    for (const body of cases) {
      const req = reqOf({
        path:    "/form_demo",
        method:  "POST",
        headers: { "content-type": FORM_URLENCODED_CONTENT_TYPE },
        body,
      });
      const action = classifyWebSurfaceRequest(req);
      expect(action.kind).toBe("render");
      if (action.kind === "render") {
        expect(action.view).toBe(ERROR_500_VIEW);
        expect((action.params as { message: string }).message)
          .toContain("must be a string");
      }
    }
  });

  test("precedence: /redirect with form body still classifies as redirect", () => {
    // Redirect detection comes BEFORE form detection in the
    // classifier — the URL routing primitive wins over method/
    // content-type heuristics.
    const req = formReq("/redirect?to=/foo", "ignored=body");
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("redirect");
    if (action.kind === "redirect") {
      expect(action.to).toBe("/foo");
    }
  });

  test("precedence: form wins over 404 rewrite (unknown view + form body)", () => {
    // An unknown view name with a POSTed form body emits a
    // ``form`` action carrying the original view name. The
    // handler will dispatch through the pipeline, where the
    // unknown view falls to defaultRenderer — but the fields
    // survive (rather than being discarded by the 404 rewrite).
    const req = formReq("/unknown_view_xyz", "k=v");
    const action = classifyWebSurfaceRequest(req);
    expect(action.kind).toBe("form");
    if (action.kind === "form") {
      expect(action.view).toBe("unknown_view_xyz");
      expect(action.rawBody).toBe("k=v");
    }
  });

  test("does not mutate the request", () => {
    const req = formReq("/form_demo", "name=Alice");
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 3. Form handler
// ---------------------------------------------------------------------------
describe("handleForm", () => {
  test("parses rawBody and dispatches via the render pipeline", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=a%40b.com",
      mode:    V.Mode.html,
    });
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain('value="Alice"');
    expect(html).toContain('value="a@b.com"');
  });

  test("the receiving view reads fields via ctx.params", async () => {
    // Custom view that surfaces ctx.params verbatim — proves
    // handleForm hands the parsed fields through as params.
    let seen: Record<string, unknown> | undefined;
    registerView("form_probe", {
      template: "base",
      async render(ctx) {
        seen = ctx.params as Record<string, unknown> | undefined;
        return { title: "probe", content: "" };
      },
    });
    await handleForm({
      kind:    "form",
      view:    "form_probe",
      rawBody: "x=1&y=two&z=three%20words",
      mode:    V.Mode.html,
    });
    expect(seen).toEqual({ x: "1", y: "two", z: "three words" });
  });

  test("does not mutate the input action", async () => {
    const action = {
      kind:    "form" as const,
      view:    "form_demo",
      rawBody: "name=Alice",
      mode:    V.Mode.html,
    };
    const frozen = JSON.stringify(action);
    await handleForm(action);
    expect(JSON.stringify(action)).toBe(frozen);
  });

  test("JSON mode stays canonical (returns {view, params} envelope)", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "name=Alice&email=a%40b.com",
      mode:    V.Mode.json,
    });
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      view:   "form_demo",
      params: { name: "Alice", email: "a@b.com" },
    });
  });

  test("empty body → empty params surface in the view", async () => {
    const res = await handleForm({
      kind:    "form",
      view:    "form_demo",
      rawBody: "",
      mode:    V.Mode.html,
    });
    const html = res.body as string;
    // Inputs render with empty value attributes.
    expect(html).toContain('value=""');
  });
});


// ---------------------------------------------------------------------------
// 4. End-to-end (routeWebSurface)
// ---------------------------------------------------------------------------
describe("routeWebSurface — form_demo round-trip", () => {
  test("GET /form_demo renders an empty form", async () => {
    const res = await routeWebSurface(reqOf({ path: "/form_demo" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("<h1>Form Demo</h1>");
    expect(html).toContain('name="name"');
    expect(html).toContain('name="email"');
    expect(html).toContain('value=""');
    // Empty form → no <pre> echo.
    expect(html).not.toContain('"email":');
  });

  test("POST /form_demo echoes submitted values into the inputs", async () => {
    const res = await routeWebSurface(formReq(
      "/form_demo",
      "name=Alice&email=a%40b.com",
    ));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain('value="Alice"');
    expect(html).toContain('value="a@b.com"');
    // The <pre> echo block shows the JSON round-trip.
    expect(html).toContain("&quot;name&quot;: &quot;Alice&quot;");
  });

  test("POST is wrapped in the standard layout", async () => {
    const res = await routeWebSurface(formReq("/form_demo", "name=A"));
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
    expect(html).toContain("<header>");
    expect(html).toContain("<footer>");
  });

  test("POST with JSON Accept returns the canonical envelope", async () => {
    const res = await routeWebSurface(formReq("/form_demo", "name=Alice", {
      headers: {
        "content-type": FORM_URLENCODED_CONTENT_TYPE,
        accept:         "application/json",
      },
    }));
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      view:   "form_demo",
      params: { name: "Alice" },
    });
  });

  test("POST with non-string body routes through error_500", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/form_demo",
      method:  "POST",
      headers: { "content-type": FORM_URLENCODED_CONTENT_TYPE },
      body:    { hijacked: true },
    }));
    expect(res.status).toBe(500);
    const html = res.body as string;
    expect(html).toContain("Internal Error");
    expect(html).toContain("must be a string");
  });
});


// ---------------------------------------------------------------------------
// 5. XSS safety
// ---------------------------------------------------------------------------
describe("form_demo — XSS safety", () => {
  test("hostile name value is HTML-escaped in the input value", async () => {
    const hostile = '"><script>alert(1)</script>';
    const body = `name=${encodeURIComponent(hostile)}&email=x@y.com`;
    const res = await routeWebSurface(formReq("/form_demo", body));
    const html = res.body as string;
    // The escaped form appears; the raw script tag does NOT.
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
    // Quote-escape so the value doesn't break out of the
    // ``value="..."`` attribute boundary.
    expect(html).toContain("&quot;");
  });

  test("hostile email value is HTML-escaped too", async () => {
    const hostile = "'\"><img src=x onerror=alert(1)>";
    const body = `name=A&email=${encodeURIComponent(hostile)}`;
    const res = await routeWebSurface(formReq("/form_demo", body));
    const html = res.body as string;
    expect(html).not.toContain("<img src=x onerror=alert(1)>");
    expect(html).toContain("&lt;img");
  });

  test("script-tag count stays at the layout baseline (no injection)", async () => {
    // The standard layout's <script src="...app.js"> is the only
    // expected <script> tag in the page. A hostile form value
    // must not inflate the count.
    const safe = await routeWebSurface(formReq(
      "/form_demo",
      "name=Alice&email=a%40b.com",
    ));
    const safeCount =
      (safe.body as string).match(/<script\b/g)?.length ?? 0;
    expect(safeCount).toBe(1);

    const hostile = await routeWebSurface(formReq(
      "/form_demo",
      `name=${encodeURIComponent('"><script>alert(1)</script>')}&email=x`,
    ));
    const hostileCount =
      (hostile.body as string).match(/<script\b/g)?.length ?? 0;
    expect(hostileCount).toBe(safeCount);
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("form handling — determinism", () => {
  test("same form body → byte-identical HTML across 5 runs", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await routeWebSurface(formReq(
        "/form_demo",
        "name=Alice&email=a%40b.com",
      ));
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("classifier output is byte-identical for repeated calls", () => {
    const req = formReq("/form_demo", "name=Alice");
    const a = classifyWebSurfaceRequest(req);
    const b = classifyWebSurfaceRequest(req);
    expect(a).toEqual(b);
  });

  test("form pathway does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice().sort();
    await routeWebSurface(formReq("/form_demo", "name=Alice"));
    await routeWebSurface(formReq("/form_demo", "name=Bob"));
    const after = _listRegisteredViewsForTests().slice().sort();
    expect(after).toEqual(before);
  });

  test("router does not mutate the input request", async () => {
    const req = formReq("/form_demo", "name=Alice&email=a%40b.com");
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("form_demo view does not mutate ctx", async () => {
    const ctx = {
      view:   "form_demo",
      params: { name: "Alice", email: "a@b.com" },
      mode:   V.Mode.html,
    };
    const frozen = JSON.stringify(ctx);
    await renderWebSurface(ctx);
    expect(JSON.stringify(ctx)).toBe(frozen);
  });
});
