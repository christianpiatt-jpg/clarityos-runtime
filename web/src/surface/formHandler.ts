/**
 * Web Surface v0.2.0 — form-submission handler (Cards A13-R + A14-R + A15).
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
 *   4. View lookup. If the target view declares a ``schema``
 *      (Card A14-R), the fields are run through
 *      ``validator.validateForm``; the resulting structured
 *      ``{values, errors}`` becomes the pipeline's ``params``.
 *      Views without a schema pass the raw fields through
 *      untouched (A13-R behaviour preserved).
 *   5. ``executeRenderPipeline`` is called with those params.
 *      The named view's ``render(ctx)`` reads them via
 *      ``ctx.params``, exactly as it would for GET-supplied
 *      querystring params — the form pathway is invisible to
 *      the view aside from the optional ``errors`` field.
 *
 * params shape (A14-R):
 *   * Without schema: ``params = fields`` (the parsed form).
 *   * With schema:    ``params = {...values, errors}``. The
 *                     ``values`` map contains validated (and
 *                     type-coerced for ``number`` rules) entries
 *                     for fields that passed; invalid fields are
 *                     absent from ``values`` and surface in
 *                     ``errors`` instead. ``errors`` is always
 *                     present (``{}`` when the form is valid),
 *                     so views can safely read
 *                     ``ctx.params.errors`` without an
 *                     existence check.
 *
 * Schema resolution (A15):
 *   * ``def.schema`` may be EITHER a static ``ValidationSchema``
 *     OR a function ``(fields) => ValidationSchema | undefined``.
 *     ``resolveViewSchema`` calls the function (passing the
 *     parsed form fields) if it's callable, otherwise returns
 *     the literal. Multi-step wizards use this to pick a
 *     different schema per step based on ``fields.step``.
 *   * A schema function returning ``undefined`` falls into the
 *     passthrough branch — same as a view with no schema at all.
 *
 * Properties:
 *   * No state, no persistence, no side effects.
 *   * No JSON-mode drift. The action's ``mode`` flows through to
 *     the pipeline unchanged — JSON form submissions still emit
 *     the canonical ``{view, params}`` envelope via
 *     ``defaultRenderer``; the envelope just carries the extra
 *     ``errors`` key for schema-bound views.
 *   * The pipeline's existing try/catch (Card A11) covers the
 *     full handler — a view that throws while consuming form
 *     fields surfaces as the structured 500 page, never as an
 *     exception bubble.
 *
 * Determinism:
 *   * Same (rawBody, view, mode, schema) in → same Response out.
 *   * The handler does not mutate the action, the registry, or
 *     any cache.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { parseFormBody } from "./formParser";
import { executeRenderPipeline } from "./renderPipeline";
import { getView, resolveViewSchema } from "./viewRegistry";
import { validateForm } from "./validator";


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

  // Card A14-R + A15: schema lookup + optional validation.
  // The view definition may carry a ``schema`` field; absent
  // schema (or a schema-function returning undefined) → behave
  // like A13-R (passthrough fields). Unknown view (``getView``
  // returns undefined) is also treated as passthrough — the
  // pipeline's defaultRenderer fallback will handle it.
  //
  // Card A15: ``def.schema`` may be a function picking a schema
  // per-submission based on the parsed form fields. The wizard
  // view uses this to validate a different field per step
  // without server-side state.
  const def = getView(action.view);
  const schema = resolveViewSchema(def?.schema, fields);

  if (!schema) {
    return executeRenderPipeline({
      view:   action.view,
      params: fields,
      mode:   action.mode,
    });
  }

  const result = validateForm(fields, schema);

  return executeRenderPipeline({
    view:   action.view,
    params: {
      ...result.values,
      errors: result.errors,
    },
    mode:   action.mode,
  });
}
