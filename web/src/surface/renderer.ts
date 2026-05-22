/**
 * Web Surface v0.2.0 — render dispatcher.
 *
 * Card A1 update: the renderer is no longer a 501 stub. It now
 * dispatches to a view registry (``viewRegistry.ts``) and falls
 * back to a deterministic default renderer
 * (``viewDefaultRenderer.ts``) when the requested view name isn't
 * registered. Output is real HTML or JSON depending on
 * ``ctx.mode``.
 *
 * The dispatcher's return type is the view contract's
 * ``RenderOutput``, which is a structural subtype of the wire
 * contract's ``WebSurfaceV0_2.Response`` — the router can return
 * it directly with no field shimming.
 *
 * Behavioural note:
 *   * The router's classifier today always returns
 *     ``{ kind: "noop" }``, so the renderer is never called from
 *     the live request path. Direct callers (tests, future
 *     classifier rules) get the real view output via this module.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { defaultRenderer } from "./viewDefaultRenderer";
import { getView } from "./viewRegistry";


/**
 * Backward-compat alias: external callers built against Card 9's
 * ``RenderContext`` interface keep working. The view-engine
 * contract is the source of truth going forward.
 */
export type RenderContext = V.RenderContext;


/**
 * Dispatch a Web Surface render request.
 *
 * Resolves the view name against ``viewRegistry``; falls back to
 * ``defaultRenderer`` for unknown names. The returned
 * ``RenderOutput`` is type-compatible with
 * ``WebSurfaceV0_2.Response`` so the router can return it
 * unchanged.
 */
export async function renderWebSurface(
  ctx: V.RenderContext,
): Promise<V.RenderOutput> {
  const renderer = getView(ctx.view) ?? defaultRenderer;
  return renderer(ctx);
}
