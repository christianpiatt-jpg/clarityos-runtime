/**
 * Web Surface v0.2.0 — asset manifest.
 *
 * Card A9 — Track A. Process-singleton ``original ↔ fingerprinted``
 * mapping built lazily on demand. Sits on top of
 * ``assetFingerprint.fingerprintAsset`` (which is pure) so the
 * fingerprint for any given pathname is computed at most once per
 * process.
 *
 * Two lookups:
 *
 *   * ``getFingerprintedPath(pathname)`` — forward map. The render
 *     pipeline asks the manifest for the cache-safe URL to embed in
 *     ``standard.html`` (and any future layout). First call populates
 *     the entry; subsequent calls return the cached string.
 *
 *   * ``resolveFingerprintedPath(fingerprinted)`` — reverse map. The
 *     asset router asks the manifest to translate an incoming
 *     fingerprinted URL back to the on-disk filename before passing
 *     it to the loader. Returns ``null`` when no entry has been
 *     registered, which the router treats as "serve the pathname
 *     unchanged" (preserving backward-compat with the original A8
 *     URLs).
 *
 * Determinism guarantees (locked by tests):
 *   * Forward map is reference-stable: two calls with the same
 *     pathname return the same string (``toBe``).
 *   * Reverse map is consistent with the forward map: every
 *     fingerprinted value resolves back to its original, and
 *     ``resolveFingerprintedPath(fp) === original`` whenever
 *     ``getFingerprintedPath(original) === fp``.
 *   * No eviction. The fixed v0.2 asset set means unbounded growth
 *     is bounded in practice by the assets directory file count.
 *
 * Test-only helpers (``_listManifestForTests`` /
 * ``clearAssetManifest``) mirror the conventions of
 * ``templateCache``, ``layoutCache``, ``partialCache``, and
 * ``assetCache``. Production code MUST NOT call
 * ``clearAssetManifest``.
 */
import { fingerprintAsset } from "./assetFingerprint";


/** Forward map: original pathname → fingerprinted pathname. */
const manifest = new Map<string, string>();


/**
 * Return the fingerprinted (cache-safe) pathname for ``pathname``,
 * populating the manifest on first miss. Throws (via
 * ``fingerprintAsset``) on missing / malformed inputs.
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


/** Drop every manifest entry. Production MUST NOT call this. */
export function clearAssetManifest(): void {
  manifest.clear();
}


/**
 * Test-only: snapshot the manifest as a plain object mapping
 * ``original → fingerprinted``. Used by tests that assert on the
 * manifest's exact state.
 */
export function _listManifestForTests(): Record<string, string> {
  return Object.fromEntries(manifest.entries());
}
