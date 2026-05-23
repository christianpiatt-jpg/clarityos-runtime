/**
 * Web Surface v0.2.0 — diagnostics types (Card A21-R).
 *
 * Typed shapes for the operator-facing diagnostic payload that
 * the ``/__diagnostics`` route renders into the diagnostic
 * fragment.
 *
 * Shape policy:
 *   * ``DiagnosticEntry`` is one observation — a named key, an
 *     opaque value, and a severity tag. Severity is a closed
 *     enum so renderers can colour-code without ad-hoc strings.
 *   * ``DiagnosticPayload.entries`` preserves the order in which
 *     the collector pushes them, so JSON serialisation is
 *     byte-stable for any given collector implementation.
 *   * ``DiagnosticPayload.timestamp`` is an ISO-8601 string —
 *     the wall-clock at collection time. The only non-pure field
 *     in the payload; isolated so the rest of the collector
 *     stays deterministic per (request, registry-state).
 *
 * Held in its own file so ``collect.ts`` and ``index.ts`` can
 * import the types without circular dependencies (mirrors the
 * A20-R ``forms/`` module's split).
 */


/** One observation. ``value`` is unknown so the collector can
 *  attach arbitrary payloads (headers, counts, route names)
 *  without losing type information at the boundary. */
export interface DiagnosticEntry {
  key: string;
  value: unknown;
  severity: "info" | "warn" | "error";
}


/**
 * Aggregate payload returned by ``collectDiagnostics``. The route
 * handler JSON-stringifies this object and injects it into the
 * ``diagnosticFragment`` template.
 */
export interface DiagnosticPayload {
  entries: DiagnosticEntry[];
  timestamp: string;
}
