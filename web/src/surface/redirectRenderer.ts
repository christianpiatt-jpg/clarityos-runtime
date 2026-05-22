/**
 * Web Surface v0.2.0 — redirect renderer (Card A12).
 *
 * Mode-aware dispatch for the ``redirect`` classifier action:
 *
 *   * JSON mode → 200 ``RedirectEnvelope`` ({redirect: <to>}).
 *   * HTML mode → 200 + HTML body, rendered via the same view /
 *                 layout pipeline that every other view uses
 *                 (``redirect_view`` registered by
 *                 ``views/redirect.ts``).
 *
 * The renderer NEVER returns HTTP 302. Both modes return 200 — the
 * redirect is a payload, not a transport-level instruction. The
 * client decides whether to follow (the HTML view embeds a small
 * ``setTimeout`` that performs the actual ``window.location``
 * jump; the JSON envelope is consumed by SPA-side code that
 * decides how to navigate).
 *
 * Determinism guarantees:
 *   * Same (to, mode) in → same Response out, byte-for-byte.
 *   * The renderer does not mutate the classifier action, the
 *     view registry, or any cache. URL validation lives in the
 *     view's ``render()`` (single sanitisation boundary).
 *   * The pipeline's existing try/catch (Card A11) covers the
 *     HTML branch — a missing redirect view / template would
 *     surface as a 500 page, never as an exception bubble.
 *
 * Why dispatch through ``executeRenderPipeline`` rather than
 * directly to the redirect view:
 *   * Symmetry with every other view rendering path.
 *   * Re-uses the asset-var injection, layout wrapping, partial
 *     inclusion, and template caching the pipeline already
 *     provides.
 *   * Lets the redirect view declare ``layout: "standard"`` and
 *     get the same chrome as ``home``.
 */
import { WebSurfaceV0_2 } from "../contracts/webSurfaceV0_2";
import { WebSurfaceV0_2_View as V } from "./viewContract";
import { executeRenderPipeline } from "./renderPipeline";
import { RedirectEnvelope } from "./redirectEnvelope";


/** Registered view name for the HTML redirect renderer. The
 *  classifier's magic URL name (``"redirect"``) is intentionally
 *  different from the view name (``"redirect_view"``) so the URL
 *  routing primitive doesn't collide with the view registration. */
export const REDIRECT_VIEW_REGISTRY_KEY = "redirect_view";


/**
 * Build a redirect response. Pure dispatch — the renderer does
 * not validate ``to`` itself; the redirect view's ``render()``
 * applies the URL allowlist before substitution into the template.
 */
export async function renderRedirect(
  to: string,
  mode: V.Mode,
): Promise<WebSurfaceV0_2.Response> {
  if (mode === V.Mode.json) {
    const body: RedirectEnvelope = { redirect: to };
    return {
      status:  200,
      headers: { "content-type": "application/json" },
      body,
    };
  }

  return executeRenderPipeline({
    view:   REDIRECT_VIEW_REGISTRY_KEY,
    params: { to },
    mode,
  });
}
