/**
 * Web Surface v0.2.0 — form semantics types (Card A20-R).
 *
 * Typed wrappers around the validator's flat ``Record<string, string>``
 * error map (A14-R) so callers don't have to remember whether a
 * given API hands them ``{errors: {...}}`` or just ``{...}``.
 *
 * Shape policy:
 *   * ``FormErrorBag.errors`` mirrors ``ValidationResult.errors``
 *     exactly (field name → human-readable message). Iteration
 *     order matches the schema's declaration order, so JSON
 *     serialisation and template rendering are byte-stable.
 *   * ``FormFieldError`` is the per-field tuple — useful when
 *     callers want to map errors to UI components and need a
 *     stable list shape.
 *   * ``FormResult<T>`` is the discriminated union that mirrors
 *     ``validateForm`` outcomes at the type level. Authoring
 *     a handler that returns ``FormResult<MyShape>`` makes the
 *     compiler enforce the "either values or errors" invariant.
 *
 * Held in its own file so ``errors.ts`` and ``index.ts`` can
 * import the types without circular dependencies.
 */


/** One field, one message. Stable shape for list iteration. */
export interface FormFieldError {
  field: string;
  message: string;
}


/**
 * Wrapper around the validator's error map. Carrying it as a
 * named type lets callers pass it around as a single value
 * instead of a bare ``Record<string, string>`` whose meaning
 * has to be inferred from the variable name.
 */
export interface FormErrorBag {
  errors: Record<string, string>;
}


/**
 * Discriminated union mirroring the validator's outcome. Use
 * this for handlers that want to express "form succeeded with
 * typed values OR failed with errors" in their signature.
 *
 * Example:
 *
 *     async function handle(req): Promise<FormResult<User>> {
 *       const bag = await collectFormErrors(req);
 *       if (Object.keys(bag.errors).length > 0) {
 *         return { ok: false, errors: bag };
 *       }
 *       // ...build a typed value...
 *       return { ok: true, values: user };
 *     }
 */
export type FormResult<T> =
  | { ok: true;  values: T }
  | { ok: false; errors: FormErrorBag };


/**
 * Convert a ``FormErrorBag``'s map into an ordered list of
 * ``FormFieldError`` records. Preserves insertion order
 * (Object.entries iterates that way). Useful for renderers
 * that need stable list iteration.
 */
export function toFieldErrorList(bag: FormErrorBag): FormFieldError[] {
  return Object.entries(bag.errors).map(([field, message]) => ({
    field,
    message,
  }));
}
