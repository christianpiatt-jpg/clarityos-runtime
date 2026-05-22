/**
 * Web Surface v0.2.0 — navigation helpers (Card A12).
 *
 * Pure URL-building helpers that views and SPA-side code can call
 * to produce well-formed redirect URLs without re-typing the
 * surface's URL conventions.
 *
 * No state, no side effects, no network. Same input → same output.
 *
 * Usage from a view:
 *
 *     import { redirect } from "../navigation";
 *
 *     async render(ctx) {
 *       return {
 *         logout_href: redirect("/web-surface/v0.2/home"),
 *       };
 *     }
 *
 * The resulting URL hits the classifier's redirect interception
 * branch, which emits a ``{kind: "redirect", to: <target>, ...}``
 * action — the rest of the dispatch (envelope vs. HTML page) is
 * mode-driven and handled by ``renderRedirect``.
 */
import {
  REDIRECT_VIEW_NAME,
  DEFAULT_REDIRECT_TARGET,
} from "./classifier";


/** URL prefix every surface request shares. Held here as a
 *  constant so the helper doesn't have to re-derive it from the
 *  router's private prefix. */
export const SURFACE_URL_PREFIX = "/web-surface/v0.2";


/**
 * Build a surface-relative redirect URL.
 *
 * ``redirect("/x")`` →
 *     ``/web-surface/v0.2/redirect?to=%2Fx``
 *
 * The ``to`` value is ``encodeURIComponent``-encoded so any chars
 * the URL parser would otherwise mangle (``&``, ``#``, spaces)
 * survive the round-trip. The classifier reads ``to`` back from
 * the query string AFTER URL-decoding (via ``URLSearchParams``),
 * so the value at the redirect view's ``ctx.params.to`` is
 * byte-identical to what was passed in.
 */
export function redirect(to: string): string {
  return `${SURFACE_URL_PREFIX}/${REDIRECT_VIEW_NAME}?to=${encodeURIComponent(to)}`;
}


/** Re-export of the default redirect target so callers building
 *  fallback URLs don't have to import from the classifier
 *  directly. */
export { DEFAULT_REDIRECT_TARGET };
