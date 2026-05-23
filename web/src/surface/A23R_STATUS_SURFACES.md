# A23-R — Unified Status Surfaces (Success, Warning, Failure)

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A23-R adds a **unified server-authored status-fragment
surface** to the v0.2 Web Surface — three closed kinds
(success / warning / failure), one renderer, one route, one
enhancement-layer hook.

The same fragment shape powers the visible UX for:

- form submissions (A20-R) — "Saved." / "2 errors found."
- streaming completions (A22-R) — "Task complete." / "Aborted."
- diagnostic actions (A21-R) — "Refreshed." / "Stale snapshot."
- long-running tasks of any flavour
- operator-visible state transitions

Everything is additive on top of A19-R/A20-R/A21-R/A22-R. No
SPA touch, no hydration, no new template engine.

## Philosophy

- **Server HTML is the source of truth.** Status fragments
  are rendered server-side by the existing template engine;
  the client never invents structure or copy.
- **One shape, three kinds.** The three templates differ only
  in chrome (label + CSS modifier class); the dynamic slot
  (`{{ message }}`) is identical. Callers don't have to
  remember per-kind authoring conventions.
- **Operator surfaces are server-level interceptors.**
  `/__status` joins `/__diagnostics` (A21-R) and `/__stream`
  (A22-R) as a `__`-prefixed route matched in the request
  handler BEFORE `routeWebSurface`. A broken view registry
  can't take status surfaces down with it.
- **Always HTML, never JSON.** Per the A23-R card, the route
  returns `text/html` for every code path — including
  validation failures, which render as a `failure` surface
  with a diagnostic message. The enhancement layer's
  content-type branch (mirrors A20-R) replaces the target
  for any HTML response regardless of HTTP status.
- **Closed-enum kinds.** `StatusKind` is `success | warning |
  failure` and nothing else. The renderer's switch is
  exhaustive (`never` check on the default branch), so
  adding a fourth kind is a compile-time edit.
- **Defence-in-depth escaping.** The renderer HTML-escapes
  the message at the template boundary before reaching the
  engine. The engine does NOT escape (per A3 conventions);
  every renderer escapes at its own boundary.

## File map

| Path | Role |
|---|---|
| `web/templates/v0.2/statusSuccess.html` | `<div class="status-surface status-surface--success">` + `<h2>Success</h2>` + `<p data-status-message>` slot. |
| `web/templates/v0.2/statusWarning.html` | Same structure, warning chrome. |
| `web/templates/v0.2/statusFailure.html` | Same structure, failure chrome. |
| `web/src/surface/status/types.ts` | `StatusKind`, `StatusPayload`. |
| `web/src/surface/status/render.ts` | `renderStatusSurface(payload)`, `STATUS_TEMPLATE_NAMES`, `escapeHtml`. |
| `web/src/surface/status/index.ts` | Barrel: re-exports renderer + types. |
| `web/src/server/routes/status.ts` | `STATUS_PATH`, `handleStatus(request)`, `_coercePayload`. |
| `web/src/server/requestHandler.ts` | Intercepts `STATUS_PATH` before the surface router. |
| `web/src/client/enhance.ts` | Adds a second submit branch for `data-enhance="status"` forms. |

## Server-side API

### `renderStatusSurface(payload)`

```ts
import { renderStatusSurface } from "../status";

const html = await renderStatusSurface({
  kind:    "success",
  message: "Saved.",
});
// → '<div class="status-surface status-surface--success"
//          data-status-surface="success">
//      <h2>Success</h2>
//      <p data-status-message>Saved.</p>
//    </div>'
```

- Template selection is via the closed `STATUS_TEMPLATE_NAMES`
  map (kind → template name).
- Messages are HTML-escaped at the boundary; raw `<`, `"`,
  `&` etc. are converted to entities.
- Empty messages still produce a valid (but empty) `<p>`.
- Output is deterministic: same payload + same template cache
  → byte-identical HTML.

### `handleStatus(request)`

```ts
const response = await handleStatus(req);
// → {
//     status: 200,
//     headers: { "content-type": "text/html; charset=utf-8" },
//     body: '<div class="status-surface ...">...</div>',
//   }
```

Method gate: **POST only**. Any other method returns a 400 +
failure surface ("method_not_allowed").

JSON parse gate: missing body, non-string body, or
unparseable JSON all return 400 + failure surface.

Payload validation (`_coercePayload`): missing/wrong-typed
`kind`, missing/wrong-typed `message`, or unknown `kind`
return 400 + failure surface.

**All error responses are still HTML.** Never JSON. The
enhancement layer's content-type branch handles them
identically to a 200 success — the failure surface IS the
operator-facing payload.

## Client-side behaviour

### `data-enhance="status"`

```html
<form data-enhance="status"
      data-status-target="#status-panel">
  <input name="kind"    value="success">
  <input name="message" value="Saved.">
  <button type="submit">Notify</button>
</form>
<div id="status-panel"></div>
```

On submit:

1. The delegated submit handler matches `data-enhance="status"`
   (distinct from A19-R/A20-R's `data-enhance="fetch"`).
2. Resolves the target via `data-status-target`'s CSS
   selector.
3. Serialises every form field into a `Record<string, string>`
   object (duplicate keys collapse to the last value).
4. `POST /__status` with `application/json` body.
5. **HTML response** → `target.innerHTML = <response body>`.
6. **Non-HTML response** / **network failure** → strip
   `data-enhance` and re-submit natively (same defensive
   pattern as A19-R/A20-R).

### Behaviour matrix

| Condition | Behaviour |
|---|---|
| `data-enhance="status"` form submit | POST `/__status`, replace target |
| HTML response (any status) | Replace target |
| Non-HTML response | Strip `data-enhance`, native submit |
| Network failure | Strip `data-enhance`, native submit |
| File input present | Native submit (FormData yields non-string) |
| Missing `data-status-target` | No fetch, no-op |
| Target element missing | No fetch, no-op |
| Invalid CSS selector | No fetch, no-op (no throw) |
| Module re-evaluation | Bound exactly once (A19-R symbol guard) |

### Distinct from A19-R `data-enhance="fetch"`

| | `data-enhance="fetch"` (A19-R/A20-R) | `data-enhance="status"` (A23-R) |
|---|---|---|
| Target attr | `data-fragment-target` | `data-status-target` |
| URL | Form's `action` (variable) | Fixed `/__status` |
| Body type | `application/x-www-form-urlencoded` | `application/json` |
| Body shape | Per-form fields | `{kind, message}` |

Both branches share the same content-type fallback policy,
the same symbol guard for idempotency, and the same
`_fallBackToNativeSubmit` helper. They differ only in URL +
encoding.

## Integration pattern

A typical "notify on completion" hook for a form (A20-R) or a
streaming task (A22-R) panel:

```html
<form data-enhance="status"
      data-status-target="#run-status">
  <input type="hidden" name="kind"    value="success">
  <input type="hidden" name="message" value="Build complete.">
  <button type="submit">Acknowledge</button>
</form>
<div id="run-status"></div>
```

Operator clicks → POST → server renders the success
fragment → swapped into `#run-status`. No reload, no SPA,
no JSON envelope to parse.

## What's NOT here

- **No automatic emission.** A23-R is a render + transport
  layer; it does not auto-fire on form submit completion or
  stream done events. Higher-level cards can chain them
  (e.g., A22-R's `done` event triggers a `data-enhance="status"`
  POST).
- **No success/failure-specific routes.** One route, one
  payload shape. The kind is in the body, not the path.
- **No auth.** Same posture as `/__diagnostics` and
  `/__stream`. Layer an interceptor BEFORE `STATUS_PATH` in
  `requestHandler.ts` for operator-only deployments.
- **No client-side template rendering.** The client never
  decides what a "success" looks like; the server's
  templates own that.
- **No PRG (post-redirect-get).** The client never
  navigates; it just replaces the target's innerHTML.
- **No multi-message surfaces.** One kind + one message per
  fragment. Composite outcomes should render multiple
  fragments side-by-side.
- **No SPA involvement.** The SPA at `web/src/main.tsx` is
  untouched. A23-R is exclusively a Track A / Track C
  concern.

## Tests

Server-side: 34 tests in `web/src/surface/__tests__/statusRender.test.ts`.

- Constants: `STATUS_PATH`, `STATUS_TEMPLATE_NAMES` shape +
  coverage.
- `escapeHtml`: five HTML entities, `&` first, empty string
  passthrough.
- `renderStatusSurface`: per-kind chrome + label + slot
  injection; XSS escape in message; empty message produces
  empty `<p>`; determinism across 5 renders; non-mutation.
- `_coercePayload`: well-formed accepted, each valid kind
  accepted, missing/wrong-typed/unknown kind rejected, null
  / non-object rejected, empty message accepted.
- `handleStatus`: 200 + text/html on success per kind; 400 +
  failure surface for non-POST / non-string body / bad JSON
  / missing fields / unknown kind; every error path returns
  text/html (never JSON); determinism + non-mutation.

Client-side: 17 tests in `web/src/client/__tests__/statusEnhance.test.ts`.

- POST `/__status` with JSON body shape `{kind, message}`.
- 200 + text/html replaces target.
- 400 + text/html (failure surface) still replaces target.
- `text/html; charset=utf-8` detected (charset suffix).
- Non-HTML responses (JSON / plain / no content-type) →
  native submit fallback.
- Network failure → native submit fallback.
- Missing `data-status-target` → no fetch.
- Missing target element → no fetch.
- Invalid CSS selector → silent no-op.
- Non-string FormData entry → native submit fallback.
- Module re-import does not double-fire.
- A19-R `data-enhance="fetch"` path still uses
  form-urlencoded POST to form.action.
- Forms without `data-enhance` are not intercepted.
- A21-R `data-diagnostic-toggle` path unaffected.
