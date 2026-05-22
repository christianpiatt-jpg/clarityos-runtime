/**
 * Web Surface v0.2.0 — view registry.
 *
 * Card A4 update: registrations now carry a ``ViewDefinition``
 * (template name + render function returning template vars), not
 * a raw ``ViewRenderer`` function. Views own ``what data goes
 * into the template``; the renderer (``renderer.ts``) owns
 * ``which template + how to substitute + how to package as a
 * Response``. Splitting these gives the renderer one consistent
 * status / content-type / shape for every registered view.
 *
 * Card A1 contract for reference (removed in A4):
 *   type ViewRenderer = (ctx) => Promise<RenderOutput>
 *
 * Card A4 contract (current):
 *   interface ViewDefinition {
 *     template: string;
 *     render:   (ctx) => Promise<Record<string, unknown>>;
 *   }
 *
 * The registry is module-singleton (one Map per process) and
 * order-preserving. NOT thread-safe in any meaningful sense
 * because JS is single-event-loop; concurrent registrations from
 * different import paths interleave deterministically.
 */
import { WebSurfaceV0_2_View as V } from "./viewContract";


/**
 * Render function: takes a request context and returns template
 * variables. The renderer then applies these vars to the named
 * template. The function MAY be async (for views that need to
 * load data) but MUST be pure with respect to the registry — it
 * MUST NOT call back into ``registerView`` / ``getView`` itself.
 */
export type ViewRenderFn = (
  ctx: V.RenderContext,
) => Promise<Record<string, unknown>>;


/**
 * A view definition. ``template`` is the basename (no extension)
 * of an HTML file under ``web/templates/v0.2/``; ``render``
 * produces the variable bag that gets substituted into it.
 *
 * Card A7 — Optional ``layout`` field. When set to the basename
 * of a layout file under ``web/templates/v0.2/layouts/``, the
 * pipeline renders the view's template first, then wraps the
 * resulting HTML in the layout by substituting it into the
 * layout's ``{{ yield }}`` placeholder. The same view vars are
 * passed to both the template and the layout (with ``yield``
 * added to the layout's substitution context).
 *
 * Security note: ``render`` is responsible for HTML-escaping any
 * values that originate from untrusted sources (request params,
 * external data). The template engine does not escape — see
 * ``templateEngine.ts`` for the rationale.
 */
export interface ViewDefinition {
  template: string;
  layout?: string;
  render: ViewRenderFn;
}


const registry = new Map<string, ViewDefinition>();


/**
 * Register a view definition for ``name``. Subsequent calls with
 * the same name overwrite the previous definition — the last
 * writer wins. This is intentional: lets a downstream module
 * override a default view registration for a specific name.
 */
export function registerView(name: string, def: ViewDefinition): void {
  registry.set(name, def);
}


/** Look up a registered view definition. Returns ``undefined``
 *  for an unknown name so the caller can fall back to the default
 *  renderer. */
export function getView(name: string): ViewDefinition | undefined {
  return registry.get(name);
}


/**
 * Test-only: list every registered view name in insertion order.
 * Useful for asserting registry state in unit tests.
 */
export function _listRegisteredViewsForTests(): string[] {
  return Array.from(registry.keys());
}


/**
 * Test-only: wipe the registry. Tests that register custom views
 * call this in ``beforeEach`` / ``afterEach`` to keep state from
 * leaking between cases.
 */
export function _clearViewRegistryForTests(): void {
  registry.clear();
}
