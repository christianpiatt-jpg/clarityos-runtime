/**
 * Web Surface v0.2.0 — partial template loader.
 *
 * Card A6 — Track A. Loads versioned HTML partials from the
 * ``web/templates/v0.2/partials/`` directory. Mirrors
 * ``templateLoader.ts`` shape and conventions:
 *
 *   * Path resolution anchored via ``import.meta.url`` (not
 *     ``process.cwd()``) so vitest + production resolve the
 *     directory identically.
 *   * Synchronous + deterministic + unstateful. Caching is in
 *     the parallel ``partialCache.ts``.
 *   * Throws on a missing partial — callers (currently
 *     ``templateEngine``) decide whether to catch and swallow.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";


const _MODULE_DIR = dirname(fileURLToPath(import.meta.url));

// From ``web/src/surface/partialLoader.ts``:
//   ..    → web/src/
//   ../.. → web/
// so partials live at ``../../templates/v0.2/partials``.
export const PARTIALS_DIR = join(
  _MODULE_DIR, "..", "..", "templates", "v0.2", "partials",
);


/**
 * Read the partial ``name`` (no extension; ``.html`` is appended).
 * Throws if missing. The body is ``.trim()``-ed so the inclusion
 * site doesn't carry stray leading/trailing whitespace from the
 * file.
 */
export function loadPartial(name: string): string {
  const path = join(PARTIALS_DIR, `${name}.html`);
  return readFileSync(path, "utf8").trim();
}
