/**
 * Web Surface v0.2.0 — form validator (Card A14-R).
 *
 * Pure, deterministic validator over the ``ValidationSchema`` /
 * ``FieldRule`` types. Consumes a flat ``Record<string, string>``
 * (the form parser's output) and produces a structured result:
 *
 *   * ``valid``   — true iff ``errors`` is empty.
 *   * ``errors``  — field-name → human-readable error message.
 *                   Iteration order matches the schema's
 *                   declaration order; same input → same key
 *                   order → byte-identical JSON serialisation.
 *   * ``values``  — field-name → typed value for fields that
 *                   passed validation. Numbers are coerced via
 *                   ``Number()``; strings + emails pass through
 *                   as their raw text. Missing optional fields
 *                   are surfaced as ``""``.
 *
 * Properties:
 *   * Pure: no mutation of ``fields`` or ``schema``.
 *   * Deterministic: same inputs → same outputs across runs.
 *   * No side effects, no globals, no async.
 *
 * Error message stability:
 *   * Each rule produces ONE error message at most. The first
 *     failing check wins (required → length → pattern). This
 *     keeps error messages deterministic even when multiple
 *     rules would fail simultaneously.
 *   * Message text is a fixed string template seeded only by
 *     the schema's own numeric bounds (``min``/``max``) — never
 *     by user input. That keeps the error surface free of
 *     reflected XSS risk; views can safely render the message
 *     without re-escaping at the validator boundary (though the
 *     view layer should still escape for HTML output as a
 *     defence-in-depth measure).
 *
 * Schema-bounded iteration:
 *   * The validator iterates ``schema`` (NOT ``fields``). Extra
 *     fields in the POST body are silently ignored — they don't
 *     appear in ``values`` or ``errors``. This prevents a
 *     malicious POST from injecting unknown keys into
 *     ``ctx.params``.
 */
import { FieldRule, ValidationSchema } from "./validationSchema";


export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
  values: Record<string, unknown>;
}


/** Conservative email regex — must contain ``@`` with non-empty,
 *  whitespace-free parts on either side, and the right-hand part
 *  must contain a dot with non-empty / whitespace-free segments.
 *  Not RFC-compliant; intentionally simple to keep the validator
 *  surface deterministic and easy to reason about. */
const _EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


function _validateString(
  raw: string,
  rule: Extract<FieldRule, { type: "string" }>,
): { ok: true; value: string } | { ok: false; message: string } {
  if (rule.min !== undefined && raw.length < rule.min) {
    return { ok: false, message: `Must be at least ${rule.min} characters.` };
  }
  if (rule.max !== undefined && raw.length > rule.max) {
    return { ok: false, message: `Must be at most ${rule.max} characters.` };
  }
  if (rule.pattern && !rule.pattern.test(raw)) {
    return { ok: false, message: "Invalid format." };
  }
  return { ok: true, value: raw };
}


function _validateEmail(
  raw: string,
): { ok: true; value: string } | { ok: false; message: string } {
  if (!_EMAIL_RE.test(raw)) {
    return { ok: false, message: "Invalid email address." };
  }
  return { ok: true, value: raw };
}


function _validateNumber(
  raw: string,
  rule: Extract<FieldRule, { type: "number" }>,
): { ok: true; value: number } | { ok: false; message: string } {
  const num = Number(raw);
  if (Number.isNaN(num)) {
    return { ok: false, message: "Must be a number." };
  }
  if (rule.min !== undefined && num < rule.min) {
    return { ok: false, message: `Must be ≥ ${rule.min}.` };
  }
  if (rule.max !== undefined && num > rule.max) {
    return { ok: false, message: `Must be ≤ ${rule.max}.` };
  }
  return { ok: true, value: num };
}


export function validateForm(
  fields: Record<string, string>,
  schema: ValidationSchema,
): ValidationResult {
  const errors: Record<string, string> = {};
  const values: Record<string, unknown> = {};

  for (const [key, rule] of Object.entries(schema)) {
    const raw = fields[key];
    const present = typeof raw === "string" && raw.trim() !== "";

    // Required check — first failure wins, downstream rules skipped.
    if (rule.required && !present) {
      errors[key] = "This field is required.";
      continue;
    }

    // Missing-but-optional → empty-string default, no further checks.
    if (!present) {
      values[key] = "";
      continue;
    }

    // Type dispatch. ``raw`` is non-empty and a string at this
    // point. Exhaustive switch over ``rule.type`` — TypeScript's
    // ``never`` default catches a future variant that isn't
    // handled here.
    let outcome:
      | { ok: true; value: unknown }
      | { ok: false; message: string };

    switch (rule.type) {
      case "string":
        outcome = _validateString(raw, rule);
        break;
      case "email":
        outcome = _validateEmail(raw);
        break;
      case "number":
        outcome = _validateNumber(raw, rule);
        break;
      default: {
        const _exhaustive: never = rule;
        outcome = _exhaustive;
      }
    }

    if (outcome.ok) {
      values[key] = outcome.value;
    } else {
      errors[key] = outcome.message;
    }
  }

  return {
    valid:  Object.keys(errors).length === 0,
    errors,
    values,
  };
}
