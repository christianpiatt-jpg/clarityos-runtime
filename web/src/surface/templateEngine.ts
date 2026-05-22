/**
 * Web Surface v0.2.0 — template engine.
 *
 * Card A3 (initial): variable substitution + unfilled stripping.
 * Card A6 (current): adds partial inclusion as a FIRST pass.
 *
 * Minimal, deterministic, dependency-free. No logic, no loops,
 * no conditionals beyond the explicit two-pass structure below.
 *
 * Render passes (run in order):
 *
 *   1. Partial inclusion
 *      Each ``{{> name }}`` is replaced with the body of the
 *      named partial via ``loadCachedPartial(name)``. Missing
 *      partials silently substitute to empty string — same
 *      "silent removal on miss" policy as unfilled variables.
 *
 *   2. Variable substitution
 *      Each ``{{ key }}`` is replaced with ``String(vars[key])``.
 *      Variables present in partials (e.g. ``{{ subtitle }}`` in
 *      header.html) are substituted in this pass — partials are
 *      included BEFORE variables so this works.
 *
 *   3. Unfilled-placeholder strip
 *      Any ``{{ identifier }}`` not present in ``vars`` is
 *      silently removed. Never leaks literal ``{{ ... }}`` text
 *      into the output.
 *
 * Security policy (unchanged from A3):
 *   * Engine does NOT HTML-escape values. Caller (renderer / view)
 *     escapes per output content-type.
 *
 * No-nesting policy (Card A6 implementation choice):
 *   * Step 1 runs ``replace`` exactly once. If a partial body
 *     contains ``{{> other }}``, that text appears literally in
 *     the output — partials cannot include other partials.
 *   * This is deliberate. Multi-pass with cycle detection adds
 *     complexity that v0.2.0 doesn't need. If nested partials
 *     are needed later, this is the single line to revisit.
 *
 * No-double-evaluation policy:
 *   * Variable values are substituted as-is. If a value happens
 *     to be the string ``{{> header }}``, it appears literally
 *     in the output (NOT expanded as a partial). Same property
 *     for nested ``{{ x }}`` syntax. Locked by tests.
 */
import { loadCachedPartial } from "./partialCache";


/** Matches ``{{> name }}`` partial-inclusion placeholders. The
 *  name allows word chars + hyphens (e.g. ``site-header``). */
const _PARTIAL_RE = /{{>\s*([\w-]+)\s*}}/g;


/** Matches ``{{ identifier }}`` variable placeholders. Captures
 *  the key (which may contain word chars + dots). Used for the
 *  single-pass variable substitution. */
const _VAR_RE = /{{\s*([\w.]+)\s*}}/g;


/**
 * Substitute ``{{> name }}`` partials and ``{{ key }}`` variables
 * in ``template``. Unfilled variables are removed.
 *
 * Card A6 fix: variable substitution is now SINGLE-PASS — one
 * regex scan of the output, with each match's key looked up in
 * vars. The pre-A6 engine looped over ``Object.entries(vars)``
 * and applied each substitution sequentially over the
 * accumulated output, which meant a variable VALUE containing
 * ``{{ another_key }}`` would be re-substituted on a later
 * iteration (server-side template injection vector). The
 * single-pass design eliminates double evaluation.
 *
 * Determinism:
 *   * Output depends only on the template string, the vars map,
 *     and the contents of the partial files.
 *   * Partial cache is the only stateful dependency — it's
 *     populated additively on first miss; same partial → same
 *     bytes for the lifetime of the process.
 */
export function renderTemplate(
  template: string,
  vars: Record<string, unknown>,
): string {
  let output = template;

  // Pass 1: partial inclusion. Run BEFORE variable substitution
  // so that variables inside a partial body (e.g. {{ subtitle }}
  // in header.html) get filled in pass 2.
  output = output.replace(_PARTIAL_RE, (_match, name) => {
    try {
      return loadCachedPartial(name);
    } catch {
      // Missing partial → silent removal. Matches the "unfilled
      // placeholder removed" policy for variables.
      return "";
    }
  });

  // Pass 2: variable substitution + unfilled strip in one scan.
  // The replace callback fires once per placeholder found in the
  // current output; replacements are inserted into a FRESH output
  // string and NOT re-scanned. This is what prevents double
  // evaluation (a value of "{{ secret }}" is inserted as literal
  // text, never expanded against vars.secret).
  output = output.replace(_VAR_RE, (_match, key: string) => {
    if (Object.prototype.hasOwnProperty.call(vars, key)) {
      return String(vars[key]);
    }
    // Unfilled placeholder → silent removal.
    return "";
  });

  return output.trim();
}
