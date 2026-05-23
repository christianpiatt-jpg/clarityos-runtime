/**
 * Web Surface v0.2.0 — streaming event types (Card A22-R).
 *
 * Typed wrapper around the long-running-task event stream that
 * the ``/__stream`` route emits as SSE frames.
 *
 * Shape policy:
 *   * ``type`` is a closed enum so the client can dispatch on
 *     it without ad-hoc string checks. Mirrors the SSE
 *     ``event:`` field — the route uses ``type`` as the SSE
 *     event name so an ``EventSource`` can
 *     ``addEventListener("log", ...)``, etc.
 *   * ``message`` is the human-readable payload. Held as a
 *     string (not unknown) so the enhancement layer can append
 *     it directly into a ``<pre>`` without extra coercion.
 *   * Severity is implicit in ``type``; ``error`` is a hard
 *     stop, ``done`` is a soft stop, ``log`` / ``status`` are
 *     incremental.
 *
 * Held in its own file so ``controller.ts`` and ``index.ts``
 * can import the type without circular deps (mirrors the
 * A20-R ``forms/`` and A21-R ``diagnostics/`` splits).
 */


/** One event in a streaming-task transcript. */
export interface StreamEvent {
  type:    "log" | "status" | "done" | "error";
  message: string;
}
