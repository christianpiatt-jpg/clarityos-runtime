/**
 * Web Surface v0.2.0 — demo form view (Cards A13-R + A14-R).
 *
 * Registered as ``"form_demo"``. URL: ``/web-surface/v0.2/form_demo``.
 *
 * Behaviour:
 *   * GET                                 → empty form (no ``name``,
 *                                           no ``email``).
 *   * POST + ``application/x-www-form-urlencoded``
 *                                         → classifier emits a
 *                                           ``form`` action, handler
 *                                           parses ``rawBody``,
 *                                           runs validation against
 *                                           ``schema`` below, then
 *                                           re-renders with values +
 *                                           errors.
 *
 * Schema (Card A14-R):
 *   * ``name``  — required string, min 2 characters.
 *   * ``email`` — required email-formatted address.
 *
 * Pathway invariants:
 *   * The view is the SAME for GET and POST — the form pathway is
 *     invisible to ``render(ctx)`` aside from the additional
 *     ``ctx.params.errors`` object. Valid GET requests skip
 *     validation; ``ctx.params.errors`` is undefined and the
 *     view treats it as ``{}``.
 *   * JSON mode is canonical: a POST with ``Accept: application/json``
 *     returns the structured ``{view, params}`` envelope via
 *     ``defaultRenderer``; the envelope just carries an extra
 *     ``errors`` key.
 *
 * Template-binding note:
 *   * Our template engine does flat-key lookups (it doesn't
 *     traverse ``{{ errors.name }}`` into ``vars.errors.name``).
 *     The view's ``render`` flattens the errors map into vars
 *     keyed ``errors.name`` / ``errors.email`` so the template
 *     substitution works without engine changes.
 *
 * Security:
 *   * Every user-supplied value (``name``, ``email``) is
 *     HTML-escaped at the view boundary before substitution into
 *     the template. Same for error messages — they're
 *     developer-defined strings today, but defence-in-depth
 *     escaping keeps the boundary uniform.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";
import { ValidationSchema } from "../validationSchema";


/** Minimal HTML-entity escape — same shape as ``views/home.ts``
 *  and ``views/errors.ts``. Kept local so each view owns its
 *  escape policy explicitly. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Read a single param as a string; empty string for missing /
 *  non-string. The form parser always yields strings, so the
 *  ``typeof`` check is mostly defensive against direct
 *  programmatic dispatch (tests calling ``executeRenderPipeline``
 *  with arbitrary params). */
function _readField(ctx: V.RenderContext, key: string): string {
  const raw = (ctx.params as Record<string, unknown> | undefined)?.[key];
  return typeof raw === "string" ? raw : "";
}


/** Schema declared at module scope so the form handler can read
 *  it from the view definition. Tests can import the same const
 *  to drive validator-only assertions against a known shape. */
export const formDemoSchema: ValidationSchema = {
  name:  { type: "string", required: true, min: 2 },
  email: { type: "email",  required: true },
};


/** Read an error message for ``field`` from ``ctx.params.errors``.
 *  Returns ``""`` when the form is valid (no errors map) or when
 *  the field passed validation. */
function _readError(ctx: V.RenderContext, field: string): string {
  const errors =
    (ctx.params as { errors?: Record<string, unknown> } | undefined)?.errors;
  if (!errors || typeof errors !== "object") return "";
  const message = (errors as Record<string, unknown>)[field];
  return typeof message === "string" ? message : "";
}


/** Exported for tests + future programmatic re-registration. */
export const formDemoView: ViewDefinition = {
  template: "form_demo",
  layout:   "standard",
  schema:   formDemoSchema,
  async render(ctx: V.RenderContext) {
    const name      = _readField(ctx, "name");
    const email     = _readField(ctx, "email");
    const nameError  = _readError(ctx, "name");
    const emailError = _readError(ctx, "email");
    return {
      title:    escapeHtml("Form Demo"),
      subtitle: escapeHtml("Form Demo"),
      name:     escapeHtml(name),
      email:    escapeHtml(email),
      // Card A14-R: errors are flattened into dotted keys so the
      // existing flat-lookup template engine finds them via
      // ``{{ errors.name }}`` / ``{{ errors.email }}``. Each
      // message goes through escapeHtml for defence-in-depth.
      "errors.name":  escapeHtml(nameError),
      "errors.email": escapeHtml(emailError),
      // The template includes ``<pre>{{ content }}</pre>`` — when
      // any fields were submitted, render them as a pretty-printed
      // JSON echo so the round-trip is visually obvious. Empty form
      // → empty <pre>.
      content:  name || email
        ? escapeHtml(JSON.stringify({ name, email }, null, 2))
        : "",
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``form_demo`` in the registry.
registerView("form_demo", formDemoView);
