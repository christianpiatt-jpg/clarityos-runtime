# Storage Stores

## Purpose

ClarityOS has a family of small, single-purpose persistence modules — the
`*_store.py` files at the repository root. This document covers the **generic
stores** not owned by another subsystem. (The vault, threads, projects, auth,
membership, DEWEY, and regression-chain stores are documented with their own
subsystems.)

## Common pattern

Each store resolves its backend per call from `CLARITYOS_BACKEND` (default
`memory`): an in-process dict, or a lazily-initialised Firestore client (which
raises if `google-cloud-firestore` is absent). There is one Firestore
collection per store, and each module exposes a private
`_reset_memory_for_tests()`. Firestore queries that need ordering rely on
composite indexes. The one exception is `incident_store.py`, which is
JSONL-file-backed rather than Firestore-backed.

## The stores

- **`library_store.py`** — per-user authored library entries. Collection
  `library_user`, key `l_<token>`; fields `id, user, title, content, tags,
  metadata, size_bytes, created_at, updated_at`.
- **`envelopes_store.py`** — one envelope base-layer document per user.
  Collection `envelopes`, doc id = username; fields `user, elins_briefs,
  envelope_vector, updated_at`. Whole-document `set` semantics.
- **`embeddings_cache_store.py`** — the DEWEY embedding cache. Collection
  `embeddings_cache`, keyed by `sha256(text)`; stores an L2-normalised `vector`
  and `created_at`. Read/write errors degrade to a cache miss.
- **`incident_store.py`** — P0–P3 acceptance-harness incidents. An **append-only
  JSONL file** at `CLARITYOS_INCIDENT_STORE` (default `data/incidents.jsonl`) —
  not Firestore. A Pydantic `Incident` model carries `id, severity, surface,
  os, title, detail, operator_id, created_at, resolved_at`.
- **`dm_store.py`** — the founder DM tracker (metadata only — no transcripts).
  Two collections: `founder_dms` and `founder_dm_notes`.
- **`markov_states_store.py`** — Markov v2 per-user / per-session state history.
  Collection `markov_states`, key `ms_<token>`; fields include `state_index`, a
  768-dimension `state_vector`, and a `qc_envelope`.
- **`trajectories_store.py`** — DEWEY v5 trajectory storage. Collection
  `trajectories`, key `traj_<token>`.
- **`usage_store.py`** — a per-user storage-bytes counter. Collection `usage`,
  doc id = username; fields `user, bytes_used, updated_at`.
- **`timeline_store.py`** — an append-only per-user event log. Collection
  `timeline`, key `t_<token>`; fields `id, user, kind, ref, summary, ts, data,
  size_bytes, created_at`.
- **`mesh_metadata_store.py`** — Dewey-only cross-device metadata sync.
  Collection `mesh_metadata`, doc id = username; a `devices` map capped at 8
  devices (LRU) with a 16 KB per-device limit.
- **`elins_distribution_store.py`** — queued and delivered daily ELINS reports.
  Collection `elins_distribution`, doc id = username; `queued` / `delivered`
  lists capped at 500 each. On delivery the scenario text is hashed to a
  `scenario_id` and the raw text is dropped.

## APIs / entrypoints

Each store exposes its own CRUD-style functions (`create` / `get` / `list_*`
plus update helpers). They are imported directly by the routes and subsystems
that own the data; there is no shared store interface.

## Integration points

These stores are consumed across the backend — `app.py` routes, the runtime,
ELINS, DEWEY, and the acceptance harness. They depend only on the
`CLARITYOS_BACKEND` switch (and, for `incident_store`, the
`CLARITYOS_INCIDENT_STORE` path).

## Invariants

- The backend is resolved per call; changing `CLARITYOS_BACKEND` changes where
  every store reads and writes.
- Several stores enforce caps (`mesh_metadata` 8 devices / 16 KB,
  `elins_distribution` 500 entries) and size accounting (`size_bytes`).
- `elins_distribution_store` never persists raw scenario text — only a hashed
  `scenario_id`.

## Non-goals

These are persistence modules only — they hold no business logic, run no
reasoning, and expose no HTTP endpoints of their own.

## Fiction removed

None — these stores had no prior canon file; they are newly documented.
