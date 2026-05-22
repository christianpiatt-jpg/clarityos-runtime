/**
 * Web Surface v0.2.0 — demo form view (Card A13-R).
 *
 * Registered as ``"form_demo"``. URL: ``/web-surface/v0.2/form_demo``.
 *
 * Behaviour:
 *   * GET                                 → empty form (no ``name``,
 *                                           no ``email``).
 *   * POST + ``application/x-www-form-urlencoded``
 *                                         → classifier emits a
 *                                           ``form`` action, handler
 *                                           parses ``rawBody``, view
 *                                           re-renders with the
 *                                           parsed fields echoed
 *                                           back into the inputs.
 *
 * Pathway invariants:
 *   * The view is the SAME for GET and POST — the form pathway is
 *     invisible to ``render(ctx)``. It reads ``ctx.params.name`` /
 *     ``ctx.params.email`` exactly the way a GET-with-querystring
 *     view would.
 *   * JSON mode is canonical: a POST with ``Accept: application/json``
 *     still returns the structured ``{view, params}`` envelope via
 *     ``defaultRenderer``. No per-view JSON drift.
 *
 * Security:
 *   * Every user-supplied value (``name``, ``email``) is
 *     HTML-escaped at the view boundary before substitution into
 *     the template. The form re-displays whatever the user
 *     submitted; without escaping a hostile ``name`` could inject
 *     script into the page.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Minimal HTML-entity escape — same shape as ``views/home.ts``
 *  and ``views/errors.ts``. Kept local so each view owns its
 *  escape policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Read a single param as a string; empty string for missing /
 *  non-string. The form parser always yields strings, so the
 *  ``typeof`` check is mostly defensive against direct
 *  programmatic dispatch (tests calling ``executeRenderPipeline``
 *  with arbitrary params). */
function _readField(ctx: V.RenderContext, key: string): string {
  const raw = (ctx.params as Record<string, unknown> | undefined)?.[key];
  return typeof raw === "string" ? raw : "";
}


/** Exported for tests + future programmatic re-registration. */
export const formDemoView: ViewDefinition = {
  template: "form_demo",
  layout:   "standard",
  async render(ctx: V.RenderContext) {
    const name  = _readField(ctx, "name");
    const email = _readField(ctx, "email");
    return {
      title:    escapeHtml("Form Demo"),
      subtitle: escapeHtml("Form Demo"),
      name:     escapeHtml(name),
      email:    escapeHtml(email),
      // The template includes ``<pre>{{ content }}</pre>`` — when
      // any fields were submitted, render them as a pretty-printed
      // JSON echo so the round-trip is visually obvious. Empty form
      // → empty <pre>.
      content:  name || email
        ? escapeHtml(JSON.stringify({ name, email }, null, 2))
        : "",
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``form_demo`` in the registry.
registerView("form_demo", formDemoView);
