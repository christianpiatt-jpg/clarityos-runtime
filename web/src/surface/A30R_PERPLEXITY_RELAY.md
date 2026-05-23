# A30-R — Perplexity Surface Relay (REAL/MOCK Upstream)

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A30-R is the first v0.2 surface card that **exposes the
existing Perplexity upstream module** through a server-
rendered fragment. The upstream itself landed in an earlier
card (`web/src/upstream/perplexity/`) and provides both MOCK
and REAL implementations. A30-R wires it into the v0.2
surface as a `__`-prefixed operator relay.

The card is the bridge between:

- local deterministic primitives (A19-R through A24-R) and
- cloud-backed inference (REAL mode against the live
  Perplexity API)

without changing who writes the code: Claude continues
implementing local repo code; Perplexity provides upstream
inference; cloud-side verification covers REAL-mode
behaviour that local tests can't safely exercise.

## Philosophy

- **Server HTML is the source of truth.** The relay route
  renders the upstream's response as an HTML fragment via
  the existing template engine. The client never inspects
  raw JSON.
- **MOCK by default, REAL by explicit env.** The upstream's
  default is MOCK; `PERPLEXITY_MODE=REAL` flips it. The
  v0.2 surface relay inherits this — local dev / vitest
  always exercises MOCK, while Cloud Run can deploy with
  REAL set in env + `PERPLEXITY_API_KEY` injected from
  Secret Manager.
- **One template, success and failure.** The fragment is
  uniform regardless of outcome. Upstream errors land in
  the same `<pre data-answer>` slot with `tokens: 0`. The
  operator-facing UX is consistent (A23-R-style invariant).
- **Operator surfaces are server-level interceptors.**
  `/__perplexity` joins `/__diagnostics` (A21-R),
  `/__stream` (A22-R), `/__status` (A23-R), and
  `/__loading` (A24-R) as a `__`-prefixed route matched
  BEFORE `routeWebSurface`. A broken view registry can't
  take inference down with it.
- **Always HTML, never JSON.** Same posture as A23-R and
  A24-R. Bad input, upstream failures, and successful
  responses all return `text/html`. The enhancement
  layer's content-type branch decides whether to swap or
  fall back.
- **Defence-in-depth escaping.** The upstream's `text`
  field is HTML-escaped at the renderer boundary before
  reaching the template engine. A REAL-mode response that
  happens to contain HTML-sensitive characters cannot
  break out of the `<pre>`.

## File map

| Path | Role |
|---|---|
| `web/templates/v0.2/perplexityFragment.html` | `<div class="perplexity-answer">` + `<pre data-answer>` slot + `<p data-perplexity-meta>` tokens line. |
| `web/src/upstream/perplexity/` | **Pre-existing.** Upstream module — `callPerplexity`, `callPerplexityMock`, `callPerplexityReal`, error classes, types. |
| `web/src/server/routes/perplexity.ts` | `PERPLEXITY_PATH`, `handlePerplexity(request)`, `_coerceQuery`, `escapeHtml`. |
| `web/src/server/requestHandler.ts` | Intercepts `PERPLEXITY_PATH` before the surface router. |
| `web/src/client/enhance.ts` | Adds two branches for `data-perplexity-query`: a click handler (non-form elements) and a submit handler (forms). |

## Server-side API

### `handlePerplexity(request)`

```ts
const response = await handlePerplexity(req);
// → {
//     status: 200,
//     headers: { "content-type": "text/html; charset=utf-8" },
//     body: '<div class="perplexity-answer">...</div>',
//   }
```

Request validation:

| Condition | Status | Body |
|---|---|---|
| `POST` + `{"query": "non-empty"}` | 200 | upstream answer |
| Non-POST method | 400 | failure fragment |
| Missing / non-string / empty body | 400 | failure fragment |
| Unparseable JSON | 400 | failure fragment |
| Missing / wrong-typed / empty `query` | 400 | failure fragment |
| Upstream throws (config / timeout / network / parse) | 502 | failure fragment |

**Every response is `text/html`.** The fragment is uniform:
the `<pre data-answer>` slot carries either the upstream's
answer text or the failure diagnostic; the meta line shows
`tokens: <n>` (0 for failures).

### Upstream delegation

```ts
import { callPerplexity } from "../../upstream/perplexity";

const { text, tokensUsed } = await callPerplexity({ query });
```

Mode is resolved at call time by the upstream itself:

| `PERPLEXITY_MODE` | Behaviour |
|---|---|
| unset / anything other than `REAL` | MOCK — deterministic, no network |
| `REAL` | REAL — one outbound HTTPS call (10s timeout); requires `PERPLEXITY_API_KEY` |

REAL-mode errors are mapped to typed classes
(`PerplexityConfigError`, `PerplexityTimeoutError`,
`PerplexityUpstreamError`, `PerplexityParseError`) and
surfaced through the route's 502 path. The error message is
operator-facing diagnostic text; the upstream's own design
keeps the API key out of error messages, so surfacing the
message is safe.

## Client-side behaviour

### Click variant — `data-perplexity-query` (non-form element)

```html
<button data-perplexity-query
        data-perplexity-target="#out"
        data-query="What is the weather in Boston?">
  Ask
</button>
<div id="out"></div>
```

On click:

1. Reads `data-query` (the query string) and
   `data-perplexity-target` (the target selector).
2. POST `/__perplexity` with `application/json` body
   `{query: "..."}`.
3. **HTML response** → `target.innerHTML = <response body>`.
4. **Non-HTML response / network failure** → silent no-op.
   No native fallback because clicks don't have a default
   submit action.

Missing / empty `data-query` is a silent no-op — there's no
sensible default for a search query.

### Form variant — `<form data-perplexity-query>`

```html
<form data-perplexity-query
      data-perplexity-target="#out">
  <input name="query" placeholder="Ask Perplexity">
  <button type="submit">Ask</button>
</form>
<div id="out"></div>
```

On submit:

1. Resolves the target via `data-perplexity-target`.
2. Pulls the query from the form's `name="query"` field.
3. POST `/__perplexity` with the same JSON body shape.
4. **HTML response** → `target.innerHTML = <response body>`.
5. **Non-HTML response / network failure** → strip
   `data-perplexity-query` and re-submit natively (mirrors
   the A19-R/A23-R form fallback contract).

Missing / empty `query` field falls through to native submit.

### Why two branches share one marker

`data-perplexity-query` marks both element shapes; the
enhancement layer dispatches on event type:

- The click handler explicitly skips form elements (so a
  submit-button click doesn't fire a duplicate POST before
  the submit handler runs).
- The submit handler only fires for forms.

This keeps the marker attribute easy to remember while
preserving the right fallback semantics per element type.

### Behaviour matrix

| Trigger | HTML response | Non-HTML / network failure |
|---|---|---|
| `<button data-perplexity-query data-query="..." ...>` | Replace target | Silent no-op |
| `<form data-perplexity-query ...>` with `name="query"` | Replace target | Strip marker + native submit |

## Distinct from prior cards

| | A21-R diagnostic | A23-R status | A24-R loading | **A30-R perplexity** |
|---|---|---|---|---|
| Trigger event | click | submit | click | click + submit |
| Trigger attr | `data-diagnostic-toggle` | `data-enhance="status"` | `data-loading-trigger` | `data-perplexity-query` |
| Target attr | `data-diagnostic-target` | `data-status-target` | `data-loading-target` | `data-perplexity-target` |
| HTTP method | GET | POST | POST | POST |
| Body | none | `{kind, message}` | `{}` or `{message}` | `{query}` |
| Upstream | none (deterministic) | none (deterministic) | none (deterministic) | **MOCK or REAL Perplexity** |
| Fallback | silent no-op | native submit | silent no-op | branch-dependent |

A30-R is the first card whose route can perform an outbound
HTTPS call. Every prior `__`-prefixed route is fully local.

## REAL-mode deployment notes

REAL mode requires three coordinated pieces:

1. **Env vars** on the Cloud Run service:
   - `PERPLEXITY_MODE=REAL`

2. **Secret Manager** binding:
   - Secret: `perplexity-api-key` (or similar)
   - Mounted as env var `PERPLEXITY_API_KEY`
   - The upstream reads `process.env.PERPLEXITY_API_KEY`
     at call time; it is never logged.

3. **Outbound HTTP** allowed:
   - The Cloud Run service must be able to reach
     `https://api.perplexity.ai` on port 443.
   - Default Cloud Run egress permits this — no extra
     VPC connector configuration is needed unless the
     project enforces a private-only egress policy.

The route degrades gracefully if any piece is missing:
`PERPLEXITY_MODE=REAL` without an API key returns a 502 +
failure fragment with the `PerplexityConfigError` message,
not a crash or a silent fallback to MOCK.

### Cloud-side verification

REAL-mode behaviour is **not exercised by vitest**. The
local suite locks MOCK semantics and the upstream's error-
mapping contract; verifying that the deployed service can
actually reach the Perplexity API is a deployment-time
smoke test, e.g.:

```bash
curl -X POST https://<service>.run.app/__perplexity \
     -H "Content-Type: application/json" \
     -d '{"query": "hello"}'
```

A successful response should contain a non-mock answer and
`tokens: <n>` with `n > 0`.

## What's NOT here

- **No streaming.** The route waits for the full upstream
  response and returns it atomically. A future card could
  layer this onto the A22-R streaming primitive (yielding
  partial chunks as SSE events) without changing the
  upstream module.
- **No retry / backoff.** The upstream is one deterministic
  HTTP call. Operator-side retries are explicit (re-click /
  re-submit).
- **No caching.** Every POST goes to the upstream. A future
  card could add a content-keyed cache layer.
- **No conversation memory.** The route is single-turn. The
  query field has no implicit context from prior calls.
- **No auth.** Same posture as the other `__`-prefixed
  routes. Layer an interceptor BEFORE `PERPLEXITY_PATH` in
  `requestHandler.ts` for operator-only deployments.
- **No model selection.** The upstream's `PERPLEXITY_MODEL`
  constant (`sonar-pro`) is fixed per the upstream card;
  changing it is a new upstream card.
- **No SPA involvement.** The SPA at `web/src/main.tsx` is
  untouched. A30-R is exclusively a Track A / Track C
  concern.

## Tests

Server-side: 22 tests in `web/src/surface/__tests__/perplexityRelay.test.ts`.

- Constants: `PERPLEXITY_PATH`, `PERPLEXITY_TEMPLATE_NAME`.
- `escapeHtml`: five HTML entities, `&` first.
- `_coerceQuery`: well-formed, missing, non-string, empty,
  null, non-object — each shape locked.
- `handlePerplexity` MOCK happy path: 200 + text/html,
  fragment with mock answer, `tokens: 0`, XSS escape,
  byte-identical body across calls, non-mutation.
- `handlePerplexity` error paths: non-POST / non-string
  body / empty body / unparseable JSON / missing query /
  empty query → 400 + failure fragment; upstream throws
  (`trigger_error` mock) → 502 + failure fragment with
  `MOCK_PERPLEXITY_ERROR` message; every error path
  returns text/html (never JSON).
- MOCK default sanity check (confirms tests aren't
  silently hitting the real API).

Client-side: 20 tests in `web/src/client/__tests__/perplexityEnhance.test.ts`.

- Click branch: POST `/__perplexity` with `data-query`,
  HTML response replaces target, missing/empty query →
  no fetch, nested click fires.
- Submit branch: POST with `name="query"` field value,
  HTML response replaces target, missing query field →
  fall through to native.
- Click handler skips form elements (no double-fire on
  submit-button clicks).
- Non-HTML response: click → silent no-op; form → native
  submit + marker stripped.
- Network failure: click → silent no-op; form → native
  submit.
- Defensive: missing target / missing element / bad
  selector → no fetch.
- Module re-import does not double-fire.
- A23-R `data-enhance="status"` and A24-R
  `data-loading-trigger` still POST to their own routes.
- Plain clicks on non-trigger elements remain no-ops.

REAL-mode tests are intentionally absent — they require a
live API key + outbound network and are verified cloud-side
per the deployment notes above.
