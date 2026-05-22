/**
 * Web Surface v0.2.0 — render pipeline skeleton.
 *
 * Card 9 placeholder. Today every call returns a schema-conformant
 * 501 ``ErrorEnvelope`` Response that carries the requested view +
 * params under ``detail`` for diagnostics. A future card will
 * replace this with real view dispatch (HTML / JSON / templated
 * output, dictionary of view-name → handler).
 *
 * Constraints:
 *   * Pure: same RenderContext in → equivalent Response out
 *           (modulo identity — the function always builds a fresh
 *            response object).
 *   * Output MUST conform to ``WebSurfaceV0_2.Response``.
 *   * Output body MUST conform to ``WebSurfaceV0_2.ErrorEnvelope``
 *     until real rendering lands (top-level keys = {error, detail}).
 *   * No side effects: no fetch, no storage, no globals.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";


/**
 * Input to the renderer. Mirrors the ``render`` variant of
 * ``ClassifiedSurfaceAction`` from the classifier — the router
 * destructures the variant into this shape before dispatch.
 */
export interface RenderContext {
  view: string;
  params?: Record<string, unknown>;
}


/**
 * Render a Web Surface view.
 *
 * v0.2.0 stub: returns a 501 ErrorEnvelope. The requested view +
 * any params are echoed under ``detail`` so a caller can confirm
 * the classification → render pipeline composed correctly (the
 * router-level integration tests rely on this).
 */
export async function renderWebSurface(
  ctx: RenderContext,
): Promise<WebSurfaceV0_2.Response> {
  // TODO(v0.2.0): replace with real view dispatch. Anticipated shape:
  //   const handler = VIEW_HANDLERS[ctx.view];
  //   if (!handler) return notFoundResponse(ctx.view);
  //   return handler(ctx.params ?? {});
  const envelope: WebSurfaceV0_2.ErrorEnvelope = {
    error: "web_surface_renderer_not_implemented",
    detail: {
      message: "Web Surface renderer not implemented",
      view:    ctx.view,
      version: WebSurfaceV0_2.VERSION,
      ...(ctx.params !== undefined
        ? { param_count: Object.keys(ctx.params).length }
        : {}),
    },
  };
  return {
    status:  501,
    headers: { "content-type": "application/json" },
    body:    envelope,
  };
}
