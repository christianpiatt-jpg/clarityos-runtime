/**
 * Web Surface v0.2.0 — default streaming strategy (Card A17).
 *
 * Fallback iterator used by ``handleStream`` when a view doesn't
 * declare its own ``stream`` async-generator function. Turns the
 * view's regular ``render(ctx)`` output into a deterministic
 * sequence of chunks — one chunk per (key, value) pair from the
 * rendered vars.
 *
 * Pure / deterministic:
 *   * Object.entries() iterates in insertion order (matches the
 *     view's render() return shape).
 *   * No async timing, no concurrency, no I/O beyond what
 *     ``def.render`` itself does.
 *   * Output is content-determined by (def, ctx); same inputs →
 *     same chunk sequence.
 *
 * Output shape:
 *   ``<div data-key="<key>">${value}</div>`` per var. The HTML
 *   escaping responsibility stays where it lives in every other
 *   view (the view's own ``render()`` escapes its values before
 *   they reach the template engine / stream emitter). This
 *   wrapper deliberately does NOT re-escape — it's symmetric with
 *   the template engine, which also doesn't escape.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { ViewDefinition } from "./viewRegistry";


export async function* defaultStream(
  def: ViewDefinition,
  ctx: V.RenderContext,
): AsyncIterable<string> {
  // Run the view's normal render path to compute the vars bag.
  // The view's render() already handles HTML escaping for any
  // values originating from untrusted sources.
  const vars = await def.render(ctx);

  // Emit one chunk per var, in insertion order.
  for (const [key, value] of Object.entries(vars)) {
    yield `<div data-key="${key}">${String(value)}</div>`;
  }
}
