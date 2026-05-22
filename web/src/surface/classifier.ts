/**
 * Web Surface v0.2.0 — request classifier.
 *
 * Pure, deterministic, side-effect-free. Takes a validated
 * ``WebSurfaceV0_2.Request`` and decides what kind of surface
 * action it represents. The output ``ClassifiedSurfaceAction``
 * is the router's switch-on input; new classification rules
 * land here, no other module changes required.
 *
 * Card A2 update: every request now resolves to a ``render``
 * action via ``viewResolution.resolveView``. The previous Card 8
 * "always noop" behaviour is gone — the noop variant of
 * ``ClassifiedSurfaceAction`` remains in the union for future
 * use (e.g. health-probe requests that should bypass rendering)
 * but the classifier itself never emits it today.
 *
 * Card A11 update: classification now consults the view registry.
 * If ``getView(resolved.view)`` returns undefined (no view bound
 * to the requested name), the classifier rewrites the action to
 * ``error_404`` with the resolved name embedded in the message.
 * The mode is preserved — a JSON request for an unknown view
 * still receives JSON (rendered via the default JSON path with
 * ``view: "error_404"``), and an HTML request receives the
 * structured 404 page.
 *
 * Constraints:
 *   * MUST be deterministic: same (Request, registry state) in →
 *     same ClassifiedSurfaceAction out. The dependency on the
 *     registry is the one stateful escape hatch — the registry
 *     itself is module-singleton and only mutated at view
 *     registration time.
 *   * MUST NOT touch fetch / storage / globals beyond the registry.
 *   * MUST stay typed against ``WebSurfaceV0_2`` from the contract.
 *
 * Anchor docs: ../../../../docs/web_surface/v0.2.0-contract.md
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { resolveView } from "./viewResolution";
import { getView } from "./viewRegistry";


/** Registry key for the 404 view, kept as a constant so tests
 *  can assert against it without re-typing the literal. */
export const ERROR_404_VIEW = "error_404";


/**
 * The classifier's output type. Distinct from
 * ``WebSurfaceV0_2.SurfaceAction`` — that's what the SPA EMITS to
 * the surface; this is the surface's INTERNAL normalisation of
 * "what does this request actually want?". Keyed on ``kind`` (not
 * ``type``) to make the two unions visually distinct in code
 * reviews.
 *
 * Variants:
 *   * ``noop``   — request bypasses rendering (reserved for future
 *                  use; not emitted by the classifier in v0.2.0).
 *   * ``render`` — request mapped to a named view via the view
 *                  resolution layer (Card A2). The render variant
 *                  carries the resolver's full output: ``view``,
 *                  optional ``params``, and required ``mode``.
 */
export type ClassifiedSurfaceAction =
  | { kind: "noop" }
  | {
      kind: "render";
      view: string;
      params?: Record<string, unknown>;
      mode: V.Mode;
    };


/** Discriminator constants — paired with the union for typo-safety. */
export const ClassifiedSurfaceActionKind = {
  noop:   "noop",
  render: "render",
} as const;


/**
 * Classify a Web Surface request.
 *
 * Card A2: delegates to ``resolveView`` and always emits a render
 * action. The noop variant is held in the union for future
 * specialisations (e.g. a future health-probe path that should
 * bypass the renderer entirely).
 */
export function classifyWebSurfaceRequest(
  req: WebSurfaceV0_2.Request,
): ClassifiedSurfaceAction {
  const resolved = resolveView(req);

  // Card A11: unknown view → structured 404 rewrite. Mode is
  // preserved so callers asking for JSON still get JSON.
  if (!getView(resolved.view)) {
    return {
      kind:   "render",
      view:   ERROR_404_VIEW,
      params: { message: `View '${resolved.view}' not found.` },
      mode:   resolved.mode,
    };
  }

  return {
    kind:   "render",
    view:   resolved.view,
    params: resolved.params,
    mode:   resolved.mode,
  };
}
