# V34 Readiness — ELINS Forecast Engine (multi-primitive envelopes)

Status: ✅ Ready
Backend version: `3.0`
ELINS pipeline version: `elins.v34.1`
Forecast block version: `forecast.v34.1`
Build: `20260506600000`

---

## What v34 ships

A deterministic multi-primitive envelope engine that wraps the canonical
ELINS pipeline. Every `generate_ELINS` call now embeds a top-level
`forecast_engine` block alongside the existing 10 layers; three HTTP
surfaces let callers run the engine standalone, fetch a UI fixture, or
run+persist a full ELINS+forecast as a founder. Web cockpit and phone
both render the new surface with no external charting deps.

### Core math

```
ep(D+n) = ep0 * exp(-λ * n)
```

Per-primitive `λ` defaults are tuned (acute stress decays faster, drift
decays slowest). Same input → same output. No model calls, no random,
no clock dependency.

| Function | Returns | Notes |
| --- | --- | --- |
| `compute_envelope(primitive, days=5)` | `[ep(D+0)..ep(D+days)]` | single primitive |
| `compute_multi_envelope(primitives, days=5)` | `[ep(D+0)..ep(D+days)]` | magnitude-weighted average, normalized by Σ\|intensity\| |
| `compute_domain_envelope(domain_vector, primitives, days=5)` | `[ep(D+0)..ep(D+days)]` | weighted by domain vector contribution |
| `compute_chain_envelope(chain, days=5)` | `[ep(D+0)..ep(D+days)]` | sum of attenuated, decayed link contributions |

---

## Files added / changed

### New
- `ELINS/forecast_engine.py` — core math + builders + example payload
- `tests/test_v34_forecast_engine.py` — 32 tests
- `web/src/components/founder/forecast/PrimitiveEnvelopeChart.tsx`
- `web/src/components/founder/forecast/MultiEnvelopeChart.tsx`
- `web/src/components/founder/forecast/DomainEnvelopeChart.tsx`
- `web/src/components/founder/forecast/ChainEnvelopeChart.tsx`
- `web/src/components/founder/forecast/ForecastPanel.tsx`
- `phone/app/forecast.tsx`
- `phone/app/primitive_envelope.tsx`
- `phone/app/multi_envelope.tsx`
- `phone/app/domain_envelope.tsx`
- `phone/app/chain_envelope.tsx`
- `V34_READINESS.md` (this file)

### Modified
- `ELINS/__init__.py` — export `forecast_engine`
- `ELINS/standard_elins.py` — embed `forecast_engine` block; bump version to `elins.v34.1`; add to `LAYER_NAMES`
- `app.py` — new endpoints `/elins/forecast`, `/elins/forecast/example`, `/founder/elins/forecast/run`; bump backend version to `3.0`; advertise capability `elins_forecast`
- `web/src/lib/api.ts` — `V34ForecastBlock`, `V34DomainName`, `elinsForecast`, `elinsForecastExample`, `founderElinsForecastRun`; extend `V33ELINSObject.forecast_engine`
- `web/src/components/founder/ELINSInspector.tsx` — embed `<ForecastPanel block={obj.forecast_engine} />`
- `web/src/components/founder/FounderDashboard.tsx` — embed `<ForecastPanel />` (example mode)
- `phone/lib/api.ts` — same v34 types/helpers as web; extend `V33ELINSObject.forecast_engine`
- `phone/app/elins_inspector.tsx` — inline mini multi-envelope + link to `/forecast`
- `phone/app/_layout.tsx` — register `forecast` + `elins_inspector` stack screens
- `BUILD_VERSION` — `20260506600000`
- `tests/test_v28_endpoints.py` — health version `3.0`
- `tests/test_v33_founder_console.py` — version prefix `elins.v34`
- `membership_store.py` — strictly-monotonic transaction `ts` (fixes pre-existing v30 ordering flake on Windows)

---

## API surface

### `POST /elins/forecast` (auth, gated by `v28_surfaces`)
Request:
```json
{
  "primitives": [
    {"key": "pressure", "intensity": 0.85},
    {"key": "tension",  "intensity": 0.6, "lambda": 0.18}
  ],
  "chain": [{"key": "pressure", "intensity": 0.85, "attenuation": 1.0}, ...],
  "domains": ["Geopolitical", "Economic_Markets"],
  "days": 5
}
```
Response: `{ ok: true, forecast: V34ForecastBlock }`.

### `GET /elins/forecast/example` (public)
Returns the `Iran-style escalation chain` fixture for UI development.

### `POST /founder/elins/forecast/run` (founder only)
Runs the full ELINS pipeline + forecast, persists the run via
`elins_project.save_daily_run`, and returns the canonical ELINS object
(forecast embedded). `days` is configurable.

---

## UI

### Web
- `ForecastPanel` composes 4 charts into one card.
- All charts are pure SVG with design-token colors (`var(--os-...)`); no
  external charting library; no animation; mobile-friendly viewBoxes.
- Wired into `ELINSInspector` (renders after a preview run) and the
  `/founder` dashboard (defaults to the static example).

### Phone
- `forecast.tsx` is a single scrollable screen with all four charts.
- Charts use only React Native primitives (`<View>` bars), no SVG dep.
- `elins_inspector.tsx` renders the multi-envelope inline after a
  preview and links to `/forecast` for the full surface; an
  always-present link-out works even before the first run.

---

## Tests

```
tests/test_v34_forecast_engine.py — 32 tests, all pass
Full suite — 238 passed, 0 failed
```

Coverage:
- single primitive envelope (formula correctness, default λ, validation)
- multi-primitive envelope (weighting, normalization, zero-magnitude, decay)
- domain envelope (full-weight identity, 50/50 average, decay, zero-weight, negative-weight rejection)
- chain envelope (attenuation, default decreasing tuple, decay propagation, empty rejection, negative-attenuation rejection)
- determinism (single-fn + composite block + ELINS round-trip)
- ELINS integration (block presence, all spec domains present, chain when edges exist)
- endpoint validation: empty primitives 400, bad domain 400, v28 gate 403, founder gate 403, custom days
- UI API shape — top-level keys, primitive_envelopes shape, all 7 spec domain names, chain link structure

---

## Notes / follow-ups

- The static example labelled "Iran-style escalation chain" is the
  fixture the UI loads on first paint; replace with a more
  representative scenario when the founder console captures one.
- Per-primitive λ values in `DEFAULT_LAMBDAS` are the only tuning knob
  that changes envelope shapes; they're stable across deploys.
- v32–v33 surfaces are unchanged. The `forecast_engine` block is
  forward-compatible: clients that ignore it continue to work.
