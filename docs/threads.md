# Threads

## Purpose

Threads are persistent threaded conversations. Each user owns a set of threads;
each thread is a titled, ordered sequence of role-tagged messages.

## Implementation location

`threads_vault.py` (version `threads_vault.v51.1`; introduced v47). A thin layer
over the Memory Vault (`docs/memory_vault.md`) — it never bypasses the vault
API.

## Data model

Stored entirely as Memory Vault entries under the `threads` namespace:

- `threads.meta.{thread_id}` — a `ThreadMeta`: `thread_id` (a `uuid4` hex),
  `title`, `created_at` / `updated_at` (ms), `message_count`, `archived`,
  `summary` and `summary_ts_ms` (v50, kernel-generated, metadata-only), and
  `project_id` (v51, optional).
- `threads.messages.{thread_id}.{ts_ms}_{seq}` — a `Message`: `role`
  (`user` / `assistant` / `system`), `content`, `ts_ms`, `model`. `seq` is a
  6-digit zero-padded per-thread counter, so message keys sort lexically into
  chronological order.
- `threads.embeddings.{thread_id}.…` — reserved; no logic yet.

## APIs / entrypoints

`create_thread(user_id, title, *, project_id=None)` · `list_threads(user_id)`
(newest-first by `updated_at`) · `get_thread(user_id, thread_id)` →
`(meta, messages)` · `append_message(user_id, thread_id, message)` ·
`rename_thread` · `delete_thread` · `get_thread_meta` · `update_thread_summary`.

## Integration points

- **Memory Vault** — the sole persistence layer.
- **Intelligence kernel** — `summarize_thread` computes the v50 thread summary
  via `update_thread_summary`.
- **Projects** — a thread's optional `project_id` ties it to a project (see
  `docs/projects.md`).

## Invariants

- Persistence is vault-only; no thread state lives outside the Memory Vault.
- `KeyError` is raised for a missing thread (the app layer maps it to HTTP
  404); `ValueError` for malformed arguments (→ 400).
- `delete_thread` is idempotent and removes the meta, every message, and the
  reserved embedding keys.
- A `Message` role must be `user`, `assistant`, or `system`.

## Non-goals

Threads do not run reasoning or model calls themselves — that is the runtime
stack and the kernel. The `threads.embeddings.*` namespace is reserved but
unused.

## Fiction removed

None — this subsystem had no prior canon file; it is newly documented.
