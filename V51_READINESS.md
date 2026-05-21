# V51 Readiness — Project Layer (backend)

Status: ✅ Ready
Backend version: `4.5`
Threads vault: `threads_vault.v51.1`
Projects vault: `projects_vault.v51.1`
Build: `20260507690000`

---

## What v51 ships

A first-class project layer on top of the existing v47 thread
substrate. Threads can now belong to a project; lists can filter by
project; the kernel routes messages through a project's
`default_model` / `allowed_models` when one is supplied.

Backend-only pass per the spec — desktop, web, and phone clients are
untouched. The desktop client (the next step) calls these endpoints
verbatim per its hardwired `ACTIVE_PROJECT_ID = "VA_LITIGATION"` flow.

The implementation reuses every pattern v47 / v50 established:

* `projects_vault.py` mirrors the shape of `threads_vault.py` —
  same `_coerce_meta` discipline, same `KeyError → 404` contract,
  same memory-vault-backed encrypted persistence.
* `ThreadMeta` gains `project_id: Optional[str]` (default `None` for
  backward compatibility); `_coerce_meta` carries the field so
  existing v47 / v50 mutators automatically preserve it.
* `intelligence_kernel.run_thread_message` accepts an optional
  `project_id`; matching project meta drives a routing override
  through the existing `_resolve_model` + a new
  `_apply_project_routing` reconciler.
* All v50 / v47 / v40 tests still pass; 40 new tests cover the
  v51 surface.

---

## Files added / changed

### New
- `projects_vault.py` — `create_project`, `list_projects`,
  `get_project`, `update_project`, `update_project_summary`,
  `add_thread_to_project`, `remove_thread_from_project`,
  `list_project_threads`, `is_thread_in_project`, `delete_project`.
  TypedDicts (`ProjectMeta`, `ProjectSummary`). Validation:
  `project_id` matches `^[A-Za-z0-9_-]{1,64}$`; name + description +
  tags soft-capped.
- `tests/test_v51_projects.py` — 40 tests.
- `V51_READINESS.md` (this file).

### Modified
- `memory_vault.py`:
  - `ALLOWED_NAMESPACES` adds `"projects"`. Vault keys:
    `projects.{project_id}.meta`, `projects.{project_id}.summary`,
    `projects.{project_id}.threads`.
- `threads_vault.py`:
  - `THREADS_VAULT_VERSION` → `threads_vault.v51.1`.
  - `ThreadMeta` adds `project_id: Optional[str]`. `_coerce_meta`
    carries it so `rename_thread`, `append_message`, `list_threads`,
    `get_thread`, `update_thread_summary`, `get_thread_meta` all
    preserve it automatically.
  - `create_thread(user, title, *, project_id=None)` — keyword-only
    `project_id` parameter. Existing v47 callers stay valid.
- `model_router.py`:
  - New `resolve_model_alias(name)` helper. Maps friendly names
    (`"claude"`, `"gpt"`, `"gemini"`, `"local"`, etc.) to canonical
    `SUPPORTED_MODELS` ids; pass-through for already-canonical ids;
    `None` for unknown.
  - Internal `_MODEL_ALIASES` table.
- `intelligence_kernel.py`:
  - Imports `projects_vault`.
  - New `_resolve_project_routing(user, project_id)` — loads project
    meta, resolves `default_model` + `allowed_models` (via
    `resolve_model_alias`) into canonical ids; gracefully returns
    `(None, None)` when the project doesn't exist.
  - New `_apply_project_routing(chosen, default_model, allowed_models)`
    — reconciles. `default_model` wins when set + allowed (or no
    `allowed_models`); else `allowed_models` constrains; else
    pass-through.
  - `run_thread_message(user, thread_id, content, *, project_id=None)`
    — keyword-only `project_id`. Pre-validates the supplied
    `project_id` against the thread's stored `ThreadMeta.project_id`
    (mismatch → `ValueError` → app-layer 400). Plumbs the project's
    routing through `_resolve_model` + reconciler. Re-records
    `last_model_used` if `allowed_models` forces a different choice.
  - Kernel log line `meta` includes `project_id`.
- `app.py`:
  - Imports `projects_vault` + extends `fastapi` import with `Query`.
  - `/health` reports `4.5`.
  - 4 new endpoints:
    - `GET  /me/projects`                              — list user's projects
    - `POST /me/projects`                              — create project
    - `GET  /me/projects/{project_id}`                 — read one project
    - `GET  /me/projects/{project_id}/threads`         — threads via the project's index
  - 3 modified endpoints:
    - `GET  /me/threads?project_id=X`                  — optional filter
    - `POST /me/threads`                               — accepts `{title, project_id}`
    - `POST /me/threads/{thread_id}/message`           — accepts `{content, project_id}`
  - 4 new Pydantic models: `V51ProjectMetaModel`,
    `V51ProjectListResponse`, `V51CreateProjectRequest`,
    `_project_meta_to_model` helper.
  - `V47ThreadMetaModel` adds `project_id`.
  - `V47CreateThreadRequest` + `V47PostMessageRequest` add
    `project_id`.
  - `_meta_to_model` carries `project_id` field through.
  - `projects` capability advertised on `/me`.
  - Root listing extended with the four new routes.
- `tests/test_v28_endpoints.py` — health version `4.5`.
- `tests/test_v50_thread_summaries.py::test_health_version_4_4` loosened
  to a `4.*` prefix.
- `BUILD_VERSION` — `20260507690000`.

No web/phone/desktop code changes.

---

## Public API

```python
# projects_vault
PROJECTS_VAULT_VERSION = "projects_vault.v51.1"

create_project(user_id, project_meta) -> ProjectMeta
list_projects(user_id) -> list[ProjectMeta]
get_project(user_id, project_id) -> ProjectMeta
update_project(user_id, project_id, patch) -> ProjectMeta
update_project_summary(user_id, project_id, summary, ts_ms=None) -> ProjectMeta
add_thread_to_project(user_id, project_id, thread_id) -> list[str]
remove_thread_from_project(user_id, project_id, thread_id) -> list[str]
list_project_threads(user_id, project_id) -> list[str]
is_thread_in_project(user_id, project_id, thread_id) -> bool
delete_project(user_id, project_id) -> None
```

```python
# threads_vault — extended
class ThreadMeta(TypedDict):
    ...
    project_id: Optional[str]    # v51

create_thread(user, title, *, project_id=None) -> ThreadMeta
```

```python
# model_router — extended
resolve_model_alias(name) -> Optional[str]
# claude → anthropic:claude-3.7, gpt → openai:gpt-4.2, etc.
```

```python
# intelligence_kernel — extended
run_thread_message(user, thread_id, content, *, project_id=None) -> dict
```

### project_id format

Validated against `^[A-Za-z0-9_-]{1,64}$` everywhere. Matches the
ALL_CAPS_TAG style the founder uses (`VA_LITIGATION`,
`MSJ_OPPOSITION`).

### Routing precedence (v51)

When `project_id` is supplied to `run_thread_message`:

1. Load project meta.
2. If `default_model` set → resolve via `resolve_model_alias`; use as
   `_resolve_model` override.
3. If `allowed_models` set → enforce that the chosen model is in the
   list; if not, fall back to `allowed_models[0]`.
4. Else → standard task-default routing (unchanged from v47).

The model_router's user-pref / founder-default precedence still wins
over the task default, but the project's `default_model` (when set)
becomes the override and beats both.

---

## API surface

### `GET /me/projects` (auth)
```jsonc
{ "projects": [V51ProjectMetaModel, ...] }     // newest-first
```

### `POST /me/projects` (auth)
```jsonc
{
  "project_id":     "VA_LITIGATION",
  "name":           "VA Litigation",
  "description":    "Workspace for drafting MSJ Opposition",
  "default_model":  "claude",
  "allowed_models": null,
  "tags":           ["legal", "va"]
}
```
* 400 on duplicate `project_id`.
* 400 on bad `project_id` format / empty name.
* Returns the freshly-created `V51ProjectMetaModel`.

### `GET /me/projects/{project_id}` (auth)
404 on missing.

### `GET /me/projects/{project_id}/threads` (auth)
Returns `V47ThreadListResponse` filtered to threads in the project's
denormalised index. Equivalent to `GET /me/threads?project_id=X`
(which reads from the authoritative `ThreadMeta.project_id` field) —
the two converge as long as the index hasn't drifted.

### `GET /me/threads?project_id=X` (auth) — extended
When `project_id` query is supplied, results are filtered to
`ThreadMeta.project_id == X`. Threads with no project_id are
excluded by a project filter (consistent with the spec wording).

### `POST /me/threads` (auth) — extended
```jsonc
{ "title": "MSJ_OPPOSITION", "project_id": "VA_LITIGATION" }
```
* If `project_id` is supplied:
  * 404 if project doesn't exist.
  * Tags `ThreadMeta.project_id` + adds to project's threads index in
    one round-trip.

### `POST /me/threads/{thread_id}/message` (auth) — extended
```jsonc
{ "content": "draft the opposition", "project_id": "VA_LITIGATION" }
```
* If `project_id` is supplied:
  * Validates `thread.project_id == project_id` (400 on mismatch).
  * Routes through the project's `default_model` / `allowed_models`.

### `/me` additions
```jsonc
"capabilities": [..., {"id": "projects", "label": "Projects", "route": "/me/projects"}]
```

---

## Migration

Per spec STEP 6: **no-op**.

* `list_projects(user_id)` returns `[]` for fresh users.
* Existing v47/v50 threads continue to work unchanged. Their
  `ThreadMeta.project_id` field reads as `None` (the `_coerce_meta`
  default for legacy records that don't carry the field).
* Nothing is auto-created on first request.

---

## Tests

```
tests/test_v51_projects.py   — 40 tests, all pass
Full backend suite           — 730 passed, 0 failed (690 → 730, +40)
```

Coverage:

**projects_vault** (10): create happy / bad shape / duplicate / list
empty / list newest-first / get 404 / update_summary set+clear /
add_thread idempotent + count bump / remove_thread / is_thread_in_project
edges / delete idempotent.

**threads_vault** (4): default project_id is None / create_with_project_id
/ rename preserves / append preserves.

**model_router aliases** (3): known aliases (case-insensitive) /
canonical pass-through / unknown returns None.

**Kernel routing** (6): project default_model overrides task default /
alias resolution (`"claude"` → `anthropic:claude-3.7`) / project_id
mismatch raises ValueError / no project_id falls back to task default
/ allowed_models constrains choice / kernel_run log carries project_id.

**Endpoints** (16): list empty / create round-trip / duplicate 400 /
bad project_id 400 / get 404 / threads filter (multi project) /
create thread with project_id (index + count bump) / unknown project
404 on thread create / message routes through project default_model /
message project_id mismatch 400 / message without project_id works
(backward compat) / project's threads index matches filter / capability
advertised / health version 4.5.

**Migration / backward compat** (2): fresh user has empty projects +
threads / legacy thread without project_id still round-trips.

All tests run with the mock backend + real encryption (no plaintext
mode, no network).

---

## Notes / follow-ups

- The desktop client can now be wired exactly per its v51 spec:
  `GET /me/projects`, `POST /me/projects` with the literal body
  shape, `GET /me/threads?project_id=VA_LITIGATION`, `POST /me/threads`
  with `{title, project_id}`, and `POST /me/threads/{tid}/message`
  with `{content, project_id}`. (The spec used `text` field name for
  the message body; the actual backend uses `content` per v47 — the
  desktop client should send `content`. This is the same field name
  it already uses today.)
- `default_model` accepts both canonical IDs (`anthropic:claude-3.7`)
  and friendly aliases (`claude`). Aliases are case-insensitive.
- `allowed_models` is per-project. When set, it constrains routing
  even if the user's `preferred_model` or the founder's default would
  pick something else. This is the v51 mechanism that makes "this
  project must use Claude" enforceable.
- `delete_project` doesn't delete the threads themselves — they keep
  their `project_id` field but become orphans (excluded from
  `?project_id=` filters; still readable by id). Future passes can
  add a "rehome" or "cascade delete" mode.
- The project's threads index (`projects.{pid}.threads`) is a
  denormalised list that's kept in sync by `add_thread_to_project`.
  The authoritative source remains `ThreadMeta.project_id`. Both
  endpoints (`GET /me/projects/{id}/threads` via index;
  `GET /me/threads?project_id=X` via field scan) converge on the same
  set; the test suite asserts this.
- Backend version `4.5`. Web / phone / desktop clients unchanged.
