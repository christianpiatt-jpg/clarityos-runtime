/**
 * Web Surface v0.2.0 — loading route (Card A24-R, Track C).
 *
 * Server-level interceptor for ``POST /__loading``. The
 * request handler in ``../requestHandler.ts`` matches the
 * path BEFORE the surface router (mirrors the A21-R
 * ``/__diagnostics``, A22-R ``/__stream``, and A23-R
 * ``/__status`` patterns) and dispatches here.
 *
 * Why a server-level interceptor (not a surface view):
 *   * ``__``-prefixed paths are operator/system surfaces; they
 *     must respond regardless of the view registry's state.
 *   * Single-purpose: render a loading fragment for the
 *     (optional) message in the JSON body. No view
 *     registration, no params schema.
 *
 * Request shape:
 *   * Method: ``POST``. Any other method returns the loading
 *     surface anyway (lenient — the worst case is "showed a
 *     spinner on a GET"). The lenience matches the A24-R card
 *     spec, which calls out "optional JSON body" — the route
 *     is designed to be hard to break.
 *   * Content-type: ``application/json`` (recommended). The
 *     handler is lenient about the declared content-type and
 *     about parse failures.
 *   * Body: ``{}`` or ``{"message": "..."}`` — both valid.
 *     Missing / unparseable bodies degrade to the default
 *     message ``"Loading…"`` rather than failing.
 *
 * Response shape:
 *   * Always 200 + ``text/html; charset=utf-8`` (per the
 *     A24-R card spec).
 *   * Body is the rendered loading fragment.
 *
 * Determinism / side effects:
 *   * Pure function over (request body, template cache). No
 *     view registry mutations, no logs, no clock.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  renderLoadingSurface,
  type LoadingPayload,
} from "../../surface/loading";


/** The path the request handler matches against. Exported so
 *  the interceptor in ``requestHandler.ts`` imports the same
 *  constant (single source of truth). */
export const LOADING_PATH = "/__loading";


/**
 * Handle a ``POST /__loading`` request. Always returns
 * 200 + HTML; never throws past its caller.
 *
 * Lenient by design:
 *   * Missing body → default-message fragment.
 *   * Non-string body (multipart, etc.) → default-message
 *     fragment.
 *   * Unparseable JSON → default-message fragment.
 *   * JSON without ``message`` → default-message fragment.
 *   * JSON with non-string ``message`` → default-message
 *     fragment (the renderer's own fallback handles this).
 */
export async function handleLoading(
  request: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  const payload = _coercePayload(request.body);
  const html = await renderLoadingSurface(payload);
  return {
    status:  200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    html,
  };
}


/** Coerce an arbitrary request body into a ``LoadingPayload``.
 *  Returns an empty payload on any parse / shape failure so
 *  the renderer falls back to the default message. Exported
 *  for tests so the lenient parser can be exercised
 *  directly. */
export function _coercePayload(body: unknown): LoadingPayload {
  if (typeof body !== "string" || body.length === 0) {
    return {};
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return {};
  }
  if (parsed === null || typeof parsed !== "object") {
    return {};
  }
  const message = (parsed as { message?: unknown }).message;
  if (typeof message !== "string") {
    return {};
  }
  return { message };
}
