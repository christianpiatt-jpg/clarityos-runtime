# A19-R — Progressive Enhancement for the v0.2 Surface

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A19-R adds **client-side progressive enhancement** to the
server-rendered v0.2 Web Surface — toggles, fetch-and-replace
forms, and Server-Sent Events subscription — **without** React,
hydration, a virtual DOM, a client router, or any new server
endpoint.

Everything is opt-in via documented `data-*` attributes on the
HTML the server already emits.

## What this is **not**

- Not hydration. There is no React tree to attach to the
  server-rendered HTML, and A19-R does not invent one.
- Not a SPA framework. No router, no component model.
- Not a JSON-first rendering layer. The server's HTML is the
  authoritative tree; this script enhances behaviour, never
  replaces the page.
- Not a build step in the traditional sense. The TS source
  compiles to one tiny JS asset that ships through the existing
  fingerprinted-asset pipeline.

## File map

| Path | Role |
|---|---|
| `web/src/client/enhance.ts` | **Source of truth.** All enhancement behaviour lives here. Pure side-effect module. No exports. |
| `web/scripts/build-client.mjs` | Generator. esbuild-transforms `enhance.ts` → `app.js`. Deterministic; byte-stable banner. |
| `web/assets/v0.2/app.js` | **Generated artifact** (committed). Mirrors the manifest.json pattern. The asset router serves it. |
| `web/assets/v0.2/manifest.json` | Carries the fingerprint of the new `app.js`. Regenerated via `npm run assets:gen`. |
| `web/templates/v0.2/layouts/standard.html` | **Unchanged.** Already references the fingerprinted asset via `<script src="/web-surface/v0.2/assets/{{ app_js }}" defer>` from card A9/A10. |
| `web/src/client/__tests__/enhance.test.ts` | Vitest + jsdom tests. Imports the TS source directly. |

## Regeneration

When you edit `enhance.ts`, run two scripts in order:

```bash
cd web
npm run client:gen     # rebuild app.js from enhance.ts
npm run assets:gen     # refresh manifest.json with the new fingerprint
```

CI has two drift gates:

```bash
npm run client:check   # regen + git diff --exit-code on app.js
npm run assets:check   # regen + git diff --exit-code on manifest.json
```

A merge that ships an out-of-date asset will fail both.

## The three `data-*` contracts

### 1. Toggles / expanders

```html
<button data-toggle-target="#some-panel">Toggle</button>
<div id="some-panel" class="panel">...</div>
```

On click, the script toggles the `is-open` class on the
selector target. CSS owns the visual state — the script never
mutates the panel's contents or structure.

- Triggers can be nested elements: a `<span>` inside a
  `<button data-toggle-target=...>` works because the delegated
  click handler walks `event.target.closest("[data-toggle-target]")`.
- Bad selectors are silently no-ops.
- Missing targets are silently no-ops.

### 2. Fetch-and-replace forms

```html
<form method="POST"
      action="/web-surface/v0.2/form_demo"
      data-enhance="fetch"
      data-fragment-target="#result">
  <input name="name" value="">
  <button type="submit">Submit</button>
</form>
<div id="result"></div>
```

On submit:
1. The script `event.preventDefault()`s.
2. Form data is serialised as
   `application/x-www-form-urlencoded` (matches the v0.2
   classifier's form branch).
3. POSTed via `fetch` to `form.action`.
4. The response body replaces `data-fragment-target`'s
   `innerHTML`.

If anything fails — network error, non-2xx response, file inputs
present (multipart not supported by this path), or the target
selector misses — the script:
1. Removes its own `data-enhance` attribute.
2. Re-submits the form natively.

The user never sees a broken interaction. Worst case is a full
page navigation, which is the no-JS default anyway.

### 3. Server-Sent Events subscription

```html
<div data-sse-url="/web-surface/v0.2/stream_sse_demo"
     data-sse-target="#sse-output"></div>
<pre id="sse-output"></pre>
```

> Note: A18's SSE handler ships `text/event-stream` ONLY when
> the request carries `x-sse: 1`. To subscribe from this
> attribute, you'd need either a server that always streams at
> that URL or a small URL-rewrite that adds the header. v0.2.0
> demos this primitive without wiring it to the A18 endpoint.

On DOM ready (or immediately if already past `loading`):
1. Opens an `EventSource` to the URL.
2. Each `message` event replaces the target's `innerHTML` with
   the message data.
3. On `error`, closes the source — no reconnection storm.

A `data-sse-active="1"` marker is set on the container after
subscription to prevent double-wiring if the script re-runs.

## Philosophy

**The server's HTML is the source of truth.** A19-R is "what
you can do to a server-rendered page without breaking its
no-JS baseline." Every behaviour falls back gracefully:

- Toggles: with JS off, the trigger and target are both
  present in the DOM; the page works without the show/hide
  affordance.
- Fetch-and-replace: with JS off, the form submits normally
  and the page reloads with the server's response.
- SSE: with JS off (or `EventSource` missing), the container
  simply doesn't subscribe. The rest of the page is unaffected.

**The script binds listeners exactly once per document
lifetime.** A `Symbol.for("clarityos.v0_2.enhance.bound")`
marker on `document` makes the binding idempotent across
re-evaluations (hot reload in dev, `vi.resetModules()` in
tests). The per-element `data-sse-active` marker provides the
same idempotency for SSE wiring.

**Server rendering semantics are unchanged.** No template was
modified for A19-R. The layout's `<script>` tag was already
there (added in A9 alongside the asset-pipeline cards). The
only change to the asset pipeline is that `app.js` is now a
generated 3.5 KB enhancement module instead of the 1-line stub.

## Why no `/client/enhance.js` route

The A19-R card's example layout used
`<script type="module" src="/client/enhance.js"></script>` — a
hypothetical new URL prefix. We didn't create that route
because the **existing** asset pipeline already serves what we
need:

- Cache-safe URL (fingerprinted, A9/A10).
- Drift-gated (CI fails on stale manifest, A10).
- Path-traversal-protected (A8).
- Content-type-correct (A8: `.js` → `application/javascript`).

Reusing the existing pipeline means **zero new code in the
server adapter** (Track C) and zero new layout entries. The
TS-source-of-truth contract is preserved; the runtime URL just
flows through `{{ app_js }}` exactly as designed.

## Testing

```bash
cd web
npx vitest run src/client/__tests__/enhance.test.ts
```

Coverage:

- `has-js` bootstrap (applied once, no duplicates on re-import).
- Toggle delegate (happy path, nested triggers, bad selectors,
  missing targets, empty attribute values, plain clicks no-op).
- Fetch-and-replace (happy path, non-2xx fall-back, network
  fall-back, missing target attribute, form without
  data-enhance, blank action defaults to current URL).
- SSE wiring (open, message → innerHTML, error → close, missing
  attributes, double-wiring guard, missing-EventSource graceful).
- Defensiveness (empty DOM, no data-* hooks, no named exports).

24 tests, all green.
