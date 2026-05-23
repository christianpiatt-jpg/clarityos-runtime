/**
 * Web Surface v0.2.0 — status route (Card A23-R, Track C).
 *
 * Server-level interceptor for ``POST /__status``. The request
 * handler in ``../requestHandler.ts`` matches the path BEFORE
 * the surface router (mirrors the A21-R ``/__diagnostics`` and
 * A22-R ``/__stream`` patterns) and dispatches here.
 *
 * Why a server-level interceptor (not a surface view):
 *   * ``__``-prefixed paths are operator/system surfaces; they
 *     must respond regardless of the view registry's state.
 *   * The route's job is exactly one thing — render a status
 *     fragment for the JSON payload. No view registration, no
 *     params schema, no mode switching.
 *
 * Request shape:
 *   * Method: ``POST``. ``GET`` (or any non-POST) returns the
 *     ``method_not_allowed`` failure surface.
 *   * Content-type: ``application/json`` (recommended). The
 *     handler is lenient — it tries to parse the body as JSON
 *     regardless of the declared content-type.
 *   * Body: ``{"kind": "success"|"warning"|"failure", "message": "..."}``.
 *
 * Response shape:
 *   * Always HTML. Per the A23-R card, no JSON responses.
 *   * Status 200 for a well-formed payload; 400 for bad input
 *     (the body is still HTML — the ``failure`` template, with
 *     a diagnostic message).
 *   * Content-type: ``text/html; charset=utf-8``.
 *
 * Determinism / side effects:
 *   * Pure function over (request body, template cache). No
 *     view registry mutations, no logs, no clock.
 *   * The renderer is the only stateful collaborator and its
 *     state (template cache) is populated once per process.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import {
  renderStatusSurface,
  type StatusKind,
  type StatusPayload,
} from "../../surface/status";


/** The path the request handler matches against. Exported so
 *  the interceptor in ``requestHandler.ts`` imports the same
 *  constant (single source of truth). */
export const STATUS_PATH = "/__status";


/** Allowed StatusKind values. Held as a set so the parse
 *  validator can check membership in O(1). */
const _VALID_KINDS: ReadonlySet<StatusKind> = new Set<StatusKind>([
  "success",
  "warning",
  "failure",
]);


/**
 * Handle a ``POST /__status`` request. Always returns HTML;
 * never throws past its caller.
 *
 * Failure paths (all produce a 400 + ``failure`` surface):
 *   * Non-POST method.
 *   * Non-string body (multipart upload, empty GET-style body).
 *   * Body that doesn't parse as JSON.
 *   * Payload missing / wrong-typed ``kind`` or ``message``.
 *   * ``kind`` not in the allowed set.
 *
 * Success path:
 *   * Status 200, body = the rendered status fragment.
 */
export async function handleStatus(
  request: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  if (request.method !== "POST") {
    return _failureResponse(
      400,
      "method_not_allowed: /__status requires POST",
    );
  }

  if (typeof request.body !== "string") {
    return _failureResponse(
      400,
      "bad_request: missing JSON body",
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(request.body);
  } catch {
    return _failureResponse(
      400,
      "bad_request: body is not valid JSON",
    );
  }

  const payload = _coercePayload(parsed);
  if (!payload) {
    return _failureResponse(
      400,
      "bad_request: payload must be {kind, message} " +
      "with kind in {success, warning, failure}",
    );
  }

  const html = await renderStatusSurface(payload);
  return {
    status:  200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    html,
  };
}


/** Coerce an arbitrary parsed JSON value into a
 *  ``StatusPayload``, or return ``null`` if the shape is
 *  wrong. Exported for tests so the validation table can be
 *  exercised directly. */
export function _coercePayload(raw: unknown): StatusPayload | null {
  if (raw === null || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const kind = obj.kind;
  const message = obj.message;
  if (typeof kind !== "string") return null;
  if (typeof message !== "string") return null;
  if (!_VALID_KINDS.has(kind as StatusKind)) return null;
  return { kind: kind as StatusKind, message };
}


/** Render a failure-surface response with the given status
 *  code and message. The body is HTML produced by the standard
 *  renderer, so error responses look exactly like success
 *  responses to the enhancement layer (one of the key A23-R
 *  invariants — the UX is uniform regardless of outcome). */
async function _failureResponse(
  status: number,
  message: string,
): Promise<WebSurfaceV0_2.Response> {
  const html = await renderStatusSurface({ kind: "failure", message });
  return {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    html,
  };
}
