/**
 * Web Surface v0.2.0 — redirect view (Card A12).
 *
 * HTML rendering path for the ``redirect`` classifier action.
 * The redirect renderer (``redirectRenderer.ts``) dispatches
 * here via ``executeRenderPipeline``; the JSON envelope path
 * never reaches this view.
 *
 * URL allowlist (load-bearing security boundary):
 *   The same ``{{ to }}`` value is substituted into THREE
 *   distinct contexts in ``redirect.html``:
 *
 *     1. HTML attribute  — ``<a href="{{ to }}">``
 *     2. HTML text       — ``<a ...>{{ to }}</a>``
 *     3. JS string lit.  — ``window.location.href = "{{ to }}"``
 *
 *   To stay safe across all three with a SINGLE substitution
 *   value, the view applies a strict character allowlist before
 *   the value reaches the template. The allowlist excludes the
 *   union of dangerous chars across the three contexts:
 *     * ``<>``      — would break out of HTML attribute / text
 *     * ``" ' \``  — would break out of attribute / JS string
 *     * backtick   — would break a future template-literal use
 *     * newline    — would break the script line
 *     * ``;``      — would terminate a script statement
 *
 *   What's left is a strict URL-path subset:
 *     ``/ a-z A-Z 0-9 _ . ~ ? & = % : -``
 *
 *   Any input that doesn't match falls back to the home URL
 *   ``DEFAULT_REDIRECT_TARGET``. This is the v0.2.0 policy — it
 *   accepts the common case (relative paths with normal query
 *   strings) and rejects everything else.
 *
 *   Absolute http(s) URLs are NOT in the allowlist (no ``//``
 *   prefix support, no scheme allowlist) because v0.2.0's only
 *   intended redirect destination is the surface itself. Cross-
 *   origin redirect support can be added later behind an
 *   explicit ``allowed_origins`` config.
 *
 * Determinism:
 *   * Pure function of ``ctx.params.to``.
 *   * No registry / cache / network access at render time.
 *   * Same input → same vars out.
 */
import { WebSurfaceV0_2_View as V } from "../viewContract";
import { registerView, ViewDefinition } from "../viewRegistry";
import { DEFAULT_REDIRECT_TARGET } from "../classifier";
import { REDIRECT_VIEW_REGISTRY_KEY } from "../redirectRenderer";


/** Hard upper bound on the URL length we'll accept. Anything
 *  longer falls back to the default. */
const MAX_REDIRECT_LENGTH = 2048;


/** Strict allowlist — see the module-level comment for the
 *  reasoning behind each excluded character. */
const SAFE_REDIRECT_RE = /^\/[A-Za-z0-9/_.~?&=%:-]*$/;


/**
 * Return ``raw`` if it passes the safe-URL allowlist, otherwise
 * fall back to the default redirect target. Exported for tests
 * so the allowlist can be exercised without going through the
 * full render path.
 *
 * Protocol-relative URLs (``//evil.example.com``) ALSO fall
 * back to the default. They satisfy the regex (every char is in
 * the safe class) but browsers treat them as origin-changing
 * redirects — the classic open-redirect XSS vector. Explicit
 * prefix check keeps the regex simple and the rejection
 * unambiguous.
 */
export function sanitizeRedirectTarget(raw: unknown): string {
  if (typeof raw !== "string") return DEFAULT_REDIRECT_TARGET;
  if (raw.length === 0 || raw.length > MAX_REDIRECT_LENGTH) {
    return DEFAULT_REDIRECT_TARGET;
  }
  if (raw.startsWith("//")) return DEFAULT_REDIRECT_TARGET;
  if (!SAFE_REDIRECT_RE.test(raw)) return DEFAULT_REDIRECT_TARGET;
  return raw;
}


/** Exported for tests + future programmatic re-registration. */
export const redirectView: ViewDefinition = {
  template: "redirect",
  layout:   "standard",
  async render(ctx: V.RenderContext) {
    const to = sanitizeRedirectTarget(ctx.params?.["to"]);
    return {
      // The title appears in the layout's <head><title> and the
      // header partial's subtitle slot. Static literal — no
      // sanitisation required.
      title:    "Redirecting",
      subtitle: "302",
      // ``to`` has been allowlist-validated above and is safe to
      // substitute into HTML attribute, HTML text, and JS string
      // contexts as-is.
      to,
    };
  },
};


// Side-effect registration: the first import of this module
// installs ``redirect_view`` in the registry.
registerView(REDIRECT_VIEW_REGISTRY_KEY, redirectView);
