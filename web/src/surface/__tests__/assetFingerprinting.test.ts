// Card A9 — asset fingerprinting + cache-safe URLs.
//
// Five contract surfaces under test:
//
//   1. Fingerprint generator (``assetFingerprint.ts``):
//      * Deterministic: same asset → same hash.
//      * Sensitive: different assets → different hashes.
//      * Hash width = FINGERPRINT_HEX_LENGTH (12 hex chars).
//      * Structure: ``base.<hash>.<ext>`` for normal pathnames.
//      * Throws on missing / malformed inputs (inherited from
//        the underlying loader).
//
//   2. Manifest (``assetManifest.ts``):
//      * First call populates the manifest entry.
//      * Subsequent calls return the cached fingerprint
//        reference (no re-hash).
//      * Reverse lookup resolves fingerprinted → original
//        whenever the forward entry has been populated.
//      * Reverse lookup returns ``null`` when no entry exists.
//      * Clear empties both directions in one shot.
//
//   3. Router (``assetRouter.ts``):
//      * Fingerprinted CSS URL serves CSS bytes (200).
//      * Fingerprinted JS URL serves JS bytes (200).
//      * Body for fingerprinted URL is byte-identical to body
//        for the original URL.
//      * Content-type is derived from the resolved original
//        (i.e. ``text/css`` for ``style.<hash>.css``).
//      * Unknown fingerprinted pattern → 404 + envelope.
//      * Original URLs continue to work (A8 backward-compat).
//
//   4. Template integration (``renderPipeline.ts`` + standard.html):
//      * ``buildAssetVars`` returns ``{ style_css, app_js }`` with
//        fingerprinted values.
//      * Rendered HTML for the home view contains the
//        fingerprinted ``<link>`` and ``<script>`` URLs.
//      * Rendered HTML does NOT contain the bare
//        ``style.css`` / ``app.js`` placeholders.
//      * No stray ``{{ ... }}`` placeholders survive in the
//        output.
//
//   5. Determinism + immutability:
//      * Same asset → same fingerprint across runs / across
//        manifest clears.
//      * Pipeline does not mutate the asset vars object
//        (subsequent renders see identical values).
//      * Manifest population does not corrupt the template
//        cache or layout cache.
//
// Path: web/src/surface/__tests__/assetFingerprinting.test.ts
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  fingerprintAsset,
  FINGERPRINT_HEX_LENGTH,
} from "../assetFingerprint";
import {
  getFingerprintedPath,
  resolveFingerprintedPath,
  clearAssetManifest,
  _listManifestForTests,
} from "../assetManifest";
import { routeAsset } from "../assetRouter";
import { clearAssetCache } from "../assetCache";
import { renderWebSurface } from "../renderer";
import { buildAssetVars } from "../renderPipeline";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import {
  clearTemplateCache,
  _listCachedTemplatesForTests,
} from "../templateCache";
import {
  clearLayoutCache,
  _listCachedLayoutsForTests,
} from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { homeView } from "../views/home";


// Hash-formed-the-task-card-way: 12 hex chars before the
// extension. Matches ``base.<12-hex>.ext`` exactly.
const _FINGERPRINTED_RE = /^(.+)\.([0-9a-f]{12})\.([^.]+)$/;


beforeEach(() => {
  // A9 introduces the manifest cache. The other caches (template,
  // layout, partial, asset, view registry) are cleared too so each
  // test starts from a clean room and can assert on first-touch
  // behaviour. Home is re-registered for the layout/template
  // integration tests.
  clearAssetManifest();
  clearAssetCache();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  _clearViewRegistryForTests();
  registerView("home", homeView);
});

afterEach(() => {
  clearAssetManifest();
  clearAssetCache();
  clearTemplateCache();
  clearLayoutCache();
  clearPartialCache();
  _clearViewRegistryForTests();
});


// ---------------------------------------------------------------------------
// 1. Fingerprint generator
// ---------------------------------------------------------------------------
describe("fingerprintAsset", () => {
  test("style.css → base.<12-hex>.css", () => {
    const fp = fingerprintAsset("style.css");
    expect(fp).toMatch(_FINGERPRINTED_RE);
    const m = fp.match(_FINGERPRINTED_RE);
    expect(m).not.toBeNull();
    expect(m![1]).toBe("style");
    expect(m![3]).toBe("css");
    expect(m![2].length).toBe(FINGERPRINT_HEX_LENGTH);
  });

  test("app.js → base.<12-hex>.js", () => {
    const fp = fingerprintAsset("app.js");
    expect(fp).toMatch(_FINGERPRINTED_RE);
    const m = fp.match(_FINGERPRINTED_RE);
    expect(m).not.toBeNull();
    expect(m![1]).toBe("app");
    expect(m![3]).toBe("js");
  });

  test("same asset → identical fingerprint (determinism)", () => {
    const a = fingerprintAsset("style.css");
    const b = fingerprintAsset("style.css");
    const c = fingerprintAsset("style.css");
    expect(a).toBe(b);
    expect(b).toBe(c);
  });

  test("different assets → different fingerprints", () => {
    const cssFp = fingerprintAsset("style.css");
    const jsFp  = fingerprintAsset("app.js");
    // Extract just the hash portions so we're comparing the
    // bytes-derived component, not the extension.
    const cssHash = cssFp.match(_FINGERPRINTED_RE)![2];
    const jsHash  = jsFp .match(_FINGERPRINTED_RE)![2];
    expect(cssHash).not.toBe(jsHash);
  });

  test("hash uses exactly FINGERPRINT_HEX_LENGTH lowercase hex chars", () => {
    const fp = fingerprintAsset("style.css");
    const hash = fp.match(_FINGERPRINTED_RE)![2];
    expect(hash.length).toBe(FINGERPRINT_HEX_LENGTH);
    expect(hash).toMatch(/^[0-9a-f]+$/);
  });

  test("FINGERPRINT_HEX_LENGTH constant equals 12 (locked contract)", () => {
    expect(FINGERPRINT_HEX_LENGTH).toBe(12);
  });

  test("throws on missing asset (loader contract preserved)", () => {
    expect(() => fingerprintAsset("does-not-exist.css")).toThrow();
  });

  test("throws on path traversal (loader contract preserved)", () => {
    expect(() => fingerprintAsset("../../../etc/passwd")).toThrow();
  });

  test("throws on empty pathname", () => {
    expect(() => fingerprintAsset("")).toThrow();
  });

  test("fingerprint is pure — does not populate the manifest", () => {
    // ``fingerprintAsset`` is independent from the manifest cache.
    // A bare call returns the hashed string without side-effects
    // on the manifest map.
    expect(_listManifestForTests()).toEqual({});
    fingerprintAsset("style.css");
    expect(_listManifestForTests()).toEqual({});
  });
});


// ---------------------------------------------------------------------------
// 2. Manifest behaviour
// ---------------------------------------------------------------------------
describe("assetManifest — forward map", () => {
  test("first call populates the manifest", () => {
    expect(_listManifestForTests()).toEqual({});
    const fp = getFingerprintedPath("style.css");
    expect(_listManifestForTests()).toEqual({ "style.css": fp });
  });

  test("second call returns the cached fingerprint (no re-compute)", () => {
    const first = getFingerprintedPath("style.css");
    const second = getFingerprintedPath("style.css");
    // Reference equality: a re-hash would allocate a fresh string
    // that compares equal by content but not by reference.
    expect(second).toBe(first);
  });

  test("forward fingerprint equals the pure fingerprint", () => {
    const viaManifest = getFingerprintedPath("style.css");
    const viaPure = fingerprintAsset("style.css");
    expect(viaManifest).toBe(viaPure);
  });

  test("multiple assets populate independently (no eviction)", () => {
    getFingerprintedPath("style.css");
    getFingerprintedPath("app.js");
    const snapshot = _listManifestForTests();
    expect(Object.keys(snapshot).sort()).toEqual(["app.js", "style.css"]);
  });

  test("clearAssetManifest empties the manifest", () => {
    getFingerprintedPath("style.css");
    getFingerprintedPath("app.js");
    expect(Object.keys(_listManifestForTests()).length).toBe(2);
    clearAssetManifest();
    expect(_listManifestForTests()).toEqual({});
  });

  test("failed forward lookup does not pollute the manifest", () => {
    expect(() => getFingerprintedPath("does-not-exist.css")).toThrow();
    expect(_listManifestForTests()).not.toHaveProperty("does-not-exist.css");
  });
});


describe("assetManifest — reverse map", () => {
  test("resolves fingerprinted → original after forward call", () => {
    const fp = getFingerprintedPath("style.css");
    expect(resolveFingerprintedPath(fp)).toBe("style.css");
  });

  test("returns null when the manifest holds no matching entry", () => {
    expect(resolveFingerprintedPath("style.abc123.css")).toBeNull();
  });

  test("returns null for the bare original pathname (asymmetric)", () => {
    // Reverse map maps fingerprinted → original; an UN-fingerprinted
    // string isn't a key on the reverse side, even when its forward
    // entry exists. The router falls back to passing the string
    // through unchanged in that case.
    getFingerprintedPath("style.css");
    expect(resolveFingerprintedPath("style.css")).toBeNull();
  });

  test("reverse stays in sync across multiple assets", () => {
    const cssFp = getFingerprintedPath("style.css");
    const jsFp  = getFingerprintedPath("app.js");
    expect(resolveFingerprintedPath(cssFp)).toBe("style.css");
    expect(resolveFingerprintedPath(jsFp)).toBe("app.js");
  });

  test("reverse map clears with the forward map", () => {
    const fp = getFingerprintedPath("style.css");
    expect(resolveFingerprintedPath(fp)).toBe("style.css");
    clearAssetManifest();
    expect(resolveFingerprintedPath(fp)).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// 3. Router — fingerprinted URL resolution
// ---------------------------------------------------------------------------
describe("routeAsset — fingerprinted URL resolution", () => {
  test("fingerprinted CSS URL → 200 + text/css + bytes", () => {
    const fp = getFingerprintedPath("style.css");
    const res = routeAsset(fp);
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/css");
    expect(Buffer.isBuffer(res.body)).toBe(true);
    expect((res.body as Buffer).toString("utf8")).toContain("font-family");
  });

  test("fingerprinted JS URL → 200 + application/javascript + bytes", () => {
    const fp = getFingerprintedPath("app.js");
    const res = routeAsset(fp);
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("application/javascript");
    // Card A19-R replaced the 1-line stub with the generated
    // progressive-enhancement bundle; match its banner.
    expect((res.body as Buffer).toString("utf8"))
      .toContain("ClarityOS v0.2 Web Surface");
  });

  test("fingerprinted body is byte-identical to original body", () => {
    const fp = getFingerprintedPath("style.css");
    const fromFp = routeAsset(fp);
    const fromRaw = routeAsset("style.css");
    expect((fromFp.body as Buffer).equals(fromRaw.body as Buffer)).toBe(true);
  });

  test("unrecognised fingerprinted pattern → 404", () => {
    // No entry in the manifest matches this string, and there is
    // no file ``style.deadbeef0000.css`` on disk — falls through
    // to the loader, which throws, and the router catches it.
    const res = routeAsset("style.deadbeef0000.css");
    expect(res.status).toBe(404);
    expect(res.headers["content-type"]).toBe("application/json");
    expect((res.body as any).error).toBe("asset_not_found");
    // The 404 envelope echoes the caller-provided pathname, not
    // the resolved one.
    expect((res.body as any).detail).toEqual({
      pathname: "style.deadbeef0000.css",
    });
  });

  test("original URL still works after fingerprinting (A8 back-compat)", () => {
    // Populating the manifest must NOT break direct loads.
    getFingerprintedPath("style.css");
    const res = routeAsset("style.css");
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toBe("text/css");
  });

  test("path traversal through a fake-fingerprinted URL still 404s", () => {
    const res = routeAsset("../../etc.deadbeef0000.passwd");
    expect(res.status).toBe(404);
    expect((res.body as any).error).toBe("asset_not_found");
  });

  test("router never throws on a fingerprinted-looking input", () => {
    expect(() => routeAsset("style.deadbeef0000.css")).not.toThrow();
    expect(() => routeAsset("")).not.toThrow();
  });
});


// ---------------------------------------------------------------------------
// 4. Template / render-pipeline integration
// ---------------------------------------------------------------------------
describe("renderPipeline — fingerprinted asset vars", () => {
  test("buildAssetVars returns style_css + app_js", () => {
    const vars = buildAssetVars();
    expect(Object.keys(vars).sort()).toEqual(["app_js", "style_css"]);
  });

  test("buildAssetVars values match the manifest's fingerprints", () => {
    const vars = buildAssetVars();
    expect(vars.style_css).toBe(getFingerprintedPath("style.css"));
    expect(vars.app_js).toBe(getFingerprintedPath("app.js"));
  });

  test("buildAssetVars values match the pure fingerprint output", () => {
    const vars = buildAssetVars();
    expect(vars.style_css).toBe(fingerprintAsset("style.css"));
    expect(vars.app_js).toBe(fingerprintAsset("app.js"));
  });

  test("home render embeds the fingerprinted CSS URL in <link>", async () => {
    const fpCss = getFingerprintedPath("style.css");
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).toContain(`/web-surface/v0.2/assets/${fpCss}`);
    expect(html).toMatch(
      new RegExp(
        `<link[^>]*href="/web-surface/v0\\.2/assets/${fpCss.replace(/\./g, "\\.")}"`,
      ),
    );
  });

  test("home render embeds the fingerprinted JS URL in <script>", async () => {
    const fpJs = getFingerprintedPath("app.js");
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).toContain(`/web-surface/v0.2/assets/${fpJs}`);
    expect(html).toMatch(
      new RegExp(
        `<script[^>]*src="/web-surface/v0\\.2/assets/${fpJs.replace(/\./g, "\\.")}"`,
      ),
    );
  });

  test("home render does NOT contain the bare style.css URL", async () => {
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).not.toContain('href="/web-surface/v0.2/assets/style.css"');
    expect(html).not.toContain('src="/web-surface/v0.2/assets/app.js"');
  });

  test("home render has no stray {{ ... }} placeholders", async () => {
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).not.toMatch(/{{\s*\w+\s*}}/);
  });

  test("custom view with layout=standard also gets fingerprinted URLs", async () => {
    registerView("custom-fingerprinted", {
      template: "base",
      layout:   "standard",
      async render() {
        return { title: "Cx", subtitle: "Sub", content: "body" };
      },
    });
    const fpCss = getFingerprintedPath("style.css");
    const out = await renderWebSurface({
      view: "custom-fingerprinted",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain(`/web-surface/v0.2/assets/${fpCss}`);
  });

  test("view-supplied vars override asset vars (view authority)", async () => {
    // If a view legitimately wants to pin its own style_css value,
    // the pipeline must not clobber it. Spread order in
    // renderPipeline puts view vars LAST, so the view wins.
    registerView("override-style", {
      template: "base",
      layout:   "standard",
      async render() {
        return {
          title:     "Override",
          subtitle:  "S",
          content:   "c",
          style_css: "override.css",
          app_js:    "override.js",
        };
      },
    });
    const out = await renderWebSurface({
      view: "override-style",
      mode: V.Mode.html,
    });
    const html = out.body as string;
    expect(html).toContain("/web-surface/v0.2/assets/override.css");
    expect(html).toContain("/web-surface/v0.2/assets/override.js");
  });
});


// ---------------------------------------------------------------------------
// 5. Determinism + immutability
// ---------------------------------------------------------------------------
describe("asset fingerprinting — determinism + immutability", () => {
  test("fingerprint stable across manifest clears (content addressed)", () => {
    const first = getFingerprintedPath("style.css");
    clearAssetManifest();
    const second = getFingerprintedPath("style.css");
    // Same string content (the fingerprint is a function of the
    // file bytes, not the manifest state). Reference identity is
    // NOT required across a clear — the Map allocates fresh.
    expect(second).toEqual(first);
  });

  test("home render is byte-identical across runs", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await renderWebSurface({ view: "home", mode: V.Mode.html });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("router output for the same fingerprinted URL is structurally identical", () => {
    const fp = getFingerprintedPath("style.css");
    const a = routeAsset(fp);
    const b = routeAsset(fp);
    expect(a.status).toBe(b.status);
    expect(a.headers).toEqual(b.headers);
    expect((a.body as Buffer).equals(b.body as Buffer)).toBe(true);
  });

  test("buildAssetVars returns a fresh object each call (no shared mutation surface)", () => {
    const a = buildAssetVars();
    const b = buildAssetVars();
    // Same content, different object identity. If the pipeline
    // returned a shared object, a view could mutate it and poison
    // every subsequent render.
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });

  test("rendering does not mutate the manifest after first population", async () => {
    // First render populates style.css + app.js in the manifest.
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    const snapshot = { ..._listManifestForTests() };

    // Three more renders — no new entries, no changed values.
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    await renderWebSurface({ view: "home", mode: V.Mode.html });

    expect(_listManifestForTests()).toEqual(snapshot);
  });

  test("rendering does not corrupt the template / layout caches", async () => {
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    const templates = _listCachedTemplatesForTests().slice();
    const layouts   = _listCachedLayoutsForTests().slice();

    // Render again — caches must be additive, not overwritten /
    // duplicated by the asset-var injection.
    await renderWebSurface({ view: "home", mode: V.Mode.html });
    expect(_listCachedTemplatesForTests().slice()).toEqual(templates);
    expect(_listCachedLayoutsForTests().slice()).toEqual(layouts);
  });
});
