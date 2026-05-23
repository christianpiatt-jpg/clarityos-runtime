/**
 * Web Surface v0.2.0 — loading surface types (Card A24-R).
 *
 * Typed wrapper for the deferred-work loading-fragment surface
 * that the ``/__loading`` route renders. One fragment shape,
 * one optional dynamic slot.
 *
 * Shape policy:
 *   * ``message`` is optional. When omitted, the renderer
 *     substitutes ``DEFAULT_LOADING_MESSAGE`` (``"Loading…"``).
 *     This lets the most common case (a generic spinner) elide
 *     the payload entirely — both server-side calls and route
 *     POSTs can pass an empty payload.
 *   * ``message`` is a string when present. The renderer
 *     HTML-escapes it at the boundary (defence-in-depth) so
 *     callers can pass raw operator-facing copy without
 *     worrying about embedded ``<`` / ``"`` / ``&``.
 *
 * Held in its own file so ``render.ts`` and ``index.ts`` can
 * import the types without circular deps (mirrors the
 * A20-R ``forms/``, A21-R ``diagnostics/``, A22-R
 * ``streaming/``, and A23-R ``status/`` splits).
 */


/** Optional payload for ``renderLoadingSurface``. An empty
 *  object (or ``undefined``) renders the default message. */
export interface LoadingPayload {
  message?: string;
}
