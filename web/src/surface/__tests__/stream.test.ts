// Card A17 — streaming response tests.
//
// Six contract surfaces under test:
//
//   1. Classifier — x-stream opt-in:
//      * ``x-stream: 1`` header → stream action.
//      * No header → normal render action.
//      * Header on POST + form body → form wins (precedence
//        rule: data-shape branches outrank the stream opt-in).
//      * Header preserves mode (HTML default + json Accept).
//      * Header value other than "1" → not a stream action
//        (strict opt-in).
//
//   2. defaultStream:
//      * Yields one chunk per (key, value) pair from render().
//      * Insertion-order preserved.
//      * Empty render output → empty iterator (no chunks).
//
//   3. handleStream — HTML mode:
//      * Body wraps chunks in begin/end markers.
//      * Chunks concatenated in generator emission order.
//      * status 200, content-type text/html.
//      * View without ``stream`` → default strategy emits
//        key/value divs.
//      * Generator throwing mid-stream → aborted marker, no
//        crash, partial output preserved.
//
//   4. handleStream — JSON mode:
//      * Body shape: ``{stream: true, chunks: [...]}``.
//      * Chunks array matches emission order.
//      * Aborted stream surfaces ``aborted: true``.
//
//   5. End-to-end via routeWebSurface:
//      * GET /stream_demo (no header) → normal layout-wrapped
//        Response.
//      * GET /stream_demo + x-stream: 1 → streamed Response
//        with begin/end markers.
//      * Unknown view + x-stream → no crash, empty chunks.
//
//   6. Determinism + non-mutation:
//      * Same params → byte-identical Response across runs.
//      * Handler does not mutate the action, the registry, or
//        the request.
//      * Stream pathway does not register or unregister views.
//
// Path: web/src/surface/__tests__/stream.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  handleStream,
  STREAM_HTML_START_MARKER,
  STREAM_HTML_END_MARKER,
  STREAM_HTML_ERROR_MARKER,
} from "../streamHandler";
import { defaultStream } from "../defaultStream";
import {
  classifyWebSurfaceRequest,
  STREAM_HEADER,
  STREAM_OPT_IN_VALUE,
  FORM_URLENCODED_CONTENT_TYPE,
} from "../classifier";
import { routeWebSurface } from "../router";
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
import { streamDemoView } from "../views/streamDemo";


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
  registerView("home",         homeView);
  registerView("error_404",    error404View);
  registerView("error_500",    error500View);
  registerView("stream_demo",  streamDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Classifier — x-stream opt-in
// ---------------------------------------------------------------------------
describe("classifier — stream detection", () => {
  test("`x-stream: 1` header → stream action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    expect(action.kind).toBe("stream");
    if (action.kind === "stream") {
      expect(action.view).toBe("stream_demo");
      expect(action.mode).toBe(V.Mode.html);
    }
  });

  test("no header → normal render (not stream)", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/stream_demo",
    }));
    expect(action.kind).toBe("render");
  });

  test("header value other than '1' → no stream action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: "true" },
    }));
    expect(action.kind).not.toBe("stream");
  });

  test("mode preserved through Accept: application/json", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_demo",
      headers: {
        [STREAM_HEADER]: STREAM_OPT_IN_VALUE,
        accept:          "application/json",
      },
    }));
    expect(action.kind).toBe("stream");
    if (action.kind === "stream") {
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("params from querystring flow into the stream action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_demo?x=1&y=2",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    expect(action.kind).toBe("stream");
    if (action.kind === "stream") {
      expect(action.params).toEqual({ x: "1", y: "2" });
    }
  });

  test("precedence: form-encoded POST + x-stream → form wins", () => {
    // Data-shape branches (form / upload) outrank the stream
    // opt-in. Streaming requests are GET-shaped; if a client
    // sends a POST with a body, it goes through form parsing
    // (or upload parsing) first, even with the stream header
    // set.
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_demo",
      method:  "POST",
      headers: {
        "content-type": FORM_URLENCODED_CONTENT_TYPE,
        [STREAM_HEADER]: STREAM_OPT_IN_VALUE,
      },
      body: "k=v",
    }));
    expect(action.kind).toBe("form");
  });

  test("precedence: /redirect with x-stream → redirect wins", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/redirect?to=/foo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    expect(action.kind).toBe("redirect");
  });

  test("does not mutate the request", () => {
    const req = reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    });
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 2. defaultStream
// ---------------------------------------------------------------------------
describe("defaultStream", () => {
  test("yields one chunk per render() var, in insertion order", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return { a: "1", b: "2", c: "3" };
      },
    };
    const chunks: string[] = [];
    for await (const c of defaultStream(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      chunks.push(c);
    }
    expect(chunks).toEqual([
      '<div data-key="a">1</div>',
      '<div data-key="b">2</div>',
      '<div data-key="c">3</div>',
    ]);
  });

  test("empty render output → empty iterator", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return {};
      },
    };
    const chunks: string[] = [];
    for await (const c of defaultStream(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      chunks.push(c);
    }
    expect(chunks).toEqual([]);
  });

  test("number values are String()-coerced (deterministic)", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return { count: 42 };
      },
    };
    const chunks: string[] = [];
    for await (const c of defaultStream(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      chunks.push(c);
    }
    expect(chunks).toEqual(['<div data-key="count">42</div>']);
  });
});


// ---------------------------------------------------------------------------
// 3. handleStream — HTML mode
// ---------------------------------------------------------------------------
describe("handleStream — HTML mode", () => {
  test("wraps chunks in begin/end markers", async () => {
    const res = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
    const html = res.body as string;
    expect(html.startsWith(STREAM_HTML_START_MARKER)).toBe(true);
    expect(html.endsWith(STREAM_HTML_END_MARKER)).toBe(true);
  });

  test("chunks concatenated in emission order", async () => {
    const res = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    // Strip the markers so we can assert on raw chunk concat.
    const inner = html
      .slice(STREAM_HTML_START_MARKER.length, -STREAM_HTML_END_MARKER.length);
    expect(inner).toBe(
      "<p>Chunk 1: preparing.</p>" +
      "<p>Chunk 2: loading.</p>" +
      "<p>Chunk 3: done.</p>",
    );
  });

  test("view without ``stream`` uses defaultStream fallback", async () => {
    registerView("non_streaming", {
      template: "base",
      async render() {
        return { a: "alpha", b: "beta" };
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "non_streaming",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).toContain('<div data-key="a">alpha</div>');
    expect(html).toContain('<div data-key="b">beta</div>');
    expect(html).toContain(STREAM_HTML_START_MARKER);
    expect(html).toContain(STREAM_HTML_END_MARKER);
  });

  test("generator throwing mid-stream → aborted marker, partial output preserved", async () => {
    registerView("kaboom_stream", {
      template: "base",
      async render() {
        return { x: "1" };
      },
      async *stream() {
        yield "<p>before</p>";
        throw new Error("boom");
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "kaboom_stream",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(res.status).toBe(200);  // handler never throws past
    expect(html).toContain("<p>before</p>");
    expect(html).toContain(STREAM_HTML_ERROR_MARKER);
    expect(html).not.toContain(STREAM_HTML_END_MARKER);
  });

  test("aborted body does NOT include the original exception message", async () => {
    const secret = "leak-this-and-the-test-fails";
    registerView("leaky_stream", {
      template: "base",
      async render() { return {}; },
      async *stream() {
        throw new Error(secret);
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "leaky_stream",
      mode: V.Mode.html,
    });
    expect((res.body as string)).not.toContain(secret);
  });

  test("unknown view → 200 with empty inner body (no crash)", async () => {
    const res = await handleStream({
      kind: "stream",
      view: "no_such_view",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toBe(STREAM_HTML_START_MARKER + STREAM_HTML_END_MARKER);
  });
});


// ---------------------------------------------------------------------------
// 4. handleStream — JSON mode
// ---------------------------------------------------------------------------
describe("handleStream — JSON mode", () => {
  test("body is {stream: true, chunks: [...]} envelope", async () => {
    const res = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.json,
    });
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      stream: true,
      chunks: [
        "<p>Chunk 1: preparing.</p>",
        "<p>Chunk 2: loading.</p>",
        "<p>Chunk 3: done.</p>",
      ],
    });
  });

  test("aborted stream surfaces `aborted: true`", async () => {
    registerView("aborted_json", {
      template: "base",
      async render() { return {}; },
      async *stream() {
        yield "first";
        throw new Error("nope");
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "aborted_json",
      mode: V.Mode.json,
    });
    expect(res.body).toEqual({
      stream:  true,
      chunks:  ["first"],
      aborted: true,
    });
  });

  test("non-aborted JSON body has NO `aborted` key (clean shape)", async () => {
    const res = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.json,
    });
    expect(res.body).not.toHaveProperty("aborted");
  });

  test("default-strategy view (no stream fn) yields chunks via render", async () => {
    registerView("non_streaming_json", {
      template: "base",
      async render() {
        return { a: "1", b: "2" };
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "non_streaming_json",
      mode: V.Mode.json,
    });
    expect(res.body).toEqual({
      stream: true,
      chunks: [
        '<div data-key="a">1</div>',
        '<div data-key="b">2</div>',
      ],
    });
  });
});


// ---------------------------------------------------------------------------
// 5. End-to-end via routeWebSurface
// ---------------------------------------------------------------------------
describe("routeWebSurface — stream end-to-end", () => {
  test("no header → normal layout-wrapped Response", async () => {
    const res = await routeWebSurface(reqOf({ path: "/stream_demo" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
    expect(html).toContain("Streaming Demo");
    // Standard layout, NOT the stream markers.
    expect(html).not.toContain(STREAM_HTML_START_MARKER);
  });

  test("x-stream: 1 → streamed Response with begin/end markers", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html.startsWith(STREAM_HTML_START_MARKER)).toBe(true);
    expect(html.endsWith(STREAM_HTML_END_MARKER)).toBe(true);
    expect(html).toContain("Chunk 1: preparing.");
    expect(html).toContain("Chunk 2: loading.");
    expect(html).toContain("Chunk 3: done.");
    // Streaming bypasses the layout entirely — no chrome.
    expect(html).not.toContain('<div id="layout">');
  });

  test("x-stream + JSON accept → envelope", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/stream_demo",
      headers: {
        [STREAM_HEADER]: STREAM_OPT_IN_VALUE,
        accept:          "application/json",
      },
    }));
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      stream: true,
      chunks: [
        "<p>Chunk 1: preparing.</p>",
        "<p>Chunk 2: loading.</p>",
        "<p>Chunk 3: done.</p>",
      ],
    });
  });

  test("unknown view + x-stream → empty chunks, no crash", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/no_such_view_xyz",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    expect(res.status).toBe(200);
    expect(res.body).toBe(
      STREAM_HTML_START_MARKER + STREAM_HTML_END_MARKER,
    );
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("stream — determinism + non-mutation", () => {
  test("same params → byte-identical Response across 5 calls", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await handleStream({
        kind: "stream",
        view: "stream_demo",
        mode: V.Mode.html,
      });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("JSON envelope is deep-equal across runs", async () => {
    const a = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.json,
    });
    const b = await handleStream({
      kind: "stream",
      view: "stream_demo",
      mode: V.Mode.json,
    });
    expect(a.body).toEqual(b.body);
  });

  test("handler does not mutate the input action", async () => {
    const action = {
      kind:   "stream" as const,
      view:   "stream_demo",
      params: { x: "1" },
      mode:   V.Mode.html,
    };
    const frozen = JSON.stringify(action);
    await handleStream(action);
    expect(JSON.stringify(action)).toBe(frozen);
  });

  test("stream pathway does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice().sort();
    await routeWebSurface(reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE },
    }));
    await routeWebSurface(reqOf({
      path:    "/stream_demo",
      headers: {
        [STREAM_HEADER]: STREAM_OPT_IN_VALUE,
        accept:          "application/json",
      },
    }));
    const after = _listRegisteredViewsForTests().slice().sort();
    expect(after).toEqual(before);
  });

  test("router does not mutate the request on stream path", async () => {
    const req = reqOf({
      path:    "/stream_demo",
      headers: { [STREAM_HEADER]: STREAM_OPT_IN_VALUE, accept: "text/html" },
    });
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("stream body has no `at file:line` stack frame leakage", async () => {
    registerView("frame_check", {
      template: "base",
      async render() { return {}; },
      async *stream() {
        throw new Error("with stack");
      },
    });
    const res = await handleStream({
      kind: "stream",
      view: "frame_check",
      mode: V.Mode.html,
    });
    const html = res.body as string;
    expect(html).not.toMatch(/\bat\s+\w+\s*\(/);
    expect(html).not.toContain("Error:");
  });

  test("stream generator runs independently across two calls (no shared state)", async () => {
    // The view's async-generator factory must produce a fresh
    // iterator per call — confirm the chunk sequence is the
    // SAME (deterministic) for two independent invocations.
    const a = await handleStream({
      kind: "stream", view: "stream_demo", mode: V.Mode.json,
    });
    const b = await handleStream({
      kind: "stream", view: "stream_demo", mode: V.Mode.json,
    });
    expect((a.body as { chunks: string[] }).chunks)
      .toEqual((b.body as { chunks: string[] }).chunks);
  });
});
