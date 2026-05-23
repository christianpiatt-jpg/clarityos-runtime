# A22-R — Surface Streaming & Partial-Fragment Pipeline

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A22-R adds a **server-authored streaming-fragment surface** to
the v0.2 Web Surface, layered on top of A18 (SSE handler),
A19-R (progressive enhancement), A20-R (form semantics), and
A21-R (operator diagnostics).

It exposes:

- A streaming task controller (`runStreamTask`) — a pure
  async generator that yields a deterministic sequence of
  `StreamEvent` records describing each phase of a
  long-running operation.
- A server-level route at `GET /__stream` that frames the
  generator's events as SSE and returns them as a single
  buffered response (the v0.2 single-Response architecture,
  same shape A18 documents).
- A client `data-stream-start` attribute that opens an
  `EventSource("/__stream")` on click and routes incoming
  named events into a panel's `<pre data-stream-log>` /
  `<div data-stream-status>` children.

Everything is additive. No SPA touch, no hydration, no new
view registration, no new template engine.

## Philosophy

- **Server HTML is the source of truth.** The stream fragment
  is rendered server-side; the client never invents structure.
  All the enhancement layer does is route per-event payloads
  into pre-existing child elements.
- **Operator surfaces are server-level interceptors.** Just
  like `/health`, `/ready`, and `/__diagnostics`,
  `/__stream` is matched in the Node HTTP request handler
  BEFORE `routeWebSurface`. A broken view registry can't
  take streaming feedback down with it.
- **SSE in v0.2 is buffered.** Same shape as A18 — the
  handler collects frames into an array and returns them in
  one body. Real wire streaming lands when Track C upgrades
  the response writer; the controller + route don't change.
- **Progressive enhancement respects the no-JS baseline.**
  With JS off, an operator can navigate directly to
  `/__stream` and read the SSE transcript as a raw text
  page. The base page (the one with the START button) is
  unaffected.
- **Deterministic by default.** `runStreamTask` is a pure
  generator with no `await sleep`, no random IDs, no I/O.
  Same request → byte-identical event sequence. Test mode
  (`?simulate=error`) is an explicit branch, not a
  randomised failure injection.

## File map

| Path | Role |
|---|---|
| `web/templates/v0.2/streamFragment.html` | Server-rendered `<div class="stream-fragment">` with `<pre data-stream-log>` + `<div data-stream-status>` children. |
| `web/src/surface/streaming/types.ts` | `StreamEvent` (closed-type union). |
| `web/src/surface/streaming/controller.ts` | `runStreamTask(request)` async generator + `SIMULATE_ERROR_QUERY`. |
| `web/src/surface/streaming/index.ts` | Barrel: re-exports controller + type. |
| `web/src/server/routes/stream.ts` | `STREAM_PATH` + `handleStream(request)` + `STREAM_FATAL_ERROR_EVENT`. |
| `web/src/server/requestHandler.ts` | Intercepts `STREAM_PATH` before the surface router. |
| `web/src/client/enhance.ts` | Adds delegated click handler for `data-stream-start`. |

## Server-side API

### `runStreamTask(request)`

```ts
import { runStreamTask, type StreamEvent } from "../streaming";

for await (const event of runStreamTask(req)) {
  // event: StreamEvent = { type, message }
}
```

Default sequence (7 events):

| # | type | message |
|---|---|---|
| 1 | `status` | `starting` |
| 2 | `log` | `task initialized` |
| 3 | `status` | `processing` |
| 4 | `log` | `step 1 complete` |
| 5 | `log` | `step 2 complete` |
| 6 | `status` | `finalizing` |
| 7 | `done` | `task complete` |

Error sequence (3 events), triggered by `?simulate=error` in
the request path:

| # | type | message |
|---|---|---|
| 1 | `status` | `starting` |
| 2 | `log` | `task initialized` |
| 3 | `error` | `simulated failure` |

Determinism: pure generator, no async timing, no I/O. Same
request → byte-identical sequence.

### `handleStream(request)`

```ts
import { handleStream } from "../server/routes/stream";

const response = await handleStream(req);
// → {
//     status: 200,
//     headers: { "content-type": "text/event-stream; charset=utf-8" },
//     body: "event: status\ndata: {\"type\":\"status\",\"message\":\"starting\"}\n\n" +
//           "event: log\ndata: {\"type\":\"log\",\"message\":\"task initialized\"}\n\n" +
//           ...
//   }
```

Each `StreamEvent` becomes one SSE frame via the existing
`_formatSseFrame` helper from A18:

```
event: <type>
data: {"type": "<type>", "message": "<message>"}
<blank line>
```

If the generator throws past its own `error` event, the catch
block appends a trailing `STREAM_FATAL_ERROR_EVENT` frame and
returns whatever was already buffered. The route never throws
past its caller.

## Client-side behaviour

### `data-stream-start`

```html
<button data-stream-start
        data-stream-target="#stream-panel">
  Run task
</button>
<div id="stream-panel" class="stream-fragment" data-stream-fragment>
  <pre data-stream-log></pre>
  <div data-stream-status></div>
</div>
```

On click:

1. The delegated click handler walks `closest("[data-stream-start]")`.
2. If the trigger already carries `data-stream-active="1"`,
   the click is a silent no-op (per-trigger guard against
   double-starts).
3. Resolves the panel via `data-stream-target`'s CSS
   selector.
4. Opens `new EventSource("/__stream")`.
5. Marks the trigger with `data-stream-active="1"`.
6. Registers four named-event listeners on the source:
   - `log` → append `<message>\n` to `[data-stream-log]`
   - `status` → set `[data-stream-status]` text to `<message>`
   - `done` → close the source + clear the active marker
   - `error` → close the source + clear the active marker

After `done` / `error`, re-clicking opens a fresh session.

### Event payload contract

The enhancement layer expects each SSE `data:` payload to be
JSON-encoded with a string `message` field:

```json
{ "type": "log", "message": "step 1 complete" }
```

Malformed JSON, missing `message`, or non-string `message`
are silently dropped — the DOM is never partially mutated by
a corrupted frame.

### Defensive paths

| Condition | Behaviour |
|---|---|
| Missing `data-stream-target` | No fetch, no-op |
| Target element doesn't exist | No fetch, no-op |
| Invalid CSS selector | No fetch, no-op (no throw) |
| `EventSource` unavailable (jsdom) | Silent no-op |
| `EventSource` constructor throws | Active marker never set; trigger remains re-clickable |
| Active session in progress | Re-clicks dropped until `done`/`error` |
| Plain clicks on non-trigger elements | No-op |
| Module re-evaluation (HMR / `vi.resetModules`) | Listeners bound exactly once via A19-R symbol guard |

## Integration pattern

A typical operator surface combining a start button and a
server-rendered panel:

```html
<section class="task-runner">
  <button data-stream-start
          data-stream-target="#run-panel">
    Start run
  </button>
  <div id="run-panel">
    {{> streamFragment }}
  </div>
</section>
```

The `streamFragment` partial renders the `<pre>` + `<div>`
the enhancement layer expects. Clicking the button opens an
EventSource and starts populating those children live. With
JS off, the button does nothing — the operator can still
navigate to `/__stream` directly to read the raw SSE output.

## What's NOT here

- **No real wire streaming.** The route buffers the full
  body and writes it in one shot, matching the v0.2
  single-Response architecture. A future card can swap
  `writeSurfaceResponse` for a chunked writer without
  touching the route or the controller.
- **No POST.** The route is GET-only. Future cards can add
  `/__stream/cancel` if needed.
- **No auth.** Same posture as `/__diagnostics`. Layer an
  interceptor BEFORE `STREAM_PATH` in `requestHandler.ts`
  for operator-only deployments.
- **No retry / reconnect.** EventSource's built-in
  reconnection is fine for browser sessions; the
  enhancement layer doesn't add a second layer on top.
- **No real long-running task.** `runStreamTask` is a
  deterministic demo. Future cards can wire it to actual
  work (build runs, ELINS macro runs, etc.) by extracting
  the task as a strategy.
- **No SPA involvement.** The SPA at `web/src/main.tsx` is
  untouched. A22-R is exclusively a Track A / Track C
  concern.

## Tests

Server-side: 18 tests in `web/src/surface/__tests__/streaming.test.ts`.

- Constants: `STREAM_PATH` / `SIMULATE_ERROR_QUERY` / `STREAM_FATAL_ERROR_EVENT`.
- `runStreamTask`: default sequence ordering, event shape
  (type + non-empty message), terminal `done` payload,
  `?simulate=error` branch, deterministic across calls,
  request non-mutation.
- `handleStream`: 200 + `text/event-stream` response,
  `event:` + `data:` line structure, canonical `\n\n` frame
  terminator count, frame ordering matches generator order,
  error branch produces terminal `error` frame (no `done`),
  byte-identical body across calls, request non-mutation,
  no stack-trace leak.

Client-side: 24 tests in `web/src/client/__tests__/streamEnhance.test.ts`.

- Click opens `EventSource("/__stream")`, sets
  `data-stream-active`, registers log/status/done/error
  listeners.
- Nested element inside trigger still fires.
- `log` events append to `<pre>` with trailing newline; in
  arrival order.
- `status` events replace `<div>` (overwrite, not append).
- `done` closes source + clears active marker.
- `error` closes source + clears active marker.
- Per-trigger guard: re-clicking while active opens no
  second source; clicking after `done` opens a fresh one.
- Idempotent module re-import (no double-fire).
- Missing target attribute / element / bad selector → no
  source opened.
- Malformed JSON / missing message / non-string message →
  silent drop.
- Missing `EventSource` global → silent no-op.
- A19-R toggle path unaffected.
- Plain clicks on non-trigger elements are no-ops.
