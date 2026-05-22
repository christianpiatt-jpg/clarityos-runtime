/**
 * Web Surface v0.2.0 — view registry.
 *
 * Deterministic lookup table for named view renderers. Registered
 * at module-import time by feature modules (one per view); consumed
 * by ``renderer.ts`` via ``getView(name)``. An unknown name returns
 * ``undefined`` so the renderer can fall back to the default
 * renderer.
 *
 * The registry is module-singleton (one Map per process). It is
 * NOT thread-safe in a meaningful sense because TypeScript runs in
 * a single event loop; concurrent registrations from different
 * import paths interleave deterministically.
 *
 * Card A1 — Track A — View Engine foundation.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";


/** Function signature for a view renderer. */
export type ViewRenderer = (
  ctx: V.RenderContext,
) => Promise<V.RenderOutput>;


/** The singleton registry. Map preserves insertion order, which is
 *  useful for diagnostics (the introspection helpers below dump
 *  registered names in insertion order). */
const registry = new Map<string, ViewRenderer>();


/**
 * Register a renderer for ``name``. Subsequent calls with the same
 * name overwrite the previous registration — the last writer wins.
 * This is intentional: it lets a downstream feature module override
 * a default renderer for a specific view name.
 */
export function registerView(name: string, renderer: ViewRenderer): void {
  registry.set(name, renderer);
}


/** Look up a registered renderer. Returns ``undefined`` for an
 *  unknown name so the caller can fall back to the default. */
export function getView(name: string): ViewRenderer | undefined {
  return registry.get(name);
}


/**
 * Test-only: list every registered view name. Useful for asserting
 * the registry state in unit tests without inspecting the Map
 * directly.
 */
export function _listRegisteredViewsForTests(): string[] {
  return Array.from(registry.keys());
}


/**
 * Test-only: wipe the registry. Tests that register custom views
 * call this in ``beforeEach`` / ``afterEach`` to keep state from
 * leaking between cases.
 */
export function _clearViewRegistryForTests(): void {
  registry.clear();
}
