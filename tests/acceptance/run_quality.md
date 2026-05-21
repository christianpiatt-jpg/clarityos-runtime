# Run-Quality Scoring

A 0–100 rubric for scoring each acceptance run on a fixed set of
dimensions, plus a series-level summary across runs. The math lives in
`run_quality.py` at the repo root (Phase 6A); per-run scores feed the
founder analytics dashboard at `/founder/analytics/quality`.

> **Path note.** All Phase 6/7 backend modules sit at the repo root
> alongside `incident_store.py`, `acceptance_dashboard.py`, and
> `stability_math.py`. Phase 1's adaptation (no `backend/` directory)
> still applies.

---

## Dimensions

Five components, each scored 0–100, equally weighted at 20%.

| dimension | what it measures | data source |
|---|---|---|
| `timing_stability` | within-run variance — how consistent are the per-iteration durations of scenario 05? | `record.stability.mean_ms`, `stddev_ms` |
| `monotonicity` | scenario 05 monotonicity_pass for this run | `record.stability.monotonicity_pass` |
| `drift_proxy` | within-run max/mean ratio as a proxy for in-run slowdown | `record.stability.mean_ms`, `max_ms` |
| `surface_health` | percentage of scenarios that passed | `record.scenarios[*].pass` |
| `scenario_variance` | how dominant the longest scenario is vs the mean | `record.scenarios[*].duration_ms` |

The composite score is a simple weighted sum:

```
score = 0.20 * timing_stability
      + 0.20 * monotonicity
      + 0.20 * drift_proxy
      + 0.20 * surface_health
      + 0.20 * scenario_variance
```

Weights are exposed in the response (`components` + `weights`) so
callers can re-weight if they need a different lens.

---

## Per-component scoring

### `timing_stability`

Coefficient of variation = `stddev_ms / mean_ms`. A perfectly
consistent run has CV near 0; a wildly variable run has CV > 0.5.

| CV | score |
|---|---|
| ≤ 0.05 | 100 |
| 0.05 → 0.50 | linearly interpolated |
| ≥ 0.50 | 0 |

Returns `50` (and a "no timing data" reason) when `mean_ms` or
`stddev_ms` are absent — typical for fast-mode runs that skipped
scenario 05.

### `monotonicity`

Binary, mapped to 100 / 0:

| `monotonicity_pass` | score |
|---|---|
| `true`  | 100 |
| `false` | 0 |
| `null` / absent | 50 (with "no monotonicity data" reason) |

A `false` value emits `"monotonicity broken (artifact count decreased
between iterations)"` in `reasons[]`.

### `drift_proxy`

Within-run max / mean ratio. Values near 1.0 are clean; values near
2.0 indicate a single iteration spiked.

| ratio | score |
|---|---|
| ≤ 1.0 | 100 |
| 1.0 → 2.0 | linearly interpolated |
| ≥ 2.0 | 0 |

This is intentionally a single-run proxy; cross-run drift is computed
by `stability_math.compute_timing_drift` (Phase 5B) and surfaced
separately in the trust-center telemetry (Phase 7).

### `surface_health`

Pass rate across all scenarios in the run:

```
score = (n_passed / n_total) * 100
```

When any scenario fails, `reasons[]` lists the failing ids:
`"failed: 03_two_operators_concurrent"`.

### `scenario_variance`

Max scenario duration / mean scenario duration. Some scenarios are
naturally longer (02 cross-surface jump, 05 stability window), so
ratios up to 2× are expected. The score buckets:

| ratio | score |
|---|---|
| ≤ 2.0 | 100 |
| 2.0 → 5.0 | linearly interpolated |
| ≥ 5.0 | 0 |

A ratio above 4.0 emits `"one scenario dominates duration"` in
`reasons[]` — often a sign of one slow surface or backend endpoint.

---

## Bands

The composite score maps to one of three bands:

| score | band | semantics |
|---|---|---|
| 80 – 100 | `healthy` | green path; no action |
| 50 – 79  | `warning` | track; investigate if sustained |
| 0 – 49   | `critical_fail` | open P1 incident; do not ship until resolved |

Run-level override: if `record.pass == false`, a score that would
otherwise be `healthy` is downgraded to `warning` and a reason is
appended. This prevents a single failing scenario from being masked
by component averages.

---

## Series-level summary

`score_series(records)` returns:

```jsonc
{
  "n_runs": 17,
  "scores": [ /* one entry per run, oldest-first */ ],
  "summary": {
    "mean":   83.4,
    "median": 86.0,
    "latest": 79.5,
    "trend":  "improving" | "flat" | "degrading" | "insufficient data",
    "n_healthy": 12,
    "n_warning": 4,
    "n_critical_fail": 1
  }
}
```

Trend rule: split the score series in half, compare the means.

| early_mean → late_mean delta | trend |
|---|---|
| `delta > +5` | improving |
| `−5 ≤ delta ≤ +5` | flat |
| `delta < −5` | degrading |
| `n < 4` runs | insufficient data |

---

## Examples

### Example A — clean run (all green)

```jsonc
{
  "run_id": "run-20260612T091200Z-aaaa",
  "score": 96.0,
  "band": "healthy",
  "components": {
    "timing_stability": 95.0,
    "monotonicity":    100.0,
    "drift_proxy":      90.0,
    "surface_health":  100.0,
    "scenario_variance": 95.0
  },
  "reasons": []
}
```

### Example B — single scenario failure on a low-prevalence partition

```jsonc
{
  "run_id": "run-20260612T112400Z-bbbb",
  "score": 64.0,
  "band": "warning",
  "components": {
    "timing_stability": 88.0,
    "monotonicity":    100.0,
    "drift_proxy":      85.0,
    "surface_health":   80.0,
    "scenario_variance": 70.0
  },
  "reasons": [
    "failed: 03_two_operators_concurrent",
    "run-level pass is False; capped at warning"
  ]
}
```

### Example C — monotonicity break (critical)

```jsonc
{
  "run_id": "run-20260612T143300Z-cccc",
  "score": 41.0,
  "band": "critical_fail",
  "components": {
    "timing_stability": 75.0,
    "monotonicity":      0.0,
    "drift_proxy":      60.0,
    "surface_health":   75.0,
    "scenario_variance": 65.0
  },
  "reasons": [
    "monotonicity broken (artifact count decreased between iterations)",
    "failed: 05_stability_window"
  ]
}
```

---

## What the rubric does NOT do

- It does not auto-post incidents. Critical-fail rows surface in the
  dashboard and the `reasons[]` array; the operator decides whether
  to escalate.
- It does not weight scenarios differently. Scenario 03 (security
  boundary) and scenario 04 (artifact presence) carry equal weight in
  `surface_health`. Operators who want stricter weighting can
  re-derive locally from the exposed `components`.
- It does not predict. There is no forecast — only a description of
  what the historical data says.

---

## Anti-execution boundary

`run_quality.py` is a pure-stdlib module. It performs no I/O, raises
no exceptions, and consumes only the in-memory record dicts passed in.
The dashboard endpoint reads the JSONL and calls these functions on
the live request path — no scheduler, no daemon.
