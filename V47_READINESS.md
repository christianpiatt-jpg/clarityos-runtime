# V47 Readiness — Threads (persistent threaded interactions)

Status: ✅ Ready
Backend version: `4.3`
Threads vault: `threads_vault.v47.1`
Build: `20260507630000`

---

## What v47 ships

A backend-only threaded interaction substrate. Each user can hold an
unbounded set of named threads in their `memory_vault`, post messages
into them, and receive an assistant reply routed through the existing
multi-model router. The vault layout reuses v46's encryption +
namespace machinery — threads add a single new namespace (`threads`)
with three reserved sub-prefixes (`meta.*`, `messages.*`,
`embeddings.*` — the third is wired into `delete_thread` but otherwise
inert until v48).

Six new endpoints under `/me/threads/*` cover the full lifecycle
(create / list / detail / message / rename / delete). The kernel gets
a new `run_thread_message(user_id, thread_id, content)` that writes
the user turn, dispatches the assistant reply, writes the assistant
turn, and emits a `kernel_run` log line — same telemetry shape as
ELINS / #G runs. The `kernel_view_for_user` response carries
`thread_count` + `last_thread_updated_at` so `/me` clients can render
a "you have N threads, latest activity X" line in one round-trip.

No frontend code in this pass. Web + phone surfaces will pick up the
new endpoints in a later UX pass; today they're consumable from any
HTTP client.

---

## Files added / changed

### New
- `threads_vault.py` — `create_thread`, `list_threads`, `get_thread`,
  `append_message`, `rename_thread`, `delete_thread` + TypedDicts
  (`ThreadMeta`, `Message`) + helpers.
- `tests/test_v47_threads.py` — 34 tests.
- `V47_READINESS.md` (this file).

### Modified
- `memory_vault.py`:
  - `ALLOWED_NAMESPACES` adds `"threads"` (vault keys may now use
    `threads.meta.{tid}`, `threads.messages.{tid}.{ts_ms}_{seq}`,
    `threads.embeddings.{tid}.…`).
- `model_router.py`:
  - `TASK_DEFAULTS` adds `"thread"` → `"anthropic:claude-3.7"`.
- `intelligence_kernel.py`:
  - Imports `threads_vault`.
  - New `run_thread_message(user_id, thread_id, content)` — appends
    user turn → resolves model → dispatches via `model_router.route_request`
    → appends assistant turn → emits `kernel_run` log line. Returns
    `{meta, user_message, assistant_message, model_id}`.
  - `_format_thread_context(messages, latest)` builds a compact
    `role: content` transcript (last 8 messages, 6 KB cap) for the
    prompt body.
  - `kernel_view_for_user()` adds `thread_count` +
    `last_thread_updated_at`.
- `app.py`:
  - Imports `threads_vault`.
  - Pydantic models: `V47ThreadMetaModel`, `V47ThreadDetailMessage`,
    `V47ThreadDetailResponse`, `V47ThreadListResponse`,
    `V47CreateThreadRequest`, `V47PostMessageRequest`,
    `V47PostMessageResponse`, `V47RenameThreadRequest`,
    `V47DeleteThreadRequest`.
  - 6 new endpoints (see API surface below).
  - `threads` capability advertised on `/me`.
  - Backend version `4.3`; `/health` reports `4.3`; root listing
    extended.
- `tests/test_v28_endpoints.py` — health version assertion → `"4.3"`.
- `tests/test_v46_memory_vault.py::test_health_version_bumped_to_4_2`
  loosened (matches the `4.*` family).
- `BUILD_VERSION` — `20260507630000`.

---

## Public API

```python
# threads_vault
THREADS_VAULT_VERSION = "threads_vault.v47.1"
VALID_ROLES = ("user", "assistant", "system")

create_thread(user_id, title) -> ThreadMeta
list_threads(user_id) -> list[ThreadMeta]                # newest first
get_thread(user_id, thread_id) -> (ThreadMeta, list[Message])
append_message(user_id, thread_id, message) -> (ThreadMeta, Message)
rename_thread(user_id, thread_id, title) -> ThreadMeta
delete_thread(user_id, thread_id) -> None                # idempotent
```

```python
# intelligence_kernel additions
THREAD_CONTEXT_MESSAGES = 8
THREAD_CONTEXT_CHAR_BUDGET = 6000

run_thread_message(user_id, thread_id, content) -> {
    "meta":              ThreadMeta,
    "user_message":      Message,
    "assistant_message": Message,
    "model_id":          str,
}
```

### Vault layout

| Key                                                       | Value                |
|-----------------------------------------------------------|----------------------|
| `threads.meta.{thread_id}`                                | `ThreadMeta` JSON    |
| `threads.messages.{thread_id}.{ts_ms}_{seq:06d}`          | `Message` JSON       |
| `threads.embeddings.{thread_id}.…`                        | reserved (no logic)  |

Sorting `threads.messages.{thread_id}.*` keys lexically is equivalent
to sorting by (ts_ms, seq) — the seq is a 6-digit zero-padded counter
so two appends in the same millisecond stay ordered.

### Error contract

- `KeyError` from the vault layer → 404 at the app layer (thread not
  found).
- `ValueError` from the vault layer → 400 at the app layer (bad input
  / bad role / dotted thread_id).
- `delete_thread` is idempotent; passing a missing thread_id is a
  no-op at every layer.

---

## API surface

### `GET /me/threads` (auth)
```jsonc
{ "threads": [ThreadMetaModel, ...] }
```
Newest-first by `updated_at`.

### `POST /me/threads` (auth)
```jsonc
{ "title": "first conversation" }
```
Returns the freshly-created `ThreadMetaModel`. `title` is optional
(≤200 chars).

### `GET /me/threads/{thread_id}` (auth)
```jsonc
{
  "meta": { "thread_id": "...", "title": "...", ... },
  "messages": [
    { "role": "user", "content": "...", "ts_ms": ..., "model": null },
    { "role": "assistant", "content": "...", "ts_ms": ..., "model": "..." }
  ]
}
```
404 when the thread doesn't exist for the caller. 400 when the path
contains `.`, `/`, `\\`, or null bytes.

### `POST /me/threads/{thread_id}/message` (auth)
```jsonc
{ "content": "hello there" }
```
Returns:
```jsonc
{
  "meta":              ThreadMetaModel,
  "user_message":      ThreadDetailMessage,
  "assistant_message": ThreadDetailMessage,
  "model_id":          "anthropic:claude-3.7"
}
```
- 400 on empty / whitespace-only content.
- 400 when `len(content) > 32 KB`.
- 404 when `thread_id` doesn't exist for the caller.

### `POST /me/threads/{thread_id}/rename` (auth)
```jsonc
{ "title": "renamed thread" }
```
Returns updated `ThreadMetaModel`. 404 on unknown thread.

### `POST /me/threads/{thread_id}/delete` (auth)
```jsonc
{}
```
Returns `{"ok": true, "thread_id": "..."}`. Idempotent.

### `/me` additions

```jsonc
"intelligence_kernel": {
  ...,
  "thread_count":           2,
  "last_thread_updated_at": 1762345678123
}
"capabilities": [..., {"id": "threads", "label": "Threads", "route": "/me/threads"}]
```

---

## Kernel observability

`run_thread_message` emits a structured kernel log line via
`kernel_logging.log_kernel_run`:

```jsonc
{
  "kind":        "run_thread_message",
  "user_id":     "alice",
  "duration_ms": 3.7,
  "ok":          true,
  "meta": {
    "thread_id":             "...",
    "model_id":              "anthropic:claude-3.7",
    "message_count":         2,
    "user_content_len":      11,
    "assistant_content_len": 47
  }
}
```

`safe_meta` strips raw text fields, so the assistant content body
itself never appears in logs — only its length.

`_resolve_model` continues to record `last_model_used` on
`operator_state` and bump `local_model_usage_count` when the chosen
model is the on-device one — same mechanism the ELINS / #G paths use.

---

## Tests

```
tests/test_v47_threads.py — 34 tests, all pass
Full suite — 667 passed, 0 failed
```

Coverage:

* **Vault**: create_thread default shape; None title accepted;
  list_threads round-trip ordering by `updated_at`; per-user
  isolation; get_thread message ordering (incl. same-ms appends);
  append_message updates meta + fills missing `ts_ms`; invalid role
  rejected; missing thread → KeyError; rename round-trip + missing
  → KeyError; delete removes meta + messages + idempotent on
  missing; thread_id validator rejects `.` and `/`.
* **Kernel**: `run_thread_message` round-trip (meta.message_count == 2,
  roles, deterministic mock content, model_id surfaced + persisted on
  the assistant turn); messages persist via the vault and read back
  in order; `last_model_used` populated post-run; empty content →
  ValueError; missing thread → KeyError; structured log line emitted
  with `kind=run_thread_message` and meta.message_count == 2;
  `kernel_view_for_user` exposes `thread_count` +
  `last_thread_updated_at`.
* **Endpoints**: full create → list → get → message → rename →
  delete → 404 round-trip; create with no title; per-user
  isolation; unknown thread 404 on get / message / rename; 400 on
  empty content; idempotent delete; path-validator 400 on dotted
  thread_id; `/me` advertises `threads` capability + carries
  `thread_count` + `last_thread_updated_at`; `/health` reports `4.3`.

All tests run in mock mode — `model_router.route_request` returns
the deterministic `[mock <model_id>] <preview>` payload, so the
assistant content is reproducible without any network.

---

## Notes / follow-ups

- The vault read pattern walks every `threads.messages.*` key for the
  active thread on each `get_thread`. With the mock backend that's a
  dict lookup; with fs/sqlite it's still cheap because keys are
  scoped per user. If a single thread starts holding tens of
  thousands of messages, swap to a per-thread index entry under
  `threads.meta.*` carrying `next_seq` + bookkeeping.
- The assistant reply is mocked because `route_request` itself is
  mocked. When v48 wires real provider calls, prompts will start
  flowing through the existing context formatter — no API change
  needed.
- `threads.embeddings` is reserved but unused. `delete_thread`
  already cleans up keys under it, so v48 can land embedding writes
  without a follow-up cleanup pass.
- Pre-v47 surfaces are unchanged. Older clients that don't know
  about `thread_count` / `last_thread_updated_at` continue to work.
- The "title" capability on `/me` follows the existing
  `{id, label, route}` pattern (consistent with v44's `model_router`,
  v45's `local_model`, v46's `memory_vault`). Tests assert
  `"threads"` is in the capability ids.
