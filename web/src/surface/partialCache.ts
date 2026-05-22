/**
 * Web Surface v0.2.0 — partial template cache.
 *
 * Card A6 — Track A. Process-singleton cache mirroring the
 * structure of ``templateCache.ts`` for partial templates.
 * Wraps ``partialLoader.loadPartial`` so each partial is read
 * from disk exactly once per process.
 *
 * Without this cache, every ``renderTemplate`` call that touches
 * a ``{{> header }}`` placeholder would hit the filesystem. With
 * the cache, each partial is read once on first miss; subsequent
 * inclusions return the cached reference.
 *
 * Same design notes as templateCache:
 *   * No eviction (small fixed working set).
 *   * No async (loader is sync; partials are small).
 *   * Reference-preserving — ``loadCachedPartial(name)`` twice
 *     returns the same string reference (tests check via ``toBe``).
 *   * Production should never call ``clearPartialCache``; tests
 *     use it in ``beforeEach`` to ensure isolation.
 */
import { loadPartial } from "./partialLoader";


const cache = new Map<string, string>();


/**
 * Return the partial body for ``name``, populating the cache on
 * the first miss. Subsequent calls with the same name return the
 * same string reference.
 */
export function loadCachedPartial(name: string): string {
  const hit = cache.get(name);
  if (hit !== undefined) {
    return hit;
  }
  const content = loadPartial(name);
  cache.set(name, content);
  return content;
}


/** Drop every cached partial. Production should not call this. */
export function clearPartialCache(): void {
  cache.clear();
}


/** Test-only: list every cached partial name in insertion order. */
export function _listCachedPartialsForTests(): string[] {
  return Array.from(cache.keys());
}


/**
 * Test-only: peek at the cached body for ``name`` without going
 * through the loader. Returns the stored reference (or undefined).
 */
export function _getCachedPartialForTests(name: string): string | undefined {
  return cache.get(name);
}
