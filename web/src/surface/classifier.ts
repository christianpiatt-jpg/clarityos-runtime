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
 * Card A12 update: a new ``redirect`` action variant. Any request
 * resolving to the magic view name ``"redirect"`` is intercepted
 * BEFORE the registry check and emitted as
 * ``{kind: "redirect", to, mode}``. The target URL comes from the
 * ``?to=...`` query param; a missing / non-string value falls
 * back to the default home URL. The router dispatches this to
 * ``renderRedirect`` (JSON envelope or HTML redirect page).
 * Redirects are NEVER served as HTTP 302 — both responses are
 * 200 with the redirect target carried in the body.
 *
 * Card A13-R update: a new ``form`` action variant. ``POST``
 * requests with ``content-type: application/x-www-form-urlencoded``
 * are emitted as ``{kind: "form", view, rawBody, mode}``. Detection
 * precedence (top wins):
 *   1. Redirect (URL-routed primitive — wins regardless of method)
 *   2. Form (POST + form content-type)
 *   3. 404 rewrite (unknown view)
 *   4. Normal render
 *
 * Why form precedes the 404 rewrite: a POST to an unknown view
 * with form data should preserve the input by routing through
 * ``handleForm`` (which dispatches the unknown view through the
 * pipeline's defaultRenderer fallback), rather than discarding
 * the body and rewriting to an error page.
 *
 * Non-string body policy (A13-R):
 *   * The wire contract types ``req.body`` as ``unknown`` —
 *     callers may pass strings, Buffers, parsed objects, etc.
 *   * For a POST with form content-type, the body MUST be a
 *     string. The classifier rejects any other shape by emitting
 *     a ``render(error_500)`` action with a diagnostic message,
 *     rather than silently coercing to an empty form (which
 *     would mask malformed requests as legitimate "user
 *     submitted blank form" cases).
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


/** Registry key for the 500 view. Mirrors ``ERROR_404_VIEW``;
 *  also re-exported by ``router.ts`` so the envelope→HTML
 *  transform doesn't need to type the literal either. */
export const ERROR_500_VIEW = "error_500";


/** Content-type marker the form classifier branch tests against.
 *  Matches both ``application/x-www-form-urlencoded`` and the
 *  ``application/x-www-form-urlencoded; charset=utf-8`` form
 *  some clients send. */
export const FORM_URLENCODED_CONTENT_TYPE = "application/x-www-form-urlencoded";


/** The magic view name that triggers the redirect-action branch.
 *  ``/web-surface/v0.2/redirect`` (or any path resolving to last
 *  segment ``"redirect"``) → ``{kind: "redirect", ...}``. Held
 *  here as a constant so the renderer + navigation helper can
 *  import it without re-typing the literal. */
export const REDIRECT_VIEW_NAME = "redirect";


/** Fallback target when ``?to=...`` is missing or non-string.
 *  Matches the home URL the v0.2 surface ships with. */
export const DEFAULT_REDIRECT_TARGET = "/web-surface/v0.2/home";


/**
 * The classifier's output type. Distinct from
 * ``WebSurfaceV0_2.SurfaceAction`` — that's what the SPA EMITS to
 * the surface; this is the surface's INTERNAL normalisation of
 * "what does this request actually want?". Keyed on ``kind`` (not
 * ``type``) to make the two unions visually distinct in code
 * reviews.
 *
 * Variants:
 *   * ``noop``     — request bypasses rendering (reserved for future
 *                    use; not emitted by the classifier in v0.2.0).
 *   * ``render``   — request mapped to a named view via the view
 *                    resolution layer (Card A2). The render variant
 *                    carries the resolver's full output: ``view``,
 *                    optional ``params``, and required ``mode``.
 *   * ``redirect`` — request asked for a navigation jump (Card A12).
 *                    Carries the validated target URL + mode. The
 *                    router dispatches to ``renderRedirect``, which
 *                    returns either a JSON ``RedirectEnvelope`` or
 *                    an HTML redirect page (client-side navigation,
 *                    no HTTP 302).
 *   * ``form``     — POST submission carrying a form-encoded body
 *                    (Card A13-R). The classifier copies the raw
 *                    body verbatim into the action; parsing happens
 *                    in ``handleForm`` (which dispatches the parsed
 *                    fields back through the render pipeline).
 */
export type ClassifiedSurfaceAction =
  | { kind: "noop" }
  | {
      kind: "render";
      view: string;
      params?: Record<string, unknown>;
      mode: V.Mode;
    }
  | {
      kind: "redirect";
      to: string;
      mode: V.Mode;
    }
  | {
      kind: "form";
      view: string;
      rawBody: string;
      mode: V.Mode;
    };


/** Discriminator constants — paired with the union for typo-safety. */
export const ClassifiedSurfaceActionKind = {
  noop:     "noop",
  render:   "render",
  redirect: "redirect",
  form:     "form",
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

  // Card A12: redirect interception. The magic ``"redirect"``
  // view name triggers the redirect action regardless of registry
  // state — it's a URL routing primitive, not a view. The target
  // URL comes from ``?to=...``; missing / non-string falls back
  // to the home default. Final URL validation happens in the
  // renderer / view (strict allowlist) so the classifier stays
  // free of HTML / JS concerns.
  if (resolved.view === REDIRECT_VIEW_NAME) {
    const target = resolved.params["to"];
    return {
      kind: "redirect",
      to:   typeof target === "string" ? target : DEFAULT_REDIRECT_TARGET,
      mode: resolved.mode,
    };
  }

  // Card A13-R: form-submission interception. POST + form
  // content-type → ``form`` action. A non-string body is rejected
  // with a render(error_500) action — see the module docstring
  // for the rationale (silent coercion masks malformed requests).
  if (req.method === "POST") {
    const contentType = req.headers["content-type"] ?? "";
    if (contentType.includes(FORM_URLENCODED_CONTENT_TYPE)) {
      if (typeof req.body !== "string") {
        return {
          kind:   "render",
          view:   ERROR_500_VIEW,
          params: {
            message: "Form submission body must be a string.",
          },
          mode:   resolved.mode,
        };
      }
      return {
        kind:    "form",
        view:    resolved.view,
        rawBody: req.body,
        mode:    resolved.mode,
      };
    }
  }

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
