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
 *   4. Diagnostic toggle (Card A21-R).
 *      ``<button data-diagnostic-toggle data-diagnostic-target="#out">``
 *        → click fetches ``/__diagnostics`` and, if the response
 *          carries ``text/html``, replaces the target's
 *          ``innerHTML`` with the server-rendered fragment.
 *        → non-HTML responses and network failures are a silent
 *          no-op (no native fallback — the diagnostics route is
 *          read-only, so there is no "submit" to fall back to).
 *
 *   5. Streaming task (Card A22-R).
 *      ``<button data-stream-start data-stream-target="#panel">``
 *        with ``#panel`` containing ``[data-stream-log]`` and
 *        ``[data-stream-status]`` children.
 *        → click opens ``new EventSource("/__stream")``.
 *        → ``log`` events append a line to the ``<pre>``.
 *        → ``status`` events replace the ``<div>`` text.
 *        → ``done`` / ``error`` events close the source.
 *        → A per-trigger ``data-stream-active`` marker prevents
 *          opening a second connection while one is active;
 *          the marker is cleared on close so the user can
 *          re-run the task.
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

  // --- 4. Diagnostic toggle delegate (Card A21-R) ---
  //
  // Sits alongside the toggle / form delegates: a single
  // document-level click handler walks ``closest`` to find a
  // trigger carrying ``data-diagnostic-toggle``. The diagnostics
  // route is fixed at ``/__diagnostics`` (see
  // ``web/src/server/routes/diagnostics.ts``); the trigger only
  // needs to name the swap target via ``data-diagnostic-target``.
  //
  // Behaviour:
  //   * HTML response → replace target.innerHTML (mirrors the
  //     A20-R content-type-based form path).
  //   * Non-HTML response → silent no-op.
  //   * Network failure → silent no-op.
  //
  // There is no native fallback because ``/__diagnostics`` is
  // read-only — there's no form submission to defer to. With JS
  // off, the trigger element simply does nothing; the server's
  // base page is unaffected.
  document.addEventListener("click", (event) => {
    const node = event.target;
    if (!(node instanceof Element)) return;
    const trigger = node.closest("[data-diagnostic-toggle]");
    if (!(trigger instanceof Element)) return;

    const selector = trigger.getAttribute("data-diagnostic-target");
    if (!selector) return;

    let target: Element | null = null;
    try {
      target = document.querySelector(selector);
    } catch {
      // Bad selector — silently no-op (defensive).
      return;
    }
    if (!target) return;

    event.preventDefault();
    void _fetchDiagnosticFragment(target);
  });

  // --- 5. Streaming task delegate (Card A22-R) ---
  //
  // Sits alongside the toggle / form / diagnostic delegates:
  // a single document-level click handler walks ``closest`` to
  // find a trigger carrying ``data-stream-start``. The
  // streaming route is fixed at ``/__stream`` (see
  // ``web/src/server/routes/stream.ts``); the trigger only
  // needs to name the panel target via ``data-stream-target``.
  //
  // Per-trigger idempotency: once a session is active, the
  // trigger gets ``data-stream-active="1"``. Re-clicking is a
  // no-op until the session closes (cleared on ``done`` /
  // ``error``). This mirrors the SSE-container active marker
  // already used by ``_wireSseContainers``.
  document.addEventListener("click", (event) => {
    const node = event.target;
    if (!(node instanceof Element)) return;
    const trigger = node.closest("[data-stream-start]");
    if (!(trigger instanceof Element)) return;

    // Already running → silent no-op until ``done``/``error``
    // clears the marker.
    if (trigger.hasAttribute(_STREAM_ACTIVE_ATTR)) return;

    const selector = trigger.getAttribute("data-stream-target");
    if (!selector) return;

    let panel: Element | null = null;
    try {
      panel = document.querySelector(selector);
    } catch {
      return;  // bad selector
    }
    if (!panel) return;

    event.preventDefault();
    _startStreamSession(trigger, panel);
  });

  // --- 6. SSE wiring: schedule the FIRST scan ---
  // The post-load rescan (every module re-eval) is at the
  // bottom of this file; this branch handles the initial
  // DOMContentLoaded firing exactly once per document lifetime.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _wireSseContainers);
  }
}


// ---------------------------------------------------------------------------
// Card A22-R — streaming-task wiring helpers
// ---------------------------------------------------------------------------

/** URL of the server-level streaming route. Held as a module
 *  constant so the EventSource target matches the server's
 *  ``STREAM_PATH`` constant exactly. */
const _STREAM_URL = "/__stream";

/** Per-trigger marker preventing duplicate concurrent sessions.
 *  Cleared when the stream closes (done/error). */
const _STREAM_ACTIVE_ATTR = "data-stream-active";


/**
 * Open an ``EventSource`` to ``/__stream`` and route incoming
 * events into the panel's log + status children. Card A22-R.
 *
 * Defensive guarantees:
 *   * If ``EventSource`` is unavailable (jsdom, etc.) the
 *     function is a silent no-op.
 *   * If the constructor throws (malformed URL, CSP block) the
 *     active marker is never set so the trigger remains
 *     re-clickable.
 *   * ``log`` events that arrive with malformed JSON are
 *     silently dropped — partial corruption never disturbs the
 *     panel's existing content.
 */
function _startStreamSession(trigger: Element, panel: Element): void {
  if (typeof EventSource === "undefined") return;

  const logEl    = panel.querySelector("[data-stream-log]");
  const statusEl = panel.querySelector("[data-stream-status]");

  let source: EventSource;
  try {
    source = new EventSource(_STREAM_URL);
  } catch {
    return;
  }
  trigger.setAttribute(_STREAM_ACTIVE_ATTR, "1");

  const closeSession = (): void => {
    try { source.close(); } catch { /* noop */ }
    trigger.removeAttribute(_STREAM_ACTIVE_ATTR);
  };

  source.addEventListener("log", (msg: MessageEvent) => {
    if (!logEl) return;
    const message = _extractStreamMessage(msg.data);
    if (message === null) return;
    // Append (don't replace) — the log is a running transcript.
    logEl.textContent = (logEl.textContent ?? "") + message + "\n";
  });

  source.addEventListener("status", (msg: MessageEvent) => {
    if (!statusEl) return;
    const message = _extractStreamMessage(msg.data);
    if (message === null) return;
    // Replace (don't append) — the status reflects the current
    // phase, not the history of phases.
    statusEl.textContent = message;
  });

  source.addEventListener("done",  closeSession);
  source.addEventListener("error", closeSession);
}


/** Pull the ``message`` field out of an SSE ``data`` payload.
 *  Returns ``null`` for malformed JSON or for payloads where
 *  ``message`` isn't a string. Defensive: never throws. */
function _extractStreamMessage(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed !== null &&
      typeof parsed === "object" &&
      typeof (parsed as { message?: unknown }).message === "string"
    ) {
      return (parsed as { message: string }).message;
    }
  } catch {
    // Malformed JSON — silent drop.
  }
  return null;
}


/**
 * Fetch the diagnostic fragment and swap it into ``target``.
 * Card A21-R helper.
 *
 * Content-type branching mirrors the A20-R form path:
 *   * ``text/html`` (case-insensitive, charset-tolerant) →
 *     replace ``target.innerHTML``.
 *   * Anything else → silent no-op (no native fallback).
 *
 * Network failures are also silent — the catch block swallows
 * the throw without disturbing the page.
 */
async function _fetchDiagnosticFragment(target: Element): Promise<void> {
  try {
    const response = await fetch(_DIAGNOSTICS_URL, {
      method:      "GET",
      credentials: "same-origin",
    });
    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().includes("text/html")) {
      // Non-HTML response → silent no-op. Mirrors the A20-R
      // form path's content-type check; the diagnostics route
      // is read-only so there's nothing to fall back to.
      return;
    }
    const html = await response.text();
    target.innerHTML = html;
  } catch {
    // Network failure → silent no-op.
  }
}


/** URL of the server-level diagnostics interceptor. Held as a
 *  module constant so the fetch target matches the server's
 *  ``DIAGNOSTICS_PATH`` constant exactly. */
const _DIAGNOSTICS_URL = "/__diagnostics";


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
