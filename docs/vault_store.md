# Vault Store

## Purpose

Vault Store is the per-user Firestore document store for notes,
sessions, and raw ELINS objects, implemented in `vault_store.py` as a
thin, schema-blind wrapper around a single Firestore collection. It
is **unencrypted**, accepts opaque dicts, and enforces no schema,
type, or ownership rules — all of that lives at the route layer in
`app.py`. It is not Memory Vault (see `docs/memory_vault.md`), not a
search engine, and not a security boundary.

## Implementation location

- **File:** `vault_store.py` (the entire subsystem, ~120 lines).
- **Imports:**
  - Eager (stdlib only): `logging`, `os`, `secrets`, `typing.Optional`.
  - Lazy: `google.cloud.firestore`, `google.cloud.firestore_v1.FieldFilter`
    (inside `_get_firestore()` and `list_for_user()`, only when the
    `firestore` backend is selected).

## Data model

### ID format

A vault id is `"v_"` followed by `secrets.token_urlsafe(16)` — 22
URL-safe characters of cryptographic randomness. Issued by `new_id()`.

### Document schema (11 fields, populated by `app.py`)

`vault_store` itself accepts opaque dicts. The fields below are
written by `app.py` at write / update time and constitute the actual
persisted shape in production:

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | str | `new_id()` | the vault_id |
| `user` | str | app.py route | owner; enforced at the route layer |
| `type` | str | app.py route | one of `ALLOWED_VAULT_TYPES` |
| `title` | str | app.py route | defaults to `""` |
| `content` | str | app.py route | body |
| `tags` | list[str] | app.py route | |
| `metadata` | dict | app.py route | passthrough (provider, payload, etc.) |
| `created_at` | float | app.py route | Unix timestamp |
| `object_vector` | list[float] | app.py route | Dewey embedding; recomputed on update; backfilled by `dewey_worker` |
| `size_bytes` | int | app.py route | cached serialised JSON size, so delete can decrement usage without a re-fetch |
| `updated_at` | float | app.py route | set only on update |

The module docstring at `vault_store.py:4-15` lists only 8 fields
(missing `title`, `object_vector`, `updated_at`) and is stale relative
to the current `app.py`-persisted shape. This document reflects the
persisted shape, not the docstring.

### Type whitelist

```python
ALLOWED_VAULT_TYPES = ("note", "session", "elins_raw")
```

Defined at `app.py:281`; enforced on `/vault/write` at `app.py:1647`.
`vault_store` does not validate `type`.

### Backends

| Backend | Storage | Notes |
|---|---|---|
| `memory` | `_MEMORY: dict[str, dict]` (in-process) | default; local development |
| `firestore` | Firestore collection `"vault"` (constant `_COLL`) | production; lazy-init client |

**Backend selection:** `_backend()` reads `CLARITYOS_BACKEND` (default
`"memory"`), lowercased. There is no `CLARITYOS_VAULT_BACKEND`
override — that env var belongs to Memory Vault.

### Required Firestore composite index

`list_for_user()` against the Firestore backend requires a composite
index on `(user ASC, created_at DESC)`. The first uncreated-index
query fails with a console URL; one-click index creation makes
subsequent queries free.

## APIs / entrypoints

### Public functions

- **`new_id() -> str`** — `"v_"` + `secrets.token_urlsafe(16)`.
- **`create(item_id, payload)`** — write a new doc; full document set.
- **`update(item_id, payload)`** — full replacement (same `.set()`
  semantics as `create`, **not** a partial merge).
- **`get(item_id) -> dict | None`** — read; returns `None` if absent.
- **`delete(item_id)`** — remove (no-op if absent).
- **`list_for_user(user, limit=100) -> list[dict]`** — sorted
  `created_at` descending.

Test-only `_reset_memory_for_tests()` clears `_MEMORY`; not part of
the canonical API.

### HTTP entrypoints

All under `/vault/*` at the root (distinct from Memory Vault's
`/me/vault/*`):

- **`POST /vault/write`** → `vault_write` (app.py:1644)
- **`POST /vault/update`** → `vault_update` (app.py:1678)
- **`POST /vault/delete`** → `vault_delete` (app.py:1730)
- **`GET /vault/list`** → `vault_list` (app.py:1754)

Additionally: `POST /elins/ingest/raw` writes here with
`type="elins_raw"`, sharing the same Firestore collection.

## Integration points

### Writers / consumers

- **`app.py`** — every `/vault/*` HTTP endpoint plus the ELINS raw
  ingest writer; the only module that constructs the 11-field
  document shape.
- **`dewey_worker.py`** — `get()` + `update()` for backfilling
  `object_vector` on legacy docs that pre-date the embedding field.

### Readers

- **`app.py`** — `/vault/list` and its callers.
- **DEWEY pipeline (indirect)** — uses the persisted `object_vector`
  for similarity search but reads via `app.py` HTTP, not by
  importing `vault_store`.

### Required configuration

- **`CLARITYOS_BACKEND`** selects the backend. In production it is
  `firestore`; tests and local development use `memory`.
- Firestore backend requires Google application-default credentials
  and the composite index above.

## Invariants

- **Schema-blind storage.** `vault_store` accepts any dict; the
  schema is defined and enforced by `app.py`. The module never
  inspects payload field names or types.
- **No security boundary.** `vault_store` has no ownership check; any
  caller of `get(item_id)` reads any doc. Ownership is enforced on
  `/vault/update` and `/vault/delete` at the route layer
  (`app.py:1687-1690`, `app.py:1739-1742`).
- **Full-replacement updates.** `update()` uses `.set()` semantics —
  it replaces the entire document, not a partial merge. Callers must
  pass the complete payload.
- **Plaintext at rest.** No encryption envelope, no key derivation,
  no scheme byte. Documents are stored as-is in Firestore (or
  `_MEMORY`).
- **No background work.** No threads, no schedulers, no async tasks,
  no TTL, no garbage collection. Every operation is request-driven.
- **No batch / multi-key API.** Each call writes or reads one
  document.
- **Lazy Firestore initialisation.** The client is constructed on
  first use; a missing `google-cloud-firestore` package raises only
  when `firestore` is the active backend.
- **Composite-index dependency.** `list_for_user()` against Firestore
  requires the composite index above; running without it fails
  loudly the first time.

## Non-goals

Vault Store is **not**:

- a replacement for Memory Vault (see `docs/memory_vault.md`); the
  two systems coexist and back different surfaces;
- encrypted — for sensitive per-user data, write to Memory Vault,
  not here;
- a security boundary — ownership lives in `app.py` route handlers;
- a search engine — only `list_for_user(user)` and `get(item_id)`
  are supported;
- a query language — no predicates, no filters beyond Firestore's
  composite-index query;
- a partial-update / patch / merge surface — `update()` is full
  replacement;
- a background processor — no auto-prune, no TTL, no GC, no
  scheduled work;
- a schema engine — fields are caller-supplied; the type whitelist
  lives in `app.py`;
- a distributed transaction substrate — each call is one Firestore
  document op;
- a DEWEY embedding service — `object_vector` is *persisted* here
  but *computed* by callers; backfill is `dewey_worker`'s job;
- pagination-aware beyond the `limit: int = 100` argument; there are
  no cursors.

## Fiction removed

The following constructs are explicitly not present in
`vault_store.py` and must not be inferred:

- **Fabricated APIs:** `find`, `search`, `query`, `update_partial`,
  `patch`, `merge`, `count_for_user`, `list_all`, `bulk_write`,
  `batch_create`, pagination cursors, async / callback variants.
- **Fabricated architecture:** a "Vault Store engine", autonomous
  store, "vault store AI" / ML model, distributed `vault_store`,
  multi-region replication, vault watchers / events / triggers /
  pub-sub, auto-pruning / TTL / GC / size quotas, background
  compaction, vault-store query language.
- **Fabricated security framings:** schema enforcement in
  `vault_store` (it is in `app.py`), type validation in
  `vault_store` (it is in `app.py`), ownership enforcement in
  `vault_store` (it is in `app.py`), encryption at rest
  (`vault_store` is plaintext in both backends), per-user backend
  selection (`_backend()` is global).
- **Fabricated configuration:** `CLARITYOS_VAULT_*` env vars (those
  belong to Memory Vault; `vault_store` uses only
  `CLARITYOS_BACKEND`), `vault_store`-specific auth tokens beyond
  Firestore IAM.

Only the behaviour, fields, and integrations described in this
document are present in the code; the stale module docstring is
explicitly superseded by this doc on the schema field list.
