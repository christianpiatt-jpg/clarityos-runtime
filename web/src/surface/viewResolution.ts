/**
 * Web Surface v0.2.0 — view resolution layer.
 *
 * Card A2 — Track A. Deterministic mapping from a
 * ``WebSurfaceV0_2.Request`` to:
 *
 *   * a view name        (registry key for the renderer)
 *   * a rendering mode   (``html`` or ``json``)
 *   * a params record    (querystring → opaque object)
 *
 * The resolver is pure and side-effect-free: same Request in →
 * same ResolvedView out, no fetch / storage / globals touched.
 * It is consumed by the classifier (``classifier.ts``); the router
 * never calls it directly.
 *
 * Resolution rules (locked by tests):
 *
 *   * Mode is ``json`` if either:
 *       (a) the Accept header carries ``application/json``, or
 *       (b) the querystring carries ``?mode=json``
 *     Anything else → ``html``.
 *
 *   * View name is the LAST non-empty path segment, falling back
 *     to ``"index"`` for empty paths. Examples:
 *       /web-surface/v0.2/home      → "home"
 *       /web-surface/v0.2/          → "v0.2" (trailing slash dropped)
 *       /web-surface/v0.2/foo/bar   → "bar"
 *       /                           → "index"
 *
 *   * Params is the querystring as a key→string map, with the
 *     resolver's own ``mode`` key stripped (it controls the
 *     resolver itself, not the view).
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";


export interface ResolvedView {
  view: string;
  mode: V.Mode;
  params: Record<string, unknown>;
}


/**
 * Resolve a Request into a (view, mode, params) tuple. Pure; same
 * inputs → same outputs. Called by ``classifier.ts`` to produce the
 * ``render`` variant of ``ClassifiedSurfaceAction``.
 *
 * ``req.path`` may carry a querystring (``"/home?x=1"``); the
 * resolver parses it via ``new URL(path, base)`` with a sentinel
 * base so relative paths work without a host context.
 */
export function resolveView(req: WebSurfaceV0_2.Request): ResolvedView {
  const url = new URL(req.path, "http://placeholder");

  // 1. Mode selection — Accept header OR ?mode=json query wins.
  const accept = req.headers["accept"] ?? "";
  const acceptJson = accept.includes("application/json");
  const queryJson = url.searchParams.get("mode") === "json";
  const mode: V.Mode =
    acceptJson || queryJson ? V.Mode.json : V.Mode.html;

  // 2. View name — last non-empty path segment, fallback "index".
  const segments = url.pathname.split("/").filter(Boolean);
  const view = segments[segments.length - 1] || "index";

  // 3. Params — querystring entries minus our own ``mode`` key.
  const params: Record<string, unknown> = {};
  for (const [k, v] of url.searchParams.entries()) {
    if (k === "mode") continue;
    params[k] = v;
  }

  return { view, mode, params };
}
