# ELINS Dashboard

## Purpose

`elins_dashboard` is a pure read-side aggregator that assembles a
unified, operator-facing snapshot of ELINS activity for a given user
and day. It merges:

- ELINS daily runs (global view)
- 6-region ELINS runs
- latest macro-pass summary
- entity-graph overlay
- continuity state from `operator_state`

The dashboard exposes this snapshot through two user routes and one
founder route. It performs **no writes**, **no LLM calls**, **no
model routing**, **no vault access**, and **no kernel coupling**. It
is a deterministic projection over upstream ELINS data.

## Implementation location

- **File:** `elins_dashboard.py` (single file, 378 lines).
- **Version:** `SNAPSHOT_VERSION = "elins_dashboard.v39.1"` (line 78).
- **Public exports:**
  - `get_dashboard_snapshot(user) -> dict`
  - `get_dashboard_for_date(user, date_str) -> dict`
  - `get_founder_overview() -> dict`
  - `SNAPSHOT_VERSION`
- **Private constants:** `_TOP_PRIMITIVES_LIMIT = 4`,
  `_TOP_ENTITIES_LIMIT = 6`.
- **No classes, no module state, no caching, no test reset hook.**
- **Module docstring is stale:** lines 18-62 document a 7-field
  snapshot shape and claim `"elins_dashboard.v38.1"`; the actual
  return shape is 8 fields (incl. `continuity`, added in v39) and
  the version constant is `v39.1`. The `SNAPSHOT_VERSION` constant
  is authoritative.

### Private helpers (15) — grouped by role

**Time / identity:**
- `_today_utc() -> str`
- `_user_day_id(user, day) -> str`

**Section skeleton:**
- `_empty_section() -> dict`

**Run-record extractors:**
- `_has_eso(run_record) -> bool`
- `_intensities_of(run_record) -> dict`
- `_domain_scores_of(run_record) -> dict`
- `_ep_mean_of(run_record) -> float`
- `_forecast_of(run_record) -> list[float]`

**Aggregators:**
- `_top_primitives(intensities, limit=_TOP_PRIMITIVES_LIMIT) -> list[dict]`
- `_section_from_run(run_record, *, day) -> dict`
- `_global_section(user, *, date_str=None) -> dict`
- `_regional_section(*, date_str=None) -> dict`
- `_macro_section() -> dict`
- `_entity_graph_section(*, top_n=_TOP_ENTITIES_LIMIT) -> dict`

**Snapshot orchestrator:**
- `_build_snapshot(user, *, date_str) -> dict`

## Data model

### Snapshot shape (8 top-level fields)

`_build_snapshot` returns:

```python
{
    "ts":           float,    # time.time()
    "date":         str,      # date_str or _today_utc() (YYYY-MM-DD)
    "global":       dict,     # global ELINS section (one run, with fallback)
    "regional":     dict,     # 6 regions, keyed by region code
    "macro":        dict,     # latest macro-pass summary (5 fields)
    "entity_graph": dict,     # latest entity-graph snapshot (5 fields)
    "continuity":   dict,     # operator_state.continuity_section(user)
    "version":      str,      # SNAPSHOT_VERSION
}
```

### Section shapes

**Empty section** (`_empty_section`, line 91-100) — the fallback
shape used whenever a run is missing:

```python
{
    "scenario_id":    None,
    "ep_mean":        0.0,
    "domains":        {},
    "top_primitives": [],
    "forecast":       [],
    "has_eso":        False,
    "available":      False,
}
```

**Filled section** (`_section_from_run`, line 166-185) — same 7
fields with values populated, plus `available=True`. The orchestrator
adds `day` to every section, and `_global_section` additionally adds
`user`.

**`global` section** — single run (NOT an aggregation). If the
caller has no global run for the day, falls back to the scheduler's
`system_user` run (line 203-211) so regular users still see "the
system view." `user` field reflects the actual source user (caller's
id, or `"scheduler"` after fallback).

**`regional` section** — dict keyed by region code, populated by
iterating `regional_elins.REGION_CODES`. Always 6 regions. Missing
regions get an `_empty_section` with `available=False`.

**`macro` section** (`_macro_section`, line 236-258) — exactly 5
fields:

```python
{
    "last_run_id":          str | None,
    "last_run_ts":          float | None,
    "ep_mean":              float | None,    # from constituent global run
    "regions_count":        int | None,
    "external_signal_mode": str | None,
}
```

Scheduler config is **not** part of this section — it appears in
`get_founder_overview`.

**`entity_graph` section** (`_entity_graph_section`, line 261-297) —
5 fields:

```python
{
    "entity_count": int,
    "edge_count":   int,
    "updated_ts":   float,
    "top_entities": [
        {"name": str, "degree": int, "ep_mean": float, "top_domains": [str, str, str]},
        ...
    ],   # capped at _TOP_ENTITIES_LIMIT (6)
    "available":    bool,
}
```

When no entity graph exists, returns the same shape with zeros, an
empty `top_entities`, and `available=False`.

**`continuity` section** — direct passthrough of
`operator_state.continuity_section(user)`. If that call raises, a
defensive fallback (lines 330-337) substitutes:

```python
{
    "last_topics":          [],
    "preferred_domains":    [],
    "preferred_regions":    [],
    "external_signal_mode": "cloud_only",
    "history_count":        0,
    "g_count":              0,
}
```

### Founder overview shape

`get_founder_overview` (line 353-378) returns:

```python
{
    "latest_date":            str | None,    # YYYY-MM-DD derived from macro_runs[0].ts
    "macro_runs_count":       int,
    "entity_graph_snapshots": int,
    "regional_coverage": {                   # per-region count + latest day
        <region>: {"runs": int, "latest_day": str | None},
        ...
    },
    "scheduler_config":       dict,          # full elins_scheduler_config.get_config()
    "version":                str,           # SNAPSHOT_VERSION
}
```

## APIs / entrypoints

### Public functions

- `get_dashboard_snapshot(user: str) -> dict` (line 303) — "today"
  snapshot. Raises `ValueError` on empty/non-string user.
- `get_dashboard_for_date(user: str, date_str: str) -> dict` (line
  309) — date-pinned snapshot. Raises `ValueError` on empty/non-string
  user or malformed `date_str` (must be 10 chars, `YYYY-MM-DD` form).
- `get_founder_overview() -> dict` (line 353) — founder-only
  operational summary (no user argument).

### HTTP routes

| Method | Path | Handler | Auth | Underlying fn |
|---|---|---|---|---|
| GET | `/elins/dashboard` | `elins_dashboard_latest` (app.py:10317) | `require_session` + `v28_surfaces` feature gate + rate-limit | `get_dashboard_snapshot(user)` |
| GET | `/elins/dashboard/{date}` | `elins_dashboard_for_date` (app.py:10336) | `require_session` + `v28_surfaces` feature gate | `get_dashboard_for_date(user, date)` |
| GET | `/founder/elins/dashboard/overview` | `founder_dashboard_overview` (app.py:10360) | `_require_founder` | `get_founder_overview()` |

### HTTP semantics

- **200** on success with response envelope `{"ok": True, "snapshot": <dict>}` (or `"overview"` for the founder route).
- **400** on `/elins/dashboard/{date}` when `date_str` is malformed (kernel `ValueError` → translated by `v29_hardening.raise_validation`).
- **403** on both user routes when the `v28_surfaces` feature flag is disabled for the caller (lines 10324-10330 and 10344-10350).
- **Rate-limited** only on `/elins/dashboard` via `v29_hardening.enforce_rate_limit(user, "/elins/dashboard")`.
- **No 5xx logic inside dashboard.** The dashboard function itself does not raise except for the `ValueError` cases above; any uncaught upstream exception would propagate, but every section builder degrades to an empty section rather than raising.

## Integration points

### Upstream stores / modules (read-only)

The dashboard calls **12 distinct upstream functions**:

- **`ELINS.elins_project`** (8 calls): `get_run`, `list_runs_for_user`, `load_regional_run`, `latest_regional_run`, `list_macro_runs`, `get_macro_run_with_constituents`, `load_latest_entity_graph`, `list_entity_graph_snapshots`, `list_regional_runs`
- **`ELINS.forecast_engine`** (1 call): `compute_forecast_block(intensities, edges, days=5)` — only invoked when a persisted run pre-dates v34 and lacks an embedded `forecast_engine.multi_envelope` block.
- **`ELINS.regional_elins`** (1 reference): `REGION_CODES` (used as the iteration set for the regional section).
- **`elins_scheduler_config`** (1 call): `get_config()` — for `_global_section`'s system-user fallback and for `get_founder_overview`'s scheduler block.
- **`operator_state`** (1 call): `continuity_section(user)` — read-only, with defensive Exception fallback.

### Imported but unused
- **`elins_entity_graph`** (line 72) is imported but never referenced in the module body. All entity-graph data flows through `elins_project.load_latest_entity_graph()`. The import can be safely removed — flagged as a small code-side cleanup, not a behavior issue.

### No coupling to
- `intelligence_kernel` — no kernel imports or calls
- `model_router` — no model selection, no provider dispatch
- `memory_vault` — no vault reads or writes
- LLM SDKs — no `openai`, `anthropic`, etc.
- File system — no `open()`, no `Path.read_text()`
- Network — no `urllib`, `requests`, `socket`

### Logging
Logger declared at line 76 (`clarityos.elins_dashboard`) but **never invoked** anywhere in the module. Cleanup candidate — either pin a single log line at snapshot completion or remove the declaration.

### Tests
- **`tests/test_v38_elins_dashboard.py`** — primary test file (v38 introduction).
- **`tests/test_elins_timeline_dashboard.py`** — likely coupled (date-pinned behavior).
- 12 other `test_elins_*` files match the grep but their names suggest they target ELINS internals (run drift, scoring, regression-compare, persistence). Classification deferred to PASS-5 if pursued.

## Invariants

1. **Pure read-side.** No writes to any store. No `operator_state` writes, no vault access, no kernel calls, no `model_router`, no LLM, no file I/O.
2. **Stable 8-field snapshot.** `_build_snapshot` always returns dict keys `ts`, `date`, `global`, `regional`, `macro`, `entity_graph`, `continuity`, `version`.
3. **Global-section system-user fallback.** If the caller has no global run for the day, `_global_section` falls back to the scheduler's `system_user` run. The returned section's `user` field reflects the actual source.
4. **Regional section always 6 regions.** Iteration is over `regional_elins.REGION_CODES`; missing regions get an `_empty_section` with `available=False`.
5. **Macro section is 5 fields.** Exactly `{last_run_id, last_run_ts, ep_mean, regions_count, external_signal_mode}`. Scheduler metadata is NOT included here.
6. **Entity-graph cap.** Top entities capped at `_TOP_ENTITIES_LIMIT` (6); each top-domain list capped at 3.
7. **Continuity defensive fallback.** If `operator_state.continuity_section(user)` raises, the snapshot substitutes a deterministic empty-continuity dict.
8. **Forecast always a list.** `_forecast_of` returns `[]` when neither the embedded `multi_envelope` nor `forecast_engine.compute_forecast_block` produces values.
9. **Date-format validation.** `get_dashboard_for_date` enforces exactly 10 chars, `YYYY-MM-DD` form; HTTP layer translates the `ValueError` to 400.
10. **Feature-gated user routes.** Both `/elins/dashboard` and `/elins/dashboard/{date}` return 403 when `v28_surfaces` is disabled.
11. **Version field.** `version` always equals `SNAPSHOT_VERSION`.

## Non-goals

`elins_dashboard` is **not**:

- a kernel reasoning mode — no kernel imports
- a multi-run aggregator — `global` section is one run, not a fold
- a persistence layer — nothing is stored
- a router or LLM surface — no model dispatch
- an ELINS computation engine — only reads persisted ELINS records
- a vault consumer — does not import `memory_vault`
- a state mutator — purely read-side
- a streaming or paginated endpoint — single round-trip, complete snapshot

## Fiction removed

The following constructs are explicitly not present and must not be
inferred:

- **No multi-run aggregation in `global`.** `_global_section` selects exactly one run (caller's latest, or system-user's run as fallback).
- **No scheduler metadata in `macro` section.** `_macro_section` returns 5 fields; scheduler config appears only in `get_founder_overview`.
- **No LLM call anywhere.** Zero `model_router` imports.
- **No operator_state or vault writes.** Only `continuity_section` is read.
- **No kernel coupling.** Neither side imports the other.
- **No file I/O.** Inline computation only.
- **No use of `elins_entity_graph` module despite the import.** All entity-graph data flows through `elins_project.load_latest_entity_graph()`. The import is dead code.
- **No logging output despite the logger declaration.** The logger at line 76 is declared but never invoked.
- **No retry, no caching, no background work.** Every call recomputes the snapshot fresh.
- **No 5xx surface from dashboard.** The only kernel-raised exception is `ValueError` for bad input, which HTTP translates to 400.

Only the behaviour, fields, and integrations described in this
document are present in the code.
