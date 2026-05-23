/**
 * Web Surface v0.2.0 — demo SSE view (Card A18).
 *
 * Registered as ``"stream_sse_demo"``. Two pathways:
 *
 *   * Regular request (no ``x-sse: 1`` header):
 *       GET /stream_sse_demo → ``render`` returns the title →
 *       template substitution → standard layout → 200 HTML.
 *       Behaves exactly like a normal view.
 *
 *   * SSE request (``x-sse: 1`` header):
 *       The classifier emits an ``sse`` action; the router
 *       dispatches to ``handleSse``, which iterates this view's
 *       ``events(params)`` generator and assembles the framed
 *       ``text/event-stream`` body.
 *
 * Determinism note (card divergence — same as A17):
 *   * No ``await sleep(...)`` between yields. Async timing is
 *     the canonical source of test flakiness and byte-order
 *     surprises. The event-sequence contract is identical
 *     whether or not artificial delays are present.
 *
 * Security:
 *   * Event ``data`` is JSON-stringified by the handler — string
 *     payloads come out as ``"one"`` (with quotes), which is
 *     correct SSE JSON wire form.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";


/** Exported for tests + future programmatic re-registration. */
export const streamSseDemoView: ViewDefinition = {
  template: "stream_sse_demo",
  layout:   "standard",
  async render(_ctx: V.RenderContext) {
    return {
      title:    "SSE Demo",
      subtitle: "SSE Demo",
    };
  },
  async *events(_params) {
    yield { event: "phase", data: "one" };
    yield { event: "phase", data: "two" };
    yield { event: "phase", data: "three" };
  },
};


// Side-effect registration: first import installs the view.
registerView("stream_sse_demo", streamSseDemoView);
