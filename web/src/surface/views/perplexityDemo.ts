/**
 * Web Surface v0.2.0 — Perplexity demo view (Card A31-R).
 *
 * Registered as ``"perplexity_demo"``. URL:
 * ``/web-surface/v0.2/perplexity_demo``.
 *
 * The demo wraps the A30-R relay (``POST /__perplexity``) in a
 * server-rendered page: header + query form + result panel.
 * With JS enabled, the A19-R/A20-R/A30-R enhancement layer
 * intercepts the form submit, POSTs the query to
 * ``/__perplexity``, and swaps the answer fragment into
 * ``#perplexity-result``. With JS disabled, the form falls
 * back to a native POST to this view's own URL, which
 * re-renders the demo page (the view is intentionally
 * idempotent over GET / POST — neither mutates state).
 *
 * Pattern parity:
 *   * Same shape as ``views/formDemo.ts`` and
 *     ``views/streamDemo.ts``: a single exported
 *     ``ViewDefinition`` plus a module-level
 *     ``registerView`` side effect. The first import of this
 *     module installs the view in the registry.
 *   * ``layout: "standard"`` so the demo body fragment is
 *     wrapped by the standard layout chrome (doctype, head,
 *     header partial, footer partial).
 *   * No ``stream`` / ``events`` / ``schema`` — the view is
 *     a plain GET page; the relay POST handles all
 *     dynamic work.
 *
 * Security:
 *   * ``render`` HTML-escapes its title / subtitle vars at the
 *     view boundary. The demo has no user-supplied params, so
 *     escaping is purely policy-uniform (mirrors
 *     ``views/home.ts`` and ``views/formDemo.ts``).
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Minimal HTML-entity escape — same shape as
 *  ``views/home.ts`` and ``views/formDemo.ts``. Kept local so
 *  each view owns its escape policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Exported for tests + future programmatic re-registration. */
export const perplexityDemoView: ViewDefinition = {
  template: "perplexity_demo",
  layout:   "standard",
  async render(_ctx: V.RenderContext) {
    return {
      title:    escapeHtml("Perplexity Relay Demo"),
      subtitle: escapeHtml("Perplexity Relay Demo"),
    };
  },
};


// Side-effect registration: first import installs
// ``perplexity_demo``.
registerView("perplexity_demo", perplexityDemoView);
