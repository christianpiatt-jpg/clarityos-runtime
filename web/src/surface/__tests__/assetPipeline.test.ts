// Card A8 — static asset pipeline tests.
//
// Five contract surfaces under test:
//
//   1. Asset loader (``assetLoader.ts``):
//      * Loads style.css, app.js as Buffers.
//      * Throws on missing asset.
//      * Throws on path-traversal attempts (``..``, absolute path).
//
//   2. Asset cache (``assetCache.ts``):
//      * First load reads + caches.
//      * Second load returns same Buffer reference.
//      * clearAssetCache empties.
//      * Failed loads do NOT pollute the cache.
//
//   3. Content-type detection (``assetRouter.contentTypeFor``):
//      * Known extensions map correctly (css/js/png/jpg/svg/etc.).
//      * Unknown extension → application/octet-stream.
//      * No extension → application/octet-stream.
//
//   4. Router (``assetRouter.routeAsset``):
//      * Valid asset → 200 + correct content-type + Buffer body.
//      * Missing asset → 404 + JSON envelope.
//      * Path traversal → 404 (never 5xx, never throws).
//
//   5. Surface router integration:
//      * ``/web-surface/v0.2/assets/style.css`` short-circuits
//        the classifier and serves the CSS.
//      * Non-asset paths flow through to the classifier/renderer
//        as before (no regression).
//
// Path: web/src/surface/__tests__/assetPipeline.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { loadAsset, _resolveAssetPath, ASSETS_DIR } from "../assetLoader";
import {
  loadCachedAsset,
  clearAssetCache,
  _listCachedAssetsForTests,
  _getCachedAssetForTests,
} from "../assetCache";
import { contentTypeFor, routeAsset } from "../assetRouter";
import { routeWebSurface } from "../router";
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "../viewContract";


beforeEach(() => clearAssetCache());
afterEach(() => clearAssetCache());


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
// 1. Asset loader
// ---------------------------------------------------------------------------
describe("assetLoader", () => {
  test("loads style.css as a Buffer", () => {
    const body = loadAsset("style.css");
    expect(Buffer.isBuffer(body)).toBe(true);
    expect(body.toString("utf8")).toContain("font-family");
  });

  test("loads app.js as a Buffer", () => {
    const body = loadAsset("app.js");
    expect(Buffer.isBuffer(body)).toBe(true);
    expect(body.toString("utf8")).toContain("Web Surface v0.2.0 loaded");
  });

  test("throws on a missing asset name", () => {
    expect(() => loadAsset("does-not-exist.css")).toThrow();
  });

  test("ASSETS_DIR is anchored to web/assets/v0.2", () => {
    const normalised = ASSETS_DIR.replace(/\\/g, "/");
    expect(normalised).toContain("/web/assets/v0.2");
  });

  // ----- Path traversal protection -----
  test("rejects absolute path (Unix-style)", () => {
    expect(() => loadAsset("/etc/passwd")).toThrow(/absolute/i);
  });

  test("rejects path with .. segments that escape the assets dir", () => {
    expect(() => loadAsset("../../../etc/passwd")).toThrow(/escape/i);
  });

  test("rejects path with embedded .. that escapes via normalisation", () => {
    expect(() => loadAsset("style.css/../../../etc/passwd")).toThrow(/escape/i);
  });

  test("accepts a subdirectory pathname that stays inside ASSETS_DIR", () => {
    // A `..` that NORMALISES to staying inside is fine — e.g.
    // `subdir/../style.css` → `style.css`.
    expect(() => loadAsset("subdir/../style.css")).not.toThrow();
  });

  test("rejects empty pathname", () => {
    expect(() => loadAsset("")).toThrow();
  });

  test("_resolveAssetPath exported helper is consistent", () => {
    const resolved = _resolveAssetPath("style.css");
    expect(resolved.endsWith("style.css")).toBe(true);
    const normalised = resolved.replace(/\\/g, "/");
    expect(normalised).toContain("/web/assets/v0.2/style.css");
  });
});


// ---------------------------------------------------------------------------
// 2. Asset cache
// ---------------------------------------------------------------------------
describe("assetCache", () => {
  test("first load populates the cache", () => {
    expect(_listCachedAssetsForTests()).toEqual([]);
    loadCachedAsset("style.css");
    expect(_listCachedAssetsForTests()).toEqual(["style.css"]);
  });

  test("second load returns the same Buffer reference", () => {
    loadCachedAsset("style.css");
    const cached = _getCachedAssetForTests("style.css");
    const second = loadCachedAsset("style.css");
    expect(second).toBe(cached);
  });

  test("clearAssetCache empties the cache", () => {
    loadCachedAsset("style.css");
    loadCachedAsset("app.js");
    expect(_listCachedAssetsForTests().sort()).toEqual(["app.js", "style.css"]);
    clearAssetCache();
    expect(_listCachedAssetsForTests()).toEqual([]);
  });

  test("failed load does not pollute the cache", () => {
    expect(() => loadCachedAsset("does-not-exist.css")).toThrow();
    expect(_listCachedAssetsForTests()).not.toContain("does-not-exist.css");
  });

  test("failed load (path traversal) does not pollute the cache", () => {
    expect(() => loadCachedAsset("../../../etc/passwd")).toThrow();
    expect(_listCachedAssetsForTests()).not.toContain("../../../etc/passwd");
  });
});


// ---------------------------------------------------------------------------
// 3. Content-type detection
// ---------------------------------------------------------------------------
describe("contentTypeFor", () => {
  test.each([
    ["style.css",     "text/css"],
    ["app.js",        "application/javascript"],
    ["logo.png",      "image/png"],
    ["photo.jpg",     "image/jpeg"],
    ["photo.jpeg",    "image/jpeg"],
    ["icon.svg",      "image/svg+xml"],
    ["favicon.ico",   "image/x-icon"],
    ["font.woff",     "font/woff"],
    ["font.woff2",    "font/woff2"],
    ["manifest.json", "application/json"],
  ])("%s → %s", (pathname, expected) => {
    expect(contentTypeFor(pathname)).toBe(expected);
  });

  test("case-insensitive extension matching", () => {
    expect(contentTypeFor("STYLE.CSS")).toBe("text/css");
    expect(contentTypeFor("App.JS")).toBe("application/javascript");
  });

  test("unknown extension → application/octet-stream", () => {
    expect(contentTypeFor("file.xyz")).toBe("application/octet-stream");
  });

  test("no extension → application/octet-stream", () => {
    expect(contentTypeFor("noext")).toBe("application/octet-stream");
  });

  test("trailing dot → application/octet-stream", () => {
    expect(contentTypeFor("file.")).toBe("application/octet-stream");
  });
});


// ---------------------------------------------------------------------------
// 4. Asset router
// ---------------------------------------------------------------------------
describe("routeAsset", () => {
  test("style.css → 200 + text/css + bytes", () => {
    const res = routeAsset("style.css");
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/css");
    expect(Buffer.isBuffer(res.body)).toBe(true);
    expect((res.body as Buffer).toString("utf8")).toContain("font-family");
  });

  test("app.js → 200 + application/javascript + bytes", () => {
    const res = routeAsset("app.js");
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/javascript");
    expect((res.body as Buffer).toString("utf8")).toContain("Web Surface v0.2.0 loaded");
  });

  test("missing asset → 404 + JSON envelope", () => {
    const res = routeAsset("does-not-exist.css");
    expect(res.status).toBe(404);
    expect(res.headers["content-type"]).toBe("application/json");
    expect(res.body).toEqual({
      error:  "asset_not_found",
      detail: { pathname: "does-not-exist.css" },
    });
  });

  test("path traversal → 404 (never throws, never 5xx)", () => {
    const res = routeAsset("../../../etc/passwd");
    expect(res.status).toBe(404);
    expect(res.headers["content-type"]).toBe("application/json");
    expect((res.body as any).error).toBe("asset_not_found");
  });

  test("absolute path → 404 (never throws)", () => {
    const res = routeAsset("/etc/passwd");
    expect(res.status).toBe(404);
    expect((res.body as any).error).toBe("asset_not_found");
  });

  test("router never throws on bad input", () => {
    // Defensive — every malformed input should produce a 404
    // envelope rather than propagating an exception.
    expect(() => routeAsset("")).not.toThrow();
    const res = routeAsset("");
    expect(res.status).toBe(404);
  });
});


// ---------------------------------------------------------------------------
// 5. Surface router integration — short-circuit before classifier
// ---------------------------------------------------------------------------
describe("surface router — asset short-circuit", () => {
  test("/web-surface/v0.2/assets/style.css → CSS bytes (200)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/style.css",
      method: "GET",
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/css");
    expect((res.body as Buffer).toString("utf8")).toContain("font-family");
  });

  test("/web-surface/v0.2/assets/app.js → JS bytes (200)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/app.js",
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/javascript");
  });

  test("/web-surface/v0.2/assets/missing.css → 404 envelope (router-level catch)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/missing.css",
    }));
    expect(res.status).toBe(404);
    expect((res.body as any).error).toBe("asset_not_found");
  });

  test("/web-surface/v0.2/assets/../../etc/passwd → 404 (traversal blocked)", async () => {
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/../../etc/passwd",
    }));
    expect(res.status).toBe(404);
    expect((res.body as any).error).toBe("asset_not_found");
  });

  test("non-asset paths flow through to the classifier (no regression)", async () => {
    // ``/home`` doesn't start with the assets prefix; should go
    // through classifier → renderer → 200 HTML (default).
    const res = await routeWebSurface(reqOf({
      path: "/home",
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("root path / flows through to the renderer (asset prefix is exact)", async () => {
    const res = await routeWebSurface(reqOf({ path: "/" }));
    expect(res.status).toBe(200);
    // HTML default — not application/json or text/css.
    expect(res.headers["content-type"]).toBe("text/html; charset=utf-8");
  });

  test("asset prefix is honoured for POST requests too", async () => {
    // Asset short-circuit is path-based, method-agnostic.
    const res = await routeWebSurface(reqOf({
      path: "/web-surface/v0.2/assets/style.css",
      method: "POST",
    }));
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/css");
  });
});


// ---------------------------------------------------------------------------
// 6. Determinism
// ---------------------------------------------------------------------------
describe("asset pipeline — determinism", () => {
  test("same asset → identical bytes across reads", () => {
    const a = loadAsset("style.css");
    const b = loadAsset("style.css");
    expect(a.equals(b)).toBe(true);
  });

  test("cached asset is reference-identical across multiple reads", () => {
    const a = loadCachedAsset("style.css");
    const b = loadCachedAsset("style.css");
    const c = loadCachedAsset("style.css");
    expect(b).toBe(a);
    expect(c).toBe(a);
  });

  test("router output for the same asset is structurally identical", () => {
    const a = routeAsset("style.css");
    const b = routeAsset("style.css");
    expect(a.status).toBe(b.status);
    expect(a.headers).toEqual(b.headers);
    expect((a.body as Buffer).equals(b.body as Buffer)).toBe(true);
  });
});
