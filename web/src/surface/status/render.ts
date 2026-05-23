/**
 * Web Surface v0.2.0 — status surface renderer (Card A23-R).
 *
 * Single helper: ``renderStatusSurface(payload)`` picks one of
 * three server-rendered templates (``statusSuccess``,
 * ``statusWarning``, ``statusFailure``) based on
 * ``payload.kind`` and injects an HTML-escaped ``payload.message``
 * into the template's ``{{ message }}`` slot.
 *
 * Why the kind→template mapping is exhaustive (not a string-
 * concat shortcut):
 *   * Tests lock the exact template name per kind, so a typo
 *     in the mapping is caught.
 *   * A future card that introduces a fourth kind must update
 *     this switch — the ``never`` exhaustiveness check makes
 *     it a compile-time error to forget.
 *
 * Determinism:
 *   * Pure function over (payload, template-cache state). Same
 *     payload + same template cache → same HTML bytes.
 *   * No side effects, no clock, no I/O beyond the cached
 *     template read (which itself is cached per process).
 *
 * Security policy:
 *   * ``message`` is HTML-escaped here, at the boundary, before
 *     reaching the template engine. The engine does NOT escape
 *     (per A3); each renderer escapes per output content-type.
 *     Mirrors the A20-R ``renderFormErrors`` and A21-R
 *     ``handleDiagnostics`` policies.
 *   * The template's static chrome (the ``<h2>`` label, the
 *     ``<div>`` wrapper) is author-controlled HTML; only the
 *     dynamic ``message`` slot is escaped.
 */
import { loadCachedTemplate } from "../templateCache";
import { renderTemplate } from "../templateEngine";

import { StatusKind, StatusPayload } from "./types";


/** Closed map from status kind → template name. Exported so
 *  tests can assert each kind picks the right template without
 *  parsing HTML. */
export const STATUS_TEMPLATE_NAMES: Record<StatusKind, string> = {
  success: "statusSuccess",
  warning: "statusWarning",
  failure: "statusFailure",
};


/** Minimal HTML-entity escape. Mirrors the per-view escape
 *  policy used across the codebase (forms/errors.ts,
 *  server/routes/diagnostics.ts, views/home.ts). Exported for
 *  tests so the exact escape behaviour can be asserted without
 *  going through the renderer. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/** Compile-time exhaustiveness helper. Forcing the switch to
 *  hit ``never`` for the default case means a future fourth
 *  ``StatusKind`` will fail type-checking until the switch is
 *  updated. */
function _assertNever(x: never): never {
  throw new Error(`unhandled status kind: ${JSON.stringify(x)}`);
}


/**
 * Render a status payload as an HTML fragment string suitable
 * for inline embedding (server-rendered view) or for the
 * A23-R fetch-and-replace path (client toggle).
 *
 * Always returns a complete fragment — empty/whitespace
 * messages still produce a valid ``<p data-status-message>``
 * (the message is just empty). Callers that want to suppress
 * empty surfaces should guard at the call site.
 */
export async function renderStatusSurface(
  payload: StatusPayload,
): Promise<string> {
  const templateName = _templateNameFor(payload.kind);
  const template = loadCachedTemplate(templateName);
  return renderTemplate(template, {
    message: escapeHtml(payload.message),
  });
}


/** Exhaustive switch from kind → template name. Exported only
 *  for tests; production code uses ``STATUS_TEMPLATE_NAMES``
 *  if it needs the mapping. */
function _templateNameFor(kind: StatusKind): string {
  switch (kind) {
    case "success": return STATUS_TEMPLATE_NAMES.success;
    case "warning": return STATUS_TEMPLATE_NAMES.warning;
    case "failure": return STATUS_TEMPLATE_NAMES.failure;
    default:        return _assertNever(kind);
  }
}
