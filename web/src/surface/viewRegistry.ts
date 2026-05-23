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
import { ValidationSchema } from "./validationSchema";
import { SseEvent } from "./sseEvent";


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
 * Card A11 — Optional ``status`` field. Defaults to 200. Error
 * views (``error_404`` / ``error_500``) set this to their
 * appropriate HTTP code so the pipeline can return the correct
 * status without hard-coded view-name branches.
 *
 * Card A14-R — Optional ``schema`` field. When set, the form
 * handler reads the schema from this view's definition, runs
 * ``validator.validateForm`` over the parsed form fields, and
 * dispatches through the render pipeline with
 * ``{...values, errors}`` as ``params``. Views without a schema
 * pass form fields through untouched (A13-R behaviour). The
 * schema is per-view, declarative, and pure — no validation
 * logic in the view's ``render`` itself.
 *
 * Card A15 — ``template`` and ``schema`` may also be FUNCTIONS,
 * not just literal values. This is the stateless multi-step form
 * pattern: the wizard view picks a different template per step
 * (function of ``ctx``) AND a different schema per step (function
 * of the parsed form ``fields``), all without server-side state.
 * The pipeline calls ``template(ctx)`` if it's a function;
 * ``formHandler`` calls ``schema(fields)`` if it's a function.
 * Pure extension — static-value views still work unchanged.
 *
 * Card A17 — optional ``stream`` field, an async-generator factory
 * the streaming handler calls when the request opts into chunked
 * output (header ``x-stream: 1``). Each yielded string becomes a
 * chunk in the assembled Response. Views without a ``stream``
 * field fall back to the default streaming strategy (the view's
 * ``render()`` output turned into key/value div chunks). v0.2.0
 * collects chunks deterministically and returns a single
 * Response; a future card can stream the same chunks over the
 * wire when Cloud Run activation lands.
 *
 * Card A18 — optional ``events`` field, an async-generator factory
 * the SSE handler calls when the request opts into server-sent
 * events (header ``x-sse: 1``). Each yielded ``SseEvent`` becomes
 * a framed line group in the assembled Response. Views without an
 * ``events`` field fall back to the default SSE adapter (the
 * view's ``render()`` output wrapped in a single SSE event).
 * Same forward-compatibility story as A17: v0.2.0 assembles
 * frames in memory; Track C's wire activation can pipe them.
 *
 * Security note: ``render`` is responsible for HTML-escaping any
 * values that originate from untrusted sources (request params,
 * external data). The template engine does not escape — see
 * ``templateEngine.ts`` for the rationale.
 */

/** Card A15: a template name OR a function of the render context
 *  that returns one. The pipeline resolves it at render time. */
export type ViewTemplate =
  | string
  | ((ctx: V.RenderContext) => string);


/** Card A15: a schema OR a function of the parsed form fields
 *  that returns a schema (or undefined to skip validation). The
 *  form handler resolves it at handle time. */
export type ViewSchema =
  | ValidationSchema
  | ((fields: Record<string, string>) => ValidationSchema | undefined);


/** Card A17: an async-generator factory for chunked output. The
 *  ``params`` argument mirrors the render context's params field
 *  so streaming views can read the same data the standard render
 *  path sees. Each yielded string is one chunk in the assembled
 *  Response body. */
export type ViewStreamFn = (
  params?: Record<string, unknown>,
) => AsyncIterable<string>;


/** Card A18: an async-generator factory for Server-Sent Events.
 *  Same per-call shape as ``ViewStreamFn`` but yields structured
 *  ``SseEvent``s instead of raw strings — the SSE handler does
 *  the framing. */
export type ViewEventsFn = (
  params?: Record<string, unknown>,
) => AsyncIterable<SseEvent>;


export interface ViewDefinition {
  template: ViewTemplate;
  layout?: string;
  status?: number;
  schema?: ViewSchema;
  stream?: ViewStreamFn;
  events?: ViewEventsFn;
  render: ViewRenderFn;
}


/**
 * Resolve ``def.template`` to a literal string. Static templates
 * pass through; function templates are called with ``ctx``.
 * Exported so the renderer + tests share a single resolution
 * point.
 */
export function resolveViewTemplate(
  template: ViewTemplate,
  ctx: V.RenderContext,
): string {
  return typeof template === "function" ? template(ctx) : template;
}


/**
 * Resolve ``def.schema`` (if present) to a ValidationSchema or
 * undefined. Static schemas pass through; function schemas are
 * called with the parsed form ``fields``. Returning ``undefined``
 * skips validation entirely (the form handler then falls into
 * the A13-R passthrough branch).
 */
export function resolveViewSchema(
  schema: ViewSchema | undefined,
  fields: Record<string, string>,
): ValidationSchema | undefined {
  if (schema === undefined) return undefined;
  return typeof schema === "function" ? schema(fields) : schema;
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
