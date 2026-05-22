/**
 * Web Surface v0.2.0 — request classifier.
 *
 * Pure, deterministic, side-effect-free. Takes a validated
 * ``WebSurfaceV0_2.Request`` and decides what kind of surface
 * action it represents. The output ``ClassifiedSurfaceAction``
 * is the router's switch-on input; new classification rules
 * land here, no other module changes required.
 *
 * For v0.2.0 every request classifies to ``noop`` — real
 * classification rules (path + method → render view) arrive in
 * a follow-up card once the route table exists.
 *
 * Constraints:
 *   * MUST be pure: same Request in → same ClassifiedSurfaceAction out
 *   * MUST NOT touch fetch / storage / globals
 *   * MUST stay typed against ``WebSurfaceV0_2`` from the contract
 *
 * Anchor docs: ../../../../docs/web_surface/v0.2.0-contract.md
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";


/**
 * The classifier's output type. Distinct from
 * ``WebSurfaceV0_2.SurfaceAction`` — that's what the SPA EMITS to
 * the surface; this is the surface's INTERNAL normalisation of
 * "what does this request actually want?". Keyed on ``kind`` (not
 * ``type``) to make the two unions visually distinct in code
 * reviews.
 *
 * Variants:
 *   * ``noop``   — request did not match any classification rule;
 *                  router falls through to the 501 stub.
 *   * ``render`` — request matched a render rule for a named view;
 *                  router dispatches to the renderer.
 */
export type ClassifiedSurfaceAction =
  | { kind: "noop" }
  | { kind: "render"; view: string; params?: Record<string, unknown> };


/** Discriminator constants — paired with the union for typo-safety. */
export const ClassifiedSurfaceActionKind = {
  noop:   "noop",
  render: "render",
} as const;


/**
 * Classify a Web Surface request.
 *
 * For v0.2.0 every request returns ``{ kind: "noop" }``. The
 * function is wired through the router today so that when real
 * rules land in a future card, only this body changes — the
 * router + tests already exercise the noop AND render branches
 * via the discriminator.
 */
export function classifyWebSurfaceRequest(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _req: WebSurfaceV0_2.Request,
): ClassifiedSurfaceAction {
  // TODO(v0.2.0): expand classification rules.
  // Anticipated future shape:
  //   if (req.method === "GET" && KNOWN_VIEWS.has(req.path)) {
  //     return { kind: "render", view: ROUTE_TO_VIEW[req.path] };
  //   }
  return { kind: "noop" };
}
