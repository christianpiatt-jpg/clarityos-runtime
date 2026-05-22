/**
 * Web Surface v0.2.0 — demo streaming view (Card A17).
 *
 * Registered as ``"stream_demo"``. Two pathways:
 *
 *   * Regular request (no ``x-stream: 1`` header):
 *       GET /stream_demo → render() returns the title var →
 *       template substitution → standard layout → 200 HTML.
 *       Behaves exactly like a normal view.
 *
 *   * Streaming request (``x-stream: 1`` header):
 *       The classifier emits a ``stream`` action; the router
 *       dispatches to ``handleStream``, which iterates this
 *       view's ``stream(params)`` async generator and collects
 *       the chunks. The chunks land in the Response body
 *       wrapped by the stream begin/end markers.
 *
 * Determinism note (card divergence):
 *   * The original A17 card included ``await sleep(50)`` between
 *     yields to simulate "real" streaming work. That kind of
 *     async timing is the canonical source of test flakiness
 *     and bytes-out-of-order surprises, so this demo emits
 *     three static chunks immediately. The chunk-sequence
 *     contract (chunks arrive in declaration order) is
 *     identical either way; only the timing surface changes.
 *
 * Security:
 *   * Yielded chunks are emitted verbatim into the Response
 *     body. v0.2 demo content is fixed-string, but if a
 *     future stream view wanted to interpolate ``ctx.params``,
 *     it must HTML-escape at the view boundary (same policy
 *     as ``views/formDemo.ts`` etc.).
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Exported for tests + future programmatic re-registration. */
export const streamDemoView: ViewDefinition = {
  template: "stream_demo",
  layout:   "standard",
  async render(_ctx: V.RenderContext) {
    return {
      title:    "Streaming Demo",
      subtitle: "Streaming Demo",
    };
  },
  async *stream(_params) {
    yield "<p>Chunk 1: preparing.</p>";
    yield "<p>Chunk 2: loading.</p>";
    yield "<p>Chunk 3: done.</p>";
  },
};


// Side-effect registration: first import installs ``stream_demo``.
registerView("stream_demo", streamDemoView);
