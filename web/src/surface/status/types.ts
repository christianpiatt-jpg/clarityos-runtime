/**
 * Web Surface v0.2.0 — status surface types (Card A23-R).
 *
 * Typed wrapper for the unified status-fragment surface that
 * the ``/__status`` route renders. Three closed kinds:
 * success / warning / failure. The renderer picks one of three
 * server-rendered templates based on ``kind`` and injects the
 * caller-supplied ``message``.
 *
 * Shape policy:
 *   * ``StatusKind`` is a closed union. The renderer's
 *     template-selection switch is exhaustive, so adding a new
 *     kind is a compile-time edit — there is no silent default
 *     branch that would let an unrecognised value through.
 *   * ``message`` is a string. The renderer HTML-escapes it at
 *     the template boundary (defence-in-depth) so callers can
 *     pass raw operator-facing copy without worrying about
 *     embedded ``<`` / ``"`` / ``&``.
 *
 * Held in its own file so ``render.ts`` and ``index.ts`` can
 * import the types without circular deps (mirrors the A20-R
 * ``forms/``, A21-R ``diagnostics/``, and A22-R ``streaming/``
 * splits).
 */


/** Closed union of supported status kinds. Adding a new kind
 *  is a compile-time edit that the renderer's switch will
 *  flag via ``never``. */
export type StatusKind = "success" | "warning" | "failure";


/**
 * Payload accepted by ``renderStatusSurface`` and by the
 * ``/__status`` route's JSON body.
 *
 * Same shape on the wire and in-memory — the route handler
 * parses the JSON body directly into this type.
 */
export interface StatusPayload {
  kind:    StatusKind;
  message: string;
}
