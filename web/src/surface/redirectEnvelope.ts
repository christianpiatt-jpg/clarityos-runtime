/**
 * Web Surface v0.2.0 — redirect envelope (Card A12).
 *
 * JSON-mode shape carried in the response body when a request
 * classifies as a redirect:
 *
 *     { "redirect": "/web-surface/v0.2/home" }
 *
 * Mirrors ``WebSurfaceV0_2.ErrorEnvelope`` in structure (single
 * top-level discriminator key), but the field name is distinct
 * (``redirect`` vs. ``error``) so callers can tell the two apart
 * without consulting status codes.
 *
 * Status code policy:
 *   * The HTTP status for a redirect response is 200, NOT 302.
 *     Treating redirects as ordinary 200 responses keeps the
 *     surface free of browser-level redirect state (history,
 *     referrer, fetch redirect-mode handling) and lets the
 *     client decide whether to follow.
 *
 * Anchored here (rather than under ``contracts/``) because the
 * v0.2.0 contract module is locked — the redirect envelope is an
 * internal surface convention, not a cross-language wire shape.
 * If a later card promotes it to the wire contract, the type
 * moves; callers update the import path in one place.
 */

export interface RedirectEnvelope {
  redirect: string;
}


/**
 * Runtime predicate for the envelope shape. Mirrors the
 * ``_isErrorEnvelope`` pattern in ``router.ts`` so future router
 * passes can branch on redirect-vs-error envelopes without
 * leaking the type guard out of this module.
 */
export function isRedirectEnvelope(value: unknown): value is RedirectEnvelope {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return typeof (value as { redirect?: unknown }).redirect === "string";
}
