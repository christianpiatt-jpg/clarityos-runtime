/**
 * Web Surface v0.2.0 — loading surface renderer (Card A24-R).
 *
 * Single helper: ``renderLoadingSurface(payload?)`` loads the
 * ``loadingFragment`` template and injects an HTML-escaped
 * ``payload.message`` into the template's ``{{ message }}``
 * slot. When ``payload`` is omitted (or ``message`` is missing
 * / not a string), the renderer substitutes
 * ``DEFAULT_LOADING_MESSAGE`` (``"Loading…"``).
 *
 * Why the default is held as an exported constant:
 *   * Tests can assert the exact bytes without re-typing the
 *     string.
 *   * Future cards that want to localise the default can
 *     replace the constant in one place rather than chasing
 *     it through the renderer.
 *
 * Determinism:
 *   * Pure function over (payload, template-cache state). Same
 *     payload + same template cache → same HTML bytes.
 *   * No side effects, no clock, no I/O beyond the cached
 *     template read (which itself is cached per process).
 *
 * Security policy:
 *   * ``message`` is HTML-escaped here, at the boundary,
 *     before reaching the template engine. The engine does
 *     NOT escape (per A3); each renderer escapes per output
 *     content-type. Mirrors the A20-R ``renderFormErrors``,
 *     A21-R ``handleDiagnostics``, and A23-R
 *     ``renderStatusSurface`` policies.
 *   * The default message ``"Loading…"`` is author-controlled
 *     and intentionally passes through the escape — it
 *     contains no HTML-sensitive characters but is escaped
 *     for the same single-code-path reason.
 */
import { loadCachedTemplate } from "../templateCache";
import { renderTemplate } from "../templateEngine";

import { LoadingPayload } from "./types";


/** Default message shown when no ``message`` is supplied.
 *  Held as a constant so tests + future localisation can
 *  agree on the exact bytes. */
export const DEFAULT_LOADING_MESSAGE = "Loading…";


/** Template name resolved by ``loadCachedTemplate``. Held as
 *  a constant so the route + the renderer agree on the
 *  exact lookup key. */
export const LOADING_TEMPLATE_NAME = "loadingFragment";


/** Minimal HTML-entity escape. Mirrors the per-view escape
 *  policy used across the codebase (forms/errors.ts,
 *  server/routes/diagnostics.ts, surface/status/render.ts,
 *  views/home.ts). Exported for tests so the exact escape
 *  behaviour can be asserted without going through the
 *  renderer. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/**
 * Render a loading payload as an HTML fragment string suitable
 * for inline embedding (server-rendered view) or for the
 * A24-R click-and-replace path (client trigger).
 *
 * Empty / undefined payload → fragment with the default
 * message. Non-string ``message`` → also default (defensive
 * fallback for callers that pass through unvalidated JSON).
 */
export async function renderLoadingSurface(
  payload?: LoadingPayload,
): Promise<string> {
  const message = _pickMessage(payload);
  const template = loadCachedTemplate(LOADING_TEMPLATE_NAME);
  return renderTemplate(template, {
    message: escapeHtml(message),
  });
}


/** Pick the message to render. Returns the supplied message
 *  when it's a non-empty string; otherwise the default. The
 *  empty-string case falls through to the default so an
 *  empty ``message`` field on the wire still renders the
 *  spinner-friendly "Loading…" text. */
function _pickMessage(payload?: LoadingPayload): string {
  if (!payload) return DEFAULT_LOADING_MESSAGE;
  const m = payload.message;
  if (typeof m !== "string" || m.length === 0) {
    return DEFAULT_LOADING_MESSAGE;
  }
  return m;
}
