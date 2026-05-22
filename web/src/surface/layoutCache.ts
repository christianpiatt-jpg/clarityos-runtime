/**
 * Web Surface v0.2.0 — layout cache.
 *
 * Card A7 — Track A. Process-singleton cache mirroring
 * ``templateCache.ts`` and ``partialCache.ts``. Wraps
 * ``layoutLoader.loadLayout`` so each layout is read from disk
 * exactly once per process.
 *
 * Without this cache, every render that uses a layout would hit
 * the filesystem to load the layout body. With it, each layout
 * is read once on first miss; subsequent uses return the cached
 * reference.
 *
 * Same design notes as the other caches:
 *   * No eviction (small fixed working set; one layout today).
 *   * No async (loader is sync).
 *   * Reference-preserving — two calls return the same string
 *     reference.
 *   * Production should never call ``clearLayoutCache``; tests
 *     use it in ``beforeEach`` to ensure isolation.
 */
import { loadLayout } from "./layoutLoader";


const cache = new Map<string, string>();


/**
 * Return the layout body for ``name``, populating the cache on
 * the first miss. Subsequent calls with the same name return the
 * same string reference.
 */
export function loadCachedLayout(name: string): string {
  const hit = cache.get(name);
  if (hit !== undefined) {
    return hit;
  }
  const content = loadLayout(name);
  cache.set(name, content);
  return content;
}


/** Drop every cached layout. Production should not call this. */
export function clearLayoutCache(): void {
  cache.clear();
}


/** Test-only: list every cached layout name in insertion order. */
export function _listCachedLayoutsForTests(): string[] {
  return Array.from(cache.keys());
}


/**
 * Test-only: peek at the cached body for ``name``. Returns the
 * stored reference (or undefined).
 */
export function _getCachedLayoutForTests(name: string): string | undefined {
  return cache.get(name);
}
