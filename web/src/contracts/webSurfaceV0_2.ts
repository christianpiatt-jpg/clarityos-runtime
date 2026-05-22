/**
 * Web Surface v0.2.0 — boundary contract.
 *
 * Pure boundary definition for the v0.2.0 Web Surface. Defines the
 * versioned request / response envelope, the discriminated union of
 * surface actions the SPA + (future) runtime handler may exchange,
 * and the stable error envelope.
 *
 * Constraints:
 *   * This module MUST NOT import runtime internals (no router,
 *     no auth, no store, no fetch utilities). It is consumed by
 *     both the SPA-side adapters and any future Cloud-Run-side
 *     handler that wants to type-check against the same shape.
 *   * The version segment in the namespace name is load-bearing:
 *     a future v0.3.0 contract lives in its own namespace, so two
 *     callers on different versions can coexist during migration.
 *   * No runtime side effects at import — the module exports types
 *     and (where useful) discriminator constants only.
 *
 * Anchor docs: ../../../docs/web_surface/v0.2.0-contract.md
 */

export namespace WebSurfaceV0_2 {
  // -------------------------------------------------------------------------
  // Envelope — request / response shape
  // -------------------------------------------------------------------------

  /** Every Web Surface call carries this request shape. */
  export interface Request {
    path: string;
    method: string;
    headers: Record<string, string>;
    body: unknown;
  }

  /** Every Web Surface call returns this response shape. */
  export interface Response {
    status: number;
    headers: Record<string, string>;
    body: unknown;
  }

  // -------------------------------------------------------------------------
  // Error envelope — what `body` carries when `status >= 400`
  // -------------------------------------------------------------------------

  /**
   * Stable error envelope. The `error` string is a machine-readable
   * code (e.g. `"not_implemented"`, `"unauthorized"`); `detail` is
   * an optional, opaque payload the caller may surface for
   * diagnostics. Adding fields is allowed; removing or renaming
   * `error` is a breaking change that requires a new contract
   * version.
   */
  export interface ErrorEnvelope {
    error: string;
    detail?: unknown;
  }

  // -------------------------------------------------------------------------
  // SurfaceAction — discriminated union of actions the SPA may emit
  // -------------------------------------------------------------------------

  /**
   * Discriminated union, keyed on `type`. Consumers exhaustively
   * `switch` on `action.type` and TypeScript narrows the remaining
   * fields. New action variants must be added before they are
   * emitted; the absence of a default case in a switch is the
   * compile-time guard that catches missed variants.
   *
   * Variants:
   *   * `noop`      — explicit no-op; useful as a sentinel + as the
   *                   first/safe entry in any reducer that needs a
   *                   default case during migration.
   *   * `render`    — render a named view, optionally with params.
   *   * `navigate`  — change the current route path.
   */
  export type SurfaceAction =
    | { type: "noop" }
    | { type: "render"; view: string; params?: Record<string, unknown> }
    | { type: "navigate"; path: string };

  /**
   * Discriminator constants. Use these instead of string literals
   * at call sites so a typo surfaces as a `never` error rather
   * than a silent runtime miss. Mirrors the union exactly.
   */
  export const SurfaceActionType = {
    noop:     "noop",
    render:   "render",
    navigate: "navigate",
  } as const;

  // -------------------------------------------------------------------------
  // Version pin
  // -------------------------------------------------------------------------

  /**
   * The contract version. Imported by handler code, telemetry, and
   * the doc generator. Bump this when the envelope shape changes
   * in a breaking way; coexists with the namespace name as
   * defence-in-depth against accidental cross-version reads.
   */
  export const VERSION = "v0.2.0" as const;
}
