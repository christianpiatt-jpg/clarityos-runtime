/**
 * Web Surface v0.2.0 — forms barrel (Card A20-R).
 *
 * Single import surface for the form-semantics pieces. Callers
 * that just want to validate / render don't have to remember
 * which file each helper lives in.
 *
 * Re-exports:
 *   * ``validateForm`` from the A14-R validator.
 *   * ``collectFormErrors`` + ``renderFormErrors`` + ``EMPTY_FORM_ERRORS``
 *     from ``./errors``.
 *   * ``FormFieldError``, ``FormErrorBag``, ``FormResult``,
 *     ``toFieldErrorList`` from ``./types``.
 *   * ``ValidationSchema`` + ``FieldRule`` + ``ValidationResult``
 *     from the underlying validator + schema modules, so callers
 *     can build schemas using the same types validation runs
 *     against.
 */

export { validateForm } from "../validator";
export type { ValidationResult } from "../validator";

export type { FieldRule, ValidationSchema } from "../validationSchema";

export {
  collectFormErrors,
  renderFormErrors,
  EMPTY_FORM_ERRORS,
} from "./errors";

export {
  toFieldErrorList,
} from "./types";

export type {
  FormFieldError,
  FormErrorBag,
  FormResult,
} from "./types";
