# A21-R — Surface Diagnostics & Operator Console Hooks

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A21-R adds an **operator-visible diagnostics surface** to the
v0.2 Web Surface, layered on top of A19-R (progressive
enhancement) and A20-R (form semantics).

It exposes:

- A server-rendered HTML fragment at `GET /__diagnostics`
  describing the request, the matched view, and the
  form-validation state.
- A client `data-diagnostic-toggle` attribute that fetches the
  fragment and swaps it inline into a target element, using
  the same content-type-branching path A20-R established.

Everything is additive. No SPA touch, no hydration, no new
template engine, no new client framework, no new view
registration.

## Philosophy

- **Server HTML is the source of truth.** The fragment is
  rendered server-side via the existing template engine and
  the cached template loader. The client never owns the
  diagnostic state.
- **Operator surfaces are server-level interceptors.** Just
  like `/health` and `/ready`, `/__diagnostics` is matched in
  the Node HTTP request handler BEFORE `routeWebSurface`. A
  broken view registry can't take diagnostics down with it.
- **`__`-prefix is the operator namespace.** Double-underscore
  paths are reserved for system / operator surfaces. Future
  cards can add `/__metrics`, `/__config`, etc. without
  colliding with view names.
- **Progressive enhancement respects the no-JS baseline.** With
  JS off, an operator can navigate directly to
  `/__diagnostics` and read the fragment as a standalone page.
  With JS on, a button anywhere in the surface can swap the
  fragment inline with no reload.
- **Read-only by design.** The route is GET-only and has no
  side effects (no log writes, no cache eviction, no registry
  mutations). The client toggle is a fetch, not a submit —
  there's nothing to "fall back" to.

## File map

| Path | Role |
|---|---|
| `web/templates/v0.2/diagnosticFragment.html` | Server-rendered `<div class="diagnostic-panel">` with `<pre data-json>` slot. |
| `web/src/surface/diagnostics/types.ts` | `DiagnosticEntry`, `DiagnosticPayload`. |
| `web/src/surface/diagnostics/collect.ts` | `collectDiagnostics(request)` — walks request → entries. |
| `web/src/surface/diagnostics/index.ts` | Barrel: re-exports collector + types. |
| `web/src/server/routes/diagnostics.ts` | `handleDiagnostics(request)` + `DIAGNOSTICS_PATH` constant + `escapeHtml` helper. |
| `web/src/server/requestHandler.ts` | Intercepts `DIAGNOSTICS_PATH` before the surface router. |
| `web/src/client/enhance.ts` | Adds delegated click handler for `data-diagnostic-toggle`. |

## Server-side API

### `collectDiagnostics(request)`

```ts
import { collectDiagnostics } from "../diagnostics";

const payload = await collectDiagnostics(req);
// → {
//     entries: [
//       { key: "request.method",  value: "GET",  severity: "info" },
//       { key: "request.path",    value: "/...", severity: "info" },
//       { key: "request.headers", value: {...},  severity: "info" },
//       { key: "route.view",      value: "home", severity: "info" },
//       { key: "route.mode",      value: "html", severity: "info" },
//       { key: "server.timing_ms",  value: null, severity: "info" },
//       { key: "form.error_count", value: 0,    severity: "info" },
//       { key: "surface.render_ms", value: null, severity: "info" },
//     ],
//     timestamp: "2026-05-23T18:47:15.234Z",
//   }
```

Sources:
1. **Request envelope** — method, path, headers (always
   present).
2. **Route metadata** — `resolveView(request)` is total
   (never throws), so the matched view name + mode are always
   recorded.
3. **Server timing** — placeholder (`null`); ready for a
   future timing module to populate without a payload-shape
   change.
4. **Form error count** — defers to A20-R's
   `collectFormErrors`. Non-form requests pass through with
   zero errors via `EMPTY_FORM_ERRORS`. Severity is `info`
   when zero, `warn` otherwise.
5. **Surface render timing** — placeholder (`null`); same
   shape as server.timing_ms.

Determinism: everything except `timestamp` is a pure function
of the request + view-registry state. The timestamp is
generated once at the bottom of the function so the rest of
the entries are clock-free.

### `handleDiagnostics(request)`

```ts
import { handleDiagnostics } from "../server/routes/diagnostics";

const response = await handleDiagnostics(req);
// → {
//     status: 200,
//     headers: { "content-type": "text/html; charset=utf-8" },
//     body: '<div class="diagnostic-panel" data-diagnostic-fragment>\n  <pre data-json>{...}</pre>\n</div>',
//   }
```

- JSON payload is pretty-printed (2-space indent) so the
  operator-facing `<pre>` is readable.
- JSON content is HTML-escaped at the boundary (defence-in-
  depth, since headers can carry user-influenced strings).
- The route is wired into `requestHandler.ts` as an
  interceptor matched against `DIAGNOSTICS_PATH` BEFORE
  `routeWebSurface` is called.

## Client-side behaviour

### `data-diagnostic-toggle`

```html
<button data-diagnostic-toggle
        data-diagnostic-target="#diag-panel">
  Show diagnostics
</button>
<div id="diag-panel"></div>
```

On click:

1. The delegated click handler walks `closest("[data-diagnostic-toggle]")`.
2. Resolves the target via `data-diagnostic-target`'s CSS
   selector.
3. `fetch("/__diagnostics", { credentials: "same-origin" })`.
4. **HTML response** (case-insensitive, charset-tolerant) →
   `target.innerHTML = <response body>`.
5. **Non-HTML response** OR **network failure** → silent
   no-op. There's no native fallback because the diagnostics
   route is read-only — there's no form submit to defer to.

The handler is bound exactly once per document lifetime via
the existing `Symbol.for("clarityos.v0_2.enhance.bound")`
guard from A19-R, so module re-evaluation (hot reload, vitest
`vi.resetModules()`) does not stack listeners.

### Content-type branching

Mirrors the A20-R form path:

| Response | Behaviour |
|---|---|
| `text/html` (any status) | Replace target |
| `text/html; charset=utf-8` | Replace target (charset suffix tolerated) |
| `TEXT/HTML` | Replace target (case-insensitive) |
| `application/json` | Silent no-op |
| `text/plain` | Silent no-op |
| Missing content-type | Silent no-op |
| Network failure | Silent no-op |

### Defensive paths

| Condition | Behaviour |
|---|---|
| Missing `data-diagnostic-target` | No fetch, no-op |
| Target selector matches nothing | No fetch, no-op |
| Invalid CSS selector | No fetch, no-op (no throw) |
| Plain click on non-trigger element | No-op (no fetch) |

## Integration pattern

A typical operator dropdown anywhere in the surface:

```html
<details>
  <summary>
    <button data-diagnostic-toggle
            data-diagnostic-target="#operator-console">
      Operator
    </button>
  </summary>
  <div id="operator-console" class="operator-console">
    <!-- diagnosticFragment swaps in here on click -->
  </div>
</details>
```

The server's diagnosticFragment.html renders into the empty
`<div>`. Subsequent clicks re-fetch (the route is cheap +
deterministic), so the panel always reflects the latest
request state.

## What's NOT here

- **No POST.** The route is GET-only. Future cards can add
  `/__diagnostics/clear` or `/__diagnostics/sample` if
  needed.
- **No timing.** `server.timing_ms` and `surface.render_ms`
  are placeholders. A future card can wire a timing module
  into the request handler / render pipeline without
  changing the payload shape.
- **No auth.** The route is open. If a future deployment
  needs operator-only access, layer an auth interceptor
  BEFORE `DIAGNOSTICS_PATH` in `requestHandler.ts` (mirrors
  the health bypass position).
- **No streaming.** The fragment is rendered atomically.
  A future card could add SSE-style live updates by reusing
  the A18 stream primitives.
- **No SPA involvement.** The SPA at `web/src/main.tsx` is
  untouched. A21-R is exclusively a Track A / Track C
  concern.

## Tests

Server-side: 21 tests in `web/src/surface/__tests__/diagnostics.test.ts`.

- `DIAGNOSTICS_PATH` constant literal value.
- `collectDiagnostics`: payload shape, ISO-8601 timestamp,
  request envelope (method/path/headers), route metadata
  (`view` + `mode`, including `?mode=json`), form error
  count (zero/info vs. nonzero/warn), timing placeholders
  null, severity enum closed, request not mutated,
  deterministic entry order.
- `escapeHtml`: five HTML entities escaped, `&` first
  (prevents double-encoding), empty string unchanged.
- `handleDiagnostics`: 200 + text/html response, body wraps
  the diagnostic-panel + `<pre data-json>` structure, JSON
  payload entries + timestamp visible, HTML-escape blocks raw
  `<script>`, body parses back to the same payload shape,
  fresh timestamp per call.

Client-side: 14 tests in `web/src/client/__tests__/diagnosticEnhance.test.ts`.

- HTML response (200 + charset suffix) → target replaced.
- Nested element inside trigger still fires.
- Non-HTML response (JSON / plain / missing content-type) →
  silent no-op.
- Network failure → silent no-op.
- Missing target attribute → no fetch.
- Missing target element → no fetch.
- Invalid CSS selector → no fetch, no throw.
- Idempotent listener binding (re-import does not double-
  fire).
- `text/html; charset=utf-8` detected.
- `TEXT/HTML; CHARSET=UTF-8` detected (case-insensitive).
- A19-R toggle path still works alongside the diagnostic
  delegate.
- Plain clicks on non-trigger elements remain no-ops.
