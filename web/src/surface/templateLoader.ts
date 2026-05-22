/**
 * Web Surface v0.2.0 — template loader.
 *
 * Card A3 — Track A. Loads versioned HTML templates from the
 * ``web/templates/v0.2/`` directory. Synchronous + deterministic +
 * unstateful.
 *
 * Path resolution is anchored at the module's own location via
 * ``import.meta.url`` (ESM standard) rather than ``process.cwd()``,
 * so the loader works identically whether the runtime is launched
 * from the repo root, from inside ``web/`` (vitest's default), or
 * from a future bundled deployment.
 *
 * No caching today — that lands in a future card (A4 or beyond)
 * once a measurable working-set materialises. For a v0.2.0 skeleton
 * with one ``base.html`` template, a per-call read is fine.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";


// Anchor relative to this module so tests + bundlers resolve the
// templates dir the same way regardless of cwd.
const _MODULE_DIR = dirname(fileURLToPath(import.meta.url));

// From ``web/src/surface/templateLoader.ts``:
//   ..    → web/src/
//   ../.. → web/
// so the templates dir is ``../../templates/v0.2``.
export const TEMPLATES_DIR = join(_MODULE_DIR, "..", "..", "templates", "v0.2");


/**
 * Read the template ``name`` (no extension; ``.html`` is appended).
 * Throws if the file is missing — the caller is expected to know
 * its template names at compile time, so a missing template is a
 * deployment bug, not a runtime path to handle gracefully.
 */
export function loadTemplate(name: string): string {
  const path = join(TEMPLATES_DIR, `${name}.html`);
  return readFileSync(path, "utf8");
}
