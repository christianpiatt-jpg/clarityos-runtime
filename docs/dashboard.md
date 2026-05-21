# Dashboard

## Purpose

Dashboard is the backend read-only aggregation subsystem. It composes one
deterministic snapshot from the persisted ELINS surfaces — the global daily
run, the six regional runs, the latest macro pass, and the latest entity-graph
snapshot — plus an operator-state continuity slice, so the cockpit (and any
other consumer) can render the full intelligence picture in a single
round-trip. It is pure with respect to the persistence layer: it reads,
shapes, and composes; it computes no intelligence of its own.

## Implementation location

Repo-root module `elins_dashboard.py` — the ELINS interactive dashboard
aggregator (introduced v38; `SNAPSHOT_VERSION = "elins_dashboard.v39.1"`). The
three backend endpoints are in `app.py`. The entity-graph section is read
through `ELINS.elins_project`. The other dashboard-named modules
(`elins_timeline_dashboard.py`, `elins_run_dashboard.py`,
`acceptance_dashboard.py`, and the legacy engine dashboards) are separate
subsystems and not part of this doc.

## Data model

- **Snapshot** — what `get_dashboard_snapshot` / `get_dashboard_for_date`
  return: `{ts, date, global, regional, macro, entity_graph, continuity,
  version}`.
- **`global`** — a *section* for the user's latest (or for-date) global ELINS
  run. A section is `{scenario_id, ep_mean, domains, top_primitives (up to 4),
  forecast, has_eso, available, day}`; `global` also carries `user`. When the
  caller has no global run of their own, `global` falls back to the
  scheduler's `system_user` run.
- **`regional`** — a map of the six region codes
  (`ELINS.regional_elins.REGION_CODES`) to a section each.
- **`macro`** — the latest macro pass: `{last_run_id, last_run_ts, ep_mean,
  regions_count, external_signal_mode}`.
- **`entity_graph`** — `{entity_count, edge_count, updated_ts, top_entities
  (up to 6), available}`.
- **`continuity`** — the v39 operator-state slice (`last_topics`,
  `preferred_domains`, `preferred_regions`, `external_signal_mode`,
  `history_count`, `g_count`).
- **`version`** — `SNAPSHOT_VERSION`, currently `elins_dashboard.v39.1`.
- **Missing data is not an error** — an absent run yields an empty section
  (`available: false`, zeroed fields); a missing entity graph yields an empty
  `entity_graph` block. A date snapshot pins every section to a `YYYY-MM-DD`;
  the plain snapshot uses the most-recent persisted run per surface.
- The founder overview (`get_founder_overview`) is a different shape:
  `{latest_date, macro_runs_count, entity_graph_snapshots, regional_coverage,
  scheduler_config, version}`.

## APIs / entrypoints

- `GET /elins/dashboard` — the latest snapshot for the caller; `require_session`,
  gated by the `v28_surfaces` feature flag (403 when disabled), rate-limited.
  Returns `{ok: true, snapshot}`.
- `GET /elins/dashboard/{date}` — a snapshot pinned to `date` (`YYYY-MM-DD`);
  same gating. A malformed date raises `ValueError`, which the handler maps to
  a 400 (`bad_input`).
- `GET /founder/elins/dashboard/overview` — founder-only; returns `{ok: true,
  overview}` (macro-run count, entity-graph snapshot count, per-region
  coverage, scheduler config).
- Module functions: `get_dashboard_snapshot(user)`,
  `get_dashboard_for_date(user, date_str)`, `get_founder_overview()`, and the
  `SNAPSHOT_VERSION` constant. `get_dashboard_snapshot` raises `ValueError` on
  an empty `user`; `get_dashboard_for_date` also raises `ValueError` on a
  malformed `date_str`.

## Integration points

- **`ELINS.elins_project`** — the persistence layer; the dashboard calls only
  its *read* functions (`get_run`, `list_runs_for_user`, `load_regional_run`,
  `latest_regional_run`, `list_regional_runs`, `list_macro_runs`,
  `get_macro_run_with_constituents`, `load_latest_entity_graph`,
  `list_entity_graph_snapshots`).
- **`ELINS.forecast_engine`** — `compute_forecast_block`, used only as a
  fallback to recompute a run's multi-envelope when a persisted record
  pre-dates the embedded v34 forecast block.
- **`ELINS.regional_elins`** — `REGION_CODES`, the six regional keys.
- **`elins_scheduler_config`** — `get_config()`, for the `system_user`
  fallback and the founder overview's `scheduler_config`.
- **`operator_state`** — `continuity_section(user)` supplies the continuity
  slice; the call is wrapped in `try` / `except` so a failure degrades to an
  empty continuity dict rather than failing the snapshot.
- **Consumers** — the cockpit's `/dashboard` web route (and any other client)
  via the `/elins/dashboard*` endpoints.

## Invariants

- **Read-only** — the dashboard calls only read functions; it writes to no
  store and mutates no state.
- **No model calls, no network** — per the module contract.
- **Deterministic with respect to the persistence layer** — the same persisted
  data yields the same snapshot.
- **Stable composite shape** — every call returns the full `{ts, date, global,
  regional, macro, entity_graph, continuity, version}` dict.
- **Missing-data tolerant** — absent runs become empty sections
  (`available: false`); a failing continuity call degrades to an empty dict; a
  missing forecast block is recomputed.
- **Safe to call at any time** — a pure read with no side effects; it raises
  `ValueError` only on a bad `user` argument or a malformed `date_str`.

## Non-goals

- Dashboard is **not** a scheduler, a router, or a DEWEY / Markov / continuity
  engine — it reads what those subsystems persisted.
- It is **not** a forecasting engine — it surfaces the `forecast` produced by
  `ELINS.forecast_engine`, and only recomputes via it as a fallback for legacy
  records.
- It is not a memory system, the Cockpit, or a frontend component, and it has
  no autonomous or "intelligent" behavior.
- It is not the other dashboard-named modules — `elins_timeline_dashboard.py`,
  `elins_run_dashboard.py`, `acceptance_dashboard.py`, and the legacy engine
  dashboards are separate.

## Fiction removed

An "autonomous dashboard", a "Dashboard AI", and a "predictive dashboard
engine" do not exist — `elins_dashboard.py` is a deterministic read-only
aggregator with, in its own words, "no network, no model". The "State Engine
panel", "Drift indicator", and "Layer pipeline panel" are cockpit-era design
fictions (already recorded in `docs/cockpit/cockpit_spec.md`) and are absent
here too. There is no backend `/dashboard` route — `/dashboard` is the web
(frontend) route; the backend endpoints are `/elins/dashboard`,
`/elins/dashboard/{date}`, and `/founder/elins/dashboard/overview`.
