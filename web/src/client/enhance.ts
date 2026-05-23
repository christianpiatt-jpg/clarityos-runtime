/**
 * Web Surface v0.2.0 — client-side progressive enhancement
 * (Card A19-R).
 *
 * Single source of truth for the v0.2 surface's client behaviour.
 * The build script ``web/scripts/build-client.mjs`` compiles
 * this TS module to ``web/assets/v0.2/app.js`` via esbuild
 * (loader=ts, format=iife). The asset router serves that file
 * via the existing fingerprinted URL pipeline; the standard
 * layout already references it as
 * ``<script src="/web-surface/v0.2/assets/{{ app_js }}" defer>``
 * (no layout change was needed for A19-R).
 *
 * Hard rules (per the A19-R card):
 *   * Side-effect only. No exports. No public surface.
 *   * No framework — React, Vue, Svelte, Solid, Preact are all
 *     forbidden. This file uses only DOM APIs and ``fetch`` /
 *     ``EventSource``.
 *   * No hydration. No virtual DOM. No client router.
 *   * No mutation of server-rendered HTML structure beyond what
 *     the documented ``data-*`` contracts demand.
 *   * No JSON-first rendering. The server's HTML is the
 *     authoritative tree; this script enhances behaviour
 *     locally, never replaces the page.
 *
 * Documented data-* contracts:
 *
 *   1. Toggles / expanders.
 *      ``<X data-toggle-target="#some-id">click me</X>``
 *        → click toggles ``is-open`` on the element matched by
 *          the selector. No DOM rewrites; CSS owns visibility.
 *
 *   2. Fetch-and-replace (progressive form enhancement).
 *      ``<form data-enhance="fetch" data-fragment-target="#out">``
 *        → submit is intercepted, form data is POSTed via
 *          ``fetch`` to ``form.action`` (or the current URL),
 *          and the response body replaces the target fragment's
 *          ``innerHTML``.
 *        → On any failure (network, non-2xx, missing target)
 *          the script removes its own ``data-enhance`` attribute
 *          and re-submits the form natively. The user never
 *          sees a broken interaction.
 *
 *   3. Server-Sent Events subscription.
 *      ``<X data-sse-url="/path" data-sse-target="#out">``
 *        → opens an ``EventSource`` to the URL on DOM ready.
 *        → each message replaces the target's ``innerHTML``.
 *        → on error, closes the source (no reconnection storm).
 *
 * The ``has-js`` class is added to ``<html>`` on script load so
 * stylesheets can opt into JS-only states (e.g., progressively
 * disclosed UIs) without ever blocking the no-JS path.
 *
 * Defensive guarantees:
 *   * Idempotent: re-evaluating this module multiple times
 *     (e.g., in tests via ``vi.resetModules``) adds the
 *     ``has-js`` class once and the delegated listeners use
 *     ``document`` so they survive content swaps.
 *   * Re-entrant: the SSE wiring scans on DOM ready AND when
 *     called directly; an idempotency guard (``data-sse-active``)
 *     prevents double-subscriptions.
 *   * Graceful in test envs: ``EventSource`` is optional —
 *     jsdom omits it by default, and the script skips SSE
 *     wiring when the global is missing.
 */

// ---------------------------------------------------------------------------
// 1. has-js — mark the root for JS-only CSS branches
// ---------------------------------------------------------------------------
//   classList.add is itself idempotent; safe to run on every
//   module load.
document.documentElement.classList.add("has-js");


// ---------------------------------------------------------------------------
// 2 + 3. Delegated listener binding — bound EXACTLY ONCE per
//        document lifetime.
// ---------------------------------------------------------------------------
//   The click / submit handlers below attach to the document
//   object, which persists across module re-evaluations (hot
//   reload in dev; ``vi.resetModules`` in tests). Without an
//   idempotency guard, every re-import accumulates a fresh
//   listener and a single submit fires N handlers.
//
//   We mark the document via a non-enumerable symbol so the
//   marker doesn't leak into ``Object.keys`` enumerations and
//   so two enhance.ts modules sharing the same document (a
//   theoretical edge case) still see the same marker.
const _ENHANCE_BOUND = Symbol.for("clarityos.v0_2.enhance.bound");

interface _DocumentWithMarker extends Document {
  [_ENHANCE_BOUND]?: true;
}

const _doc = document as _DocumentWithMarker;
if (!_doc[_ENHANCE_BOUND]) {
  Object.defineProperty(_doc, _ENHANCE_BOUND, {
    value:        true,
    writable:     false,
    enumerable:   false,
    configurable: false,
  });
  _bindDelegatedListeners();
}


function _bindDelegatedListeners(): void {
  // --- 2. Toggle / expander delegate ---
  document.addEventListener("click", (event) => {
    const node = event.target;
    if (!(node instanceof Element)) return;
    const trigger = node.closest("[data-toggle-target]");
    if (!(trigger instanceof Element)) return;

    const selector = trigger.getAttribute("data-toggle-target");
    if (!selector) return;

    let target: Element | null = null;
    try {
      target = document.querySelector(selector);
    } catch {
      // Bad selector — silently no-op (defensive).
      return;
    }
    if (!target) return;

    target.classList.toggle("is-open");
  });

  // --- 3. Fetch-and-replace form enhancement ---
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.getAttribute("data-enhance") !== "fetch") return;

    const targetSelector = form.getAttribute("data-fragment-target");
    if (!targetSelector) return;

    let target: Element | null = null;
    try {
      target = document.querySelector(targetSelector);
    } catch {
      return;  // bad selector → let native submit proceed
    }
    if (!target) return;

    event.preventDefault();
    void _submitFetchAndReplace(form, target);
  });

  // --- 4. SSE wiring: schedule the FIRST scan ---
  // The post-load rescan (every module re-eval) is at the
  // bottom of this file; this branch handles the initial
  // DOMContentLoaded firing exactly once per document lifetime.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _wireSseContainers);
  }
}


async function _submitFetchAndReplace(
  form: HTMLFormElement,
  target: Element,
): Promise<void> {
  // Serialise the form as application/x-www-form-urlencoded.
  // Matches the v0.2 surface's form classifier branch.
  const params = new URLSearchParams();
  const data = new FormData(form);
  for (const [key, value] of data.entries()) {
    // FormData values can be File for type=file inputs. The
    // fetch-enhancement path doesn't support multipart; if the
    // form has files, fall back to native submission.
    if (typeof value !== "string") {
      _fallBackToNativeSubmit(form);
      return;
    }
    params.append(key, value);
  }

  try {
    const response = await fetch(form.action || window.location.href, {
      method:  (form.method || "POST").toUpperCase(),
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body:    params.toString(),
      // Same-origin cookies by default. No CORS expansion.
      credentials: "same-origin",
    });

    // Card A20-R: response-handling shifts from "status-based"
    // to "content-type-based" so 4xx-with-HTML-error-fragment
    // (e.g., the form-validation rerender) can swap into the
    // target instead of triggering a full-page native submit.
    //
    // Detection rules:
    //   * HTML response (any status)  → replace target.
    //   * Non-HTML response (JSON, plain text, anything else)
    //                                  → fall back.
    //   * Network failure (fetch throws) → fall back (catch
    //                                  block below).
    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().includes("text/html")) {
      _fallBackToNativeSubmit(form);
      return;
    }
    const html = await response.text();
    target.innerHTML = html;
  } catch {
    _fallBackToNativeSubmit(form);
  }
}


function _fallBackToNativeSubmit(form: HTMLFormElement): void {
  // Remove our hook so the next submit goes through natively,
  // then submit. The user-visible behaviour: the page navigates
  // as if no enhancement had run.
  form.removeAttribute("data-enhance");
  try {
    form.submit();
  } catch {
    // Some browsers throw if .submit() is called from inside an
    // event handler that's already preventDefault'd. Best-effort.
  }
}


// ---------------------------------------------------------------------------
// 4. SSE subscription wiring
// ---------------------------------------------------------------------------

/**
 * Marker attribute set on a container after we've opened an
 * EventSource for it. Prevents duplicate subscriptions if the
 * wiring function runs more than once (DOM-ready + manual).
 */
const _SSE_ACTIVE_ATTR = "data-sse-active";


function _wireSseContainers(): void {
  // EventSource is missing in some test environments (jsdom).
  // Skip wiring silently rather than throwing.
  if (typeof EventSource === "undefined") return;

  const containers = document.querySelectorAll<HTMLElement>("[data-sse-url]");
  containers.forEach((container) => {
    if (container.hasAttribute(_SSE_ACTIVE_ATTR)) return;

    const url = container.getAttribute("data-sse-url");
    const targetSelector = container.getAttribute("data-sse-target");
    if (!url || !targetSelector) return;

    let target: Element | null = null;
    try {
      target = document.querySelector(targetSelector);
    } catch {
      return;
    }
    if (!target) return;

    let source: EventSource;
    try {
      source = new EventSource(url);
    } catch {
      return;
    }
    container.setAttribute(_SSE_ACTIVE_ATTR, "1");

    source.onmessage = (msg) => {
      target!.innerHTML = String(msg.data ?? "");
    };
    source.onerror = () => {
      // No reconnection storm — close on first failure and
      // remove the marker so a follow-up rescan could re-wire
      // if the DOM is reset.
      try { source.close(); } catch { /* noop */ }
      container.removeAttribute(_SSE_ACTIVE_ATTR);
    };
  });
}


// Run SSE wiring on every module evaluation when the DOM is
// already parsed. ``_wireSseContainers`` is idempotent per
// element (``data-sse-active`` marker), so repeat scans are
// safe and let later-added containers (or per-test re-imports)
// pick up subscriptions. The DOMContentLoaded one-shot binding
// for the loading-state case lives inside
// ``_bindDelegatedListeners`` to keep it idempotent too.
if (document.readyState !== "loading") {
  _wireSseContainers();
}
