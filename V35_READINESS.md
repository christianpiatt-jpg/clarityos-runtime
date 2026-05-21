# V35 Readiness — Regional ELINS Modules + ESO-aware regional fields

Status: ✅ Ready
Backend version: `3.1`
Regional ELINS version: `elins.regional.v35.1`
Perplexity Oracle version: `perplexity_oracle.v35.1`
Build: `20260506700000`

---

## What v35 ships

A region-aware wrapper around the canonical ELINS pipeline that produces
six pre-tuned basin views (US / EU / MEA / APAC / Markets / Tech).
Each pass blends an entity bump, a domain-weighting overlay, and a
λ overlay routed through the v34 forecast engine. When the user opts
in via `external_signal_mode == "cloud_perplexity"`, an External
Signal Object (ESO) from `perplexity_oracle` is merged in as an
"external" primitive class and surfaced explicitly on the synthesis
record. The pipeline remains pure with respect to its inputs — the ESO
provider is a deterministic mock until a real Perplexity backend is
wired.

---

## Files added / changed

### New
- `perplexity_oracle.py` — deterministic ESO fetcher (mock today, drop-in
  for a real Perplexity provider via `CLARITYOS_PERPLEXITY_API_KEY`)
- `ELINS/regional_elins.py` — `run_regional_elins`, `REGION_PROFILES`,
  ESO merging, dependent-layer recompute
- `tests/test_v35_regional_elins.py` — 32 tests
- `web/src/components/founder/regional/RegionalSelector.tsx`
- `web/src/components/founder/regional/RegionalSummaryPanel.tsx`
- `web/src/components/founder/regional/RegionalForecastPanel.tsx`
- `web/src/components/founder/regional/RegionalMapStub.tsx`
- `web/src/components/founder/regional/RegionalPanel.tsx`
- `phone/app/regional.tsx`
- `phone/app/regional_detail.tsx`
- `phone/app/regional_forecast.tsx`
- `V35_READINESS.md` (this file)

### Modified
- `ELINS/__init__.py` — export `regional_elins`
- `ELINS/elins_project.py` — `_REGIONAL_COLL`, `_MEM_REGIONAL`,
  `save_regional_run`, `load_regional_run`, `latest_regional_run`,
  `list_regional_runs`; `_reset_memory_for_tests` now wipes regional
- `app.py` — three new endpoints (`POST /elins/regional/run`,
  `GET /elins/regional/list`, `POST /founder/elins/regional/batch`);
  ESO resolver `_resolve_eso_for`; backend version `3.1`; capability
  `elins_regional`
- `web/src/lib/api.ts` — `V35RegionCode`, `V35RegionalELINS`,
  `V35RegionalListItem`, `V35ExternalSignals`, `elinsRegionalRun`,
  `elinsRegionalList`, `founderElinsRegionalBatch`
- `web/src/components/founder/ELINSInspector.tsx` — Scenario / Regional
  tab toggle; Regional tab embeds `RegionalPanel`
- `web/src/components/founder/FounderDashboard.tsx` — embed
  `RegionalPanel` as full-width row
- `phone/lib/api.ts` — same v35 types/helpers as web
- `phone/app/_layout.tsx` — register `regional`, `regional_detail`,
  `regional_forecast` stack screens
- `phone/app/elins_inspector.tsx` — link to `/regional`
- `BUILD_VERSION` — `20260506700000`
- `tests/test_v28_endpoints.py` — health version `3.1`

---

## API surface

### `POST /elins/regional/run` (auth, gated by `v28_surfaces`)
Request:
```json
{ "region_code": "MEA", "topic_hint": "Gulf shipping disruption" }
```
Behaviour:
- Validates `region_code` against the six supported codes.
- Resolves ESO server-side: if `users_store.get_user(user).external_signal_mode == "cloud_perplexity"`, fetches via `perplexity_oracle.fetch_basin_signals(region_code)`; otherwise ESO is `None`.
- Calls `regional_elins.run_regional_elins`, persists via
  `elins_project.save_regional_run` (today’s date, idempotent).
- Returns `{ ok, run_id, region_code, elins, eso_present }`.

### `GET /elins/regional/list` (auth)
Returns the six supported region codes plus, for each, the latest
saved-run summary or `null`. Lightweight metadata only — no forecast
arrays.

### `POST /founder/elins/regional/batch` (founder only)
Runs and persists multiple regions in one call.
Request:
```json
{ "regions": ["US", "EU", "Markets"], "topic_hint": "yield curve" }
```
Returns `{ ok, results: { region_code: ELINS_object }, run_ids: { region_code: run_id } }`.

---

## ESO contract

```
{
  "region_code": str,
  "signals":  [ {"key", "intensity", "weight", "source", "anchor"}, ... ],
  "anchors":  [ str, ... ],
  "domain_bias": { domain_key: float, ... },
  "fetched_at": float,
  "version":  "perplexity_oracle.v35.1",
  "mock":     true,
  "user":     str | None
}
```

When merged into a regional ELINS run:
- Each ESO signal additively bumps the matching primitive intensity
  (capped at 1.0). Aggregated bumps are recorded under
  `elins.external_signals.contributions`.
- ESO `domain_bias` is added on top of the lexical domain mapping.
- Anchors are listed under `elins.synthesis.external_anchors` and
  `elins.external_signals.anchors`; `elins.synthesis.external_present`
  flips to `true`.

Default mode is OFF. Users opt in by setting
`users_store.get_user(user)["external_signal_mode"] = "cloud_perplexity"`.

---

## Persistence

`elins_project.save_regional_run(region_code, day, elins_object)` writes
to `_MEM_REGIONAL` (memory backend) or the `elins_project_regional`
Firestore collection. Document id: `{region_code}_{day}`. Mapping
mirrors the spec layout:

```
elins_project/
  regional/
    US/2026-05-06.json
    EU/2026-05-06.json
    MEA/2026-05-06.json
    APAC/2026-05-06.json
    Markets/2026-05-06.json
    Tech/2026-05-06.json
```

`load_regional_run`, `latest_regional_run`, `list_regional_runs` round
out the read API. Same-day re-saves overwrite (idempotent).

---

## UI

### Web
- `RegionalPanel` composes selector + map-stub + summary + forecast
  views into a single full-width section, wired into both
  `FounderDashboard` and a new `Regional` tab on `ELINSInspector`.
- All charts re-use the v34 `ForecastPanel` and its 4 SVG
  sub-components — no new external dependencies.
- ESO presence shows as a focus-cyan pill ("ESO mock" / "ESO live")
  next to the region header.

### Phone
- Three new screens: `regional` (grid of regions + latest), `regional_detail`
  (per-region run + summary + ESO anchors), `regional_forecast` (per-region
  multi/primitive/domain/chain charts).
- `elins_inspector` gains a link to `/regional`.

---

## Tests

```
tests/test_v35_regional_elins.py — 32 tests, all pass
Full suite — 270 passed, 0 failed
```

Coverage:
- perplexity_oracle: ESO shape per region, unknown region rejection,
  off-mode returns None, `is_eso_enabled` only true for `"cloud_perplexity"`,
  determinism.
- regional_elins: run for each region, ESO marks external,
  no-ESO synthesis stays clean, topic hint flows into input,
  ESO never lowers a primitive intensity, unknown region rejection,
  full-pipeline determinism, `previous_run` produces `regional_delta`.
- elins_project: save/load/latest/list regional runs, idempotent same-day
  save, unknown region rejection.
- Endpoints: `/elins/regional/run` shape + persistence + ESO
  conditional + region rejection + v28 gate; `/elins/regional/list`
  shape + reflects runs; `/founder/elins/regional/batch` multi-run +
  founder gate + empty/unknown rejection.
- UI shape: full top-level keys + external_signals/synthesis lock-down.

---

## Notes / follow-ups

- The Perplexity provider is mocked. Wire the real call in
  `perplexity_oracle.fetch_basin_signals` behind the
  `_cloud_provider_active()` flag once the API integration is approved.
- `region_code` and `topic_hint` flow through to the persisted run for
  later replay. The full ELINS payload is stored alongside the summary
  to support exact reconstruction.
- v34 forecast / v33 ELINS / v32 waitlist / v31 billing / v30
  membership surfaces are all unchanged. The new `external_signals`,
  `regional_delta`, and `region_code` fields are forward-compatible:
  pre-v35 clients ignore them.
