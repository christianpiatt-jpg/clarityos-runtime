/**
 * Web Surface v0.2.0 — default view renderer.
 *
 * Fallback renderer used when ``getView(ctx.view)`` returns
 * ``undefined``. Produces a deterministic HTML or JSON output that
 * echoes the requested view + params.
 *
 * Card A1 (initial):       inline HTML construction with manual escape.
 * Card A3 (this revision): HTML mode now uses the template engine —
 *                          loads ``base.html`` from
 *                          ``web/templates/v0.2/`` and substitutes
 *                          ``title`` + ``content`` placeholders.
 *                          JSON mode is unchanged.
 *
 * Security policy (locked by tests):
 *   * The renderer HTML-escapes every value BEFORE it reaches the
 *     template engine. The engine itself does not escape (so it
 *     can also drive non-HTML outputs in the future). This
 *     separation keeps the XSS guard at the boundary that knows
 *     the output content-type.
 *
 * Deterministic shape:
 *   * ``mode === "json"`` → 200 with body ``{ view, params }``,
 *     content-type ``application/json``.
 *   * ``mode === "html"`` → 200 with ``base.html`` substituted,
 *     content-type ``text/html; charset=utf-8``.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { loadTemplate } from "./templateLoader";
import { renderTemplate } from "./templateEngine";


/** Minimal HTML-entity escape. Covers the five characters that
 *  matter for HTML body + attribute contexts. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


export async function defaultRenderer(
  ctx: V.RenderContext,
): Promise<V.RenderOutput> {
  const params = ctx.params ?? {};

  if (ctx.mode === V.Mode.json) {
    return {
      status: 200,
      headers: { "content-type": "application/json" },
      body: { view: ctx.view, params },
    };
  }

  // HTML mode — template engine + per-value escape at the boundary.
  // ``title`` and ``content`` are the two placeholders in
  // ``base.html``. Both are HTML-escaped before substitution so
  // the engine itself stays content-type-agnostic.
  const template = loadTemplate("base");
  const html = renderTemplate(template, {
    title:   escapeHtml(ctx.view),
    content: escapeHtml(JSON.stringify(params, null, 2)),
  });

  return {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body: html,
  };
}
