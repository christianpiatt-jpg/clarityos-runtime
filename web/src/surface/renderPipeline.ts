/**
 * Web Surface v0.2.0 — render pipeline.
 *
 * Card A5 — Track A. The single source of truth for rendering.
 * ``renderer.ts`` is now a thin re-export of
 * ``executeRenderPipeline``; every render path flows through here.
 *
 * Pipeline steps (deterministic, side-effect-free except for the
 * template cache populating on first miss):
 *
 *   0. Mode dispatch
 *      If ``ctx.mode === "json"`` → return ``defaultRenderer(ctx)``.
 *      JSON is the canonical machine-readable representation; the
 *      ``{view, params}`` shape is the JSON contract for every
 *      view. Per-view JSON shaping is a follow-up card.
 *
 *   1. Resolve view definition
 *      ``getView(ctx.view)``. Unknown view → fall through to
 *      ``defaultRenderer(ctx)`` (HTML mode default — base.html
 *      via the template engine + XSS escape).
 *
 *   2. Compute template variables
 *      ``await def.render(ctx)``. The view owns DATA; the pipeline
 *      owns ENVELOPE. View is responsible for HTML-escaping any
 *      user-controlled values (see ``views/home.ts``).
 *
 *   3. Load template (cached)
 *      ``loadCachedTemplate(def.template)``. First miss reads from
 *      disk; subsequent hits return the cached reference.
 *
 *   4. Apply template engine
 *      ``renderTemplate(template, vars)``. Substitutes
 *      ``{{ name }}`` placeholders; strips unfilled placeholders.
 *
 *   5. Return deterministic output
 *      ``{ status: 200, headers, body: html }`` — shape locked.
 *      Status, content-type, body shape are renderer-owned; views
 *      cannot customise them.
 *
 * Determinism guarantees (locked by tests):
 *   * Same ``ctx`` in → same ``RenderOutput`` out, byte-for-byte.
 *   * Pipeline does not mutate ``ctx``.
 *   * Pipeline does not mutate the view registry.
 *   * Pipeline does not mutate the cache except by adding entries
 *     on first miss (additive; never overwrites).
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { getView } from "./viewRegistry";
import { loadCachedTemplate } from "./templateCache";
import { renderTemplate } from "./templateEngine";
import { defaultRenderer } from "./viewDefaultRenderer";


export async function executeRenderPipeline(
  ctx: V.RenderContext,
): Promise<V.RenderOutput> {
  // 0. Mode dispatch — JSON bypasses view bindings entirely.
  if (ctx.mode === V.Mode.json) {
    return defaultRenderer(ctx);
  }

  // 1. Resolve view definition.
  const def = getView(ctx.view);
  if (!def) {
    // Unknown view + HTML mode → defaultRenderer (base.html).
    // The default renderer respects mode AND escapes — same
    // contract as a missing-route fallback in an HTTP framework.
    return defaultRenderer(ctx);
  }

  // 2. Compute template variables.
  const vars = await def.render(ctx);

  // 3. Load template (cached).
  const template = loadCachedTemplate(def.template);

  // 4. Apply template engine.
  const html = renderTemplate(template, vars);

  // 5. Return deterministic output.
  return {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body: html,
  };
}
