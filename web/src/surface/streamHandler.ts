/**
 * Web Surface v0.2.0 — streaming response handler (Card A17).
 *
 * Architecture note (load-bearing):
 *
 * The v0.2 Web Surface is currently SHAPED around returning a
 * single Response value: ``routeWebSurface(req) → Response``.
 * There is no Node ``res`` write-stream to push chunks into —
 * the surface is deploy-inactive and tests call the function
 * directly. So "streaming" in v0.2 means:
 *
 *   * The view's ``stream(params)`` async generator (or the
 *     default fallback) yields chunks in deterministic order.
 *   * The handler COLLECTS those chunks into an in-memory buffer.
 *   * The Response body is the assembled output (HTML:
 *     ``<!-- stream start --><c1><c2>...<!-- stream end -->``;
 *     JSON: ``{stream: true, chunks: [c1, c2, ...]}``).
 *
 * The chunk-sequence API is preserved as a forward-compatibility
 * contract: when Track C activates Cloud Run, the same view
 * generators can drive real chunked transfer-encoding without
 * code changes — only the handler swaps "collect into array"
 * for "pipe to wire".
 *
 * Determinism guarantees (locked by tests):
 *   * Same (view, params, mode) in → same Response out,
 *     byte-for-byte. Chunk ordering is the generator's emission
 *     order, which is fixed by JavaScript's for-await-of
 *     semantics.
 *   * No async timing in tests / production: views are
 *     encouraged to avoid ``await sleep(...)`` and similar.
 *   * Errors inside the generator are caught here and surface as
 *     a trailing error-marker chunk; the handler never throws
 *     past its caller (mirrors the pipeline's A11 fail-safe
 *     pattern).
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { getView } from "./viewRegistry";
import { defaultStream } from "./defaultStream";


/** Shape of the classifier action this handler accepts. */
export interface StreamAction {
  kind: "stream";
  view: string;
  params?: Record<string, unknown>;
  mode: V.Mode;
}


/** Sentinel markers — exported so tests can assert against the
 *  exact strings without re-typing them. */
export const STREAM_HTML_START_MARKER = "<!-- stream start -->";
export const STREAM_HTML_END_MARKER   = "<!-- stream end -->";
export const STREAM_HTML_ERROR_MARKER =
  "<!-- stream aborted: internal error -->";


/**
 * Build the streaming response. Collects chunks from the view's
 * generator (or the default fallback) and assembles them into a
 * single Response body, mode-appropriate.
 *
 * The handler tries to recover from a thrown chunk: any chunks
 * already emitted are preserved, and an error sentinel is
 * appended so the client can detect a truncated stream. The
 * handler itself never throws.
 */
export async function handleStream(
  action: StreamAction,
): Promise<WebSurfaceV0_2.Response> {
  const def = getView(action.view);

  // Build a proper RenderContext for the view (and for the
  // default streaming fallback, which needs one to call
  // def.render). This mirrors the renderPipeline's ctx shape.
  const ctx: V.RenderContext = {
    view:   action.view,
    params: action.params,
    mode:   action.mode,
  };

  const chunks: string[] = [];
  let aborted = false;
  try {
    // Pick the view's own stream generator if defined; otherwise
    // fall back to the deterministic key/value emitter. Unknown
    // views (def === undefined) go through the default strategy
    // too, which will throw inside def.render(ctx) — caught
    // below.
    const iterator: AsyncIterable<string> = def?.stream
      ? def.stream(action.params)
      : def
        ? defaultStream(def, ctx)
        : (async function* () { /* empty */ })();
    for await (const chunk of iterator) {
      chunks.push(String(chunk));
    }
  } catch {
    // Any failure during streaming → mark aborted, keep what was
    // already emitted. Stack traces are intentionally discarded
    // (same policy as Card A11).
    aborted = true;
  }

  if (action.mode === V.Mode.json) {
    const body: { stream: true; chunks: string[]; aborted?: true } = {
      stream: true,
      chunks,
    };
    if (aborted) body.aborted = true;
    return {
      status:  200,
      headers: { "content-type": "application/json" },
      body,
    };
  }

  // HTML mode: concat chunks with begin/end markers. The markers
  // are HTML comments so they don't render visibly, and they
  // give clients (or downstream tooling) a way to detect the
  // stream boundary.
  const inner = chunks.join("");
  const tail = aborted ? STREAM_HTML_ERROR_MARKER : STREAM_HTML_END_MARKER;
  return {
    status:  200,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    `${STREAM_HTML_START_MARKER}${inner}${tail}`,
  };
}
