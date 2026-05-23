/**
 * Web Surface v0.2.0 — Server-Sent Event payload type (Card A18).
 *
 * Mirrors the SSE wire grammar (WHATWG HTML Living Standard,
 * "Server-sent events" section) at the application level. The
 * SSE handler turns each ``SseEvent`` into a framed line group
 * before emitting:
 *
 *     id: <id>
 *     event: <event>
 *     data: <JSON.stringify(data)>
 *     (blank line)
 *
 * Held in its own file to avoid the circular import that would
 * otherwise form between ``viewRegistry.ts`` (which references
 * the type on ``ViewDefinition.events?``) and ``sseHandler.ts``
 * (which uses ``ViewDefinition``). Mirrors the
 * ``redirectEnvelope.ts`` placement pattern.
 *
 * Field policy:
 *   * ``data`` is required and may be any JSON-serialisable value
 *     (string, number, object, array, ...). The handler runs
 *     ``JSON.stringify`` on it, so escaping and single-line
 *     framing are automatic.
 *   * ``id`` and ``event`` are optional bare strings. The handler
 *     strips embedded CR/LF before framing (they would break
 *     line-oriented SSE parsing).
 */

export interface SseEvent {
  /** Optional event name (becomes the ``event:`` field).
   *  Embedded CR/LF are stripped by the handler. */
  event?: string;

  /** Optional event id (becomes the ``id:`` field). Embedded
   *  CR/LF are stripped by the handler. */
  id?: string;

  /** Required payload (becomes the ``data:`` field, JSON-encoded). */
  data: unknown;
}
