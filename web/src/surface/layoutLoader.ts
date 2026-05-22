/**
 * Web Surface v0.2.0 — layout template loader.
 *
 * Card A7 — Track A. Loads versioned HTML layouts from the
 * ``web/templates/v0.2/layouts/`` directory. Mirrors the
 * structure of ``templateLoader.ts`` and ``partialLoader.ts``:
 *
 *   * Path resolution anchored via ``import.meta.url`` (not
 *     ``process.cwd()``) so vitest + production resolve the
 *     directory identically.
 *   * Synchronous + deterministic + unstateful. Caching is in
 *     the parallel ``layoutCache.ts``.
 *   * Throws on a missing layout — callers (the pipeline) decide
 *     whether to catch and swallow.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";


const _MODULE_DIR = dirname(fileURLToPath(import.meta.url));

// From ``web/src/surface/layoutLoader.ts``:
//   ..    → web/src/
//   ../.. → web/
// so layouts live at ``../../templates/v0.2/layouts``.
export const LAYOUTS_DIR = join(
  _MODULE_DIR, "..", "..", "templates", "v0.2", "layouts",
);


/**
 * Read the layout ``name`` (no extension; ``.html`` is appended).
 * Throws if the file is missing — the caller (pipeline) knows
 * its layout names from view definitions, so a missing layout
 * is a deployment bug, not a runtime path to handle gracefully.
 */
export function loadLayout(name: string): string {
  const path = join(LAYOUTS_DIR, `${name}.html`);
  return readFileSync(path, "utf8").trim();
}
