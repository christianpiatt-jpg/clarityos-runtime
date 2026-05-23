/**
 * Web Surface v0.2.0 — diagnostics route (Card A21-R, Track C).
 *
 * Server-level interceptor for ``GET /__diagnostics``. The
 * request handler in ``../requestHandler.ts`` matches the path
 * BEFORE the surface router (mirrors the ``/health`` + ``/ready``
 * pattern in ``../healthRouter.ts``) and dispatches here.
 *
 * Why a server-level interceptor (not a surface view):
 *   * ``__``-prefixed paths are operator/system surfaces; they
 *     must respond regardless of the view registry's state.
 *   * Keeping the route out of ``routeWebSurface`` means a broken
 *     view registry can't take diagnostics down with it.
 *   * Single-purpose: this route renders the diagnostic fragment
 *     and nothing else.
 *
 * Response shape:
 *   * Always HTML — the route returns a fragment, not JSON. The
 *     enhancement layer's content-type branch (A20-R) requires
 *     HTML to swap into ``data-diagnostic-target``; serving JSON
 *     would force the no-op fallback path.
 *   * The JSON payload is HTML-escaped and embedded inside the
 *     ``<pre data-json>`` element so operators can copy-paste
 *     without worrying about HTML interpretation.
 *
 * Determinism / side effects:
 *   * Pure-ish: deterministic except for the wall-clock read
 *     inside ``collectDiagnostics`` (the ``timestamp`` field).
 *   * No view registry mutations, no template cache eviction,
 *     no log writes.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { collectDiagnostics } from "../../surface/diagnostics";
import { loadCachedTemplate } from "../../surface/templateCache";
import { renderTemplate } from "../../surface/templateEngine";


/** The path the request handler matches against. Exported so
 *  the interceptor in ``requestHandler.ts`` imports the same
 *  constant (single source of truth). */
export const DIAGNOSTICS_PATH = "/__diagnostics";


/** Minimal HTML-entity escape. Mirrors the per-view escape
 *  policy across the codebase (forms/errors.ts, views/home.ts,
 *  views/errors.ts). Exported for tests that want to assert the
 *  exact escape behaviour. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/**
 * Build the diagnostic HTML fragment for the given request.
 * Returns a full ``WebSurfaceV0_2.Response`` so the request
 * handler can pass it straight through ``writeSurfaceResponse``
 * without any further translation.
 */
export async function handleDiagnostics(
  request: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  const payload = await collectDiagnostics(request);
  // Pretty-print so the operator-facing ``<pre>`` is readable.
  // The 2-space indent matches the codebase's other JSON
  // pretty-print sites (manifest.json, etc.).
  const json = JSON.stringify(payload, null, 2);
  const template = loadCachedTemplate("diagnosticFragment");
  const html = renderTemplate(template, { json: escapeHtml(json) });
  return {
    status:  200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    html,
  };
}
