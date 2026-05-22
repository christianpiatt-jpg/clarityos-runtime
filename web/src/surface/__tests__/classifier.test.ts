// Tests for the v0.2.0 Web Surface request classifier.
//
// Card 8 (original) — classifier always returned ``{ kind: "noop" }``.
// Card A2 (this revision) — classifier delegates to
// ``viewResolution.resolveView`` and always returns
// ``{ kind: "render", view, params, mode }``. The noop variant
// remains in the union for future use (health probes, etc.) but
// the classifier itself never emits it today.
// Card A11 — classifier now consults the view registry. Unknown
// views are rewritten to ``error_404`` with the resolved name in
// the message. Every test below either registers the view it
// asserts on (so the classifier falls through to the normal
// render branch) or explicitly checks the 404-rewrite path.
//
// These tests lock four contracts:
//
//   1. Known views classify to ``{ kind: "render", view: <name>, ... }``.
//   2. Unknown views classify to ``{ kind: "render", view: "error_404", ... }``
//      with the resolved name embedded in ``params.message``.
//   3. The discriminator narrows correctly through an exhaustive
//      switch (the compile-time ``never`` guard catches missed
//      variant updates).
//   4. Output depends only on (Request, registry state) — no
//      hidden globals, no module-import side effects.
//
// Path: web/src/surface/__tests__/classifier.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  classifyWebSurfaceRequest,
  ClassifiedSurfaceAction,
  ClassifiedSurfaceActionKind,
  ERROR_404_VIEW,
} from "../classifier";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { error404View } from "../views/errors";


// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------
function reqOf(overrides: Partial<WebSurfaceV0_2.Request> = {}): WebSurfaceV0_2.Request {
  return {
    path:    "/",
    method:  "GET",
    headers: {},
    body:    null,
    ...overrides,
  };
}


/** Minimal stub view definition for tests that only care about
 *  classifier output, not about what the view actually renders. */
const _stubView = {
  template: "base",
  async render() {
    return { title: "stub", content: "" };
  },
};


/**
 * Register a small set of stub views so the classifier's
 * registry-check falls through to the normal render branch for
 * every name asserted against below. The 404-rewrite tests use
 * names NOT in this set (e.g. ``"missing-view"``).
 */
function _registerStubViews(): void {
  registerView(ERROR_404_VIEW, error404View);
  for (const name of ["index", "home", "dashboard", "bar", "x", "operator"]) {
    registerView(name, _stubView);
  }
}


beforeEach(() => {
  _clearViewRegistryForTests();
  _registerStubViews();
});

afterEach(() => {
  _clearViewRegistryForTests();
});


// ---------------------------------------------------------------------------
// 1. Card A2 behaviour — every request classifies to render
// ---------------------------------------------------------------------------
describe("classifyWebSurfaceRequest — Card A2 default", () => {
  test("GET / classifies to render (view='index', mode='html')", () => {
    const action = classifyWebSurfaceRequest(reqOf());
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe("index");
      expect(action.mode).toBe(V.Mode.html);
      expect(action.params).toEqual({});
    }
  });

  test.each([
    "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
  ])("%s classifies to render", (method) => {
    const action = classifyWebSurfaceRequest(reqOf({ method }));
    expect(action.kind).toBe("render");
  });

  test.each([
    ["/",                              "index"],
    ["/home",                          "home"],
    ["/web-surface/v0.2/dashboard",    "dashboard"],
    ["/web-surface/v0.2/foo/bar",      "bar"],
  ])("path %s → view %s", (path, expectedView) => {
    const action = classifyWebSurfaceRequest(reqOf({ path }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(expectedView);
    }
  });

  test("Accept: application/json header → mode=json", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      headers: { accept: "application/json" },
    }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("?mode=json query param → mode=json (and stripped from params)", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/home?mode=json&id=abc",
    }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.mode).toBe(V.Mode.json);
      // ``mode`` is consumed by the resolver, not exposed as a param.
      expect(action.params).toEqual({ id: "abc" });
    }
  });

  test("no Accept + no ?mode= → mode=html (default)", () => {
    const action = classifyWebSurfaceRequest(reqOf({ path: "/home" }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.mode).toBe(V.Mode.html);
    }
  });

  test("request body content does not change classification (v0.2.0)", () => {
    const a = classifyWebSurfaceRequest(reqOf({ body: null }));
    const b = classifyWebSurfaceRequest(reqOf({ body: { x: 1 } }));
    const c = classifyWebSurfaceRequest(reqOf({ body: "text" }));
    expect(a.kind).toBe("render");
    expect(b.kind).toBe("render");
    expect(c.kind).toBe("render");
  });
});


// ---------------------------------------------------------------------------
// 2. Discriminator + exhaustive switch contract
// ---------------------------------------------------------------------------
describe("ClassifiedSurfaceAction — discriminated union contract", () => {
  // The classifier's output type is a discriminated union keyed on
  // ``kind``. A switch over it must narrow to the variant's full
  // field set inside each branch. The exhaustive ``never`` default
  // is the compile-time guard that catches missing variant updates.
  function describeAction(action: ClassifiedSurfaceAction): string {
    switch (action.kind) {
      case ClassifiedSurfaceActionKind.noop:
        return "noop";
      case ClassifiedSurfaceActionKind.render: {
        const paramCount = action.params
          ? Object.keys(action.params).length
          : 0;
        return `render:${action.view}:${action.mode}:${paramCount}`;
      }
      case ClassifiedSurfaceActionKind.redirect:
        return `redirect:${action.to}:${action.mode}`;
      default: {
        const _exhaustive: never = action;
        return _exhaustive;
      }
    }
  }

  test("noop variant routes through the switch", () => {
    const action: ClassifiedSurfaceAction = { kind: "noop" };
    expect(describeAction(action)).toBe("noop");
  });

  test("render variant routes (json mode, no params)", () => {
    const action: ClassifiedSurfaceAction = {
      kind: "render",
      view: "dashboard",
      mode: V.Mode.json,
    };
    expect(describeAction(action)).toBe("render:dashboard:json:0");
  });

  test("render variant routes (html mode, with params)", () => {
    const action: ClassifiedSurfaceAction = {
      kind:   "render",
      view:   "operator",
      params: { id: "abc", verbose: true },
      mode:   V.Mode.html,
    };
    expect(describeAction(action)).toBe("render:operator:html:2");
  });

  test("redirect variant routes (html mode)", () => {
    const action: ClassifiedSurfaceAction = {
      kind: "redirect",
      to:   "/foo",
      mode: V.Mode.html,
    };
    expect(describeAction(action)).toBe("redirect:/foo:html");
  });

  test("ClassifiedSurfaceActionKind mirrors the union exactly", () => {
    expect(ClassifiedSurfaceActionKind.noop).toBe("noop");
    expect(ClassifiedSurfaceActionKind.render).toBe("render");
    expect(ClassifiedSurfaceActionKind.redirect).toBe("redirect");
    expect(Object.keys(ClassifiedSurfaceActionKind).sort()).toEqual(
      ["noop", "redirect", "render"],
    );
  });

  test("classifier output is a valid ClassifiedSurfaceAction shape", () => {
    const action = classifyWebSurfaceRequest(reqOf());
    expect(action).toHaveProperty("kind");
    expect(["noop", "render", "redirect"]).toContain(action.kind);
  });
});


// ---------------------------------------------------------------------------
// 3. Purity / determinism / no side effects
// ---------------------------------------------------------------------------
describe("classifyWebSurfaceRequest — purity", () => {
  test("same input → same output (referential determinism)", () => {
    const req = reqOf({ path: "/x", method: "POST", body: { k: "v" } });
    const a = classifyWebSurfaceRequest(req);
    const b = classifyWebSurfaceRequest(req);
    expect(a).toEqual(b);
  });

  test("does not mutate the input request", () => {
    const req = reqOf({
      path: "/x?q=1", method: "GET",
      headers: { "accept": "application/json" },
      body: { k: "v" },
    });
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("module re-import is idempotent (no side effects at import time)", async () => {
    const first = await import("../classifier");
    const second = await import("../classifier");
    expect(first).toBe(second);
  });
});


// ---------------------------------------------------------------------------
// 4. Card A11 — unknown view → error_404 rewrite
// ---------------------------------------------------------------------------
describe("classifyWebSurfaceRequest — Card A11 404 rewrite", () => {
  test("unknown view name → error_404 (HTML mode)", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/missing-view",
    }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(ERROR_404_VIEW);
      expect(action.mode).toBe(V.Mode.html);
      expect(action.params).toEqual({
        message: "View 'missing-view' not found.",
      });
    }
  });

  test("unknown view name → error_404 preserves JSON mode", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path:    "/missing-view",
      headers: { accept: "application/json" },
    }));
    expect(action.kind).toBe("render");
    if (action.kind === "render") {
      expect(action.view).toBe(ERROR_404_VIEW);
      expect(action.mode).toBe(V.Mode.json);
    }
  });

  test("unknown view rewrite embeds the resolved view name verbatim", () => {
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/web-surface/v0.2/totally/nonexistent",
    }));
    if (action.kind !== "render") throw new Error("expected render");
    expect(action.view).toBe(ERROR_404_VIEW);
    expect((action.params as { message: string }).message).toBe(
      "View 'nonexistent' not found.",
    );
  });

  test("404 rewrite drops the original querystring params (replaces with message)", () => {
    // Unknown views don't carry through the original querystring —
    // params is fully replaced with the 404 envelope. This is the
    // contract the renderer relies on (it reads ``params.message``).
    const action = classifyWebSurfaceRequest(reqOf({
      path: "/missing?keep=1&also=2",
    }));
    if (action.kind !== "render") throw new Error("expected render");
    expect(action.params).toEqual({
      message: "View 'missing' not found.",
    });
  });

  test("known views fall through to the normal render branch (no rewrite)", () => {
    // Sanity-check the negative case: the views registered in
    // _registerStubViews must NOT be rewritten to error_404.
    for (const name of ["home", "dashboard", "bar"]) {
      const action = classifyWebSurfaceRequest(reqOf({ path: `/${name}` }));
      if (action.kind !== "render") throw new Error("expected render");
      expect(action.view).toBe(name);
    }
  });

  test("classifier does not mutate the request on 404 rewrite", () => {
    const req = reqOf({ path: "/missing?x=1" });
    const frozen = JSON.stringify(req);
    classifyWebSurfaceRequest(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });
});
