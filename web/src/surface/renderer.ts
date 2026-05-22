/**
 * Web Surface v0.2.0 — render dispatcher.
 *
 * Card history:
 *   * Card 9  — 501 stub
 *   * Card A1 — dispatches to registry (callable renderers); falls
 *               back to defaultRenderer for unknown views.
 *   * Card A3 — defaultRenderer now uses the template engine.
 *   * Card A4 — registry registrations are ``ViewDefinition``s
 *               (template + render-to-vars). The renderer applies
 *               the named template to those vars for HTML mode;
 *               JSON mode bypasses view definitions entirely and
 *               always uses defaultRenderer's canonical
 *               ``{view, params}`` shape.
 *
 * Dispatch logic (post-A4):
 *
 *   if mode === "json":
 *       return defaultRenderer(ctx)        # canonical {view, params}
 *   def = getView(ctx.view)
 *   if def is None:
 *       return defaultRenderer(ctx)        # HTML mode, default template
 *   vars = await def.render(ctx)
 *   html = renderTemplate(loadTemplate(def.template), vars)
 *   return 200 + text/html + html
 *
 * Why JSON mode bypasses view definitions:
 *   JSON is the machine-readable representation; the ``{view,
 *   params}`` shape is canonical and consistent across every view.
 *   Per-view JSON shaping is a follow-up card if/when needed.
 *
 * Why the renderer (not the view) sets status + headers + body
 * shape:
 *   Splitting these gives one consistent Response shape per HTTP
 *   verb. Views own DATA; the renderer owns ENVELOPE. Card A1's
 *   "view returns full RenderOutput" pattern was reverted in A4
 *   because it leaked envelope responsibility into every view.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { defaultRenderer } from "./viewDefaultRenderer";
import { getView } from "./viewRegistry";
import { loadTemplate } from "./templateLoader";
import { renderTemplate } from "./templateEngine";


/** Backward-compat alias: external callers built against earlier
 *  ``RenderContext`` shapes keep working. */
export type RenderContext = V.RenderContext;


/**
 * Dispatch a Web Surface render request.
 *
 * Mode-aware:
 *   * JSON mode → ``defaultRenderer`` (always {view, params}).
 *   * HTML mode + registered view → template-bound render.
 *   * HTML mode + unknown view  → ``defaultRenderer`` (template-
 *     based base.html with escaping).
 *
 * Always returns a ``RenderOutput`` whose shape is structurally
 * compatible with ``WebSurfaceV0_2.Response``.
 */
export async function renderWebSurface(
  ctx: V.RenderContext,
): Promise<V.RenderOutput> {
  // JSON mode: skip view definitions entirely. The default
  // renderer's canonical {view, params} shape is THE JSON contract.
  if (ctx.mode === V.Mode.json) {
    return defaultRenderer(ctx);
  }

  // HTML mode: registered view binds a template; unknown view
  // falls through to defaultRenderer (base.html via the template
  // engine, with renderer-level XSS escaping).
  const def = getView(ctx.view);
  if (!def) {
    return defaultRenderer(ctx);
  }

  // Template-bound render path. The view produces template vars;
  // the renderer loads the named template + substitutes. No
  // status/header customisation per view — those are
  // renderer-owned.
  const vars = await def.render(ctx);
  const template = loadTemplate(def.template);
  const html = renderTemplate(template, vars);

  return {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body: html,
  };
}
