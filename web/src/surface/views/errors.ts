/**
 * Web Surface v0.2.0 — error views (Card A11).
 *
 * Registers two structured error views on top of the same view /
 * layout / partial pipeline that every other view uses:
 *
 *   * ``error_404`` — view "not found" page. Reached by:
 *       - classifier rewrite when ``getView(resolved.view)`` is
 *         undefined (see ``classifier.ts``).
 *       - direct programmatic dispatch
 *         (``renderWebSurface({view: "error_404", ...})``).
 *
 *   * ``error_500`` — internal-error page. Reached by:
 *       - the router's envelope→HTML transform when a sub-response
 *         carries an ErrorEnvelope body and the request asked
 *         for HTML.
 *       - direct programmatic dispatch.
 *       The pipeline's try/catch fallback renders the same
 *       template DIRECTLY (no view binding, no layout) to avoid
 *       a double-fault when the original failure was inside the
 *       layout / asset / partial path.
 *
 * Both views:
 *   * Use the ``error`` layout (visually distinct from the
 *     ``standard`` layout used by ``home`` etc.).
 *   * Carry an HTTP status (``404`` / ``500``) via the optional
 *     ``status`` field on ``ViewDefinition`` — the pipeline reads
 *     this when assembling the Response.
 *   * HTML-escape every value before substitution (caller-side
 *     escape policy from the templateEngine docs).
 *
 * Registration is a module-level side effect at import time —
 * same as ``views/home.ts``. Tests that need these views after
 * ``_clearViewRegistryForTests`` re-register via the exported
 * ``error404View`` / ``error500View`` constants.
 *
 * Security note: ``message`` flows verbatim into the template and
 * could include attacker-controlled text (a 404 message embeds
 * the resolved view name from the URL). It MUST be HTML-escaped
 * here at the boundary.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Minimal HTML-entity escape — same shape as
 *  ``viewDefaultRenderer.escapeHtml`` and ``views/home.ts``.
 *  Kept local so each view owns its escape policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/**
 * Pull a caller-supplied ``message`` out of ``ctx.params``,
 * applying a sensible default and HTML-escaping the result.
 */
function _message(ctx: V.RenderContext, fallback: string): string {
  const raw = (ctx.params as { message?: unknown } | undefined)?.message;
  const text = typeof raw === "string" && raw.length > 0 ? raw : fallback;
  return escapeHtml(text);
}


export const error404View: ViewDefinition = {
  template: "errors/404",
  layout:   "error",
  status:   404,
  async render(ctx: V.RenderContext) {
    return {
      title:    escapeHtml("Not Found"),
      subtitle: escapeHtml("404"),
      message:  _message(ctx, "The requested resource could not be found."),
    };
  },
};


export const error500View: ViewDefinition = {
  template: "errors/500",
  layout:   "error",
  status:   500,
  async render(ctx: V.RenderContext) {
    return {
      title:    escapeHtml("Internal Error"),
      subtitle: escapeHtml("500"),
      message:  _message(ctx, "An unexpected error occurred."),
    };
  },
};


// Side-effect registration: the first import of this module
// installs both error views in the registry.
registerView("error_404", error404View);
registerView("error_500", error500View);
