/**
 * Web Surface v0.2.0 — Server-Sent Events handler (Card A18).
 *
 * Architecture note (load-bearing — same as Card A17):
 *
 * The v0.2 Web Surface is shaped around returning a single
 * Response value: ``routeWebSurface(req) → Response``. There is
 * no live wire to push SSE frames into yet. So "SSE" in v0.2
 * means:
 *
 *   * The view's ``events(params)`` async generator (or the
 *     default fallback) yields ``SseEvent`` payloads.
 *   * The handler collects them in order, frames each one per
 *     the SSE wire grammar (``id:``/``event:``/``data:`` + blank-
 *     line terminator), and concatenates the frames into a
 *     single Response body.
 *
 * The event-sequence + framing contract is preserved as the
 * forward-compatibility surface: when Track C lands real wire
 * streaming, the same view generators can drive an EventSource-
 * compatible response without code changes — only the handler
 * swaps "collect into array" for "pipe to wire".
 *
 * Wire format (WHATWG HTML, Server-sent events):
 *
 *     id: <id>
 *     event: <event>
 *     data: <JSON-encoded data>
 *     <blank line — event terminator>
 *
 *   * Each line ends with a single ``\n``.
 *   * The blank-line terminator is ``\n`` after the last field
 *     line, producing the canonical ``...\n\n`` event boundary.
 *   * ``id:`` and ``event:`` are omitted entirely when the
 *     corresponding fields are undefined on the SseEvent.
 *   * ``data:`` is always present and always JSON-encoded.
 *
 * Determinism guarantees (locked by tests):
 *   * Same (view, params) in → same Response body, byte-for-byte.
 *   * Event ordering is the generator's emission order.
 *   * No async timing (views are encouraged to avoid
 *     ``await sleep(...)``).
 *   * Errors inside the generator are caught here and surface
 *     as a trailing ``event: error / data: {"aborted": true}``
 *     frame — the handler never throws past its caller.
 *
 * Mode handling (intentional simplification):
 *   * SSE is its own wire shape. Unlike A17's stream handler
 *     (which has HTML- and JSON-mode response shapes), A18
 *     always returns ``text/event-stream; charset=utf-8``. The
 *     action's ``mode`` field is preserved on the type for
 *     consistency but ignored by the handler. JSON-Accept
 *     clients that want structured event introspection should
 *     use the A17 stream variant instead.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { getView } from "./viewRegistry";
import { SseEvent } from "./sseEvent";
import { defaultSse } from "./defaultSse";


/** Shape of the classifier action this handler accepts. */
export interface SseAction {
  kind: "sse";
  view: string;
  params?: Record<string, unknown>;
  mode: V.Mode;
}


/** Wire content-type per WHATWG. Held as a constant so tests can
 *  assert against it without re-typing the string. */
export const SSE_CONTENT_TYPE = "text/event-stream; charset=utf-8";


/** Single SSE field line terminator (one ``\n``). */
const _LF = "\n";

/** SSE event-boundary terminator (two ``\n``s — the trailing
 *  blank line). */
const _EVENT_END = "\n\n";


/** Strip CR/LF from a single-line SSE field value. The SSE spec
 *  is line-oriented: an embedded newline in ``id`` or ``event``
 *  would split the value into separate fields. We replace runs
 *  of CR/LF with a single space and trim trailing whitespace.
 *  Same defensive policy as ``views/redirect.ts``'s allowlist:
 *  hostile-looking values get rendered as bytes-safe text rather
 *  than rejected outright. Exported for tests. */
export function _sanitizeSseField(value: string): string {
  return value.replace(/[\r\n]+/g, " ").trim();
}


/**
 * Format a single ``SseEvent`` as an SSE frame string.
 *
 * Field order: ``id:`` → ``event:`` → ``data:`` (per WHATWG).
 * ``id`` and ``event`` are omitted when undefined / null;
 * ``data`` is always emitted, JSON-stringified. The frame ends
 * with the blank-line terminator (``\n\n``).
 *
 * Exported for tests so the framing logic can be exercised
 * without going through the handler.
 */
export function _formatSseFrame(ev: SseEvent): string {
  const lines: string[] = [];
  if (ev.id !== undefined && ev.id !== null) {
    lines.push(`id: ${_sanitizeSseField(String(ev.id))}`);
  }
  if (ev.event !== undefined && ev.event !== null) {
    lines.push(`event: ${_sanitizeSseField(String(ev.event))}`);
  }
  lines.push(`data: ${JSON.stringify(ev.data)}`);
  return lines.join(_LF) + _EVENT_END;
}


/** The error-sentinel event appended to the stream when the
 *  generator throws. Exported so tests can match its exact
 *  bytes. */
export const SSE_ERROR_EVENT: SseEvent = {
  event: "error",
  data:  { aborted: true },
};


/**
 * Build the SSE response. Collects events from the view's
 * generator (or the default fallback) and assembles them into a
 * single Response body.
 *
 * The handler tries to recover from a thrown generator: any
 * frames already emitted are preserved, and the error sentinel
 * is appended so the client can detect the truncation. The
 * handler itself never throws past its caller.
 */
export async function handleSse(
  action: SseAction,
): Promise<WebSurfaceV0_2.Response> {
  const def = getView(action.view);

  const ctx: V.RenderContext = {
    view:   action.view,
    params: action.params,
    mode:   action.mode,
  };

  const frames: string[] = [];
  let aborted = false;
  try {
    const iterator: AsyncIterable<SseEvent> = def?.events
      ? def.events(action.params)
      : def
        ? defaultSse(def, ctx)
        : (async function* () { /* empty */ })();
    for await (const ev of iterator) {
      frames.push(_formatSseFrame(ev));
    }
  } catch {
    // Any failure during event emission → mark aborted, keep
    // what was already framed. Stack traces are intentionally
    // discarded (same policy as Card A11).
    aborted = true;
  }

  if (aborted) {
    frames.push(_formatSseFrame(SSE_ERROR_EVENT));
  }

  return {
    status:  200,
    headers: { "content-type": SSE_CONTENT_TYPE },
    body:    frames.join(""),
  };
}
