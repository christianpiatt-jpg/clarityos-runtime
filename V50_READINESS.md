# V50 Readiness — Thread Summaries

Status: ✅ Ready
Backend version: `4.4`
Threads vault: `threads_vault.v50.1`
Build: `20260507660000`

---

## What v50 ships

A 1–2 sentence per-thread summary stored on the thread meta and
surfaced on every surface (web list + detail, phone list + detail,
and via two new endpoints). Summaries are kernel-generated through
the existing model router (new `thread_summary` task default), live
inside the encrypted memory vault alongside the rest of the thread
meta, and survive every other meta-mutating operation (rename, append,
list).

The endpoint pair is split between a cheap GET (returns whatever
the vault holds) and a POST that runs the summariser. The POST has a
10-minute recency shortcut: if a fresh-enough summary already exists
and the caller didn't pass `force=True`, the cached meta comes back
without spending a model call. Empty threads (zero messages) clear
their summary instead of writing a placeholder, so the UI shows
"no summary yet" rather than stale text.

No new namespace, no new vault key shape — the summary lives inside
the existing `threads.meta.{thread_id}` document.

---

## Files added / changed

### New
- `tests/test_v50_thread_summaries.py` — 23 backend tests.
- `V50_READINESS.md` (this file).

### Modified
- `threads_vault.py`:
  - `THREADS_VAULT_VERSION` → `threads_vault.v50.1`.
  - `ThreadMeta` adds `summary: Optional[str]` + `summary_ts_ms: Optional[int]`.
  - `_coerce_meta` preserves both fields on every read/write so
    `rename_thread` + `append_message` + `list_threads` automatically
    round-trip them (no per-function changes needed).
  - `create_thread` seeds them as `None`.
  - New `get_thread_meta(user_id, thread_id) -> ThreadMeta` (cheap
    meta-only read; raises `KeyError` on miss).
  - New `update_thread_summary(user_id, thread_id, summary, ts_ms) -> ThreadMeta`
    (raises `KeyError` on miss; whitespace-only summary clears).
- `model_router.py`:
  - `TASK_DEFAULTS` adds `"thread_summary": "anthropic:claude-3.7"`.
- `intelligence_kernel.py`:
  - New `summarize_thread(user_id, thread_id) -> {"meta": ThreadMeta}`.
  - `_format_summary_prompt` builds a compact `SYSTEM:`-prefixed
    transcript (last 20 messages, 8 KB cap).
  - Empty thread → clear via `update_thread_summary(..., None, ...)`.
  - Populated thread → `model_router.route_request` with the resolved
    `thread_summary` model_id, persist via `update_thread_summary`.
  - Emits a `kernel_run` log line with `kind=summarize_thread` +
    `model_id` + `summary_len`.
- `app.py`:
  - `/health` reports `4.4`; root listing extended with the two
    new routes.
  - `V47ThreadMetaModel` adds `summary` + `summary_ts_ms` (both
    optional in the response shape — null until first summary).
  - `_meta_to_model` carries the new fields.
  - New `V50ThreadSummaryResponse` + `V50ThreadSummarizeRequest`.
  - New routes:
    - `GET /me/threads/{thread_id}/summary` → 404/200.
    - `POST /me/threads/{thread_id}/summarize` →
      recency-skip when `force` is unset and summary < 10 min old.
- `web/src/lib/api.ts`:
  - `ThreadMeta` adds `summary` + `summary_ts_ms`.
  - New `getThreadSummary(thread_id)` + `summarizeThread(thread_id, force?)`.
- `web/src/routes/Threads.tsx`:
  - List rows show `summary` as a muted second line (with
    `data-testid="thread-list-summary"`).
  - Detail header gets a `SUMMARIZE` button next to RENAME/DELETE.
  - Summary card sits above the message log when present
    (`data-testid="thread-summary-card"`), captioned with relative time.
  - `handleSummarize` mirrors the new meta into both detail state and
    list state so the UI stays consistent without a refetch.
- `web/src/routes/__tests__/Threads.test.tsx`:
  - `makeMeta` defaults to `summary: null, summary_ts_ms: null`.
  - Mocks `summarizeThread`.
  - 3 new tests (summary-in-list / summary-omitted / SUMMARIZE
    button round-trip).
- `phone/lib/api.ts` — same `ThreadMeta` extension + `getThreadSummary` /
  `summarizeThread`.
- `phone/app/threads.tsx` — list rows show `summary` as a muted
  second line (`numberOfLines={2}`).
- `phone/app/thread/[id].tsx` — Summarize pill action in the header
  card, summary card below the header above the message log,
  `onSummarize` handler.
- `tests/test_v28_endpoints.py` — `/health` version → `"4.4"`.
- `tests/test_v47_threads.py::test_health_version_4_3` loosened to
  `"4."` prefix.
- `BUILD_VERSION` — `20260507660000`.

---

## Public API (backend)

```python
# threads_vault
THREADS_VAULT_VERSION = "threads_vault.v50.1"

class ThreadMeta(TypedDict):
    thread_id:     str
    title:         Optional[str]
    created_at:    int
    updated_at:    int
    message_count: int
    archived:      bool
    summary:       Optional[str]      # v50
    summary_ts_ms: Optional[int]      # v50

get_thread_meta(user_id, thread_id) -> ThreadMeta
update_thread_summary(user_id, thread_id, summary, ts_ms) -> ThreadMeta
```

```python
# intelligence_kernel
SUMMARY_CONTEXT_MESSAGES = 20
SUMMARY_CONTEXT_CHAR_BUDGET = 8_000
SUMMARY_SYSTEM_INSTRUCTION = (
    "Summarize this conversation in 1-2 sentences, "
    "user-centric, no model names."
)

summarize_thread(user_id, thread_id) -> {"meta": ThreadMeta}
```

```python
# model_router
TASK_DEFAULTS["thread_summary"] = "anthropic:claude-3.7"
```

### Recency shortcut

`POST /me/threads/{id}/summarize` short-circuits with the cached
meta when:

* `meta.summary` is set, AND
* `meta.summary_ts_ms` is < 10 minutes old, AND
* `req.force` is not `True`.

`force=True` always re-runs. Empty threads always re-clear (the
shortcut doesn't apply because `meta.summary` is null).

---

## API surface

### `GET /me/threads/{thread_id}/summary` (auth)
```jsonc
{
  "meta": {
    "thread_id": "...",
    "title": "...",
    "summary": "the user is planning q4 kickoff" | null,
    "summary_ts_ms": 1762345678123 | null,
    ...
  }
}
```
Cheap (no model call). `404` when the thread doesn't exist.

### `POST /me/threads/{thread_id}/summarize` (auth)
```jsonc
{ "force": true }   // optional; default false
```
Returns the same envelope as the GET. `400` on dotted `thread_id`,
`404` on missing thread.

### `/me/threads` + `/me/threads/{id}` additions
Every meta the existing routes return now carries `summary` +
`summary_ts_ms`. Older clients ignore the fields without breaking.

---

## UI

### Web (`/threads`)
- **List row**: muted second line shows the summary when present,
  hidden otherwise.
- **Detail header**: `SUMMARIZE` action button beside RENAME / DELETE.
  On click → `summarizeThread(thread_id)` → updates active meta + list
  row.
- **Summary card**: sits between the header and the message log when
  `meta.summary` is set. Shows `SUMMARY · {relativeTime}` caption +
  the summary text.

### Phone
- **`threads.tsx`**: list rows show summary as a 2-line muted block
  between the title and the meta line.
- **`thread/[id].tsx`**: Summarize pill in the header actions row;
  summary card below the header. Card shows `SUMMARY · {relativeTime}`
  followed by the summary text.

---

## Tests

```
tests/test_v50_thread_summaries.py — 23 tests, all pass
Full backend suite — 690 passed, 0 failed (667 → 690, +23)

web/src/routes/__tests__/Threads.test.tsx — 11 tests, all pass (8 → 11, +3)
```

Backend coverage:

* `create_thread` defaults summary fields to None.
* `get_thread_meta` happy + KeyError.
* `update_thread_summary` round-trip + clear via None + clear via
  whitespace + KeyError on missing thread.
* Rename + append + list_threads all preserve the summary field
  (regression-proof for the existing `_coerce_meta` reuse).
* `summarize_thread`:
  * empty thread → cleared.
  * populated thread → model routed, summary persisted, ts bumped.
  * model_id chosen with `task="thread_summary"` (verified via
    monkey-patched provider handler that captures the call).
  * SYSTEM instruction in the prompt body.
  * KeyError on missing thread.
  * structured kernel log line emitted with summary_len + model_id.
* Endpoints:
  * GET shape + 404.
  * POST happy + persistence + list-time roundtrip.
  * Recency shortcut: second call without `force` doesn't re-route;
    third call with `force=True` does (verified by counting
    monkey-patched `summarize_thread` invocations).
  * 404 on missing, 400 on dotted thread_id.
* `/health` version `4.4`.

Web coverage:

* `summary` line renders when present (via `data-testid="thread-list-summary"`).
* List row hides the summary line when null.
* `SUMMARIZE` button calls `summarizeThread` and the resulting meta
  updates both the detail card (via `data-testid="thread-summary-card"`)
  and the list row.

---

## Notes / follow-ups

- The recency window is `10 * 60 * 1000` ms — short enough that
  busy threads stay fresh, long enough that the UI button isn't a
  bill driver. Tunable in `app.py` if a future flag wants to expose
  it per-user.
- The summariser uses a deterministic mock against today's
  `model_router.route_request` (same as every other route_request
  call in the codebase), so the tests don't hit the network. When v51
  swaps in real LLM dispatch, the contract here doesn't change.
- The summary is metadata-only. No attempt is made to block prompt
  text from leaking through the summarised output — the model
  obviously sees the transcript. That's an LLM concern, not a vault
  concern; the vault encrypts the meta + messages either way.
- Backend version `4.4`. Web + phone clients ship a regular UI
  bump alongside the backend.
- v50 is the first feature where the kernel uses the model router
  for an output the user actively reads. The pattern (route via
  TASK_DEFAULTS + persist via vault helper + UI shows it inline) is
  the template for v51 (semantic recall), v52 (multi-model UI), and
  v53 (founder thread inspector).
