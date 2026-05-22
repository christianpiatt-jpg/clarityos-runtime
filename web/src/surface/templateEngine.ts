/**
 * Web Surface v0.2.0 — template engine.
 *
 * Card A3 — Track A. Minimal, deterministic, dependency-free
 * variable substitution. No logic, no loops, no conditionals, no
 * partials. Strictly ``{{ var_name }}`` placeholders → string
 * substitution.
 *
 * Security policy:
 *   * The engine itself does NOT HTML-escape values. The caller
 *     decides per-value whether to escape (typically the renderer,
 *     which knows the output content-type). Keeping escape policy
 *     out of the engine lets the same primitive emit non-HTML
 *     output (text, markdown) without unwanted entity expansion.
 *   * The renderer for HTML output (``viewDefaultRenderer.ts``)
 *     escapes every interpolated value before calling
 *     ``renderTemplate`` — that's the load-bearing XSS regression
 *     contract (locked by ``viewEngine.test.ts``).
 *
 * Unfilled-placeholder policy:
 *   * Any placeholder of shape ``{{ identifier }}`` not present in
 *     the ``vars`` map is silently removed (replaced with empty
 *     string). This keeps a half-populated template from leaking
 *     literal ``{{ admin_password }}`` text into the output if a
 *     caller forgets a variable.
 *
 * Placeholder grammar:
 *   * Matches ``{{ name }}`` with optional whitespace inside the
 *     braces. ``name`` is a JS identifier or dotted path (``[\w.]+``).
 *   * Dotted paths are unfilled — the substitution loop only
 *     resolves flat ``vars`` keys; nested-dotted placeholders fall
 *     through to the "unfilled → remove" branch.
 */


/** Recognises ``{{ identifier }}`` (with optional whitespace).
 *  Used for the final unfilled-placeholder strip pass. */
const _UNFILLED_PLACEHOLDER_RE = /{{\s*[\w.]+\s*}}/g;


/**
 * Substitute ``{{ key }}`` placeholders in ``template`` with the
 * matching value from ``vars``. Unfilled placeholders are removed.
 *
 * Determinism:
 *   * Output depends only on the ``template`` string and the
 *     ``vars`` map. No globals, no cwd, no time, no fetch.
 *   * Iteration order of ``Object.entries(vars)`` follows
 *     insertion order, but the substitution itself is order-
 *     independent (each placeholder matches at most one key).
 *
 * Returns the substituted output with leading/trailing whitespace
 * trimmed (the ``base.html`` template carries trailing newlines).
 */
export function renderTemplate(
  template: string,
  vars: Record<string, unknown>,
): string {
  let output = template;

  for (const [key, value] of Object.entries(vars)) {
    // Build a per-key regex. We escape the key just in case a
    // caller passes one carrying regex metacharacters (defence in
    // depth — flat identifiers won't normally need this).
    const escapedKey = _escapeForRegex(key);
    const pattern = new RegExp(`{{\\s*${escapedKey}\\s*}}`, "g");
    output = output.replace(pattern, String(value));
  }

  // Strip any unfilled placeholder so the output never leaks
  // literal ``{{ unmapped_var }}`` text.
  output = output.replace(_UNFILLED_PLACEHOLDER_RE, "");

  return output.trim();
}


/** Escape regex metacharacters in a key name. */
function _escapeForRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
