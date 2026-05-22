// Card A2 — tests for the v0.2.0 view resolution layer.
//
// The resolver is pure: same Request in → same ResolvedView out,
// no side effects. These tests lock four contract surfaces:
//
//   1. Mode selection — Accept header / ?mode= query / default
//      precedence, with edge cases (multiple Accept values, mixed
//      casing, ?mode=html as a no-op for the default path).
//   2. View name extraction — last non-empty path segment with
//      ``"index"`` fallback for empty paths.
//   3. Param extraction — querystring → string-valued record,
//      with the resolver's own ``mode`` key stripped.
//   4. Determinism — same input twice → identical output; input
//      Request is not mutated; re-import is idempotent.
//
// Path: web/src/surface/__tests__/viewResolution.test.ts
import { describe, expect, test } from "vitest";

import { resolveView, ResolvedView } from "../viewResolution";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "../viewContract";


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
// 1. Mode selection
// ---------------------------------------------------------------------------
describe("resolveView — mode selection", () => {
  test("Accept: application/json → mode = json", () => {
    const out = resolveView(reqOf({
      headers: { accept: "application/json" },
    }));
    expect(out.mode).toBe(V.Mode.json);
  });

  test("Accept containing application/json among others → mode = json", () => {
    // RFC 7231 quality-value parsing is out of scope for the
    // skeleton; substring match is sufficient.
    const out = resolveView(reqOf({
      headers: { accept: "text/html, application/json;q=0.9" },
    }));
    expect(out.mode).toBe(V.Mode.json);
  });

  test("?mode=json query → mode = json", () => {
    const out = resolveView(reqOf({ path: "/home?mode=json" }));
    expect(out.mode).toBe(V.Mode.json);
  });

  test("?mode=json overrides Accept: text/html", () => {
    const out = resolveView(reqOf({
      path:    "/home?mode=json",
      headers: { accept: "text/html" },
    }));
    expect(out.mode).toBe(V.Mode.json);
  });

  test("default (no Accept, no ?mode=) → mode = html", () => {
    const out = resolveView(reqOf({ path: "/home" }));
    expect(out.mode).toBe(V.Mode.html);
  });

  test("Accept: text/html → mode = html", () => {
    const out = resolveView(reqOf({
      headers: { accept: "text/html" },
    }));
    expect(out.mode).toBe(V.Mode.html);
  });

  test("?mode=html is a no-op (default is html)", () => {
    const out = resolveView(reqOf({ path: "/home?mode=html" }));
    expect(out.mode).toBe(V.Mode.html);
  });

  test("?mode=anything-else → mode = html (only ``json`` enables JSON)", () => {
    const out = resolveView(reqOf({ path: "/home?mode=xml" }));
    expect(out.mode).toBe(V.Mode.html);
  });

  test("missing Accept header → mode = html", () => {
    const out = resolveView(reqOf({ headers: {} }));
    expect(out.mode).toBe(V.Mode.html);
  });
});


// ---------------------------------------------------------------------------
// 2. View name extraction
// ---------------------------------------------------------------------------
describe("resolveView — view name extraction", () => {
  test.each([
    ["/web-surface/v0.2/home",       "home"],
    ["/web-surface/v0.2/dashboard",  "dashboard"],
    ["/web-surface/v0.2/foo/bar",    "bar"],
    ["/web-surface/v0.2/a/b/c/d",    "d"],
    ["/home",                        "home"],
    ["/just-one",                    "just-one"],
  ])("path %s → view %s", (path, expected) => {
    const out = resolveView(reqOf({ path }));
    expect(out.view).toBe(expected);
  });

  test("trailing slash drops empty segment (/web-surface/v0.2/ → v0.2)", () => {
    const out = resolveView(reqOf({ path: "/web-surface/v0.2/" }));
    expect(out.view).toBe("v0.2");
  });

  test("empty path (just /) falls back to 'index'", () => {
    const out = resolveView(reqOf({ path: "/" }));
    expect(out.view).toBe("index");
  });

  test("path with querystring isolates the path for view extraction", () => {
    const out = resolveView(reqOf({ path: "/dashboard?id=abc" }));
    expect(out.view).toBe("dashboard");
  });

  test("multiple consecutive slashes are ignored (filter Boolean)", () => {
    const out = resolveView(reqOf({ path: "/a//b" }));
    expect(out.view).toBe("b");
  });
});


// ---------------------------------------------------------------------------
// 3. Param extraction
// ---------------------------------------------------------------------------
describe("resolveView — param extraction", () => {
  test("?a=1&b=2 → { a: '1', b: '2' }", () => {
    const out = resolveView(reqOf({ path: "/x?a=1&b=2" }));
    expect(out.params).toEqual({ a: "1", b: "2" });
  });

  test("?mode=json&a=1 → params strip ``mode`` (it's a resolver knob)", () => {
    const out = resolveView(reqOf({ path: "/x?mode=json&a=1" }));
    expect(out.params).toEqual({ a: "1" });
  });

  test("no querystring → params = {}", () => {
    const out = resolveView(reqOf({ path: "/x" }));
    expect(out.params).toEqual({});
  });

  test("querystring with only mode → params = {}", () => {
    const out = resolveView(reqOf({ path: "/x?mode=json" }));
    expect(out.params).toEqual({});
  });

  test("repeated keys keep the last value (URL standard behavior)", () => {
    // URLSearchParams entries() iterates each occurrence; the
    // reducer-style assignment in resolveView overwrites — last
    // value wins.
    const out = resolveView(reqOf({ path: "/x?a=1&a=2&a=3" }));
    expect(out.params).toEqual({ a: "3" });
  });

  test("URL-encoded values are decoded", () => {
    const out = resolveView(reqOf({ path: "/x?msg=hello%20world" }));
    expect(out.params).toEqual({ msg: "hello world" });
  });

  test("params are always string-valued (no coercion)", () => {
    const out = resolveView(reqOf({ path: "/x?n=42&flag=true" }));
    expect(out.params).toEqual({ n: "42", flag: "true" });
    expect(typeof out.params.n).toBe("string");
    expect(typeof out.params.flag).toBe("string");
  });
});


// ---------------------------------------------------------------------------
// 4. Determinism / purity / no side effects
// ---------------------------------------------------------------------------
describe("resolveView — purity", () => {
  test("same input → same output (referential determinism)", () => {
    const req = reqOf({
      path: "/dashboard?a=1&b=2",
      headers: { accept: "application/json" },
    });
    const a = resolveView(req);
    const b = resolveView(req);
    expect(a).toEqual(b);
  });

  test("does not mutate the input request", () => {
    const req = reqOf({
      path: "/x?a=1",
      headers: { accept: "application/json" },
    });
    const frozen = JSON.stringify(req);
    resolveView(req);
    expect(JSON.stringify(req)).toBe(frozen);
  });

  test("module re-import is idempotent", async () => {
    const first = await import("../viewResolution");
    const second = await import("../viewResolution");
    expect(first).toBe(second);
  });

  test("output shape matches ResolvedView contract", () => {
    const out: ResolvedView = resolveView(reqOf({ path: "/x?a=1" }));
    expect(Object.keys(out).sort()).toEqual(["mode", "params", "view"]);
    expect(typeof out.view).toBe("string");
    expect(["html", "json"]).toContain(out.mode);
    expect(typeof out.params).toBe("object");
  });
});


// ---------------------------------------------------------------------------
// 5. End-to-end combined scenarios
// ---------------------------------------------------------------------------
describe("resolveView — end-to-end scenarios", () => {
  test("rich request: path + query + Accept all resolve correctly", () => {
    const out = resolveView(reqOf({
      path:    "/web-surface/v0.2/dashboard?id=abc&filter=open&mode=json",
      headers: { accept: "text/html" },  // overridden by ?mode=json
    }));
    expect(out.view).toBe("dashboard");
    expect(out.mode).toBe(V.Mode.json);
    expect(out.params).toEqual({ id: "abc", filter: "open" });
  });

  test("bare root request: defaults across all three fields", () => {
    const out = resolveView(reqOf());
    expect(out.view).toBe("index");
    expect(out.mode).toBe(V.Mode.html);
    expect(out.params).toEqual({});
  });
});
