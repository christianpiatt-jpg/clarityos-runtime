/**
 * Web Surface v0.2.0 — static asset loader.
 *
 * Card A8 — Track A. Loads versioned static files from the
 * ``web/assets/v0.2/`` directory. Returns the raw bytes as a
 * ``Buffer`` so binary assets (images, fonts) flow through
 * unchanged.
 *
 * Security model:
 *   * Path resolution is anchored via ``import.meta.url`` —
 *     identical to ``templateLoader`` / ``partialLoader`` /
 *     ``layoutLoader``. Vitest + production resolve the
 *     directory the same way regardless of cwd.
 *   * The pathname argument MUST NOT escape ``ASSETS_DIR``.
 *     We normalise the resolved path and verify it sits inside
 *     ``ASSETS_DIR`` before reading. A ``..`` segment, an
 *     absolute path, or an URL-encoded escape that resolves
 *     outside the assets directory throws — never reads.
 *   * No symbolic-link following protection beyond what Node's
 *     ``readFileSync`` already provides. Production deployments
 *     should not symlink anything from inside ``assets/`` to
 *     outside.
 *
 * Caching is in the parallel ``assetCache.ts`` (Buffer-valued).
 */
import { readFileSync } from "node:fs";
import { dirname, isAbsolute, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";


const _MODULE_DIR = dirname(fileURLToPath(import.meta.url));

// From ``web/src/surface/assetLoader.ts``:
//   ..    → web/src/
//   ../.. → web/
// so assets live at ``../../assets/v0.2``.
export const ASSETS_DIR = join(
  _MODULE_DIR, "..", "..", "assets", "v0.2",
);


/**
 * Resolve a requested asset pathname (relative to ``ASSETS_DIR``)
 * to an absolute path that's guaranteed to live inside that
 * directory. Throws on any attempt to escape via ``..``, an
 * absolute path, or a normalised path that lands elsewhere.
 *
 * Exported for tests + the asset router (which catches and
 * converts the throw into a 404 response).
 */
export function _resolveAssetPath(pathname: string): string {
  if (!pathname || typeof pathname !== "string") {
    throw new Error(
      `Asset path must be a non-empty string: ${String(pathname)}`,
    );
  }
  if (isAbsolute(pathname)) {
    throw new Error(`Asset path must be relative, got absolute: ${pathname}`);
  }
  const resolved = normalize(join(ASSETS_DIR, pathname));
  // ``startsWith(ASSETS_DIR + sep)`` ensures the resolved path is
  // a STRICT descendant. ``=== ASSETS_DIR`` is rejected (the
  // assets dir itself isn't a file).
  if (!resolved.startsWith(ASSETS_DIR + sep)) {
    throw new Error(
      `Asset path escapes the assets directory: ${pathname}`,
    );
  }
  return resolved;
}


/**
 * Read the asset at ``pathname`` (relative to ``ASSETS_DIR``).
 * Returns raw bytes as a ``Buffer``. Throws on:
 *   * empty / non-string pathname,
 *   * absolute path,
 *   * path traversal attempt (``..``),
 *   * missing file (from ``readFileSync``).
 *
 * The router catches every throw and converts to a 404 response.
 */
export function loadAsset(pathname: string): Buffer {
  const path = _resolveAssetPath(pathname);
  return readFileSync(path);
}
