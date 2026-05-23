/**
 * Web Surface v0.2.0 — Perplexity relay route (Card A30-R, Track C).
 *
 * Server-level interceptor for ``POST /__perplexity``. The
 * request handler in ``../requestHandler.ts`` matches the
 * path BEFORE the surface router (mirrors the A21-R
 * ``/__diagnostics``, A22-R ``/__stream``, A23-R
 * ``/__status``, and A24-R ``/__loading`` patterns).
 *
 * Why a server-level interceptor (not a surface view):
 *   * ``__``-prefixed paths are operator/system surfaces; they
 *     must respond regardless of the view registry's state.
 *   * Single-purpose: relay a query to the Perplexity upstream
 *     and render the response as an HTML fragment.
 *
 * Upstream contract:
 *   * Delegates to ``callPerplexity`` from
 *     ``web/src/upstream/perplexity``. The upstream resolves
 *     REAL vs. MOCK at call time via ``PERPLEXITY_MODE``:
 *       - Default / unset                  → MOCK (deterministic)
 *       - ``PERPLEXITY_MODE=REAL``         → REAL (online; also
 *                                            requires
 *                                            ``PERPLEXITY_API_KEY``)
 *   * Upstream returns ``{ text, tokensUsed }``; both fields
 *     are rendered into the fragment via the template's
 *     ``{{ text }}`` and ``{{ tokens_used }}`` slots.
 *
 * Request shape:
 *   * Method: ``POST``. Any other method returns a 400 +
 *     failure-style fragment.
 *   * Content-type: ``application/json`` (recommended). The
 *     handler tries to parse the body as JSON regardless.
 *   * Body: ``{"query": "..."}``. The query must be a
 *     non-empty string.
 *
 * Response shape:
 *   * Always HTML. Per the A30-R card, the route never
 *     returns JSON. Success and failure both render via the
 *     same template; failure surfaces the error message in
 *     the ``<pre data-answer>`` slot with ``tokens: 0``.
 *   * Content-type: ``text/html; charset=utf-8``.
 *   * Status 200 on success; 400 on bad input; 502 when the
 *     upstream throws (network / config / parse / timeout).
 *
 * Determinism / side effects:
 *   * MOCK mode is deterministic by construction.
 *   * REAL mode performs one outbound HTTPS call to the
 *     Perplexity API and reads ``PERPLEXITY_API_KEY`` from
 *     env (never logged).
 *   * The route never throws past its caller; upstream
 *     exceptions are caught and rendered as failure
 *     fragments.
 */
import { WebSurfaceV0_2 } from "../../contracts/webSurfaceV0_2";
import { callPerplexity } from "../../upstream/perplexity";
import { loadCachedTemplate } from "../../surface/templateCache";
import { renderTemplate } from "../../surface/templateEngine";


/** The path the request handler matches against. Exported so
 *  the interceptor in ``requestHandler.ts`` imports the same
 *  constant (single source of truth). */
export const PERPLEXITY_PATH = "/__perplexity";


/** Template name resolved by ``loadCachedTemplate``. Held as
 *  a constant so the route + tests agree on the exact lookup
 *  key. */
export const PERPLEXITY_TEMPLATE_NAME = "perplexityFragment";


/** Minimal HTML-entity escape. Mirrors the per-renderer
 *  escape policy used across the codebase. Exported for tests
 *  so the exact escape behaviour can be asserted without
 *  going through the full handler. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


/**
 * Handle a ``POST /__perplexity`` request. Always returns
 * HTML; never throws past its caller.
 *
 * Failure paths (all produce an HTML failure fragment):
 *   * Non-POST method                         → 400.
 *   * Non-string body / unparseable JSON      → 400.
 *   * Missing / non-string / empty query      → 400.
 *   * Upstream throws (config/timeout/etc.)   → 502.
 *
 * Success path:
 *   * Status 200, body = the rendered Perplexity fragment.
 */
export async function handlePerplexity(
  request: WebSurfaceV0_2.Request,
): Promise<WebSurfaceV0_2.Response> {
  if (request.method !== "POST") {
    return _failureResponse(
      400,
      "method_not_allowed: /__perplexity requires POST",
    );
  }

  if (typeof request.body !== "string" || request.body.length === 0) {
    return _failureResponse(400, "bad_request: missing JSON body");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(request.body);
  } catch {
    return _failureResponse(400, "bad_request: body is not valid JSON");
  }

  const query = _coerceQuery(parsed);
  if (query === null) {
    return _failureResponse(
      400,
      "bad_request: payload must be {query: <non-empty string>}",
    );
  }

  let upstream: { text: string; tokensUsed: number };
  try {
    upstream = await callPerplexity({ query });
  } catch (err) {
    // Upstream faults — config / timeout / network / parse.
    // The error message is operator-facing diagnostic text.
    // The upstream's own design guarantees the API key is
    // never embedded in error messages, so it's safe to
    // surface.
    return _failureResponse(
      502,
      `upstream_error: ${(err as Error).message}`,
    );
  }

  return _renderResponse(200, upstream.text, upstream.tokensUsed);
}


/** Pull a non-empty string ``query`` field out of an arbitrary
 *  parsed JSON value. Returns ``null`` for any shape
 *  violation. Exported for tests. */
export function _coerceQuery(raw: unknown): string | null {
  if (raw === null || typeof raw !== "object") return null;
  const q = (raw as { query?: unknown }).query;
  if (typeof q !== "string" || q.length === 0) return null;
  return q;
}


/** Render the standard perplexity fragment with the given
 *  text + token count. Both fields are HTML-escaped at the
 *  boundary. */
async function _renderResponse(
  status: number,
  text: string,
  tokensUsed: number,
): Promise<WebSurfaceV0_2.Response> {
  const template = loadCachedTemplate(PERPLEXITY_TEMPLATE_NAME);
  const html = renderTemplate(template, {
    text:        escapeHtml(text),
    tokens_used: String(tokensUsed),
  });
  return {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    html,
  };
}


/** Render a failure fragment with the given diagnostic
 *  message. Same template as success — the operator-facing
 *  UX is uniform regardless of outcome (A23-R-style
 *  invariant). Tokens always ``0`` for failures. */
async function _failureResponse(
  status: number,
  message: string,
): Promise<WebSurfaceV0_2.Response> {
  return _renderResponse(status, message, 0);
}
