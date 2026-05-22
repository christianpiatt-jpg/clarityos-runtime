/**
 * Web Surface v0.2.0 — render dispatcher (public entrypoint).
 *
 * Card history:
 *   * Card 9  — 501 stub.
 *   * Card A1 — registry dispatch + default fallback.
 *   * Card A3 — defaultRenderer uses the template engine.
 *   * Card A4 — registry registrations are ``ViewDefinition``s
 *               (template + render-to-vars); JSON mode bypasses.
 *   * Card A5 — dispatch logic moves into ``renderPipeline.ts``
 *               (single source of truth); this module re-exports
 *               under the public ``renderWebSurface`` name to
 *               preserve every existing caller's import path.
 *
 * Why the re-export indirection:
 *   * The router + tests have called ``renderWebSurface`` since
 *     Card 9. Keeping that name stable means callers don't
 *     change when the implementation moves.
 *   * ``executeRenderPipeline`` is the canonical implementation
 *     name; ``renderWebSurface`` is the public alias.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";


/** Backward-compat alias for callers built against earlier
 *  ``RenderContext`` shapes. */
export type RenderContext = V.RenderContext;


/**
 * Public renderer entrypoint. Delegates to the deterministic
 * render pipeline (``executeRenderPipeline``). See
 * ``renderPipeline.ts`` for the per-step contract.
 */
export { executeRenderPipeline as renderWebSurface } from "./renderPipeline";
