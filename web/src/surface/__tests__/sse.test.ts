// Card A18 — Server-Sent Events tests.
//
// Six contract surfaces under test:
//
//   1. Classifier — x-sse opt-in:
//      * ``x-sse: 1`` header → sse action.
//      * No header → normal render action.
//      * Header value other than "1" → not an sse action.
//      * Header preserves mode + params.
//      * Precedence: data-shape (form / upload) outranks SSE.
//      * Precedence: stream outranks SSE.
//      * Precedence: redirect outranks SSE.
//
//   2. _formatSseFrame (pure helper):
//      * data-only event → ``data: <json>\n\n``.
//      * event + data → ``event: <name>\ndata: <json>\n\n``.
//      * id + event + data → all three, in spec order.
//      * data JSON-encoded (string → quoted; object → braces;
//        number → bare).
//      * Embedded CR/LF in id/event sanitised to spaces.
//
//   3. _sanitizeSseField:
//      * Plain values pass through.
//      * Single newline → space.
//      * Multiple CR/LF runs collapse to a single space.
//      * Surrounding whitespace trimmed.
//
//   4. handleSse:
//      * Status 200, content-type text/event-stream; charset=utf-8.
//      * Frames concatenated in emission order.
//      * View without ``events`` → default adapter (single
//        envelope event wrapping render result).
//      * Generator throwing → aborted sentinel appended,
//        previous frames preserved.
//      * Aborted body does NOT include the original exception
//        message or stack frames.
//      * Unknown view → empty body (no crash).
//      * No layout wrapping (raw SSE output, never HTML chrome).
//
//   5. End-to-end via routeWebSurface:
//      * GET /stream_sse_demo (no header) → layout-wrapped
//        HTML Response.
//      * GET + x-sse: 1 → SSE Response.
//      * Body bytes match the expected 3-frame sequence
//        byte-for-byte.
//
//   6. Determinism + non-mutation:
//      * Same params → byte-identical body across 5 calls.
//      * Handler does not mutate the action, the registry, or
//        the request.
//      * SSE pathway does not register or unregister views.
//
// Path: web/src/surface/__tests__/sse.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  handleSse,
  _formatSseFrame,
  _sanitizeSseField,
  SSE_CONTENT_TYPE,
  SSE_ERROR_EVENT,
} from "../sseHandler";
import {
  classifyWebSurfaceRequest,
  SSE_HEADER,
  SSE_OPT_IN_VALUE,
  STREAM_HEADER,
  STREAM_OPT_IN_VALUE,
  FORM_URLENCODED_CONTENT_TYPE,
} from "../classifier";
import { routeWebSurface } from "../router";
import { defaultSse } from "../defaultSse";
import { SseEvent } from "../sseEvent";
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
import { streamSseDemoView } from "../views/streamSseDemo";


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
  registerView("home",             homeView);
  registerView("error_404",        error404View);
  registerView("error_500",        error500View);
  registerView("stream_sse_demo",  streamSseDemoView);
});

afterEach(() => {
  _clearViewRegistryForTests();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  clearAssetManifest();
});


// ---------------------------------------------------------------------------
// 1. Classifier — x-sse opt-in
// ---------------------------------------------------------------------------
describe("classifier — sse detection", () => {
  test("`x-sse: 1` header → sse action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    expect(action.kind).toBe("sse");
    if (action.kind === "sse") {
      expect(action.view).toBe("stream_sse_demo");
      expect(action.mode).toBe(V.Mode.html);
    }
  });

  test("no header → normal render (not sse)", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/stream_sse_demo",
    }));
    expect(action.kind).toBe("render");
  });

  test("header value other than '1' → not an sse action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: "yes" },
    }));
    expect(action.kind).not.toBe("sse");
  });

  test("mode preserved through Accept: application/json", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo",
      headers: {
        [SSE_HEADER]: SSE_OPT_IN_VALUE,
        accept:       "application/json",
      },
    }));
    expect(action.kind).toBe("sse");
    if (action.kind === "sse") {
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("params from querystring flow into the sse action", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo?x=1&y=2",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    if (action.kind !== "sse") throw new Error("expected sse");
    expect(action.params).toEqual({ x: "1", y: "2" });
  });

  test("precedence: form POST + x-sse → form wins", () => {
    // Data-shape branches (form / upload) outrank the SSE
    // opt-in — same as the stream opt-in.
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo",
      method:  "POST",
      headers: {
        "content-type": FORM_URLENCODED_CONTENT_TYPE,
        [SSE_HEADER]:   SSE_OPT_IN_VALUE,
      },
      body: "k=v",
    }));
    expect(action.kind).toBe("form");
  });

  test("precedence: x-stream + x-sse together → stream wins", () => {
    // Stream is the more general chunked output; SSE is the
    // specialised one. If a client asks for both, the classifier
    // picks the simpler — locked by test so the choice is
    // explicit.
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/stream_sse_demo",
      headers: {
        [STREAM_HEADER]: STREAM_OPT_IN_VALUE,
        [SSE_HEADER]:    SSE_OPT_IN_VALUE,
      },
    }));
    expect(action.kind).toBe("stream");
  });

  test("precedence: /redirect with x-sse → redirect wins", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/redirect?to=/foo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    expect(action.kind).toBe("redirect");
  });

  test("does not mutate the request", () => {
    const req = reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    });
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});


// ---------------------------------------------------------------------------
// 2. _formatSseFrame
// ---------------------------------------------------------------------------
describe("_formatSseFrame", () => {
  test("data-only event → `data: <json>\\n\\n`", () => {
    expect(_formatSseFrame({ data: "hello" }))
      .toBe('data: "hello"\n\n');
  });

  test("event + data → `event: <name>\\ndata: <json>\\n\\n`", () => {
    expect(_formatSseFrame({ event: "phase", data: "one" }))
      .toBe('event: phase\ndata: "one"\n\n');
  });

  test("id + event + data → all three lines in spec order", () => {
    expect(_formatSseFrame({ id: "42", event: "tick", data: 3.14 }))
      .toBe('id: 42\nevent: tick\ndata: 3.14\n\n');
  });

  test("data is JSON-encoded — string → quoted", () => {
    expect(_formatSseFrame({ data: "hello" }))
      .toContain('data: "hello"');
  });

  test("data is JSON-encoded — object → braces", () => {
    expect(_formatSseFrame({ data: { a: 1, b: "x" } }))
      .toContain('data: {"a":1,"b":"x"}');
  });

  test("data is JSON-encoded — number → bare", () => {
    expect(_formatSseFrame({ data: 42 }))
      .toContain("data: 42");
  });

  test("data is JSON-encoded — null → null literal", () => {
    expect(_formatSseFrame({ data: null }))
      .toContain("data: null");
  });

  test("embedded CR/LF in id is sanitised to a single space", () => {
    const out = _formatSseFrame({
      id:   "line1\nline2",
      data: "x",
    });
    expect(out).toContain("id: line1 line2");
    expect(out).not.toContain("id: line1\nline2");
  });

  test("embedded CR/LF in event is sanitised to a single space", () => {
    const out = _formatSseFrame({
      event: "phase\rone",
      data:  "x",
    });
    expect(out).toContain("event: phase one");
    expect(out).not.toContain("event: phase\rone");
  });

  test("each frame ends with exactly two newlines (\\n\\n)", () => {
    const out = _formatSseFrame({ data: "x" });
    expect(out.endsWith("\n\n")).toBe(true);
    expect(out.endsWith("\n\n\n")).toBe(false);
  });

  test("undefined id and event are omitted from the frame", () => {
    const out = _formatSseFrame({ data: "x" });
    expect(out).not.toContain("id:");
    expect(out).not.toContain("event:");
  });
});


// ---------------------------------------------------------------------------
// 3. _sanitizeSseField
// ---------------------------------------------------------------------------
describe("_sanitizeSseField", () => {
  test("plain value passes through unchanged", () => {
    expect(_sanitizeSseField("phase")).toBe("phase");
  });

  test("single \\n → single space", () => {
    expect(_sanitizeSseField("a\nb")).toBe("a b");
  });

  test("single \\r → single space", () => {
    expect(_sanitizeSseField("a\rb")).toBe("a b");
  });

  test("multiple CR/LF runs collapse to a single space", () => {
    expect(_sanitizeSseField("a\r\n\r\nb")).toBe("a b");
  });

  test("surrounding whitespace trimmed", () => {
    expect(_sanitizeSseField("  hello  ")).toBe("hello");
  });

  test("string of only newlines collapses to empty", () => {
    expect(_sanitizeSseField("\n\n\r")).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 4. handleSse
// ---------------------------------------------------------------------------
describe("handleSse", () => {
  test("status 200 + content-type text/event-stream; charset=utf-8", async () => {
    const res = await handleSse({
      kind: "sse",
      view: "stream_sse_demo",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe(SSE_CONTENT_TYPE);
  });

  test("frames concatenated in generator emission order", async () => {
    const res = await handleSse({
      kind: "sse",
      view: "stream_sse_demo",
      mode: V.Mode.html,
    });
    expect(res.body).toBe(
      'event: phase\ndata: "one"\n\n' +
      'event: phase\ndata: "two"\n\n' +
      'event: phase\ndata: "three"\n\n',
    );
  });

  test("view without `events` → default adapter wraps render result", async () => {
    registerView("no_events_sse", {
      template: "base",
      async render() {
        return { a: "1", b: "2" };
      },
    });
    const res = await handleSse({
      kind: "sse",
      view: "no_events_sse",
      mode: V.Mode.html,
    });
    // Single event whose data payload is the entire render bag.
    expect(res.body).toBe('data: {"a":"1","b":"2"}\n\n');
  });

  test("generator throwing mid-stream → aborted sentinel appended", async () => {
    registerView("kaboom_sse", {
      template: "base",
      async render() { return {}; },
      async *events() {
        yield { event: "phase", data: "before" };
        throw new Error("boom");
      },
    });
    const res = await handleSse({
      kind: "sse",
      view: "kaboom_sse",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(200);
    const body = res.body as string;
    expect(body).toContain('event: phase\ndata: "before"\n\n');
    expect(body).toContain('event: error\ndata: {"aborted":true}\n\n');
  });

  test("aborted body does NOT include the original exception message", async () => {
    const secret = "leak-this-and-the-test-fails";
    registerView("leaky_sse", {
      template: "base",
      async render() { return {}; },
      async *events() {
        throw new Error(secret);
      },
    });
    const res = await handleSse({
      kind: "sse",
      view: "leaky_sse",
      mode: V.Mode.html,
    });
    expect((res.body as string)).not.toContain(secret);
  });

  test("aborted body has no `at file:line` stack frame leakage", async () => {
    registerView("stack_sse", {
      template: "base",
      async render() { return {}; },
      async *events() {
        throw new Error("with stack");
      },
    });
    const res = await handleSse({
      kind: "sse",
      view: "stack_sse",
      mode: V.Mode.html,
    });
    const body = res.body as string;
    expect(body).not.toMatch(/\bat\s+\w+\s*\(/);
    expect(body).not.toContain("Error:");
  });

  test("unknown view → empty body, no crash", async () => {
    const res = await handleSse({
      kind: "sse",
      view: "no_such_view_xyz",
      mode: V.Mode.html,
    });
    expect(res.status).toBe(200);
    expect(res.body).toBe("");
  });

  test("body never contains layout chrome (no <!DOCTYPE>, no <div id=\"layout\">)", async () => {
    const res = await handleSse({
      kind: "sse",
      view: "stream_sse_demo",
      mode: V.Mode.html,
    });
    const body = res.body as string;
    expect(body).not.toContain("<!DOCTYPE html>");
    expect(body).not.toContain('<div id="layout">');
    expect(body).not.toContain("<header>");
    expect(body).not.toContain("<footer>");
  });

  test("SSE_ERROR_EVENT exported sentinel matches what's appended", async () => {
    // The handler appends ``_formatSseFrame(SSE_ERROR_EVENT)``
    // on abort — confirm the exported constant is what tests
    // can lock against.
    registerView("abort_check", {
      template: "base",
      async render() { return {}; },
      async *events() { throw new Error("nope"); },
    });
    const res = await handleSse({
      kind: "sse", view: "abort_check", mode: V.Mode.html,
    });
    expect(res.body).toBe(_formatSseFrame(SSE_ERROR_EVENT));
    expect(SSE_ERROR_EVENT).toEqual({
      event: "error",
      data:  { aborted: true },
    });
  });
});


// ---------------------------------------------------------------------------
// 4b. defaultSse (separate scope for clarity)
// ---------------------------------------------------------------------------
describe("defaultSse", () => {
  test("yields exactly one event with render result as data", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return { x: 1, y: "two" };
      },
    };
    const events: SseEvent[] = [];
    for await (const ev of defaultSse(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      events.push(ev);
    }
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ data: { x: 1, y: "two" } });
  });

  test("empty render result → one event with empty-object data", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return {};
      },
    };
    const events: SseEvent[] = [];
    for await (const ev of defaultSse(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      events.push(ev);
    }
    expect(events).toEqual([{ data: {} }]);
  });

  test("no event name or id set on the default-wrapped event", async () => {
    const fakeDef = {
      template: "base",
      async render() {
        return { ok: true };
      },
    };
    for await (const ev of defaultSse(fakeDef, {
      view: "x", mode: V.Mode.html,
    })) {
      expect(ev.event).toBeUndefined();
      expect(ev.id).toBeUndefined();
    }
  });
});


// ---------------------------------------------------------------------------
// 5. End-to-end via routeWebSurface
// ---------------------------------------------------------------------------
describe("routeWebSurface — sse end-to-end", () => {
  test("no header → layout-wrapped HTML Response (regular render)", async () => {
    const res = await routeWebSurface(reqOf({ path: "/stream_sse_demo" }));
    expect(res.status).toBe(200);
    const html = res.body as string;
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain('<div id="layout">');
    expect(html).toContain("SSE Demo");
  });

  test("x-sse: 1 → SSE Response with the 3-frame phase sequence", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe(SSE_CONTENT_TYPE);
    expect(res.body).toBe(
      'event: phase\ndata: "one"\n\n' +
      'event: phase\ndata: "two"\n\n' +
      'event: phase\ndata: "three"\n\n',
    );
  });

  test("x-sse + JSON accept still returns text/event-stream", async () => {
    // The handler ignores the action's mode field; SSE always
    // produces wire-format SSE regardless of Accept.
    const res = await routeWebSurface(reqOf({
      path:    "/stream_sse_demo",
      headers: {
        [SSE_HEADER]: SSE_OPT_IN_VALUE,
        accept:       "application/json",
      },
    }));
    expect(res.headers["content-type"]).toBe(SSE_CONTENT_TYPE);
    expect(typeof res.body).toBe("string");
  });

  test("unknown view + x-sse → empty body, no crash", async () => {
    const res = await routeWebSurface(reqOf({
      path:    "/no_such_view_xyz",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    expect(res.status).toBe(200);
    expect(res.body).toBe("");
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism + non-mutation
// ---------------------------------------------------------------------------
describe("sse — determinism + non-mutation", () => {
  test("same params → byte-identical body across 5 calls", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await handleSse({
        kind: "sse",
        view: "stream_sse_demo",
        mode: V.Mode.html,
      });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("handler does not mutate the input action", async () => {
    const action = {
      kind:   "sse" as const,
      view:   "stream_sse_demo",
      params: { x: "1" },
      mode:   V.Mode.html,
    };
    const frozen = JSON.stringify(action);
    await handleSse(action);
    expect(JSON.stringify(action)).toBe(frozen);
  });

  test("sse pathway does not register or unregister views", async () => {
    const before = _listRegisteredViewsForTests().slice().sort();
    await routeWebSurface(reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE },
    }));
    await routeWebSurface(reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE, accept: "application/json" },
    }));
    const after = _listRegisteredViewsForTests().slice().sort();
    expect(after).toEqual(before);
  });

  test("router does not mutate the request on sse path", async () => {
    const req = reqOf({
      path:    "/stream_sse_demo",
      headers: { [SSE_HEADER]: SSE_OPT_IN_VALUE, accept: "text/html" },
    });
    const frozen = JSON.stringify(req);
    await routeWebSurface(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("independent calls produce the same frame sequence (no shared state)", async () => {
    const a = await handleSse({
      kind: "sse", view: "stream_sse_demo", mode: V.Mode.html,
    });
    const b = await handleSse({
      kind: "sse", view: "stream_sse_demo", mode: V.Mode.html,
    });
    expect(a.body).toBe(b.body);
  });

  test("aborted runs are byte-identical across repeats", async () => {
    registerView("repeat_abort", {
      template: "base",
      async render() { return {}; },
      async *events() {
        yield { event: "phase", data: "first" };
        throw new Error("nope");
      },
    });
    const a = await handleSse({
      kind: "sse", view: "repeat_abort", mode: V.Mode.html,
    });
    const b = await handleSse({
      kind: "sse", view: "repeat_abort", mode: V.Mode.html,
    });
    expect(a.body).toBe(b.body);
  });
});
