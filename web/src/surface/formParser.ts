/**
 * Web Surface v0.2.0 — form body parser (Card A13-R).
 *
 * Pure, deterministic parser for ``application/x-www-form-urlencoded``
 * request bodies. Turns a string body into a flat string→string
 * map so the form handler can hand it straight to the render
 * pipeline as ``params``.
 *
 * Properties:
 *   * No JSON parsing — HTML form encoding only.
 *   * No multipart parsing — that's a future card if file uploads
 *     ever land in the surface.
 *   * No side effects, no state. Same input → same output.
 *
 * Type contract — load-bearing:
 *   * Argument is typed as ``string``. The parser does NOT accept
 *     ``unknown`` and does NOT silently coerce non-string input
 *     to ``{}``. Per A13-R, the type-narrowing happens at the
 *     classifier: a POST with form content-type and a non-string
 *     ``req.body`` is routed to the error path BEFORE the parser
 *     is reached. Keeping this argument strict means the parser
 *     can't be the place where a malformed body is silently
 *     dropped.
 *
 * Empty string:
 *   * ``URLSearchParams("")`` yields zero entries; ``parseFormBody("")``
 *     returns ``{}``. That's the correct "empty form" semantics —
 *     not an error.
 *
 * Duplicate keys:
 *   * ``URLSearchParams.entries()`` yields each occurrence. The
 *     reduction below keeps the LAST value (later writes win),
 *     which is the same behaviour as PHP's ``$_POST`` and the
 *     usual default for "browser form posts the same field
 *     twice" cases. If a future card needs all values, it should
 *     expose a parallel ``parseFormBodyMulti`` rather than
 *     changing this contract.
 *
 * Limits:
 *   * No upper bound on body length. The surface is deploy-inactive
 *     in v0.2.0; once it goes live an upstream gateway should
 *     enforce body-size limits.
 */

export function parseFormBody(body: string): Record<string, string> {
  const params = new URLSearchParams(body);
  const out: Record<string, string> = {};
  for (const [k, v] of params.entries()) {
    out[k] = v;
  }
  return out;
}
