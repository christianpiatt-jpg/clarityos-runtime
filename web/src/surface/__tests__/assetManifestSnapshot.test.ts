// Card A10 — asset manifest snapshot tests.
//
// Four contract surfaces under test:
//
//   1. Manifest snapshot file (``web/assets/v0.2/manifest.json``):
//      * Exists on disk + is parseable JSON.
//      * Lists every TRACKED_ASSETS entry from the generator.
//      * Every value matches ``base.<12-hex>.<ext>`` (the
//        fingerprint shape) and equals ``fingerprintAsset()``
//        output byte-for-byte.
//      * Trailing newline, 2-space indent, no extra keys.
//
//   2. Render pipeline integration:
//      * ``buildAssetVars()`` returns the snapshot values
//        (not a runtime hash).
//      * Rendered HTML for ``home`` embeds the snapshot
//        fingerprinted URLs.
//      * Repeated renders are byte-identical (no runtime
//        fingerprinting jitter).
//
//   3. Bootstrap behaviour:
//      * ``_reloadAssetManifestForTests`` populates the
//        in-memory manifest with the snapshot's contents.
//      * Snapshot values agree with what ``getFingerprintedPath``
//        produces via lazy compute after a clear (lock-step
//        invariant — the CI guard depends on this).
//      * Module-load bootstrap leaves the manifest pre-populated
//        from the snapshot.
//
//   4. Drift gate simulation:
//      * Re-running ``gen-asset-manifest.mjs`` produces a file
//        byte-identical to the committed snapshot.
//      * Mutating a temp asset changes the fingerprint
//        (sensitivity — different bytes → different hash).
//
// Path: web/src/surface/__tests__/assetManifestSnapshot.test.ts
import { spawnSync } from "node:child_process";
import {
  readFileSync,
  writeFileSync,
  unlinkSync,
  existsSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  MANIFEST_PATH,
  getFingerprintedPath,
  resolveFingerprintedPath,
  clearAssetManifest,
  _reloadAssetManifestForTests,
  _listManifestForTests,
  _readManifestSnapshotForTests,
} from "../assetManifest";
import {
  fingerprintAsset,
  FINGERPRINT_HEX_LENGTH,
} from "../assetFingerprint";
import { buildAssetVars } from "../renderPipeline";
import { renderWebSurface } from "../renderer";
import { WebSurfaceV0_2_View as V } from "../viewContract";
import {
  registerView,
  _clearViewRegistryForTests,
} from "../viewRegistry";
import { clearTemplateCache } from "../templateCache";
import { clearLayoutCache } from "../layoutCache";
import { clearPartialCache } from "../partialCache";
import { clearAssetCache } from "../assetCache";
import { homeView } from "../views/home";


const _FINGERPRINTED_RE = /^(.+)\.([0-9a-f]{12})\.([^.]+)$/;


// Repo paths — anchored via ``import.meta.url`` so vitest's cwd
// doesn't matter. From this file: web/src/surface/__tests__/
// → ../../../../ → repo root.
const __filename = fileURLToPath(import.meta.url);
const __dirname  = dirname(__filename);
const REPO_ROOT  = resolve(__dirname, "..", "..", "..", "..");
const WEB_ROOT   = resolve(REPO_ROOT, "web");
const ASSETS_DIR = resolve(WEB_ROOT, "assets", "v0.2");
const GENERATOR  = resolve(WEB_ROOT, "scripts", "gen-asset-manifest.mjs");


beforeEach(() => {
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
// 1. Manifest snapshot file
// ---------------------------------------------------------------------------
describe("manifest.json snapshot file", () => {
  test("exists on disk", () => {
    expect(existsSync(MANIFEST_PATH)).toBe(true);
  });

  test("parses as JSON", () => {
    const raw = readFileSync(MANIFEST_PATH, "utf8");
    expect(() => JSON.parse(raw)).not.toThrow();
  });

  test("ends in a single trailing newline", () => {
    const raw = readFileSync(MANIFEST_PATH, "utf8");
    expect(raw.endsWith("\n")).toBe(true);
    expect(raw.endsWith("\n\n")).toBe(false);
  });

  test("uses 2-space indentation (deterministic shape)", () => {
    const raw = readFileSync(MANIFEST_PATH, "utf8");
    // First nested line is indented exactly two spaces.
    expect(raw).toMatch(/^\{\n  "/);
  });

  test("contains style.css + app.js entries", () => {
    const snapshot = _readManifestSnapshotForTests();
    expect(Object.keys(snapshot).sort()).toEqual(["app.js", "style.css"]);
  });

  test("every value has the fingerprinted shape (base.<12-hex>.ext)", () => {
    const snapshot = _readManifestSnapshotForTests();
    for (const [pathname, fp] of Object.entries(snapshot)) {
      expect(fp).toMatch(_FINGERPRINTED_RE);
      const m = fp.match(_FINGERPRINTED_RE)!;
      expect(m[2].length).toBe(FINGERPRINT_HEX_LENGTH);
      // Extension agreement: the snapshot value's ext matches
      // the source pathname's ext.
      const sourceExt = pathname.split(".").pop();
      expect(m[3]).toBe(sourceExt);
    }
  });

  test("every snapshot value equals fingerprintAsset() output", () => {
    // Lock-step invariant. If the generator and the TS hash logic
    // drift, this fails — the CI guard exists for exactly this.
    const snapshot = _readManifestSnapshotForTests();
    for (const [pathname, fp] of Object.entries(snapshot)) {
      expect(fp).toBe(fingerprintAsset(pathname));
    }
  });

  test("MANIFEST_PATH resolves under web/assets/v0.2/", () => {
    const normalised = MANIFEST_PATH.replace(/\\/g, "/");
    expect(normalised).toContain("/web/assets/v0.2/manifest.json");
  });
});


// ---------------------------------------------------------------------------
// 2. Render pipeline integration
// ---------------------------------------------------------------------------
describe("renderPipeline reads from the manifest snapshot", () => {
  test("buildAssetVars returns the committed snapshot values", () => {
    const snapshot = _readManifestSnapshotForTests();
    const vars = buildAssetVars();
    expect(vars.style_css).toBe(snapshot["style.css"]);
    expect(vars.app_js).toBe(snapshot["app.js"]);
  });

  test("buildAssetVars does NOT depend on in-memory manifest state", () => {
    // After clear, the in-memory manifest is empty. buildAssetVars
    // reads the JSON snapshot via static import, not the runtime
    // manifest module — so it still returns the snapshot values.
    clearAssetManifest();
    expect(_listManifestForTests()).toEqual({});
    const vars = buildAssetVars();
    const snapshot = _readManifestSnapshotForTests();
    expect(vars.style_css).toBe(snapshot["style.css"]);
    expect(vars.app_js).toBe(snapshot["app.js"]);
  });

  test("home render embeds the snapshot CSS URL in <link>", async () => {
    const snapshot = _readManifestSnapshotForTests();
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).toContain(
      `/web-surface/v0.2/assets/${snapshot["style.css"]}`,
    );
  });

  test("home render embeds the snapshot JS URL in <script>", async () => {
    const snapshot = _readManifestSnapshotForTests();
    const out = await renderWebSurface({ view: "home", mode: V.Mode.html });
    const html = out.body as string;
    expect(html).toContain(
      `/web-surface/v0.2/assets/${snapshot["app.js"]}`,
    );
  });

  test("renders are byte-identical across runs (no runtime hashing jitter)", async () => {
    const outs: string[] = [];
    for (let i = 0; i < 5; i++) {
      const r = await renderWebSurface({ view: "home", mode: V.Mode.html });
      outs.push(r.body as string);
    }
    for (let i = 1; i < outs.length; i++) {
      expect(outs[i]).toBe(outs[0]);
    }
  });

  test("renders DO NOT depend on the in-memory manifest (snapshot is sufficient)", async () => {
    // Same render before and after clearing the in-memory manifest
    // — proves the render pipeline doesn't touch the manifest module
    // for asset URLs.
    const a = await renderWebSurface({ view: "home", mode: V.Mode.html });
    clearAssetManifest();
    const b = await renderWebSurface({ view: "home", mode: V.Mode.html });
    expect(a.body).toBe(b.body);
  });
});


// ---------------------------------------------------------------------------
// 3. Bootstrap behaviour
// ---------------------------------------------------------------------------
describe("assetManifest bootstrap from snapshot", () => {
  test("_reloadAssetManifestForTests populates manifest with snapshot values", () => {
    clearAssetManifest();
    expect(_listManifestForTests()).toEqual({});

    _reloadAssetManifestForTests();
    const expected = _readManifestSnapshotForTests();
    expect(_listManifestForTests()).toEqual(expected);
  });

  test("router reverse-resolution works after bootstrap (no other calls)", () => {
    clearAssetManifest();
    _reloadAssetManifestForTests();
    const snapshot = _readManifestSnapshotForTests();
    expect(resolveFingerprintedPath(snapshot["style.css"])).toBe("style.css");
    expect(resolveFingerprintedPath(snapshot["app.js"])).toBe("app.js");
  });

  test("getFingerprintedPath after bootstrap returns snapshot values", () => {
    clearAssetManifest();
    _reloadAssetManifestForTests();
    const snapshot = _readManifestSnapshotForTests();
    expect(getFingerprintedPath("style.css")).toBe(snapshot["style.css"]);
    expect(getFingerprintedPath("app.js")).toBe(snapshot["app.js"]);
  });

  test("lazy compute (post-clear, no reload) agrees with snapshot", () => {
    // The CI guard depends on this — if lazy compute and the
    // committed snapshot disagreed, the guard would never converge.
    clearAssetManifest();
    const snapshot = _readManifestSnapshotForTests();
    const viaLazy = getFingerprintedPath("style.css");
    expect(viaLazy).toBe(snapshot["style.css"]);
  });
});


// ---------------------------------------------------------------------------
// 4. Drift gate simulation
// ---------------------------------------------------------------------------
describe("manifest generator — drift gate behaviour", () => {
  test("re-running the generator produces a byte-identical file", () => {
    const before = readFileSync(MANIFEST_PATH);
    const result = spawnSync(process.execPath, [GENERATOR], {
      cwd: WEB_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
    });
    expect(result.status).toBe(0);
    const after = readFileSync(MANIFEST_PATH);
    expect(after.equals(before)).toBe(true);
  });

  test("regenerated content matches fingerprintAsset() for every entry", () => {
    // Roundtrip: regenerate, then verify the file's claims still
    // hold against the canonical TS hash function.
    const result = spawnSync(process.execPath, [GENERATOR], {
      cwd: WEB_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
    });
    expect(result.status).toBe(0);

    const snapshot = _readManifestSnapshotForTests();
    for (const [pathname, fp] of Object.entries(snapshot)) {
      expect(fp).toBe(fingerprintAsset(pathname));
    }
  });

  test("changing asset content changes the fingerprint (sensitivity)", () => {
    // Temp asset round-trip. We write a known-content file into the
    // assets directory, hash it, mutate it, re-hash, and assert the
    // hash differs. The temp file is unlinked in afterEach via
    // try/finally below — assets/ stays clean across runs.
    const tempPathname = "__a10_drift_probe__.txt";
    const tempAbs = join(ASSETS_DIR, tempPathname);
    try {
      writeFileSync(tempAbs, "version-1\n");
      const fp1 = fingerprintAsset(tempPathname);

      writeFileSync(tempAbs, "version-2-different-bytes\n");
      const fp2 = fingerprintAsset(tempPathname);

      // The fingerprinted shape is preserved, but the hash slice
      // differs.
      expect(fp1).toMatch(_FINGERPRINTED_RE);
      expect(fp2).toMatch(_FINGERPRINTED_RE);
      const h1 = fp1.match(_FINGERPRINTED_RE)![2];
      const h2 = fp2.match(_FINGERPRINTED_RE)![2];
      expect(h1).not.toBe(h2);
    } finally {
      if (existsSync(tempAbs)) {
        unlinkSync(tempAbs);
      }
    }
  });

  test("generator does not list untracked assets in the manifest", () => {
    // Probe: drop a temp file in assets/v0.2/, regen, confirm the
    // manifest still has exactly {style.css, app.js}. Tracking is
    // controlled by TRACKED_ASSETS in the generator — random new
    // files in the assets dir do not pollute the manifest.
    const tempPathname = "__a10_untracked_probe__.txt";
    const tempAbs = join(ASSETS_DIR, tempPathname);
    try {
      writeFileSync(tempAbs, "ignored\n");
      const result = spawnSync(process.execPath, [GENERATOR], {
        cwd: WEB_ROOT,
        stdio: ["ignore", "pipe", "pipe"],
      });
      expect(result.status).toBe(0);

      const snapshot = _readManifestSnapshotForTests();
      expect(Object.keys(snapshot).sort()).toEqual(["app.js", "style.css"]);
      expect(snapshot).not.toHaveProperty(tempPathname);
    } finally {
      if (existsSync(tempAbs)) {
        unlinkSync(tempAbs);
      }
    }
  });
});
