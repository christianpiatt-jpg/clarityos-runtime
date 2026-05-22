/**
 * Web Surface v0.2.0 — static asset cache.
 *
 * Card A8 — Track A. Process-singleton cache for asset bodies,
 * mirroring ``templateCache.ts`` / ``partialCache.ts`` /
 * ``layoutCache.ts``. Wraps ``assetLoader.loadAsset`` so each
 * asset is read from disk exactly once per process.
 *
 * Differences from the template caches:
 *   * Stores ``Buffer`` (raw bytes) instead of ``string``, so
 *     binary assets (images, fonts) survive the cache cycle
 *     without text coercion.
 *   * Otherwise identical contract: no eviction, no async,
 *     reference-preserving across repeat reads.
 *
 * Production should never call ``clearAssetCache``; tests use it
 * in ``beforeEach`` for isolation.
 */
import { loadAsset } from "./assetLoader";


const cache = new Map<string, Buffer>();


/**
 * Return the asset body for ``pathname``, populating the cache
 * on the first miss. Subsequent calls return the same Buffer
 * reference.
 *
 * Throws if the loader throws (missing asset, path traversal,
 * invalid pathname). The cache is NOT polluted on throw.
 */
export function loadCachedAsset(pathname: string): Buffer {
  const hit = cache.get(pathname);
  if (hit !== undefined) {
    return hit;
  }
  const body = loadAsset(pathname);
  cache.set(pathname, body);
  return body;
}


/** Drop every cached asset. Production should not call this. */
export function clearAssetCache(): void {
  cache.clear();
}


/** Test-only: list every cached asset pathname in insertion order. */
export function _listCachedAssetsForTests(): string[] {
  return Array.from(cache.keys());
}


/**
 * Test-only: peek at the cached body for ``pathname``. Returns
 * the stored reference (or undefined).
 */
export function _getCachedAssetForTests(pathname: string): Buffer | undefined {
  return cache.get(pathname);
}
