/**
 * Web Surface v0.2.0 — static asset router.
 *
 * Card A8 — Track A. Returns a ``WebSurfaceV0_2.Response`` for
 * a requested asset pathname. Used by the surface router as a
 * short-circuit BEFORE the classifier: requests under
 * ``/web-surface/v0.2/assets/`` skip view rendering and serve
 * the raw bytes.
 *
 * Card A9 — Track A. The router now accepts BOTH the original
 * pathname (``style.css``) and the fingerprinted pathname
 * (``style.<hash>.css``). Fingerprinted URLs reverse-resolve
 * through ``assetManifest`` to the underlying file; if the
 * manifest holds no entry, the pathname is passed through
 * unchanged, which preserves A8 behaviour for callers that never
 * touch the render pipeline. Either way the response is byte-
 * identical (same content, same content-type) — only the URL
 * surface changes, which is exactly the "cache-safe URL" property
 * the card is targeting.
 *
 * Behaviour:
 *   * 200 + correct ``content-type`` on success.
 *   * 404 + ``application/json`` ``{error: "asset_not_found"}``
 *     when the asset is missing OR the pathname is malformed
 *     (path traversal attempt, absolute path, etc.). The loader's
 *     exceptions are caught here — never bubble to the surface
 *     entrypoint.
 *
 * Content-type detection:
 *   * Extension-based allowlist on the RESOLVED original pathname,
 *     not the fingerprinted one. ``style.<hash>.css`` resolves to
 *     ``style.css`` first, then content-type derivation runs on
 *     that. Unknown extensions fall back to
 *     ``application/octet-stream`` (safe default — the browser
 *     downloads rather than executes).
 *
 * Security:
 *   * Path traversal protection lives in ``assetLoader``. The
 *     router just catches the throw and returns 404 — no
 *     information about WHY (missing file vs. traversal attempt)
 *     leaks back to the caller.
 *   * Reverse-resolving through the manifest CANNOT bypass
 *     traversal protection. The manifest only ever stores entries
 *     whose forward fingerprinting succeeded via the same loader,
 *     so every reverse lookup yields a pathname the loader has
 *     already accepted.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { loadCachedAsset } from "./assetCache";
import { resolveFingerprintedPath } from "./assetManifest";


/** Extension → content-type map. Extensions are checked
 *  case-insensitively. Unknown → ``application/octet-stream``. */
const _CONTENT_TYPES: Record<string, string> = {
  css:  "text/css",
  js:   "application/javascript",
  png:  "image/png",
  jpg:  "image/jpeg",
  jpeg: "image/jpeg",
  gif:  "image/gif",
  svg:  "image/svg+xml",
  ico:  "image/x-icon",
  woff: "font/woff",
  woff2: "font/woff2",
  ttf:  "font/ttf",
  otf:  "font/otf",
  json: "application/json",
};


/**
 * Return the content-type for an asset pathname based on its
 * extension. Exported for tests.
 */
export function contentTypeFor(pathname: string): string {
  const dotIdx = pathname.lastIndexOf(".");
  if (dotIdx < 0 || dotIdx === pathname.length - 1) {
    return "application/octet-stream";
  }
  const ext = pathname.slice(dotIdx + 1).toLowerCase();
  return _CONTENT_TYPES[ext] ?? "application/octet-stream";
}


/**
 * Route a static asset request. Returns a 200 + bytes on success
 * or a 404 envelope on failure. Never throws.
 *
 * Card A9: the pathname may be either the original (``style.css``)
 * or a fingerprinted form (``style.<hash>.css``). Fingerprinted
 * inputs reverse-resolve through ``assetManifest``; everything
 * else falls through to A8 behaviour. The 404 envelope still
 * carries the ORIGINAL caller-provided pathname so that error
 * diagnostics match the requested URL, not its internal resolution.
 */
export function routeAsset(pathname: string): WebSurfaceV0_2.Response {
  const resolved = resolveFingerprintedPath(pathname) ?? pathname;
  try {
    const body = loadCachedAsset(resolved);
    return {
      status: 200,
      headers: { "content-type": contentTypeFor(resolved) },
      body,
    };
  } catch {
    // Missing file OR path-traversal attempt — both look the same
    // to the caller. 404 is the correct HTTP semantic; the JSON
    // body provides a minimal diagnostic without leaking why.
    return {
      status: 404,
      headers: { "content-type": "application/json" },
      body: {
        error:  "asset_not_found",
        detail: { pathname },
      },
    };
  }
}
