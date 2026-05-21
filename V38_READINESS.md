# V38 Readiness — ELINS interactive dashboard

Status: ✅ Ready
Backend version: `3.4`
Snapshot version: `elins_dashboard.v38.1`
Build: `20260507000000`

---

## What v38 ships

A single composite snapshot of every ELINS surface (global daily run +
six regional runs + latest macro pass + entity-graph snapshot) plus a
new dashboard route on web and phone. The aggregator is pure with
respect to the persistence layer — same underlying state → same
snapshot — so the UI can refresh confidently and the snapshot can be
replayed for any historical date via `GET /elins/dashboard/{date}`.

The cockpit gets a "ELINS dashboard →" CTA in the header and the phone
home gets a prominent dashboard card. Founders see an additional
operational overview (`/founder/elins/dashboard/overview`) summarising
counts + per-region coverage + current scheduler config.

---

## Files added / changed

### New
- `elins_dashboard.py` — aggregator (`get_dashboard_snapshot`,
  `get_dashboard_for_date`, `get_founder_overview`).
- `tests/test_v38_elins_dashboard.py` — 20 tests.
- `web/src/components/dashboard/GlobalPanel.tsx`
- `web/src/components/dashboard/RegionalGrid.tsx`
- `web/src/components/dashboard/MacroSummary.tsx`
- `web/src/components/dashboard/EntitySummary.tsx`
- `web/src/components/dashboard/DashboardRoot.tsx` (orchestrator)
- `web/src/routes/Dashboard.tsx`
- `phone/app/dashboard.tsx`
- `phone/app/dashboard_global.tsx`
- `phone/app/dashboard_regional.tsx`
- `phone/app/dashboard_entities.tsx`
- `V38_READINESS.md` (this file)

### Modified
- `ELINS/elins_project.py` — `save_daily_run` now also stores the full
  ELINS object + `domain_scores` + `ep_field_summary` so the dashboard
  global section has forecast/domain/ESO data without a re-run.
- `app.py` — three new endpoints (`GET /elins/dashboard`,
  `GET /elins/dashboard/{date}`,
  `GET /founder/elins/dashboard/overview`); imports `elins_dashboard`;
  capability `elins_dashboard`; backend version `3.4`; root listing
  extended.
- `elins_scheduler.py` — `_make_run_id` now uses a per-process counter
  to keep run ids strictly monotonic (fixes a pre-existing v36 flake
  on Windows where back-to-back calls landed in the same millisecond).
- `web/src/lib/api.ts` — `V38DashboardSnapshot`, `V38DashboardSection`,
  `V38FounderOverview` + 3 helper calls.
- `web/src/App.tsx` — register `/dashboard` route under `RequireAuth`.
- `web/src/routes/Cockpit.tsx` — header CTA "ELINS dashboard →"
  (gated by `v28_surfaces`).
- `web/src/components/founder/FounderDashboard.tsx` — link to
  `/dashboard` in the page header.
- `phone/lib/api.ts` — same v38 types/helpers as web.
- `phone/app/_layout.tsx` — register `dashboard` + 3 drill-in stack
  screens.
- `phone/app/index.tsx` — prominent "ELINS dashboard →" card on home.
- `phone/app/founder.tsx` — `dashboard` shortcut at the top of the hub.
- `tests/test_v28_endpoints.py` — health version `3.4`.
- `BUILD_VERSION` — `20260507000000`.

---

## API surface

### `GET /elins/dashboard` (auth, gated by `v28_surfaces`)
Returns the latest interactive dashboard snapshot for the user. The
global section falls back to the scheduler's `system_user` when the
caller has never persisted a global run, so brand-new users still see
the system view.

### `GET /elins/dashboard/{date}` (auth, gated by `v28_surfaces`)
Snapshot pinned to `YYYY-MM-DD`. Validates the date format (10 chars,
4-2-2). Sections that have no run for that day report
`available: false`.

### `GET /founder/elins/dashboard/overview` (founder-only)
Operational summary:
```jsonc
{
  "latest_date":          "2026-05-06",   // from most recent macro run
  "macro_runs_count":     12,
  "entity_graph_snapshots": 12,
  "regional_coverage":    { "US": {"runs": 12, "latest_day": "2026-05-06"}, ... },
  "scheduler_config":     { ... }
}
```

---

## Snapshot shape

```jsonc
{
  "ts":   1715080800.123,
  "date": "2026-05-06",
  "global": {
    "scenario_id": "sc_…",
    "ep_mean": 0.123,
    "domains": { "geopolitical": 0.45, ... },
    "top_primitives": [{"key": "pressure", "intensity": 0.82}, ...],
    "forecast": [0.123, 0.105, 0.090, 0.077, 0.066, 0.057],
    "has_eso": false,
    "available": true,
    "user": "scheduler",
    "day": "2026-05-06"
  },
  "regional": { "US": {…}, "EU": {…}, "MEA": {…}, "APAC": {…}, "Markets": {…}, "Tech": {…} },
  "macro":    { "last_run_id": "macro_…_1", "last_run_ts": …, "ep_mean": 0.092,
                "regions_count": 6, "external_signal_mode": "cloud_perplexity" },
  "entity_graph": {
    "entity_count": 21, "edge_count": 27, "updated_ts": …,
    "top_entities": [
      {"name": "Federal Reserve rate path", "degree": 6, "ep_mean": 0.092,
       "top_domains": ["geopolitical", "institutional", "legal"]},
      ...
    ],
    "available": true
  },
  "version": "elins_dashboard.v38.1"
}
```

---

## UI

### Web (`/dashboard`)
- `DashboardRoot` orchestrator: composes `GlobalPanel` (full-width, EP
  + top primitives + domain bars + multi-envelope SVG forecast),
  `RegionalGrid` (6 tiles with per-region forecast spark), and a
  bottom row with `MacroSummary` + `EntitySummary`.
- Header has a manual "Refresh" button + ts indicator.
- Footer cross-links to `/elins` (cockpit feed) and `/founder`.
- Cockpit gets a "ELINS dashboard →" CTA next to the existing
  ELINS-feed link (gated by `v28_surfaces`).
- Founder console gets a prominent `→ Open ELINS dashboard` link in
  the page header.

### Phone (`/dashboard`)
- `dashboard.tsx` is the top-level pull-to-refresh card stack:
  global → regional grid → macro → entity-graph top entities.
- Drill-in screens: `dashboard_global.tsx` (full bars + forecast bars),
  `dashboard_regional.tsx` (6-tile list, tap-through to
  `regional_detail`), `dashboard_entities.tsx` (top-N entities,
  tap-through to `entity_detail`).
- Home `index.tsx` gains a prominent "ELINS dashboard →" card that
  routes to `/dashboard`.
- Founder hub gets `Dashboard` as the first shortcut.

---

## Tests

```
tests/test_v38_elins_dashboard.py — 20 tests, all pass
Full suite — 357 passed, 0 failed
```

Coverage:
- Empty-state snapshot (no global, no regional, no macro, no graph).
- After-global-only snapshot (regional empty).
- System-user fallback when caller has no runs.
- Full-coverage snapshot after a macro pass with ESO.
- Top-primitives sorted desc; forecast length matches the engine.
- Determinism modulo `ts` / `date`.
- `get_dashboard_for_date` validation (empty + bad format + slashes).
- Date pinning resolves the right day; other days report unavailable.
- `/elins/dashboard` shape + happy path + 403 gate.
- `/elins/dashboard/{date}` happy path + 400 on bad date + 403 gate.
- `/founder/elins/dashboard/overview` shape + counts + scheduler config
  + founder gate + empty-state.
- `/me` capabilities advertise `elins_dashboard`.
- UI shape lockdown for the global + entity_graph + macro sections.

---

## Notes / follow-ups

- The dashboard intentionally does not fan out per-section calls;
  one round-trip suffices for the cockpit. If the macro / entity-graph
  data outgrows in-memory aggregation, swap the backing reads for
  paginated queries inside `_macro_section` / `_entity_graph_section`.
- `save_daily_run` now writes the full ELINS payload as well — no
  read-side changes needed since the new fields are additive and
  ignored by older clients. The next destructive `_reset_memory_for_tests`
  hook runs the same as before.
- Pre-v38 surfaces (v28–v37) are unchanged; the dashboard is additive
  and gated by the existing `v28_surfaces` feature flag.
- Side fix: the `_make_run_id` per-process counter resolves the macro
  list flake we caught while running the v38 suite.
