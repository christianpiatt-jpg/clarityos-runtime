/**
 * Web Surface v0.2.0 — health / readiness endpoints (Track C).
 *
 * Deterministic ``/health`` and ``/ready`` responses, served by
 * the Node HTTP entrypoint BEFORE the surface router is
 * consulted. They do not touch ``routeWebSurface``, the view
 * registry, templates, the Python 503 gate, or any other
 * surface internals.
 *
 * Same payload shape per the Track C spec — two endpoints, one
 * answer. If a future card needs differentiated readiness
 * semantics (e.g., "ready only after asset manifest validates"),
 * add a separate ``checkReadiness`` function — don't change
 * ``handleHealth``.
 *
 * Determinism:
 *   * Pure function. Same call → same response, byte-for-byte.
 *   * No env reads, no external probes, no clock.
 *
 * Cloud Run note:
 *   * Cloud Run uses ``/`` for HTTP health probes by default,
 *     so these endpoints are advisory. They're useful for
 *     manual smoke-testing + future probe configuration.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";


/** The shape both endpoints return. Exported so tests can
 *  assert against it without re-typing the literal. */
export interface HealthPayload {
  status: "ok";
  surface: "v0.2.0";
}


export const HEALTH_PAYLOAD: HealthPayload = {
  status:  "ok",
  surface: "v0.2.0",
};


/** Paths that the entrypoint must intercept BEFORE dispatching
 *  to ``routeWebSurface``. Exported so the request handler
 *  imports the same list (single source of truth). */
export const HEALTH_PATHS = ["/health", "/ready"] as const;


/**
 * Produce the surface-shaped Response for a health/ready hit.
 * The adapter writes it to the wire via ``writeSurfaceResponse``,
 * which JSON-stringifies the object body.
 */
export function handleHealth(): WebSurfaceV0_2.Response {
  return {
    status:  200,
    headers: { "content-type": "application/json" },
    body:    HEALTH_PAYLOAD,
  };
}
