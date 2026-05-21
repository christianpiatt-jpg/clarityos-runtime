# V36 Readiness — Macro-ELINS automation + scheduled global/regional runs

Status: ✅ Ready
Backend version: `3.2`
Build: `20260506800000`

---

## What v36 ships

A scheduler that runs the global ELINS pass plus all six regional ELINS
in a single tick, persists every constituent + a macro-run summary, and
honours an ESO mode toggle for the synthetic system user. Cadence is
config-driven (off / daily / 3x_week / weekly) and re-read every tick so
the founder can change it at runtime without restarting the process.
The thread is opt-in via the config store, idempotent on re-boot, and
stoppable for tests.

---

## Files added / changed

### New
- `elins_scheduler.py` — daemon-thread scheduler + `_run_macro_elins_once`
  test hook + cadence gating + ESO resolution.
- `elins_scheduler_config.py` — tiny key/value config store (memory +
  Firestore) with validated cadence/signal-mode enums.
- `tests/test_v36_macro_elins.py` — 30 tests.
- `web/src/components/founder/macro/MacroRunsList.tsx`
- `web/src/components/founder/macro/MacroRunDetail.tsx`
- `web/src/components/founder/macro/MacroSchedulerConfig.tsx`
- `web/src/components/founder/macro/MacroPanel.tsx` (composite)
- `phone/app/macro_runs.tsx`
- `phone/app/macro_run_detail.tsx`
- `phone/app/macro_scheduler_config.tsx`
- `V36_READINESS.md` (this file)

### Modified
- `ELINS/elins_project.py` — `_MACRO_COLL`, `_MEM_MACRO`,
  `record_macro_run`, `list_macro_runs`, `get_macro_run`,
  `get_macro_run_with_constituents`; reset hook clears the macro store.
- `app.py` — five new founder endpoints (status, config, run_now,
  runs list, run detail); imports `elins_scheduler` +
  `elins_scheduler_config`; lazy boot from config on startup
  (gated by `CLARITYOS_DISABLE_MACRO_SCHEDULER` for tests); backend
  version `3.2`; root-endpoint listing extended.
- `web/src/lib/api.ts` — `V36SchedulerConfig`, `V36SchedulerStatus`,
  `V36MacroRun`, `V36MacroRunDetail`, plus 5 helper calls.
- `web/src/components/founder/FounderDashboard.tsx` — embed
  `MacroPanel` as a full-width row.
- `web/src/components/founder/ELINSInspector.tsx` — pulls latest macro
  run on mount and renders a single info line above the tabs.
- `phone/lib/api.ts` — same v36 types/helpers as web.
- `phone/app/_layout.tsx` — register `macro_runs`,
  `macro_run_detail`, `macro_scheduler_config` stack screens.
- `phone/app/founder.tsx` — link to `/regional` (v35) and `/macro_runs`
  (v36).
- `tests/conftest.py` — reset hooks for `elins_scheduler_config` +
  `elins_scheduler._reset_for_tests`; `CLARITYOS_DISABLE_MACRO_SCHEDULER=1`
  in the default test env so import-time scheduler boot is suppressed.
- `tests/test_v28_endpoints.py` — health version `3.2`.
- `BUILD_VERSION` — `20260506800000`.

---

## API surface

### `GET /founder/elins/scheduler/status` (founder)
Returns `{ ok, config, running, tick_seconds, valid_cadences,
valid_signal_modes }`.

### `POST /founder/elins/scheduler/config` (founder)
Accepts any subset of `{ enabled, cadence, external_signal_mode }`. The
endpoint validates against the config store's enum tuples, persists
the change, and lazily starts/stops the daemon thread to match the new
`enabled` flag.

### `POST /founder/elins/macro/run_now` (founder)
Bypasses the cadence gate and runs the macro pass immediately. Returns
the same summary the background loop would have logged
(`ran, run_id, ts, regions, region_run_ids, global_run_id,
external_signal_mode, cadence, macro_record`).

### `GET /founder/elins/macro/runs` (founder)
Returns the most recent `limit` macro runs (default 20, max 200), newest
first. Each row is the macro-run summary record.

### `GET /founder/elins/macro/run/{run_id}` (founder)
Returns the macro-run record plus its constituent global run + regional
runs (full ELINS objects under `regional_runs[<region_code>]`). 404
when the run id is unknown.

---

## Scheduler configuration

```
{
  enabled:               bool         default False
  cadence:               "off" | "daily" | "3x_week" | "weekly"  default "3x_week"
  external_signal_mode:  "cloud_only" | "cloud_perplexity"        default "cloud_only"
  system_user:           str          default "scheduler"
  last_run_ts:           float        default 0.0
}
```

Cadence intervals (seconds between passes):
- `off`     → never due
- `daily`   → 24 h
- `3x_week` → 56 h (Mon/Wed/Fri pattern)
- `weekly`  → 168 h

Tick frequency is `CLARITYOS_MACRO_TICK_SECONDS` (default 300 s). Each
tick reads the config and gates on `_is_due(cfg, now)`; non-due ticks
are no-ops.

---

## Persistence

- Each macro pass writes:
  - one global daily run via `elins_project.save_daily_run(system_user, …)`
  - six regional runs via `elins_project.save_regional_run(region, today, …)`
  - one macro-run summary via `elins_project.record_macro_run(run_id, ts, regions, global_run_ref, region_run_ids, external_signal_mode, notes)`
- `record_macro_run` stores under `elins_project_macro_runs` (`_MEM_MACRO`
  in memory mode), keyed by `run_id` (`macro_<ms_ts>`).
- `get_macro_run_with_constituents` resolves the global run by id and
  the regional runs by `(region, day)` derived from each
  `region_run_ids[region]`.

Logical layout (mirrors the rest of `elins_project/`):

```
elins_project/
  macro_runs/
    macro_1714998000000.json
    macro_1715005200000.json
    ...
```

---

## Startup integration

`app.py` reads the scheduler config at import time (after all stores are
ready) and calls `elins_scheduler.start_elins_scheduler()` if
`enabled` is true. The `start_…` function is idempotent (one daemon per
process); `stop_…` signals the loop's `Event` to exit so tests can run
without leaking real threads. `CLARITYOS_DISABLE_MACRO_SCHEDULER=1` in
the test env keeps the daemon dormant and lets tests drive
`_run_macro_elins_once` synchronously.

---

## Tests

```
tests/test_v36_macro_elins.py — 30 tests, all pass
Full suite — 300 passed, 0 failed
```

Coverage:
- `_run_macro_elins_once` runs global + all regions, persists, records
  macro-run; respects ESO mode (`cloud_only` vs `cloud_perplexity`);
  updates `last_run_ts`.
- Cadence gating: `off` and `disabled` never due; first run due;
  within-interval not due; after-interval due; non-forced
  `_run_macro_elins_once` skips when not due and runs when due.
- `record_macro_run` / `list_macro_runs` / `get_macro_run` /
  `get_macro_run_with_constituents` — round-trip + ordering + missing
  + constituent resolution.
- All five founder endpoints — happy path, founder gate (403),
  validation errors (bad cadence / bad signal mode / 404 run detail),
  config persistence, enabled-flag lazy-boots/stops the daemon.
- UI shape lockdown for `run_now` summary + `run/{run_id}` detail.
- Determinism: regions list and ESO mode are stable across consecutive
  passes.

---

## Notes / follow-ups

- The "Mon/Wed/Fri 14:00 UTC" pattern is enforced via interval (~56 h)
  rather than wall-clock cron parsing. If exact day-of-week scheduling
  becomes a requirement, swap `_is_due` for a cron-parse implementation
  while keeping the same surface.
- The scheduler thread re-reads the config every tick, so toggling
  `enabled` mid-tick works without a restart. The `start/stop`
  endpoints are still useful when the founder wants the change to take
  effect immediately rather than at the next tick boundary.
- `external_signal_mode == "cloud_perplexity"` currently triggers the
  deterministic mock (v35). Wiring real Perplexity through is a single
  branch in `perplexity_oracle.fetch_basin_signals` — no v36 surface
  changes required.
- Pre-v36 surfaces (v28–v35) are unchanged. The new `forecast_engine`
  block + `external_signals` + macro-run records are
  forward-compatible with older clients.
