/**
 * Web Surface v0.2.0 — asset manifest.
 *
 * Card A9 — Track A. Process-singleton ``original ↔ fingerprinted``
 * mapping built lazily on demand.
 *
 * Card A10 — Track A. The committed JSON snapshot at
 * ``web/assets/v0.2/manifest.json`` is now the source of truth.
 * This module BOOTSTRAPS from that snapshot once at module load,
 * so the runtime never re-hashes a known asset. The lazy compute
 * path remains as a safety net for assets that exist on disk but
 * haven't been generated into the snapshot yet (a CI guard at
 * ``scripts/check_asset_manifest.sh`` prevents that state from
 * landing on the trunk branch).
 *
 * Two lookups:
 *
 *   * ``getFingerprintedPath(pathname)`` — forward map. The asset
 *     router and (historically) the render pipeline ask the
 *     manifest for the cache-safe URL. Snapshot hit returns the
 *     committed value; snapshot miss falls back to
 *     ``fingerprintAsset`` and memoises the result.
 *
 *   * ``resolveFingerprintedPath(fingerprinted)`` — reverse map. The
 *     asset router asks the manifest to translate an incoming
 *     fingerprinted URL back to the on-disk filename before passing
 *     it to the loader. Returns ``null`` when no entry exists,
 *     which the router treats as "serve the pathname unchanged"
 *     (preserving backward-compat with the original A8 URLs).
 *
 * Bootstrap policy — one-shot at module load:
 *   * Bootstrap fires exactly once per process the first time this
 *     module is imported. After that, ``clearAssetManifest`` empties
 *     the in-memory map but does NOT re-fire the bootstrap; tests
 *     that want to assert from a truly empty starting state can
 *     clear-and-stay-empty (preserving A9's lazy-population
 *     contracts), and tests that need the snapshot state back call
 *     ``_reloadAssetManifestForTests`` to force a fresh load.
 *
 * Determinism guarantees (locked by tests):
 *   * Snapshot values are byte-identical to ``fingerprintAsset``
 *     output (enforced by CI + the A10 test suite).
 *   * Forward map is reference-stable across calls.
 *   * Reverse map is consistent with the forward map.
 *   * No eviction. The v0.2 asset set is small and fixed.
 *
 * Test-only helpers (``_listManifestForTests``,
 * ``clearAssetManifest``, ``_reloadAssetManifestForTests``) mirror
 * the conventions of the parallel caches. Production code MUST
 * NOT call any of them.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { fingerprintAsset } from "./assetFingerprint";


const _MODULE_DIR = dirname(fileURLToPath(import.meta.url));

/** Absolute path to the committed manifest snapshot. Anchored via
 *  ``import.meta.url`` like every other path-resolver in the
 *  surface — same reasoning around vitest vs. production cwd. */
export const MANIFEST_PATH = join(
  _MODULE_DIR, "..", "..", "assets", "v0.2", "manifest.json",
);


/** Forward map: original pathname → fingerprinted pathname. */
const manifest = new Map<string, string>();


/** Sticky flag so the JSON snapshot is read at most once per
 *  populate cycle. ``clearAssetManifest`` resets this. */
let bootstrapped = false;


/**
 * Read + parse the committed manifest.json. Exposed for the A10
 * snapshot tests; not part of the runtime contract.
 */
export function _readManifestSnapshotForTests(): Record<string, string> {
  const raw = readFileSync(MANIFEST_PATH, "utf8");
  return JSON.parse(raw);
}


function _bootstrapFromSnapshot(): void {
  const snapshot = _readManifestSnapshotForTests();
  for (const [original, fp] of Object.entries(snapshot)) {
    manifest.set(original, fp);
  }
  bootstrapped = true;
}


// One-shot bootstrap at module load. Subsequent imports of this
// module reuse the existing populated map; ``clearAssetManifest``
// empties it without re-firing the bootstrap so test cases can
// assert from a known-empty starting state.
_bootstrapFromSnapshot();


/**
 * Return the fingerprinted (cache-safe) pathname for ``pathname``.
 *
 * Lookup order:
 *   1. Hit in the in-memory manifest → return committed value
 *      (which is the snapshot value at module load, or whatever
 *      lazy compute filled in after a ``clearAssetManifest``).
 *   2. Miss → ``fingerprintAsset`` (lazy compute) + memoise.
 *
 * Throws (via ``fingerprintAsset``) only if step 2 fires AND the
 * underlying loader can't read the asset (missing / traversal /
 * empty pathname).
 */
export function getFingerprintedPath(pathname: string): string {
  const hit = manifest.get(pathname);
  if (hit !== undefined) {
    return hit;
  }
  const fp = fingerprintAsset(pathname);
  manifest.set(pathname, fp);
  return fp;
}


/**
 * Translate a fingerprinted pathname back to its original. Returns
 * ``null`` if the manifest holds no matching entry — the asset
 * router falls back to serving the pathname as-is in that case
 * (so that pre-fingerprint URLs and entirely-new asset names still
 * resolve through the loader).
 *
 * O(n) over the manifest. The v0.2 asset set is single-digit;
 * this is faster in absolute terms than a second hash table while
 * keeping the module dependency-free of any auxiliary data
 * structure.
 */
export function resolveFingerprintedPath(fingerprinted: string): string | null {
  for (const [original, fp] of manifest.entries()) {
    if (fp === fingerprinted) {
      return original;
    }
  }
  return null;
}


/**
 * Drop every manifest entry. Production MUST NOT call this. Tests
 * use it to start from a known-empty state — the bootstrap flag
 * is intentionally NOT reset, so subsequent reads either find
 * what tests explicitly populate or fall through to lazy compute
 * (A9-style). Tests that want the snapshot's pre-populated state
 * back call ``_reloadAssetManifestForTests``.
 */
export function clearAssetManifest(): void {
  manifest.clear();
}


/**
 * Test-only: force a re-bootstrap from the on-disk manifest.json.
 * Used by A10 snapshot tests that explicitly want to see the
 * snapshot's pre-populated state (rather than starting empty
 * after a clear).
 */
export function _reloadAssetManifestForTests(): void {
  manifest.clear();
  bootstrapped = false;
  _bootstrapFromSnapshot();
}


/**
 * Test-only: snapshot the manifest as a plain object mapping
 * ``original → fingerprinted``. Used by tests that assert on the
 * manifest's exact state.
 */
export function _listManifestForTests(): Record<string, string> {
  return Object.fromEntries(manifest.entries());
}
