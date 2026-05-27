/**
 * Web Surface v0.2.0 — ``runtime`` view (milestone v0.2.1).
 *
 * Operator runtime panel for the Node service that serves
 * ``cockpit.pro-mediations.com``. Renders a pure server-rendered
 * HTML snapshot of the Cloud Run revision's environment:
 *
 *   * ``K_SERVICE``        — Cloud Run service name (auto-set)
 *   * ``K_REVISION``       — Cloud Run revision name (auto-set)
 *   * ``K_CONFIGURATION``  — Cloud Run configuration name (auto-set)
 *   * ``ENVIRONMENT``      — local | staging | prod (set at deploy)
 *   * ``PORT``             — listen port (set by Cloud Run)
 *   * ``COMMIT_SHA``       — optional; set via ``--set-env-vars``
 *   * ``BUILD_VERSION``    — optional; set via ``--set-env-vars``
 *
 * Notes:
 *   * No auth boundary, no operator identity. The Node surface has
 *     no auth layer — adding one is out of scope for v0.2.1.
 *   * Each value passes through ``escapeHtml`` at the view boundary
 *     (caller-side escape policy, same shape as ``home.ts``).
 *   * Missing env vars render as ``"(not set)"`` so the page always
 *     produces a usable snapshot, including when the test runner
 *     and ``npm run serve`` execute outside Cloud Run.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Minimal HTML-entity escape — same shape as ``home.ts`` and the
 *  default renderer. Kept local so each view owns its escape
 *  policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


const NOT_SET = "(not set)";


/** Read an env var, returning the ``NOT_SET`` sentinel for missing
 *  or empty values. Cloud Run sets ``K_*`` automatically in prod;
 *  this fallback covers local + test execution. */
function envOrNotSet(name: string): string {
  const v = process.env[name];
  return v && v.length > 0 ? v : NOT_SET;
}


/** Exported for tests + future programmatic re-registration. */
export const runtimeView: ViewDefinition = {
  template: "runtime",
  layout: "standard",
  async render(_ctx: V.RenderContext) {
    return {
      title:         escapeHtml("Runtime Panel"),
      subtitle:      escapeHtml("Operational state"),
      service:       escapeHtml(envOrNotSet("K_SERVICE")),
      revision:      escapeHtml(envOrNotSet("K_REVISION")),
      configuration: escapeHtml(envOrNotSet("K_CONFIGURATION")),
      environment:   escapeHtml(envOrNotSet("ENVIRONMENT")),
      port:          escapeHtml(envOrNotSet("PORT")),
      commit_sha:    escapeHtml(envOrNotSet("COMMIT_SHA")),
      build_version: escapeHtml(envOrNotSet("BUILD_VERSION")),
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``runtime`` in the registry.
registerView("runtime", runtimeView);
