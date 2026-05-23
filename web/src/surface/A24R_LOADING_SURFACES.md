# A24-R — Unified Loading Surfaces & Deferred-Work Indicators

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A24-R adds a **unified server-authored loading-fragment
surface** to the v0.2 Web Surface — one template, one
optional message, one route, one enhancement-layer click
hook.

This is the operator's visual language for deferred work:

- pending form submissions (A20-R)
- pending status updates (A23-R)
- pending streaming tasks (A22-R)
- pending diagnostics (A21-R)
- any other deferred server work

This card completes the v0.2 surface's **core interaction
primitives**: enhancement layer (A19-R) + form semantics
(A20-R) + diagnostics (A21-R) + streaming (A22-R) + status
surfaces (A23-R) + loading surfaces (A24-R).

Everything is additive on top of A19-R through A23-R. No SPA
touch, no hydration, no new template engine.

## Philosophy

- **Server HTML is the source of truth.** The loading
  fragment is rendered server-side by the existing template
  engine; the client never invents structure or copy.
- **One shape, one optional slot.** Unlike A23-R (three
  kinds), there's no per-kind branching — a loading
  indicator is a loading indicator. The single dynamic slot
  (`{{ message }}`) defaults to ``"Loading…"`` when absent,
  so the common case requires no payload.
- **Lenient by design.** The route never fails. Missing body,
  unparseable JSON, JSON without `message`, non-string
  `message`, even the wrong HTTP method — all degrade to a
  200 + default-message fragment. Operators showing a
  spinner shouldn't have to worry about request shape.
- **Operator surfaces are server-level interceptors.**
  `/__loading` joins `/__diagnostics` (A21-R), `/__stream`
  (A22-R), and `/__status` (A23-R) as a `__`-prefixed route
  matched in the request handler BEFORE `routeWebSurface`.
  A broken view registry can't take loading indicators
  down with it.
- **Always HTML, never JSON.** Same posture as A23-R. The
  enhancement layer's content-type branch replaces the
  target for any HTML response regardless of HTTP status.
- **Defence-in-depth escaping.** The renderer HTML-escapes
  the message at the template boundary. The engine does
  NOT escape (per A3 conventions); every renderer escapes
  at its own boundary.

## File map

| Path | Role |
|---|---|
| `web/templates/v0.2/loadingFragment.html` | `<div class="loading-surface">` + `<div class="spinner">` + `<p data-loading-message>` slot. |
| `web/src/surface/loading/types.ts` | `LoadingPayload` (optional message). |
| `web/src/surface/loading/render.ts` | `renderLoadingSurface(payload?)`, `DEFAULT_LOADING_MESSAGE`, `LOADING_TEMPLATE_NAME`, `escapeHtml`. |
| `web/src/surface/loading/index.ts` | Barrel: re-exports renderer + types. |
| `web/src/server/routes/loading.ts` | `LOADING_PATH`, `handleLoading(request)`, `_coercePayload`. |
| `web/src/server/requestHandler.ts` | Intercepts `LOADING_PATH` before the surface router. |
| `web/src/client/enhance.ts` | Adds delegated click handler for `data-loading-trigger`. |

## Server-side API

### `renderLoadingSurface(payload?)`

```ts
import { renderLoadingSurface } from "../loading";

// Default copy — "Loading…"
await renderLoadingSurface();

// Custom copy
await renderLoadingSurface({ message: "Crunching numbers…" });

// Empty / missing message → default copy (defensive)
await renderLoadingSurface({});
await renderLoadingSurface({ message: "" });
```

Output (default-message variant):

```html
<div class="loading-surface" data-loading-surface>
  <div class="spinner"></div>
  <p data-loading-message>Loading…</p>
</div>
```

- Messages are HTML-escaped at the boundary; raw `<`, `"`,
  `&` etc. are converted to entities.
- The empty-string case falls through to the default so an
  empty `message` field on the wire still renders the
  spinner-friendly "Loading…" text.
- Output is deterministic: same payload + same template
  cache → byte-identical HTML.

### `handleLoading(request)`

```ts
const response = await handleLoading(req);
// → {
//     status: 200,
//     headers: { "content-type": "text/html; charset=utf-8" },
//     body: '<div class="loading-surface">...</div>',
//   }
```

**Lenient by design** — always 200 + HTML:

| Request | Behaviour |
|---|---|
| `POST` + `{"message": "..."}` | Custom message |
| `POST` + `{}` | Default message |
| `POST` + no body | Default message |
| `POST` + unparseable JSON | Default message |
| `POST` + JSON without `message` | Default message |
| `POST` + JSON with non-string `message` | Default message |
| `GET` / any other method | Default message |

The route never throws past its caller; never returns a
non-HTML body; never returns non-200.

## Client-side behaviour

### `data-loading-trigger`

```html
<button data-loading-trigger
        data-loading-target="#loading-panel"
        data-loading-message="Saving…">
  Save
</button>
<div id="loading-panel"></div>
```

On click:

1. The delegated click handler walks `closest("[data-loading-trigger]")`.
2. Resolves the target via `data-loading-target`'s CSS
   selector.
3. Reads the optional `data-loading-message` attribute.
4. POST `/__loading` with `application/json` body:
   - `{message: "<attr value>"}` when the attribute is
     present and non-empty.
   - `{}` when the attribute is missing or empty.
5. **HTML response** → `target.innerHTML = <response body>`.
6. **Non-HTML response** / **network failure** → silent
   no-op. No native fallback because the trigger is a click,
   not a submit — there's no form submission to defer to.

### Behaviour matrix

| Condition | Behaviour |
|---|---|
| Click on `data-loading-trigger` | POST `/__loading`, replace target |
| HTML response (any status) | Replace target |
| Non-HTML response | Silent no-op |
| Network failure | Silent no-op |
| Missing `data-loading-target` | No fetch, no-op |
| Target element missing | No fetch, no-op |
| Invalid CSS selector | No fetch, no-op (no throw) |
| Missing `data-loading-message` | `{}` body |
| Empty `data-loading-message` | `{}` body |
| Module re-evaluation | Bound exactly once (A19-R symbol guard) |

### Distinct from prior cards

| | A21-R diagnostic | A23-R status | A24-R loading |
|---|---|---|---|
| Trigger event | click | submit | click |
| Trigger attr | `data-diagnostic-toggle` | `data-enhance="status"` | `data-loading-trigger` |
| Target attr | `data-diagnostic-target` | `data-status-target` | `data-loading-target` |
| HTTP method | GET | POST | POST |
| Body | none | `{kind, message}` | `{}` or `{message}` |
| Fallback | silent no-op | native submit | silent no-op |

All four share the same content-type fallback policy and the
same symbol guard for idempotency.

## Integration patterns

### Pre-submit spinner for a long-running form

```html
<form data-enhance="status" data-status-target="#status-panel">
  <input type="hidden" name="kind"    value="success">
  <input type="hidden" name="message" value="Done.">
  <button data-loading-trigger
          data-loading-target="#status-panel"
          data-loading-message="Saving…"
          type="submit">
    Save
  </button>
</form>
<div id="status-panel"></div>
```

Click fires both handlers (in registration order):
1. **Loading trigger** (click) → POST `/__loading` → swaps
   "Saving…" spinner into `#status-panel`.
2. **Status submit** (submit) → POST `/__status` → swaps
   the success surface in, replacing the spinner.

The user sees: button click → spinner → success card.

### Spinner before a streaming task

```html
<div id="run-panel">{{> streamFragment }}</div>

<button data-loading-trigger
        data-loading-target="#run-panel">
  Prepare
</button>

<button data-stream-start
        data-stream-target="#run-panel">
  Start
</button>
```

Operator clicks Prepare → spinner appears. Operator clicks
Start → SSE events progressively populate the panel.

### Standalone "long fetch" indicator

```html
<button data-loading-trigger
        data-loading-target="#out"
        data-loading-message="Fetching data…">
  Load
</button>
<div id="out"></div>

<script>
  document.getElementById("out")
    .addEventListener("DOMNodeInserted", () => {
      // Operator-defined work, e.g. start a fetch and
      // replace the spinner with the result.
    });
</script>
```

## What's NOT here

- **No automatic spinner-on-fetch.** A24-R is a render +
  transport layer; it does not auto-fire before
  `data-enhance="fetch"` submissions. Higher-level cards or
  operator scripts can chain them.
- **No spinner removal on completion.** The fragment is
  static once swapped in. Subsequent fragments (status,
  stream, etc.) replace it via their own `data-...-target`
  attributes.
- **No timeout.** The spinner sits forever until something
  else replaces it. Future cards can layer a "stale after
  N seconds" indicator on top.
- **No auth.** Same posture as `/__diagnostics`, `/__stream`,
  `/__status`. Layer an interceptor BEFORE `LOADING_PATH` in
  `requestHandler.ts` for operator-only deployments.
- **No per-trigger active guard.** Multiple clicks just
  re-POST and re-swap. The route is cheap + deterministic,
  so this is fine UX.
- **No animation.** The `class="spinner"` element is empty;
  CSS owns the visual rotation. Future cards can ship a
  default stylesheet.
- **No SPA involvement.** The SPA at `web/src/main.tsx` is
  untouched. A24-R is exclusively a Track A / Track C
  concern.

## Tests

Server-side: 36 tests in `web/src/surface/__tests__/loadingRender.test.ts`.

- Constants: `DEFAULT_LOADING_MESSAGE`, `LOADING_TEMPLATE_NAME`,
  `LOADING_PATH`.
- `escapeHtml`: five entities, `&` first, empty string.
- `renderLoadingSurface`: default-message fallback for no
  payload / undefined / empty object / undefined message /
  empty-string message; custom message injection; XSS
  escape; static chrome (spinner div + wrapper +
  data-attr); determinism across 5 renders; non-mutation.
- `_coercePayload`: lenient parsing table — well-formed,
  empty object, non-string body, empty string body,
  unparseable JSON, non-object JSON, JSON without message,
  JSON with non-string message.
- `handleLoading`: 200 + text/html for all input shapes
  (valid body, no body, null body, unparseable JSON, JSON
  without message); non-POST methods also accepted
  (lenient); content-type always text/html; determinism
  + non-mutation; XSS escape on the wire.

Client-side: 18 tests in `web/src/client/__tests__/loadingEnhance.test.ts`.

- Click POSTs to `/__loading` with `application/json`.
- HTML response replaces target.
- Nested element inside trigger fires.
- `data-loading-message` attribute forwarded as
  `{message: "..."}`.
- Missing attribute → `{}` body.
- Empty attribute → `{}` body.
- Non-HTML responses (JSON / plain / no content-type) →
  silent no-op.
- Network failure → silent no-op.
- Missing `data-loading-target` → no fetch.
- Missing target element → no fetch.
- Invalid CSS selector → no fetch.
- Module re-import does not double-fire.
- A19-R toggle path unaffected.
- A21-R diagnostic toggle still posts to `/__diagnostics`.
- Loading trigger does not match diagnostic-toggle elements.
- Plain clicks on non-trigger elements remain no-ops.
