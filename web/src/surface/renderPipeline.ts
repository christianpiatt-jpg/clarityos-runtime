/**
 * Web Surface v0.2.0 — render pipeline.
 *
 * Card A5 (initial): single source of truth for rendering.
 * Card A6        : engine gained partial inclusion.
 * Card A7        : pipeline gained optional layout wrapping.
 * Card A9 (this) : pipeline auto-injects fingerprinted asset URLs.
 *
 * Mode-aware dispatch (preserved from A4/A5):
 *
 *   0. If ``ctx.mode === "json"`` → return ``defaultRenderer(ctx)``.
 *      JSON is the canonical machine-readable representation; per-
 *      view JSON shaping is a follow-up card.
 *
 *   1. Resolve view definition via ``getView(ctx.view)``. Unknown
 *      view → fall through to ``defaultRenderer(ctx)`` (HTML mode
 *      uses base.html via the template engine + XSS escape).
 *
 *   2. ``vars = await def.render(ctx)``. The view owns DATA; the
 *      pipeline owns ENVELOPE.
 *
 *   2.5 Asset-var injection (NEW in A9). The pipeline merges a
 *      small fixed set of fingerprinted asset URLs into ``vars``
 *      BEFORE template + layout substitution:
 *
 *        style_css → fingerprintedPath("style.css")
 *        app_js    → fingerprintedPath("app.js")
 *
 *      The layout (``standard.html``) consumes these via
 *      ``{{ style_css }}`` / ``{{ app_js }}`` placeholders inside
 *      ``<link>`` and ``<script>`` tags. View templates ignore the
 *      vars (unused placeholders just disappear). View renders
 *      that happen to declare their own ``style_css`` / ``app_js``
 *      win — the spread order keeps view-supplied values
 *      authoritative.
 *
 *   3. View-template substitution. Load + cache ``def.template``,
 *      run it through the template engine with ``vars``. This is
 *      ``viewHtml``.
 *
 *   4. Layout wrapping (A7). If ``def.layout`` is set, load + cache
 *      the named layout and run it through the template engine with
 *      ``{ ...vars, yield: viewHtml }``. ``{{ yield }}`` in the
 *      layout substitutes the rendered view body; all other ``vars``
 *      (including the asset vars) propagate through unchanged. If
 *      ``def.layout`` is undefined, the unwrapped ``viewHtml`` is
 *      the final output.
 *
 *   5. Return deterministic 200 + ``text/html`` Response.
 *
 * Composition contract:
 *   base.html  ─ used ONLY by the default renderer for unknown
 *                views. Standalone full document.
 *   layouts/*  ─ full documents with ``{{ yield }}``. View
 *                templates wrapped in a layout supply just the
 *                inner body content; the layout owns the document
 *                chrome (DOCTYPE / html / head / body / partials).
 *   views/*    ─ when bound to a layout, they're body fragments.
 *                When standalone (no layout), they're full
 *                documents (like base.html).
 *
 * Determinism guarantees (locked by tests):
 *   * Same ``ctx`` in → same ``RenderOutput`` out, byte-for-byte
 *     (asset vars derive from the asset bytes via SHA-256, so the
 *     fingerprints themselves are deterministic).
 *   * Pipeline does not mutate ``ctx``, the registry, or the
 *     view's vars (the layout-substitution context is a fresh
 *     spread, not an in-place mutation).
 *   * Caches grow additively on first miss; never overwrite.
 *   * Asset manifest is process-singleton; the same vars object is
 *     populated on every render after the first.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { getView } from "./viewRegistry";
import { loadCachedTemplate } from "./templateCache";
import { loadCachedLayout } from "./layoutCache";
import { renderTemplate } from "./templateEngine";
import { defaultRenderer } from "./viewDefaultRenderer";
import { getFingerprintedPath } from "./assetManifest";


/**
 * Build the asset-var bag that the render pipeline merges into
 * every view's ``vars``. Exported so tests can compare what the
 * pipeline computes against what the layout actually renders.
 *
 * Each fingerprinted URL is computed via the manifest, which
 * caches the SHA-256 → 12-hex result. Two calls produce the same
 * strings; production runs incur one disk read per asset per
 * process lifetime.
 */
export function buildAssetVars(): Record<string, string> {
  return {
    style_css: getFingerprintedPath("style.css"),
    app_js:    getFingerprintedPath("app.js"),
  };
}


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
    return defaultRenderer(ctx);
  }

  // 2. Compute view variables.
  // 2.5 Merge in the pipeline-owned asset vars. Asset vars go
  // FIRST so a view's own render() can override them by simply
  // including the same key in its return value — defaults that
  // bend to view authority, not the other way round.
  const vars = {
    ...buildAssetVars(),
    ...(await def.render(ctx)),
  };

  // 3. View-template substitution.
  const viewTemplate = loadCachedTemplate(def.template);
  const viewHtml = renderTemplate(viewTemplate, vars);

  // 4. Layout wrapping (optional). The layout receives the view's
  // vars + an auto-added ``yield`` that contains the rendered
  // view body. Note: the spread builds a FRESH object — vars is
  // not mutated.
  let finalHtml = viewHtml;
  if (def.layout) {
    const layoutTemplate = loadCachedLayout(def.layout);
    finalHtml = renderTemplate(layoutTemplate, {
      ...vars,
      yield: viewHtml,
    });
  }

  // 5. Return deterministic output.
  return {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body: finalHtml,
  };
}
