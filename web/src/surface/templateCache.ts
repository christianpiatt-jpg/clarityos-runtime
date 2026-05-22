/**
 * Web Surface v0.2.0 — template cache.
 *
 * Card A5 — Track A. Process-singleton cache for template bodies.
 * Wraps ``templateLoader.loadTemplate`` so the path-resolution +
 * fs read happen exactly once per template name; every subsequent
 * call returns the cached reference.
 *
 * Design notes:
 *   * Cache is a ``Map<string, string>`` keyed on the basename
 *     (the same identifier ``loadTemplate`` accepts).
 *   * No eviction. v0.2.0 ships a small fixed set of templates
 *     (``base``, ``home``) so unbounded cache growth is bounded
 *     in practice by the template directory's file count.
 *   * No async. The wrapped loader is synchronous; templates are
 *     small enough that blocking the event loop briefly at boot
 *     is acceptable.
 *   * The cache is reference-preserving: ``loadCachedTemplate(name)``
 *     twice returns the same string reference (not a freshly-allocated
 *     copy), which is the load-bearing property the tests check via
 *     ``toBe``.
 *
 * Why we wrap ``loadTemplate`` instead of calling readFileSync
 * directly:
 *   * The loader anchors the template directory via
 *     ``import.meta.url`` — the cache reuses that path-resolution
 *     work rather than duplicating ``process.cwd()`` logic that's
 *     fragile across vitest / production launch contexts.
 *   * Single point of truth: any future change to template path
 *     resolution lands in the loader; the cache stays unchanged.
 */
import { loadTemplate } from "./templateLoader";


const cache = new Map<string, string>();


/**
 * Return the template body for ``name``, populating the cache on
 * the first miss. Subsequent calls with the same name return the
 * same string reference.
 */
export function loadCachedTemplate(name: string): string {
  const hit = cache.get(name);
  if (hit !== undefined) {
    return hit;
  }
  const content = loadTemplate(name).trim();
  cache.set(name, content);
  return content;
}


/**
 * Drop every cached entry. Production code SHOULD NOT call this
 * — the cache is meant to live the lifetime of the process.
 * Tests use it in ``beforeEach`` to avoid cross-test contamination
 * (e.g. when a test wants to assert "first load reads from disk").
 */
export function clearTemplateCache(): void {
  cache.clear();
}


/**
 * Test-only: list every cached template name in insertion order.
 */
export function _listCachedTemplatesForTests(): string[] {
  return Array.from(cache.keys());
}


/**
 * Test-only: peek at the cached body for ``name`` without going
 * through the loader. Returns the stored reference (or undefined
 * if not cached). Used to verify reference-preservation across
 * repeated ``loadCachedTemplate`` calls.
 */
export function _getCachedTemplateForTests(name: string): string | undefined {
  return cache.get(name);
}
