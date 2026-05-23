/**
 * Web Surface v0.2.0 — default SSE adapter (Card A18).
 *
 * Fallback async-iterator used by ``handleSse`` when a view
 * doesn't declare its own ``events`` generator. Runs the view's
 * regular ``render(ctx)`` and yields a SINGLE SSE event whose
 * ``data`` payload is the entire render-vars bag.
 *
 * Same role + shape as ``defaultStream.ts``, just SSE-flavoured.
 *
 * Determinism:
 *   * Pure pass-through to ``def.render``: the yield order is
 *     trivially deterministic (there's only one yield).
 *   * No fan-out, no per-key emission. Views that want a richer
 *     SSE shape should declare their own ``events`` generator.
 *
 * Why a single envelope event instead of one event per render
 * var (like ``defaultStream``):
 *   * SSE consumers (``EventSource`` in the browser) typically
 *     listen for named event types. A spray of unrelated events
 *     keyed on var name would be confusing. A single ``message``
 *     event carrying the whole render result is the more
 *     idiomatic SSE default.
 *   * Views that want fine-grained event types implement
 *     ``events()`` and skip this adapter entirely.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { ViewDefinition } from "./viewRegistry";
import { SseEvent } from "./sseEvent";


export async function* defaultSse(
  def: ViewDefinition,
  ctx: V.RenderContext,
): AsyncIterable<SseEvent> {
  const vars = await def.render(ctx);
  yield { data: vars };
}
