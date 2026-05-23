/**
 * Web Surface v0.2.0 — form-error collection + rendering
 * (Card A20-R).
 *
 * Two public helpers, both server-side:
 *
 *   * ``collectFormErrors(request)`` — given a v0.2 surface
 *     Request, resolve the matched view, pick its (possibly
 *     function-typed) schema, run the validator, and return a
 *     typed ``FormErrorBag``. Auto-orchestrates everything A13-R
 *     + A14-R + A15 already do, but exposed as a single call
 *     so progressive-enhancement endpoints don't have to repeat
 *     the dance.
 *
 *   * ``renderFormErrors(bag)`` — turn a ``FormErrorBag`` into
 *     an HTML fragment string suitable for inline embedding
 *     (or for the A19-R fetch-and-replace path to swap into
 *     ``data-fragment-target``). Uses the existing template
 *     engine + the ``errorFragment`` template; messages are
 *     HTML-escaped at the boundary (defence-in-depth, since
 *     the validator's messages are developer-defined today
 *     but might one day carry user input).
 *
 * No side effects, no state. Pure functions of their inputs
 * plus the singleton view-registry / template-cache state.
 *
 * Empty-bag policy:
 *   * ``renderFormErrors({errors: {}})`` returns an empty-list
 *     fragment (``<ul class="form-errors"></ul>``). Renderers
 *     that want to skip the surrounding wrapper for empty bags
 *     can guard on ``Object.keys(bag.errors).length === 0``.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { parseFormBody } from "../formParser";
import { resolveView } from "../viewResolution";
import { getView, resolveViewSchema } from "../viewRegistry";
import { validateForm } from "../validator";
import { loadCachedTemplate } from "../templateCache";
import { renderTemplate } from "../templateEngine";

import { FormErrorBag, toFieldErrorList } from "./types";


/** Empty bag — exported as a constant so callers comparing
 *  "no errors found" don't have to spread or copy. */
export const EMPTY_FORM_ERRORS: FormErrorBag = { errors: {} };


/** Minimal HTML-entity escape — mirrors the per-view escape
 *  policy across the codebase (views/home.ts, views/errors.ts,
 *  views/formDemo.ts). */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/**
 * Walk the v0.2 request → fields → schema → validation chain
 * and return whatever errors land. Returns ``EMPTY_FORM_ERRORS``
 * in any "can't validate" situation (non-string body, unknown
 * view, view without a schema), which is the right
 * pass-through behaviour for the progressive-enhancement
 * endpoints that consume this.
 *
 * Pure function over (request, view-registry state). No
 * side effects.
 */
export async function collectFormErrors(
  request: WebSurfaceV0_2.Request,
): Promise<FormErrorBag> {
  // The form classifier branch already type-checks for string
  // bodies; this helper is defensive in case it's called
  // outside that pathway.
  if (typeof request.body !== "string") {
    return EMPTY_FORM_ERRORS;
  }

  const fields = parseFormBody(request.body);
  const resolved = resolveView(request);
  const def = getView(resolved.view);
  if (!def) {
    return EMPTY_FORM_ERRORS;
  }

  const schema = resolveViewSchema(def.schema, fields);
  if (!schema) {
    return EMPTY_FORM_ERRORS;
  }

  const result = validateForm(fields, schema);
  return { errors: result.errors };
}


/**
 * Render a ``FormErrorBag`` as an HTML fragment via the
 * ``errorFragment`` template. Empty bag → empty ``<ul>``.
 *
 * Each error becomes one ``<li data-field="<field>">message</li>``
 * line. Both ``field`` and ``message`` are HTML-escaped at this
 * boundary.
 *
 * The fragment is intended for:
 *   * Server-rendered inclusion in a view template (just embed
 *     ``renderFormErrors(bag)`` in the view's ``render()``
 *     output as a var).
 *   * Wire-level response to a progressive-enhancement
 *     ``data-enhance="fetch"`` form — the client swaps the
 *     fragment into ``data-fragment-target``.
 */
export function renderFormErrors(bag: FormErrorBag): string {
  const items = toFieldErrorList(bag)
    .map(({ field, message }) =>
      `<li data-field="${escapeHtml(field)}">${escapeHtml(message)}</li>`,
    )
    .join("");

  const template = loadCachedTemplate("errorFragment");
  return renderTemplate(template, { items });
}
