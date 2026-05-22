/**
 * Web Surface v0.2.0 — view-engine contract.
 *
 * Internal contract for the view rendering layer. Distinct from the
 * wire-level ``WebSurfaceV0_2`` contract in
 * ``../contracts/webSurfaceV0_2.ts``:
 *
 *   * Wire contract  (cross-language) — what the SPA sends and what
 *                                       the runtime returns.
 *   * View contract  (this module)    — what a view renderer
 *                                       accepts and produces inside
 *                                       the surface.
 *
 * The wire contract is versioned in lock-step with the schema +
 * Pydantic model; the view contract is implementation-internal and
 * is replaceable atomically across the surface code.
 *
 * Card A1 — Track A — View Engine foundation.
 */

export namespace WebSurfaceV0_2_View {
  /** Output rendering mode. ``html`` produces a string body with
   *  ``text/html`` content-type; ``json`` produces an object body
   *  with ``application/json`` content-type. */
  export type Mode = "html" | "json";

  /** Per-call input to a view renderer. ``view`` is the registry
   *  key (string); ``params`` is the opaque per-call payload from
   *  the surface action; ``mode`` is the requested output format. */
  export interface RenderContext {
    view: string;
    params?: Record<string, unknown>;
    mode: Mode;
  }

  /** The structural output of a view renderer. ``body`` is a string
   *  for HTML mode and a plain JSON-serialisable object for JSON
   *  mode. This shape is a structural subtype of
   *  ``WebSurfaceV0_2.Response`` — every ``RenderOutput`` is a
   *  valid Response (string|object ⊂ unknown). */
  export interface RenderOutput {
    status: number;
    headers: Record<string, string>;
    body: string | Record<string, unknown>;
  }

  /** Discriminator constants — paired with the union for typo-safety
   *  at call sites (``Mode.html`` etc.) */
  export const Mode = {
    html: "html",
    json: "json",
  } as const;
}
