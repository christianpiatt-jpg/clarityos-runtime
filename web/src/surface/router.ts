/**
 * Web Surface v0.2.0 — router.
 *
 * Wires the classifier (Card 8) to the surface action handlers.
 * For Card 8 every request classifies to ``noop`` and the router
 * returns a 501 ``ErrorEnvelope`` directly. The render branch is
 * a placeholder until Card 9 introduces the renderer skeleton.
 *
 * Card A11: the router additionally transforms ErrorEnvelope-
 * shaped responses into HTML when the original request asked for
 * HTML. The transform fires AFTER the sub-router (asset / render
 * / noop) returns, so every error path — asset 404, noop 501,
 * future server errors — gets the same structured 500 page when
 * a browser asks for HTML. JSON requests pass through unchanged.
 *
 * The router stays pure: classification + response shaping are
 * side-effect-free. Anything stateful (logging, telemetry,
 * persistence) lands in a future card, not here.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { classifyWebSurfaceRequest } from "./classifier";
import { renderWebSurface } from "./renderer";
import { routeAsset } from "./assetRouter";


/** URL prefix the asset router claims. Anything below this path
 *  short-circuits the classifier and serves a static file. */
const _ASSETS_PREFIX = "/web-surface/v0.2/assets/";


/** Registry key for the 500 view, kept as a constant so tests
 *  can assert against it without re-typing the literal. */
export const ERROR_500_VIEW = "error_500";


/**
 * Returns true when ``response.body`` matches the contract's
 * ``ErrorEnvelope`` shape (``{error: string, detail?: unknown}``).
 * Used by the envelope→HTML transform to decide whether a
 * response is an error worth re-rendering.
 */
function _isErrorEnvelope(
  response: WebSurfaceV0_2.Response,
): response is WebSurfaceV0_2.Response & {
  body: WebSurfaceV0_2.ErrorEnvelope;
} {
  const body = response.body;
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return false;
  }
  return typeof (body as { error?: unknown }).error === "string";
}


/**
 * Returns true when the caller wants HTML — same heuristic as
 * ``viewResolution.resolveView``: Accept: application/json OR
 * ?mode=json → JSON; anything else → HTML.
 *
 * Duplicated rather than imported because the resolver returns a
 * full ResolvedView (view + mode + params), and the router only
 * needs the mode bit AND must also run for asset-prefix requests
 * (which the resolver isn't intended to inspect).
 */
function _wantsHtml(req: WebSurfaceV0_2.Request): boolean {
  const accept = req.headers["accept"] ?? "";
  if (accept.includes("application/json")) return false;
  try {
    const url = new URL(req.path, "http://placeholder");
    if (url.searchParams.get("mode") === "json") return false;
  } catch {
    // Malformed path → fall through to the HTML default; the
    // sub-router will produce whatever envelope is appropriate
    // and we'll either pass it through or transform it.
  }
  return true;
}


/**
 * Card A11 — envelope → HTML transform.
 *
 * If the assembled response is an ErrorEnvelope and the caller
 * asked for HTML, re-render the envelope's ``error`` field via
 * the ``error_500`` view. Pass-through in every other case (JSON
 * requests, success responses, non-envelope bodies).
 *
 * Recursion is bounded:
 *   * The re-render dispatches through ``renderWebSurface``, which
 *     is the pipeline. The pipeline has its own try/catch (Card
 *     A11) so any failure inside it produces an HTML 500 body,
 *     never an envelope. So the transform cannot loop.
 *   * If the re-render itself somehow returns an envelope, the
 *     caller still sees the second response — we don't re-enter
 *     the transform after the recursive call.
 */
async function _envelopeToHtml(
  req: WebSurfaceV0_2.Request,
  response: WebSurfaceV0_2.Response,
): Promise<WebSurfaceV0_2.Response> {
  if (!_wantsHtml(req)) return response;
  if (!_isErrorEnvelope(response)) return response;

  return renderWebSurface({
    view:   ERROR_500_VIEW,
    params: { message: response.body.error },
    mode:   V.Mode.html,
  });
}


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
  //
  // The envelope→HTML transform deliberately does NOT fire here.
  // Asset 404s are subresource failures (browsers don't render
  // the response body; API clients want the JSON envelope), so
  // the transform's "show the user a structured error page"
  // motivation doesn't apply. Direct browser navigation to a
  // missing asset URL is the only case where this matters, and
  // it's rare enough that the JSON envelope is acceptable.
  if (req.path.startsWith(_ASSETS_PREFIX)) {
    const pathname = req.path.slice(_ASSETS_PREFIX.length);
    return routeAsset(pathname);
  }

  const action = classifyWebSurfaceRequest(req);

  let response: WebSurfaceV0_2.Response;
  switch (action.kind) {
    case "noop":
      response = notImplementedResponse(
        "web_surface_noop",
        {
          message: "no action classified for this request",
          path:    req.path,
          method:  req.method,
          version: WebSurfaceV0_2.VERSION,
        },
      );
      break;
    case "render":
      // Card A2: the classifier resolves mode via
      // ``viewResolution.resolveView`` (Accept header / ?mode=
      // query / default html), so the router forwards
      // ``action.mode`` through to the renderer unchanged.
      response = await renderWebSurface({
        view:   action.view,
        params: action.params,
        mode:   action.mode,
      });
      break;
    default: {
      // Exhaustive-switch guard. If a new ClassifiedSurfaceAction
      // variant lands without this switch being updated, TypeScript
      // narrows ``action`` to ``never`` here and the build fails.
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }

  // Card A11: noop 501 envelopes and any future envelope-shaped
  // pipeline output → HTML error page for browser-style requests.
  return _envelopeToHtml(req, response);
}
