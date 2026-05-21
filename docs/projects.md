# Projects

## Purpose

A project is a per-user grouping of threads with shared metadata — a name,
description, tags, an optional default and allowed model set, and a summary.

## Implementation location

`projects_vault.py` (version `projects_vault.v51.1`; introduced v51). Mirrors
`threads_vault.py` in shape and sits on the Memory Vault.

## Data model

Three Memory Vault entries per project, under the `projects` namespace:

- `projects.{project_id}.meta` — a `ProjectMeta`: `project_id`, `name`,
  `description`, `default_model`, `allowed_models`, `tags`, `created_at` /
  `updated_at`, `summary` / `summary_ts_ms`, `thread_count`.
- `projects.{project_id}.summary` — a `ProjectSummary` (`summary`, `ts_ms`).
- `projects.{project_id}.threads` — a denormalised list of member `thread_id`s.

`project_id` must match `^[A-Za-z0-9_-]{1,64}$`. Soft caps: name 200 chars,
description 4000, 32 tags (≤ 64 chars each), 5000 threads in the index.

## APIs / entrypoints

`create_project` (rejects a duplicate `project_id`) · `list_projects` ·
`get_project` · `update_project` · `update_project_summary` ·
`add_thread_to_project` (idempotent) · `remove_thread_from_project` ·
`list_project_threads` · `is_thread_in_project` · `delete_project`.

## Integration points

- **Memory Vault** — the sole persistence layer.
- **Threads** — the project's threads index records member `thread_id`s; a
  thread also carries its own `project_id` field.

## Invariants

- Persistence is vault-only.
- `KeyError` → HTTP 404 (project not found); `ValueError` → 400 (bad shape).
- `add_thread_to_project` / `remove_thread_from_project` are idempotent and
  keep `thread_count` in sync with the index.
- `delete_project` removes the project's three documents but **not** the member
  threads — those keep their `project_id` and become orphans (still readable by
  id; hidden when filtering by that project).

## Non-goals

Projects do not own or run threads; they index them. Deleting a project does
not delete its threads.

## Fiction removed

None — this subsystem had no prior canon file; it is newly documented.
