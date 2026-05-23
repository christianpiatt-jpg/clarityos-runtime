/**
 * Web Surface v0.2.0 — streaming route (Card A22-R, Track C).
 *
 * Server-level interceptor for ``GET /__stream``. The request
 * handler in ``../requestHandler.ts`` matches the path BEFORE
 * the surface router (mirrors the A21-R ``/__diagnostics`` and
 * the older ``/health`` + ``/ready`` patterns) and dispatches
 * here.
 *
 * Why a server-level interceptor (not a surface view):
 *   * ``__``-prefixed paths are operator/system surfaces; they
 *     must respond regardless of the view registry's state.
 *   * Single-purpose: this route runs the streaming task and
 *     frames its events as SSE — nothing else.
 *
 * Response shape:
 *   * ``text/event-stream; charset=utf-8`` — the wire type the
 *     browser ``EventSource`` constructor expects.
 *   * SSE frames are built via the existing ``_formatSseFrame``
 *     helper from the A18 SSE handler. Each ``StreamEvent``
 *     becomes one frame whose SSE ``event:`` field is the
 *     event ``type`` (``"log"`` / ``"status"`` / ``"done"`` /
 *     ``"error"``) and whose ``data:`` field is the full event
 *     JSON.
 *   * Frames are buffered into a single body, matching the
 *     v0.2 single-Response architecture documented in
 *     ``../surface/sseHandler.ts``. Real wire streaming lands
 *     when Track C upgrades the response writer; the route
 *     itself doesn't change.
 *
 * Error policy:
 *   * If the generator throws, the catch block appends a
 *     trailing ``error`` SSE frame and returns whatever was
 *     already buffered. The route never throws past its
 *     caller (defence-in-depth — the generator itself also
 *     yields a clean ``error`` event before throwing in test
 *     mode, so this catch is mainly for unexpected internal
 *     faults).
 *
 * Determinism / side effects:
 *   * Pure function of the request + controller state. No view
 *     registry mutations, no template cache eviction, no log
 *     writes.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { runStreamTask, type StreamEvent } from "../../surface/streaming";
import {
  _formatSseFrame,
  SSE_CONTENT_TYPE,
} from "../../surface/sseHandler";


/** The path the request handler matches against. Exported so
 *  the interceptor in ``requestHandler.ts`` imports the same
 *  constant (single source of truth). */
export const STREAM_PATH = "/__stream";


/** The error sentinel appended when the generator throws past
 *  its own ``error`` event. Exported for tests so the exact
 *  shape can be asserted without rebuilding the literal. */
export const STREAM_FATAL_ERROR_EVENT: StreamEvent = {
  type:    "error",
  message: "stream failed",
};


/**
 * Run the streaming task and frame its events into a single
 * SSE-shaped Response.
 *
 * Each ``StreamEvent`` is emitted as one SSE frame:
 *
 *     event: <type>
 *     data: {"type": "<type>", "message": "<message>"}
 *
 * (with the canonical ``\n\n`` event terminator that
 * ``_formatSseFrame`` appends).
 */
export async function handleStream(
  request: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  const frames: string[] = [];
  try {
    for await (const event of runStreamTask(request)) {
      frames.push(_formatSseFrame({
        event: event.type,
        data:  event,
      }));
    }
  } catch {
    // Defence-in-depth — the controller's documented contract
    // is to yield a clean ``error`` event before throwing, but
    // an unexpected fault must still produce a well-formed
    // terminal frame.
    frames.push(_formatSseFrame({
      event: STREAM_FATAL_ERROR_EVENT.type,
      data:  STREAM_FATAL_ERROR_EVENT,
    }));
  }

  return {
    status:  200,
    headers: { "content-type": SSE_CONTENT_TYPE },
    body:    frames.join(""),
  };
}
