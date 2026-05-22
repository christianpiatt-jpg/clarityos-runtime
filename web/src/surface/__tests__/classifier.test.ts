// Card 8 — tests for the v0.2.0 Web Surface request classifier.
//
// The classifier is a pure function: same Request in → same
// ClassifiedSurfaceAction out, no side effects. These tests lock
// in three contracts:
//
//   1. Every valid request classifies to ``{ kind: "noop" }`` for
//      v0.2.0 (until real classification rules land).
//   2. The output discriminator routes correctly through an
//      exhaustive ``switch`` — the compile-time ``never`` guard
//      catches a missed variant in any future caller.
//   3. The function is side-effect-free: same input → same output,
//      no global state, no module-import side effects.
//
// Path: web/src/surface/__tests__/classifier.test.ts
import { describe, expect, test } from "vitest";

import {
  classifyWebSurfaceRequest,
  ClassifiedSurfaceAction,
  ClassifiedSurfaceActionKind,
} from "../classifier";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";


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


// ---------------------------------------------------------------------------
// 1. v0.2.0 behaviour — every request classifies to noop
// ---------------------------------------------------------------------------
describe("classifyWebSurfaceRequest — v0.2.0 default", () => {
  test("GET / classifies to noop", () => {
    const action = classifyWebSurfaceRequest(reqOf());
    expect(action.kind).toBe("noop");
  });

  test.each([
    "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
  ])("%s classifies to noop", (method) => {
    const action = classifyWebSurfaceRequest(reqOf({ method }));
    expect(action.kind).toBe("noop");
  });

  test.each([
    "/", "/foo", "/foo/bar", "/x?y=z", "/web-surface/v0.2/anything",
  ])("path %s classifies to noop", (path) => {
    const action = classifyWebSurfaceRequest(reqOf({ path }));
    expect(action.kind).toBe("noop");
  });

  test("request body content does not change classification (v0.2.0)", () => {
    const a = classifyWebSurfaceRequest(reqOf({ body: null }));
    const b = classifyWebSurfaceRequest(reqOf({ body: { x: 1 } }));
    const c = classifyWebSurfaceRequest(reqOf({ body: "text" }));
    expect(a.kind).toBe("noop");
    expect(b.kind).toBe("noop");
    expect(c.kind).toBe("noop");
  });

  test("request headers do not change classification (v0.2.0)", () => {
    const action = classifyWebSurfaceRequest(
      reqOf({ headers: { "x-trace": "abc", "user-agent": "spa" } }),
    );
    expect(action.kind).toBe("noop");
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
        return `render:${action.view}:${paramCount}`;
      }
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

  test("render variant routes (no params)", () => {
    const action: ClassifiedSurfaceAction = {
      kind: "render",
      view: "dashboard",
    };
    expect(describeAction(action)).toBe("render:dashboard:0");
  });

  test("render variant routes (with params)", () => {
    const action: ClassifiedSurfaceAction = {
      kind:   "render",
      view:   "operator",
      params: { id: "abc", verbose: true },
    };
    expect(describeAction(action)).toBe("render:operator:2");
  });

  test("ClassifiedSurfaceActionKind mirrors the union exactly", () => {
    expect(ClassifiedSurfaceActionKind.noop).toBe("noop");
    expect(ClassifiedSurfaceActionKind.render).toBe("render");
    // Set-equality: keys of the constants object == set of union kinds.
    expect(Object.keys(ClassifiedSurfaceActionKind).sort()).toEqual(
      ["noop", "render"],
    );
  });

  test("classifier output is a valid ClassifiedSurfaceAction shape", () => {
    const action = classifyWebSurfaceRequest(reqOf());
    // Must have ``kind`` field that's one of the documented values.
    expect(action).toHaveProperty("kind");
    expect(["noop", "render"]).toContain(action.kind);
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
      path: "/x", method: "GET",
      headers: { "x-trace": "abc" },
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
