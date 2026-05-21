# Trust-Center Telemetry

A composite telemetry signal that summarizes the system's overall
health into one 0–100 number, an interpretation level, and a small
set of warning indicators. The math lives in `trust_center_math.py`
at the repo root (Phase 7A); surfaced at `/founder/telemetry`.

> The telemetry layer is a **read-side aggregation** of signals
> already computed by `stability_math`, `run_quality`, and
> `cadence_math`. It introduces no new measurements; it weights and
> packages existing ones.

---

## Signals

`compute_trust_signal(records)` returns a single composite score:

```
signal_score = 0.40 · quality_mean
             + 0.30 · stability
             + 0.30 · cadence_health
```

| component | source | range |
|---|---|---|
| `quality_mean` | `run_quality.score_series.summary.mean` | 0–100 |
| `stability` | `compute_stability_curve.summary.monotonicity_pass_rate × 100`, scaled by `compute_timing_drift.drift_pct` | 0–100 |
| `cadence_health` | `compute_cadence.classification` mapped to 90/70/50/60 | 0–100 |

The stability multiplier (drift adjustment):

| `drift_pct` | scaling factor on monotonicity pass rate |
|---|---|
| ≤ +0.05 | 1.00 |
| > +0.05 and ≤ +0.15 | 0.90 |
| > +0.15 and ≤ +0.30 | 0.75 |
| > +0.30 | 0.50 |
| < +0.05 (improving) | 1.00 |

The cadence-health mapping:

| classification | score |
|---|---|
| `regular` | 90 |
| `clustered` | 70 |
| `erratic` | 50 |
| `insufficient data` | 60 |

---

## Levels

| signal_score | level | semantics |
|---|---|---|
| ≥ 75 | `stable` | green; no action |
| 50–74 | `degrading` | track; review the lowest component |
| < 50 | `critical` | open P1; the system is materially regressing |

The level is the operator-facing label; the score gives the magnitude
underneath it.

---

## Alignment

`compute_alignment(records)` reports cross-surface alignment as a
proxy for "are all surfaces healthy together?":

```
alignment_score = max(0, 100 · (1 - 4 · variance(scenario_pass_rates)))
```

When all scenarios pass at the same rate, variance is 0 and alignment
is 100. When one scenario lags significantly, variance grows and
alignment drops. The factor of 4 amplifies modest variances so the
score moves visibly.

| alignment_score | interpretation |
|---|---|
| 90–100 | uniform — all surfaces tracking together |
| 70–89  | mild divergence — one scenario behind the rest |
| 50–69  | meaningful divergence — surface or scenario regression |
| < 50   | severe — escalate to P1 |

The function returns `null` when fewer than 2 scenarios have data.

---

## Warning levels

`compute_warning_levels(records)` is a thin pass-through to
`run_quality.score_series` that exposes the band counts:

```jsonc
{
  "n_runs": 27,
  "n_critical_fail": 1,
  "n_warning": 5,
  "n_healthy": 21,
  "trend": "flat" | "improving" | "degrading" | "insufficient data"
}
```

Use this to render a compact warnings panel without re-running the
full quality scoring.

---

## Composite payload

The dashboard endpoint `GET /founder/telemetry` returns:

```jsonc
{
  "trust_signal": { "signal_score": 86.3, "level": "stable", ... },
  "alignment":    { "alignment_score": 92.0, "surface_variance": 0.02, ... },
  "warnings":     { "n_runs": 27, "n_critical_fail": 1, ... },

  // Phase 7B narrative-drift signals (combined here for one-call UX):
  "drift":       { "drifting": false, "drift_components": [], ... },
  "drift_score": 0.0
}
```

If a sub-call raises (e.g., a math module is missing), the failing
slot is left as an empty default and a sibling `*_error` field is
populated. The endpoint never 500s.

---

## When to act

| signal | level | action |
|---|---|---|
| `trust_signal.level == critical` | P1 | open incident citing the lowest component |
| `trust_signal.level == degrading` for 5+ consecutive runs | P1 | sustained degradation; not a transient |
| `alignment.alignment_score < 50` | P1 | surface or scenario regression |
| `warnings.n_critical_fail` > 0 | P1 (per failing run) | follow the run-quality reasons[] |
| `drift.drifting == true` | P2 → P1 if persistent | per `narrative_drift.md` |
| `drift_score > 0.5` | P1 | composite drift severity is high |

The harness still does not auto-incident. Operators read the dashboard
and post per `tests/acceptance/operator_notifications.md`.

---

## What the telemetry layer does NOT do

- It does not introduce new measurements. It only aggregates.
- It does not auto-act. It reports.
- It does not memoize. Each request recomputes from the JSONL on disk.
- It does not require all sub-modules to succeed. A missing module
  produces a `*_error` field and an empty default; the rest of the
  payload still returns.

For drift detection specifically, see
`tests/acceptance/narrative_drift.md`.

---

## Anti-execution boundary

`trust_center_math.py` is pure stdlib + repo-root sibling imports
(`stability_math`, `run_quality`, `cadence_math`). It runs only when
the dashboard endpoint is hit. No scheduler, no daemon.
