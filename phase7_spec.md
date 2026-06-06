# Phase 7 — Drift & Trust-Center Telemetry (Spec)

**Status:** Implemented (spec + Python slice, Card 7.0)
**Surfaces:** Backend (Python). TS consoles consume this in a later card.

Phase 7 consumes Phase 6 output (`SuperstructureState`) and turns a stream of
snapshots into **drift**, **coherence-health**, and **trust-band** signals over
time. This card is the spec plus a first, in-memory Python slice. It is
additive and **does not touch** the CI-gated runtime spine (`app.py`,
`intelligence_kernel.py`, `model_router.py`, `operator_state.py`,
`memory_vault.py`, `runtime_privacy.py`).

---

## Inputs

- **`SuperstructureState`** — the Phase 6 contract from `phase6_contracts.py`,
  composed of five sub-states. Phase 7 reads:
  - **13 numeric signals** (each produced by Phase 6 in `[0, 1]`):
    `pattern.{pattern_strength, pattern_stability, pattern_coherence}`,
    `integration.{integration_strength, cross_layer_alignment}`,
    `coherence.{coherence_level, drift_resistance, load_resilience}`,
    `essence.{essence_signal, essence_clarity}`,
    `identity.{identity_strength, identity_stability, identity_projection}`.
  - **3 identity anchors** (categorical labels):
    `pattern.dominant_pattern`, `essence.invariant_identity`,
    `identity.operator_identity`.
    (The composite `*_identity` strings are intentionally *not* used as
    anchors — they embed the numeric values and would double-count
    quantitative movement.)
- **`timestamp: float`** — supplied by the caller. Phase 7 never reads a
  wall-clock.

---

## Core concepts

### DriftScore — `compute_drift(prev, curr) -> float` in `[0, 1]`

How much Phase 6 identity moved between two snapshots. A blend of quantitative
and qualitative movement:

- `numeric_drift` = mean absolute difference across the 13 numeric signals
  (each in `[0, 1]`, so the mean is in `[0, 1]`).
- `label_drift` = fraction of the 3 identity anchors that changed.

```
drift = DRIFT_NUMERIC_WEIGHT * numeric_drift + DRIFT_LABEL_WEIGHT * label_drift
```

with `DRIFT_NUMERIC_WEIGHT = 0.7`, `DRIFT_LABEL_WEIGHT = 0.3` (sum `1.0`, so the
result is already in range; it is clamped defensively). `0.0` ⇒ identical
snapshots; `1.0` ⇒ every numeric signal moved the full range *and* every anchor
changed.

### CoherenceHealth — `compute_coherence_health(history) -> float` in `[0, 1]`

A rolling view of coherence / essence / identity. For each snapshot a single
`coherence_signal` is the mean of nine fields (`pattern_coherence`, the three
`coherence.*` fields, the two `essence.*` magnitude fields, and the three
`identity.*` magnitude fields). `coherence_health` is the equal-weighted mean of
those per-snapshot signals across the history.

- An **empty** history returns `0.0` (no established health).
- Movement over time is measured separately by `DriftScore`, so health does not
  re-penalise it. **Recency weighting is a deliberate future refinement** (this
  slice uses an equal-weighted mean).

### TrustBand — `compute_trust_band(drift, coherence) -> str`

Derived from a snapshot's drift and the rolling coherence:

```
trust_score = coherence * (1 - drift)        # inputs clamped to [0, 1]

trust_score >= TRUST_HIGH_THRESHOLD   (0.66)  -> "HIGH"
trust_score >= TRUST_MEDIUM_THRESHOLD (0.33)  -> "MEDIUM"
otherwise                                     -> "LOW"
```

Trust rises with coherence and falls as drift grows; maximal drift collapses any
coherence to `LOW`.

---

## Storage model

Telemetry is an **append-only**, **per-operator**, **non-gated** channel —
explicitly **not** the encrypted/privacy-gated vault or `operator_state`.
`phase7_telemetry.py` computes the metrics; `phase7_storage.py` persists them
behind two interchangeable backends.

### Backends (`phase7_storage.py`)

- **`JsonlTelemetryStore` (durable default)** — append-only JSONL log, one file
  per operator at `<root>/<operator_id>.jsonl` (root defaults to
  `data/telemetry/`). Each `append_record` writes one sorted-keys JSON line and
  never rewrites or deletes existing lines. The root directory is created on
  first append (idempotent — the only side effect); reading an absent operator
  yields `[]`. Operator ids are validated as safe single-segment filenames
  (`[A-Za-z0-9_.-]{1,128}`, excluding `.` / `..`).
- **`MemoryTelemetryStore`** — in-memory mirror of Phase 7.0, selected
  automatically when `TESTING=1` (so the suite never writes durable files).

Both implement the same interface:

```python
append_record(operator_id: str, record: TelemetryRecord) -> None
load_history(operator_id: str, limit: int | None = None) -> list[TelemetryRecord]
```

Records are JSON-serialisable and round-trip cleanly: `record_to_json` /
`record_from_json` (and `record_to_dict` / `record_from_dict`) reconstruct the
nested `SuperstructureState` exactly. `limit` semantics: `None` ⇒ all; `> 0` ⇒
most-recent N; `<= 0` ⇒ `[]` — always a fresh list, so callers cannot mutate
stored state.

### `TelemetryRecord` (dataclass, defined in `phase7_storage.py`)

| field              | type           | notes                                            |
| ------------------ | -------------- | ------------------------------------------------ |
| `timestamp`        | `float`        | caller-supplied                                  |
| `superstructure`   | `SuperstructureState` | the Phase 6 snapshot                      |
| `drift`            | `float \| None`| `None` for an operator's first snapshot          |
| `coherence_health` | `float \| None`| rolling value *including* this snapshot          |
| `trust_band`       | `str \| None`  | `"LOW" \| "MEDIUM" \| "HIGH"`                     |

- **Per-operator**, not global: history is keyed by `operator_id`.
- **Append-only**: recording a new snapshot never mutates prior records.
- **First snapshot**: `drift` is `None` (no prior to compare); `coherence_health`
  and `trust_band` are still populated, with the trust band computed treating
  drift as `0.0` (the zero-movement baseline point).

### API (`phase7_telemetry.py`)

```python
record_snapshot(operator_id: str, snapshot: SuperstructureState, timestamp: float) -> None
get_history(operator_id: str, limit: int = 100) -> list[TelemetryRecord]
reset() -> None   # clears the active store (in-memory backend only); JSONL no-op
```

- `record_snapshot` loads the operator's history from `phase7_storage`, computes
  drift (vs. the previous snapshot), rolling coherence-health (over the history
  including this snapshot), and the trust band, then appends one
  `TelemetryRecord` via the active backend.
- `get_history` returns a **fresh list** of the most-recent `limit` records in
  chronological order (oldest first). Unknown operator or `limit <= 0` ⇒ `[]`.
- `TelemetryRecord` is defined in `phase7_storage.py` and re-exported from
  `phase7_telemetry` so `from phase7_telemetry import TelemetryRecord` is stable.

---

## Phase 7.3 — Temporal Analytics & Forecasting

`phase7_analytics.py` interprets a telemetry **history** (`list[TelemetryRecord]`,
chronological / oldest-first) into forward-looking stability signals. Pure and
deterministic: no I/O, no wall-clock, no randomness, no persistence. It imports
only `TelemetryRecord` (from `phase7_storage`).

**Regression window.** Every slope uses the most-recent `WINDOW = 5` records.
For a given field, values are taken in chronological order and missing (`None`)
values are skipped (an operator's first record has `drift = None`); the
remaining values are regressed against their position index (`0, 1, …`). The
slope is least-squares: `Σ(iᵢ−ī)(yᵢ−ȳ) / Σ(iᵢ−ī)²`.

| Function | Formula | Short-history rule | Range |
| --- | --- | --- | --- |
| `compute_drift_velocity(history)` | slope of `drift` over the window | `< 2` usable points → `0.0` | clamp `[-1, 1]` |
| `compute_drift_acceleration(history)` | slope of drift's **first differences** (local velocity) | `< 3` usable points → `0.0` | clamp `[-1, 1]` |
| `compute_coherence_trend(history)` | slope of `coherence_health` over the window | `< 2` usable points → `0.0` | clamp `[-1, 1]` |

**Stability forecast** — `compute_stability_forecast(velocity, acceleration, coherence_trend)`:

```
forecast = 0.4 * (1 - abs(velocity))
         + 0.3 * (-acceleration + 1) / 2
         + 0.3 * (coherence_trend + 1) / 2
```

clamped to `[0, 1]`. Weights: `FORECAST_VELOCITY_WEIGHT = 0.4`,
`FORECAST_ACCELERATION_WEIGHT = 0.3`, `FORECAST_COHERENCE_WEIGHT = 0.3` (sum 1.0).
Interpretation: high `|velocity|` → less stable; positive acceleration →
destabilizing; positive coherence trend → stabilizing.

**Trajectory classification** — `classify_trajectory(forecast)` (inclusive lower bounds):

| Forecast | Label |
| --- | --- |
| `≥ 0.75` (`STABLE_THRESHOLD`) | `"Stable"` |
| `≥ 0.50` (`RECOVERING_THRESHOLD`) | `"Recovering"` |
| `≥ 0.25` (`WOBBLING_THRESHOLD`) | `"Wobbling"` |
| otherwise | `"Diverging"` |

This layer has **no persistence, no endpoints, no UI** — pure analytics. (Card
7.4 will expose these signals via `/operator/telemetry`.)

---

## Phase 7.4 — Telemetry Endpoint Analytics Extension

`GET /operator/telemetry` (the Card 7.2A endpoint in `phase7_endpoint.py`)
additionally returns an `analytics` block — the Phase 7.3 signals computed on
the fly from the operator's history. The endpoint stays read-only and additive
(the `history` and `latest` fields are unchanged):

```json
{
  "history": [ ... ],
  "latest": { ... } | null,
  "analytics": {
    "drift_velocity": 0.0,
    "drift_acceleration": 0.0,
    "coherence_trend": 0.0,
    "stability_forecast": 0.0,
    "trajectory": "Stable"
  }
}
```

- `drift_velocity` / `drift_acceleration` / `coherence_trend` come from the
  matching `phase7_analytics` functions over the same `history`;
  `stability_forecast` is `compute_stability_forecast(velocity, acceleration,
  coherence_trend)`; `trajectory` is `classify_trajectory(forecast)`.
- **Empty history → neutral baseline**: all four floats `0.0` and
  `trajectory = "Stable"` (this overrides the formula, which would otherwise
  read `0.7` / `"Recovering"` for all-zero inputs).
- **Deterministic**: the analytics are a pure function of the stored history;
  the endpoint **writes nothing**, mutates nothing, and changes no persistence.

---

## Phase 7.6 — Temporal Alerts (Operator Guidance Layer)

`phase7_alerts.py` maps the analytics block to a list of operator-facing
stability alerts — read-only **guidance** surfaced in the consoles; it changes
no behavior and writes nothing. `GET /operator/telemetry` returns these as an
additional `alerts` field, computed by `compute_alerts(analytics)`.

```json
{ "...": "...", "alerts": ["No alerts — operator trajectory stable"] }
```

Rules (each evaluated independently; all that match are emitted, in this order):

| Condition | Alert |
| --- | --- |
| `trajectory == "Diverging"` | "High drift detected — operator identity destabilizing" |
| `stability_forecast < 0.40` (`FORECAST_ALERT_THRESHOLD`) | "Low stability forecast — consider reviewing recent operator actions" |
| `drift_velocity > 0.20` (`VELOCITY_ALERT_THRESHOLD`) | "Rapid drift — identity moving faster than expected" |
| `drift_acceleration > 0.15` (`ACCELERATION_ALERT_THRESHOLD`) | "Drift acceleration rising — potential instability" |
| `coherence_trend < -0.10` (`COHERENCE_DECLINE_THRESHOLD`) | "Coherence declining — structural alignment weakening" |
| _none of the above_ | "No alerts — operator trajectory stable" |

- Thresholds are **strict** (a boundary value does not fire) and are module
  constants. Missing analytics keys fall back to no-alert defaults.
- Pure and deterministic: no I/O, wall-clock, randomness, or persistence.
- **Empty-history note**: the 7.4 neutral baseline sets `stability_forecast =
  0.0`, which (being `< 0.40`) trips the low-forecast alert for a zero-record
  operator. `alerts` always equals `compute_alerts(analytics)`.

---

## Phase 7.7 — Causal Drift Mapping

`phase7_causality.py` is a pure, **diagnostic** layer: given a telemetry history
and a log of recent operator actions, it identifies which actions correlate
with drift / coherence movement. It assigns no blame and prescribes nothing.

**Inputs.** `compute_causal_factors(history: list[TelemetryRecord],
recent_actions: list[OperatorAction]) -> list[CausalFactor]`, where
`OperatorAction` is `{action: str, timestamp: float}` (caller-supplied
timestamp — no wall-clock) and `CausalFactor` is `{action: str, correlation:
float ∈ [-1, 1], contribution: float ∈ [0, 1]}`.

**Window.** Only the most-recent `WINDOW = 10` actions are considered.

**Method (deterministic).** Build per-interval deltas from the history
(`drift_delta`, `coherence_delta`; an interval touching the first record's
`None` drift contributes `drift_delta = 0.0`). For each action at time `t`,
split the intervals into BEFORE (`end ≤ t`) and AFTER (`end > t`) and measure
the shift:

```
drift_shift     = clamp(mean(after drift Δ)     - mean(before drift Δ),     -1, 1)
coherence_shift = clamp(mean(after coherence Δ) - mean(before coherence Δ), -1, 1)
correlation     = drift_shift
contribution    = clamp( (max(0, drift_shift) + max(0, -coherence_shift)) / 2, 0, 1 )
```

`contribution` is the destabilizing movement (drift rising and/or coherence
falling) attributable to the post-action window; a purely stabilizing action
scores `0`. An action with no post-action interval yields `(0.0, 0.0)`.

**Output.** Factors with `contribution < MIN_CONTRIBUTION (0.05)` are dropped;
the rest are sorted by `contribution` descending (stable sort). If none survive
— or there are no actions / no history — a single `CausalFactor("none", 0.0,
0.0)` is returned.

**Endpoint.** `GET /operator/telemetry` adds a read-only `causal_factors` field
(`[{action, correlation, contribution}, ...]`). The backend keeps **no
operator-action log** (this card adds no producer), so the endpoint calls
`compute_causal_factors(history, recent_actions=[])` and `causal_factors` is
always the `[{"action": "none", ...}]` sentinel until a later card supplies an
action source. Pure: no I/O, wall-clock, randomness, or persistence.

---

## Phase 7.9 — Causal Narrative Synthesis

`phase7_explanation.py` builds a deterministic, **templated** narrative (no
generative prose, no LLM) from the Phase 7 signals:

    generate_causal_narrative(analytics, alerts, causal_factors) -> str

where `analytics` is the Phase 7.3 block, `alerts` the Phase 7.6 list of
strings, and `causal_factors` the Phase 7.7 list of `{action, correlation,
contribution}` dicts. The output is a fixed four-section template:

```
Identity Movement Summary:
- Drift velocity: <v>
- Drift acceleration: <a>
- Coherence trend: <c>
- Stability forecast: <sf>
- Trajectory classification: <trajectory>

Key Alerts:
- <alert>            (one per alert; "- None" when the list is empty)
...

Likely Contributing Actions:
- <action> (contribution: X.XX)   (one per factor; "- No significant
...                                contributing actions detected" when empty
                                   or the Phase 7.7 "none" sentinel)

Overall Interpretation:
<one of four deterministic paragraphs, selected by trajectory>
```

Numeric values are formatted to two decimals. The interpretation paragraph is
chosen by `trajectory` (any unknown value falls back to the `Stable` text):

| Trajectory | Paragraph |
| --- | --- |
| `Diverging` | "Recent operator actions correlate with destabilizing identity movement. Continued monitoring recommended." |
| `Wobbling` | "Identity movement shows mixed signals with moderate instability. Review contributing actions." |
| `Recovering` | "Identity movement is stabilizing. Contributing actions appear to support recovery." |
| `Stable` | "Identity movement is stable. No significant contributing actions detected." |

**Endpoint.** `GET /operator/telemetry` adds a read-only `narrative` string
(`generate_causal_narrative(analytics, alerts, causal_factors)`). Pure: no
randomness, I/O, wall-clock, or persistence.

---

## Constraints (enforced by this slice)

- **No imports from runtime-spine modules.** Phase 7 imports only
  `phase6_contracts`, sibling Phase 7 modules, and the stdlib (`json`, `os`,
  `re`, `dataclasses`, `pathlib`).
- **No wall-clock**: timestamps are passed in as floats.
- **No encryption**: this is structural telemetry, not private operator data;
  it stays outside the encrypted vault.
- **Local only**: durable storage is local JSONL — no external services.
- **Deterministic**: no randomness; pure compute functions; sorted-key JSON.
- **Flat root**: `phase7_drift.py`, `phase7_telemetry.py`, and
  `phase7_storage.py` live at the repo root, like the Phase 6 modules.

## Acceptance

- This spec matches the implemented functions and constants.
- The `tests/test_phase7*.py` suites are green (drift, storage, analytics,
  endpoint, and endpoint-analytics).
- No changes to CI-gated runtime files; the Phase 7 test files carry none of the
  `runtime_spine` / `privacy_surface` / `determinism_surface` markers.
- `data/telemetry/` is created automatically (and is git-ignored).

## Next cards (not in scope here)

- An operator-action source (so Phase 7.7 `causal_factors` is non-empty) and
  surfacing causal factors in the consoles.
- Compaction / indexing / retention policies for the JSONL log.
