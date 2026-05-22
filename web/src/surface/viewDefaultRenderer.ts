/**
 * Web Surface v0.2.0 — default view renderer.
 *
 * Fallback renderer used when ``getView(ctx.view)`` returns
 * ``undefined``. Produces a deterministic HTML or JSON output that
 * echoes the requested view + params — useful for stubbing a view
 * during development and as a base case for the test suite.
 *
 * Deterministic shape:
 *   * ``mode === "json"`` → 200 with body ``{ view, params }``,
 *     content-type ``application/json``.
 *   * ``mode === "html"`` → 200 with body containing the view name
 *     in an ``<h1>`` plus the params under a ``<pre>`` block,
 *     content-type ``text/html; charset=utf-8``.
 *
 * Security note (locked by tests):
 *   * The HTML output passes the view name + params through a
 *     minimal HTML-entity escape. Even at skeleton stage, the
 *     renderer MUST NOT emit raw unescaped strings into the DOM —
 *     otherwise a future caller could pass user-controlled input
 *     and the renderer would be the XSS vector.
 *
 * Card A1 — Track A — View Engine foundation.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";


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

  // HTML mode — content-type charset is explicit so the browser
  // doesn't sniff. The view name + params are HTML-escaped before
  // interpolation.
  const safeView = escapeHtml(ctx.view);
  const safeParams = escapeHtml(JSON.stringify(params, null, 2));
  const html = [
    "<!DOCTYPE html>",
    "<html>",
    `  <head><title>${safeView}</title></head>`,
    "  <body>",
    `    <h1>${safeView}</h1>`,
    `    <pre>${safeParams}</pre>`,
    "  </body>",
    "</html>",
  ].join("\n");

  return {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body: html,
  };
}
