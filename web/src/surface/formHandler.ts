/**
 * Web Surface v0.2.0 — form-submission handler (Card A13-R).
 *
 * Bridges the classifier's ``form`` action to the existing render
 * pipeline. The handler is the SINGLE place where form-encoded
 * bytes turn into typed view params.
 *
 * Flow:
 *   1. Classifier emits ``{kind: "form", view, rawBody, mode}``.
 *   2. Router dispatches here.
 *   3. ``parseFormBody`` turns ``rawBody`` into a string→string
 *      map (URL-encoded values are auto-decoded).
 *   4. ``executeRenderPipeline`` is called with those fields as
 *      ``params``. The named view's ``render(ctx)`` reads them
 *      via ``ctx.params``, exactly as it would for GET-supplied
 *      querystring params — the form pathway is invisible to the
 *      view.
 *
 * Properties:
 *   * No state, no persistence, no side effects.
 *   * No JSON-mode drift. The action's ``mode`` flows through to
 *     the pipeline unchanged — JSON form submissions still emit
 *     the canonical ``{view, params}`` envelope via
 *     ``defaultRenderer``.
 *   * The pipeline's existing try/catch (Card A11) covers the
 *     full handler — a view that throws while consuming form
 *     fields surfaces as the structured 500 page, never as an
 *     exception bubble.
 *
 * Determinism:
 *   * Same (rawBody, view, mode) in → same Response out.
 *   * The handler does not mutate the action, the registry, or
 *     any cache.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { parseFormBody } from "./formParser";
import { executeRenderPipeline } from "./renderPipeline";


/**
 * Shape of the classifier action this handler accepts. Held as
 * a local type alias rather than importing the union variant so
 * downstream callers can construct a synthetic form action in
 * tests without exporting an extra type from ``classifier.ts``.
 */
export interface FormAction {
  kind: "form";
  view: string;
  rawBody: string;
  mode: V.Mode;
}


export async function handleForm(
  action: FormAction,
): Promise<WebSurfaceV0_2.Response> {
  const fields = parseFormBody(action.rawBody);
  return executeRenderPipeline({
    view:   action.view,
    params: fields,
    mode:   action.mode,
  });
}
