/**
 * Web Surface v0.2.0 — multi-step wizard view (Card A15).
 *
 * Registered as ``"form_wizard"``. URL:
 * ``/web-surface/v0.2/form_wizard``.
 *
 * Stateless multi-step pattern:
 *   * Each form's hidden ``step`` input carries the step the user
 *     is submitting FROM (the "current step" at submit time).
 *   * Carry-forward fields ride along as additional hidden inputs
 *     in each subsequent form, so the server never has to remember
 *     prior submissions.
 *   * Validation picks a different schema per step (the
 *     ``schema(fields)`` function). Each step's schema validates
 *     the field the user just entered AND lists the carry-forward
 *     fields as permissive ``{type: "string"}`` rules so they pass
 *     through into ``values`` (and thus into the next step's
 *     ``ctx.params``).
 *   * The view picks a different TEMPLATE per render via the
 *     ``template(ctx)`` function. The chosen template depends on
 *     the ``displayStep``, computed from the submitted step + the
 *     validation outcome (errors → stay; no errors → advance).
 *
 * Step transitions (all deterministic, no state):
 *
 *   GET  /form_wizard                          → step 1
 *   GET  /form_wizard?step=2                   → step 2 (deep link)
 *   POST step=1 + valid name                   → step 2
 *   POST step=1 + invalid name                 → step 1 (with errors)
 *   POST step=2 + valid email                  → step 3
 *   POST step=2 + invalid email                → step 2 (with errors)
 *   POST step=3 + valid age                    → done
 *   POST step=3 + invalid age                  → step 3 (with errors)
 *
 * displayStep computation (template + render share this logic):
 *   * ``ctx.params.errors === undefined``: no validation ran
 *     (GET request) → display the submitted step (or "1" by
 *     default).
 *   * ``ctx.params.errors`` has any keys: validation failed →
 *     stay on the submitted step.
 *   * ``ctx.params.errors === {}``: validation passed → advance
 *     to the next step ("1" → "2" → "3" → "done").
 *
 * Security:
 *   * Every user-supplied value goes through ``escapeHtml`` at
 *     this view's boundary before substitution into the template,
 *     same as ``views/formDemo.ts``.
 *   * Schema-bounded iteration: extra POST fields outside the
 *     per-step schema never appear in ``values``. The validator
 *     enforces this independent of view code.
 *
 * Limitations (v0.2 demo):
 *   * If the current step's field fails validation, the user's
 *     bad input is dropped (not echoed back into the input).
 *     This mirrors A14-R's params shape — invalid values aren't
 *     in ``values``. Carry-forward fields are unaffected.
 *   * The "done" step has no schema; a malicious direct POST to
 *     ``step=done`` would render the summary with whatever
 *     fields the body carries. Acceptable for v0.2; future card
 *     can add a terminal schema if needed.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";
import { ValidationSchema } from "../validationSchema";


function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Read a single param as a string; empty string for missing /
 *  null / undefined. Stringifies number-typed values via
 *  ``String()`` — the wizard's ``age`` field is coerced to a
 *  number by A14-R's number-rule validator, so a plain
 *  ``typeof === "string"`` check (as in ``views/formDemo.ts``)
 *  would drop the value at render time. */
function _readField(ctx: V.RenderContext, key: string): string {
  const raw = (ctx.params as Record<string, unknown> | undefined)?.[key];
  if (raw === undefined || raw === null) return "";
  return String(raw);
}


/** Pull an error message for ``field`` out of ``ctx.params.errors``.
 *  Returns ``""`` when the errors map is missing or the field
 *  passed validation. */
function _readError(ctx: V.RenderContext, field: string): string {
  const errors =
    (ctx.params as { errors?: Record<string, unknown> } | undefined)?.errors;
  if (!errors || typeof errors !== "object") return "";
  const message = (errors as Record<string, unknown>)[field];
  return typeof message === "string" ? message : "";
}


/** Step ordering. Each step name maps to the NEXT step name. */
const _NEXT_STEP: Record<string, string> = {
  "1":    "2",
  "2":    "3",
  "3":    "done",
  "done": "done",
};


/** Set of valid step names. Anything else falls back to "1". */
const _VALID_STEPS = new Set(["1", "2", "3", "done"]);


/**
 * Compute the step the wizard should render for this request.
 * Shared by both ``template(ctx)`` and ``render(ctx)`` so the
 * two never disagree about which file to load vs. which vars to
 * provide.
 *
 * Pure function of ``ctx.params``. Exported for tests.
 */
export function _computeDisplayStep(ctx: V.RenderContext): string {
  const params = (ctx.params as Record<string, unknown> | undefined) ?? {};
  const submittedRaw = params["step"];
  const submitted =
    typeof submittedRaw === "string" && _VALID_STEPS.has(submittedRaw)
      ? submittedRaw
      : "1";

  const errors = params["errors"];

  // GET request, or a non-object ``errors`` (null, etc.) → no
  // valid "validation passed" signal, so stay on the submitted
  // step. Only a real object reaches the advance/stay decision.
  if (
    errors === undefined ||
    errors === null ||
    typeof errors !== "object"
  ) {
    return submitted;
  }

  // POST went through validation. Errors present → stay on the
  // submitted step so the user can fix the input; empty errors
  // → advance.
  const hasErrors =
    Object.keys(errors as Record<string, unknown>).length > 0;

  return hasErrors ? submitted : (_NEXT_STEP[submitted] ?? "done");
}


/** Template filename for each step. */
function _templateFor(displayStep: string): string {
  switch (displayStep) {
    case "2":    return "form_wizard_step2";
    case "3":    return "form_wizard_step3";
    case "done": return "form_wizard_done";
    case "1":
    default:     return "form_wizard_step1";
  }
}


/**
 * Schema picker. Card A14-R's validator runs per-submission
 * against this. Each step's schema validates the field the user
 * just entered AND lists carry-forward fields as permissive
 * string rules so they survive into ``values`` and reach the
 * next step's render via ``ctx.params``.
 *
 * Includes ``step`` itself in every schema so the submitted
 * step value survives validation and lands in ``params.step``
 * for the view's display-step computation.
 *
 * Returns ``undefined`` for unknown / terminal steps; the form
 * handler then falls into the passthrough branch and the view
 * renders whatever was POSTed without validation.
 *
 * Exported for tests.
 */
export function _wizardSchemaFor(
  fields: Record<string, string>,
): ValidationSchema | undefined {
  const step = fields["step"] ?? "1";
  switch (step) {
    case "1":
      return {
        step: { type: "string" },
        name: { type: "string", required: true, min: 2 },
      };
    case "2":
      return {
        step:  { type: "string" },
        name:  { type: "string" },
        email: { type: "email", required: true },
      };
    case "3":
      return {
        step:  { type: "string" },
        name:  { type: "string" },
        email: { type: "string" },
        age:   { type: "number", required: true, min: 1 },
      };
    default:
      return undefined;
  }
}


/** Exported for tests + future programmatic re-registration. */
export const formWizardView: ViewDefinition = {
  template: (ctx) => _templateFor(_computeDisplayStep(ctx)),
  layout:   "standard",
  schema:   _wizardSchemaFor,
  async render(ctx: V.RenderContext) {
    const name  = _readField(ctx, "name");
    const email = _readField(ctx, "email");
    const age   = _readField(ctx, "age");
    return {
      title:    escapeHtml("Multi-Step Demo"),
      subtitle: escapeHtml("Wizard"),
      name:     escapeHtml(name),
      email:    escapeHtml(email),
      age:      escapeHtml(age),
      "errors.name":  escapeHtml(_readError(ctx, "name")),
      "errors.email": escapeHtml(_readError(ctx, "email")),
      "errors.age":   escapeHtml(_readError(ctx, "age")),
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``form_wizard`` in the registry.
registerView("form_wizard", formWizardView);
