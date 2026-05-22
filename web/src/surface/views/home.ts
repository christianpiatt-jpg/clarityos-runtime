/**
 * Web Surface v0.2.0 — ``home`` view.
 *
 * Card A4 — Track A. The first real, named view registration on
 * top of the multi-view registry. Bound to its own
 * ``home.html`` template under ``web/templates/v0.2/``.
 *
 * Registration is a module-level side effect (``registerView``
 * runs at import time). Production bootstrap should import
 * ``views/index.ts`` once; tests that need ``home`` explicitly
 * can re-register after ``_clearViewRegistryForTests`` via the
 * exported ``homeView`` constant.
 *
 * Security note: ``render`` HTML-escapes the JSON-serialised
 * ``content`` value before handing it to the renderer. Templates
 * substitute literally; the escape happens HERE for any value
 * that originates from the request (params come from the
 * request).
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Minimal HTML-entity escape — same shape as
 *  ``viewDefaultRenderer.escapeHtml``. Kept local so views own
 *  their escape policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Exported for tests + future programmatic re-registration. */
export const homeView: ViewDefinition = {
  template: "home",
  async render(ctx: V.RenderContext) {
    return {
      title:   escapeHtml("Home"),
      content: escapeHtml(JSON.stringify(ctx.params ?? {}, null, 2)),
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``home`` in the registry.
registerView("home", homeView);
