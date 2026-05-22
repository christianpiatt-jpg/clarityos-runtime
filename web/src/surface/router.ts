/**
 * Web Surface v0.2.0 — router.
 *
 * Wires the classifier (Card 8) to the surface action handlers.
 * For Card 8 every request classifies to ``noop`` and the router
 * returns a 501 ``ErrorEnvelope`` directly. The render branch is
 * a placeholder until Card 9 introduces the renderer skeleton.
 *
 * The router stays pure: classification + response shaping are
 * side-effect-free. Anything stateful (logging, telemetry,
 * persistence) lands in a future card, not here.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { classifyWebSurfaceRequest } from "./classifier";
import { renderWebSurface } from "./renderer";
import { routeAsset } from "./assetRouter";


/** URL prefix the asset router claims. Anything below this path
 *  short-circuits the classifier and serves a static file. */
const _ASSETS_PREFIX = "/web-surface/v0.2/assets/";


/**
 * Construct a 501 ErrorEnvelope as a ``WebSurfaceV0_2.Response``.
 * Used by the noop branch (Card 8) and as the fallback shape until
 * the renderer is wired in Card 9.
 */
function notImplementedResponse(
  error: string,
  detail?: unknown,
): WebSurfaceV0_2.Response {
  const envelope: WebSurfaceV0_2.ErrorEnvelope = { error };
  if (detail !== undefined) {
    envelope.detail = detail;
  }
  return {
    status:  501,
    headers: { "content-type": "application/json" },
    body:    envelope,
  };
}


/**
 * Route a Web Surface request through classification → dispatch.
 *
 * Card 8 wiring: every request classifies to ``noop`` → returns a
 * 501 ErrorEnvelope. Card 9 will replace the render branch's
 * placeholder with a call to ``renderWebSurface``.
 */
export async function routeWebSurface(
  req: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  // Card A8: asset short-circuit. Requests under
  // ``/web-surface/v0.2/assets/`` are static files — bypass the
  // classifier + view renderer entirely and serve the bytes.
  if (req.path.startsWith(_ASSETS_PREFIX)) {
    const pathname = req.path.slice(_ASSETS_PREFIX.length);
    return routeAsset(pathname);
  }

  const action = classifyWebSurfaceRequest(req);

  switch (action.kind) {
    case "noop":
      return notImplementedResponse(
        "web_surface_noop",
        {
          message: "no action classified for this request",
          path:    req.path,
          method:  req.method,
          version: WebSurfaceV0_2.VERSION,
        },
      );
    case "render":
      // Card A2: the classifier resolves mode via
      // ``viewResolution.resolveView`` (Accept header / ?mode=
      // query / default html), so the router forwards
      // ``action.mode`` through to the renderer unchanged.
      return renderWebSurface({
        view:   action.view,
        params: action.params,
        mode:   action.mode,
      });
    default: {
      // Exhaustive-switch guard. If a new ClassifiedSurfaceAction
      // variant lands without this switch being updated, TypeScript
      // narrows ``action`` to ``never`` here and the build fails.
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}
