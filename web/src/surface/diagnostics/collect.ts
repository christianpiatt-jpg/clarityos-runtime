/**
 * Web Surface v0.2.0 — diagnostic collector (Card A21-R).
 *
 * Single helper: ``collectDiagnostics(request)`` walks a v0.2
 * surface Request and returns a typed ``DiagnosticPayload``
 * suitable for operator-visible rendering by the
 * ``/__diagnostics`` route.
 *
 * Sources (per the A21-R card):
 *   * Request method / path / headers — always present.
 *   * Route metadata — ``resolveView`` is total (never throws),
 *     so the matched view name is always recorded.
 *   * Server timing — not yet wired into the surface; the entry
 *     records ``null`` as a placeholder so future cards can
 *     populate it without changing the payload shape.
 *   * Form error count — defers to A20-R's ``collectFormErrors``.
 *     Non-form requests pass through with zero errors (the
 *     A20-R helper returns ``EMPTY_FORM_ERRORS`` for non-string
 *     bodies, unknown views, and views without a schema).
 *   * Surface render timing — same as server timing; placeholder
 *     entry, ready for a future timing module.
 *
 * Determinism:
 *   * Everything except ``timestamp`` is a pure function of the
 *     request + view-registry state. The timestamp is generated
 *     once at the top of ``collectDiagnostics`` so the rest of
 *     the function is timestamp-free.
 *   * Tests that need a deterministic timestamp can call
 *     ``_buildDiagnosticPayload`` directly with an injected
 *     clock; production code never sees this seam.
 *
 * Severity policy:
 *   * Request / route / timing entries are ``info``.
 *   * Form error count is ``info`` when zero, ``warn`` otherwise.
 *   * No collector path produces ``error`` today — that severity
 *     is reserved for future health-check style entries.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { resolveView } from "../viewResolution";
import { collectFormErrors } from "../forms";

import { DiagnosticEntry, DiagnosticPayload } from "./types";


/**
 * Collect a diagnostic payload describing the request, the
 * matched view, and the form-error count.
 *
 * Pure-ish: deterministic except for the leading wall-clock
 * read. See module docstring.
 */
export async function collectDiagnostics(
  request: WebSurfaceV0_2.Request,
): Promise<DiagnosticPayload> {
  const entries: DiagnosticEntry[] = [];

  // --- Request envelope ---
  entries.push({
    key:      "request.method",
    value:    request.method,
    severity: "info",
  });
  entries.push({
    key:      "request.path",
    value:    request.path,
    severity: "info",
  });
  entries.push({
    key:      "request.headers",
    value:    request.headers,
    severity: "info",
  });

  // --- Route metadata --- resolveView is total (never throws).
  const resolved = resolveView(request);
  entries.push({
    key:      "route.view",
    value:    resolved.view,
    severity: "info",
  });
  entries.push({
    key:      "route.mode",
    value:    resolved.mode,
    severity: "info",
  });

  // --- Server timing --- placeholder; no timing infra yet.
  entries.push({
    key:      "server.timing_ms",
    value:    null,
    severity: "info",
  });

  // --- Form error count (A20-R) --- non-form requests pass
  // through as zero errors via ``EMPTY_FORM_ERRORS``.
  const bag = await collectFormErrors(request);
  const formErrorCount = Object.keys(bag.errors).length;
  entries.push({
    key:      "form.error_count",
    value:    formErrorCount,
    severity: formErrorCount === 0 ? "info" : "warn",
  });

  // --- Surface render timing --- placeholder; same shape as
  // server.timing_ms so renderers can treat both identically.
  entries.push({
    key:      "surface.render_ms",
    value:    null,
    severity: "info",
  });

  return {
    entries,
    timestamp: new Date().toISOString(),
  };
}
