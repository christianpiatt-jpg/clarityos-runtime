// Structural tests for the v0.2.0 Web Surface boundary contract.
//
// These tests do not exercise any runtime behaviour — the contract
// module is pure types + small const objects. We assert three things:
//
//   1. The module loads without side effects (no top-level work).
//   2. The SurfaceAction discriminated union narrows correctly when
//      switching on `type`.
//   3. The ErrorEnvelope shape is stable (the `error` field is
//      required + string-typed; `detail` is optional).
//
// Path: web/src/contracts/__tests__/webSurfaceV0_2.test.ts
import { describe, expect, test } from "vitest";

import { WebSurfaceV0_2 } from "../webSurfaceV0_2";


describe("WebSurfaceV0_2 — module shape", () => {
  test("loads without side effects (re-import is idempotent)", async () => {
    // A pure type module has no runtime state. Re-importing should
    // return the same namespace bag.
    const first = await import("../webSurfaceV0_2");
    const second = await import("../webSurfaceV0_2");
    expect(first).toBe(second);
  });

  test("exposes the version pin", () => {
    expect(WebSurfaceV0_2.VERSION).toBe("v0.2.0");
  });

  test("SurfaceActionType discriminators mirror the union", () => {
    expect(WebSurfaceV0_2.SurfaceActionType.noop).toBe("noop");
    expect(WebSurfaceV0_2.SurfaceActionType.render).toBe("render");
    expect(WebSurfaceV0_2.SurfaceActionType.navigate).toBe("navigate");
  });
});


describe("WebSurfaceV0_2.SurfaceAction — discriminated union", () => {
  // A small reducer-style helper that exercises every variant of the
  // discriminated union. The exhaustive switch + `never` default is
  // the canonical pattern for "missing variant becomes a compile
  // error"; at runtime we just confirm each variant routes correctly.
  function describeAction(action: WebSurfaceV0_2.SurfaceAction): string {
    switch (action.type) {
      case WebSurfaceV0_2.SurfaceActionType.noop:
        return "noop";
      case WebSurfaceV0_2.SurfaceActionType.render: {
        const paramCount = action.params
          ? Object.keys(action.params).length
          : 0;
        return `render:${action.view}:${paramCount}`;
      }
      case WebSurfaceV0_2.SurfaceActionType.navigate:
        return `navigate:${action.path}`;
      default: {
        // If a new variant is ever added without updating this
        // switch, TypeScript turns `action` into `never` here and
        // the compile fails. Defence-in-depth runtime fallthrough.
        const _exhaustive: never = action;
        return _exhaustive;
      }
    }
  }

  test("noop variant narrows + routes", () => {
    const action: WebSurfaceV0_2.SurfaceAction = { type: "noop" };
    expect(describeAction(action)).toBe("noop");
  });

  test("render variant narrows + routes (no params)", () => {
    const action: WebSurfaceV0_2.SurfaceAction = {
      type:   "render",
      view:   "dashboard",
    };
    expect(describeAction(action)).toBe("render:dashboard:0");
  });

  test("render variant narrows + routes (with params)", () => {
    const action: WebSurfaceV0_2.SurfaceAction = {
      type:   "render",
      view:   "operator",
      params: { id: "abc", verbose: true },
    };
    expect(describeAction(action)).toBe("render:operator:2");
  });

  test("navigate variant narrows + routes", () => {
    const action: WebSurfaceV0_2.SurfaceAction = {
      type: "navigate",
      path: "/founder",
    };
    expect(describeAction(action)).toBe("navigate:/founder");
  });

  test("returns string for every variant in a sample sweep", () => {
    const samples: WebSurfaceV0_2.SurfaceAction[] = [
      { type: "noop" },
      { type: "render", view: "x" },
      { type: "render", view: "y", params: { a: 1 } },
      { type: "navigate", path: "/" },
    ];
    for (const a of samples) {
      const out = describeAction(a);
      expect(typeof out).toBe("string");
      expect(out.length).toBeGreaterThan(0);
    }
  });
});


describe("WebSurfaceV0_2.ErrorEnvelope — shape stability", () => {
  test("required `error` field accepts a string code", () => {
    const env: WebSurfaceV0_2.ErrorEnvelope = { error: "not_implemented" };
    expect(env.error).toBe("not_implemented");
    expect(env.detail).toBeUndefined();
  });

  test("optional `detail` field accepts an arbitrary payload", () => {
    const env: WebSurfaceV0_2.ErrorEnvelope = {
      error:  "validation_failed",
      detail: { field: "username", reason: "too_short" },
    };
    expect(env.error).toBe("validation_failed");
    expect(env.detail).toEqual({ field: "username", reason: "too_short" });
  });

  test("envelope serialises to JSON without losing fields", () => {
    const env: WebSurfaceV0_2.ErrorEnvelope = {
      error:  "unauthorized",
      detail: { hint: "session expired" },
    };
    const round = JSON.parse(JSON.stringify(env));
    expect(round).toEqual(env);
  });
});


describe("WebSurfaceV0_2 — Request / Response envelope", () => {
  // Type-level smoke: build minimal Request + Response objects and
  // confirm the field set is what the contract documents. Catches
  // accidental rename in a future refactor.
  test("Request fields are present and typed", () => {
    const req: WebSurfaceV0_2.Request = {
      path:    "/",
      method:  "GET",
      headers: { "x-trace": "abc" },
      body:    null,
    };
    expect(req.path).toBe("/");
    expect(req.method).toBe("GET");
    expect(req.headers).toEqual({ "x-trace": "abc" });
    expect(req.body).toBeNull();
  });

  test("Response fields are present and typed", () => {
    const res: WebSurfaceV0_2.Response = {
      status:  501,
      headers: { "content-type": "application/json" },
      body:    { error: "not_implemented" } satisfies WebSurfaceV0_2.ErrorEnvelope,
    };
    expect(res.status).toBe(501);
    expect(res.headers["content-type"]).toBe("application/json");
    expect((res.body as WebSurfaceV0_2.ErrorEnvelope).error).toBe("not_implemented");
  });
});
