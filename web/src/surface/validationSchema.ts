/**
 * Web Surface v0.2.0 — validation schema types (Card A14-R).
 *
 * Declarative per-field rules attached to a view definition via
 * the optional ``schema`` field on ``ViewDefinition``. The form
 * handler reads the schema, runs ``validateForm``, and injects
 * any errors into the render pipeline's params.
 *
 * Design constraints:
 *   * Minimal, dependency-free — no validator library import.
 *   * Deterministic at every layer: same (fields, schema) in →
 *     same ValidationResult out.
 *   * Mirrors the simplicity of the template engine — three
 *     value kinds (string / email / number), required +
 *     length / range / pattern modifiers, that's the whole
 *     surface.
 *
 * Forward-compat:
 *   * Adding a new value kind means adding a new variant to
 *     ``FieldRule`` AND a new branch to ``validator.validateForm``.
 *     TypeScript's exhaustive-switch catches missed branches at
 *     build time.
 *   * Removing or renaming an existing variant is a breaking
 *     change — views with that rule will silently skip the
 *     field. Bump the v0.x.y minor or add a deprecation pass.
 */

export type FieldRule =
  | {
      type: "string";
      required?: boolean;
      min?: number;
      max?: number;
      pattern?: RegExp;
    }
  | {
      type: "email";
      required?: boolean;
    }
  | {
      type: "number";
      required?: boolean;
      min?: number;
      max?: number;
    };


/** Map of field name → rule. The validator iterates ``schema``
 *  (NOT ``fields``) so a malicious POST with extra fields can't
 *  pollute the validation pass — fields outside the schema are
 *  ignored. */
export type ValidationSchema = Record<string, FieldRule>;
