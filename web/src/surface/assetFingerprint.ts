/**
 * Web Surface v0.2.0 — asset fingerprint generator.
 *
 * Card A9 — Track A. Produces a content-addressed filename for a
 * static asset by hashing its bytes and slicing the first 12 hex
 * chars into the basename:
 *
 *   ``style.css`` + sha256(bytes) → ``style.<12-hex>.css``
 *
 * Why 12 hex chars?
 *   * 48 bits of entropy — collision-resistant in practice for the
 *     small fixed asset set v0.2 ships (single-digit files).
 *   * Short enough to stay readable in HTML / network logs without
 *     dominating the URL.
 *   * Matches the convention used by every major bundler
 *     (Webpack / Vite / Parcel default).
 *
 * Determinism guarantees (locked by tests):
 *   * Same asset bytes → same fingerprint, byte-for-byte, across
 *     processes and across runs.
 *   * Different bytes → different fingerprint with overwhelming
 *     probability.
 *   * No state. The fingerprint is a pure function of the asset
 *     bytes; the manifest layer (``assetManifest.ts``) memoises
 *     the result, but THIS module re-hashes every call. That
 *     keeps the fingerprint reproducible in isolation and means
 *     ``fingerprintAsset`` itself never lies about disk state.
 *
 * Path-resolution / security:
 *   * Bytes come via ``loadAsset`` from ``assetLoader.ts``. That
 *     means path traversal protection, the ``import.meta.url``-
 *     anchored asset directory, and the "throw on missing file"
 *     behaviour are inherited verbatim. We deliberately avoid
 *     ``process.cwd()`` because vitest + production resolve cwd
 *     differently — the loader's anchoring is the single source
 *     of truth.
 *
 * No deploy activation. No bundler. No build step. Reading + hashing
 * happens lazily inside ``loadAsset`` + ``createHash`` only when a
 * fingerprint is requested (the render pipeline asks for one per
 * managed asset on each render; the manifest layer ensures we
 * actually only hit this code once per asset per process).
 */
import { createHash } from "node:crypto";

import { loadAsset } from "./assetLoader";


/**
 * Width of the hex prefix taken from the SHA-256 digest. Exported
 * so tests can assert against the exact constant rather than the
 * magic number 12 sprinkled in multiple places.
 */
export const FINGERPRINT_HEX_LENGTH = 12;


/**
 * Compute the content-addressed filename for ``pathname``.
 *
 * Returns ``base.<hash>.<ext>`` where:
 *   * ``ext``  is the substring after the LAST dot in ``pathname``,
 *   * ``base`` is everything before that last dot,
 *   * ``hash`` is the first ``FINGERPRINT_HEX_LENGTH`` chars of
 *     ``sha256(bytes)`` in lowercase hex.
 *
 * Throws (via the underlying loader) on:
 *   * empty / non-string pathname,
 *   * absolute path,
 *   * path traversal attempt,
 *   * missing file.
 *
 * Callers that want a graceful fallback should catch and decide.
 * The asset router never calls this directly — it goes through
 * ``assetManifest.resolveFingerprintedPath`` which is read-only.
 */
export function fingerprintAsset(pathname: string): string {
  const buf = loadAsset(pathname);
  const hash = createHash("sha256")
    .update(buf)
    .digest("hex")
    .slice(0, FINGERPRINT_HEX_LENGTH);

  const dotIdx = pathname.lastIndexOf(".");
  if (dotIdx <= 0 || dotIdx === pathname.length - 1) {
    // No extension (or a leading-dot dotfile, or a trailing dot).
    // Append the hash as a suffix — the URL still changes when
    // bytes change, which is the load-bearing property.
    return `${pathname}.${hash}`;
  }
  const base = pathname.slice(0, dotIdx);
  const ext = pathname.slice(dotIdx + 1);
  return `${base}.${hash}.${ext}`;
}
