# Narrative Drift Detection

"Narrative drift" is the metaphor for measurable change in the
acceptance harness's behaviour over time: timing climbing, scenario
pass rates falling, run-quality degrading. The math lives in
`narrative_drift.py` at the repo root (Phase 7B) and feeds the
combined `/founder/telemetry` payload.

> Drift detection is **observational**, not prescriptive. It surfaces
> components that look like they are changing; the operator decides
> whether the change matters and whether to act.

---

## What "drift" is here

Three component-level signals, evaluated across all ingested runs:

1. **Timing drift** — `stability_math.compute_timing_drift(records)`
   reports a baseline-vs-current `drift_pct` of per-iteration mean.
   Drift is flagged when `drift_pct > +0.15`.
2. **Run-quality drift** — `run_quality.score_series(records)` mean
   over the early half vs the late half. Flagged when the late-half
   mean drops by more than 10 points relative to the early-half mean.
3. **Scenario pass-rate drift** — per-scenario pass rate over the
   most-recent quarter of runs vs the prior three-quarters. Flagged
   when any scenario's recent rate drops by more than 0.10.

A scenario is considered "drifting" if any of (1)–(3) fires.

---

## How drift manifests in metrics

| signal | what the dashboard shows |
|---|---|
| timing drift | `drift.drift_components` lists `iteration_mean_ms` with the actual `drift_pct` |
| quality drift | `drift.drift_components` lists `run_quality_score` with `early_mean`, `late_mean`, and `delta` |
| pass-rate drift | `drift.early_signals` lists one entry per scenario with its `prior` and `recent` rates |
| composite severity | `drift_score` (0.0–1.0) blends the three signals |

`drift_score` composition:

```
score = min(1.0, (0.25 × n_drift_components)
                + min(0.25, 0.05 × n_early_signals)
                + timing_contribution)
```

where `timing_contribution` is:

| `drift_pct` | timing_contribution |
|---|---|
| > +0.30 | 0.30 |
| > +0.15 | 0.15 |
| > +0.05 | 0.05 |
| otherwise | 0.00 |

| `drift_score` | severity |
|---|---|
| 0.0 – 0.2 | quiet — no action |
| 0.2 – 0.5 | mild — track |
| 0.5 – 0.8 | meaningful — P2, investigate |
| > 0.8 | severe — P1, almost certainly already failing scenario gates |

---

## Early-signal detection

The "early signals" block reports per-scenario pass-rate drops that
are visible in the most recent quarter of runs. This catches
regressions that haven't yet shifted the run-level pass rate enough
to be obvious in `run_quality.score_series`, but are concentrated in
the latest activity.

Example early signal:

```jsonc
{
  "signal": "scenario_pass_rate:03_two_operators_concurrent",
  "prior":  0.965,
  "recent": 0.800,
  "delta": -0.165
}
```

Interpretation: scenario 03 was passing ~97% of historical runs but
has dropped to 80% in the last quarter. This warrants reading the
failing run reports before the drop becomes a sustained pattern.

---

## How to interpret cross-surface divergence

Cross-surface divergence shows up two ways:

1. **In `compute_alignment`** (Phase 7A) as low alignment_score —
   one scenario's pass rate is meaningfully different from the others.
2. **In drift early signals** as a per-scenario `delta` < -0.10 — the
   regression is concentrated in one scenario, which usually means
   one surface (or one backend endpoint serving that surface) is
   regressing.

Cross-reference both views:

| alignment_score | drift early signals | reading |
|---|---|---|
| high | empty | uniform health, no action |
| high | one scenario | uniform overall but a recent specific regression |
| low  | empty | persistent uneven health, but stable; investigate the lagging scenario |
| low  | one or more | active regression in a specific surface |

---

## Detection windows

The drift module uses fixed default windows for predictability:

| signal | window |
|---|---|
| timing drift baseline | first 5 runs |
| timing drift current  | last 5 runs |
| quality drift early   | first half of all runs |
| quality drift late    | second half of all runs |
| pass-rate prior       | runs 0..−quarter |
| pass-rate recent      | runs −quarter..end |
| minimum runs needed   | 4 |

Windows are not yet configurable via env or query params. Doing so is
a Phase ≥8 follow-on; the current contract is "detect with these
defaults, report what is found."

---

## What this module does NOT do

- It does not auto-incident.
- It does not memoize. Each call recomputes from the records list.
- It does not fit complex models — no ARIMA, no exponential smoothing,
  no anomaly-detection libraries. Simple windowed comparisons only.
- It does not predict the next value. There is no forecasting.
- It does not decide whether a drift is "good" or "bad" beyond the
  documented severity buckets. Operator interpretation required.

---

## Anti-execution boundary

`narrative_drift.py` is pure stdlib + sibling repo-root imports
(`run_quality`, `stability_math`). The dashboard endpoint reads the
JSONL on the live request path and computes drift on demand. No
scheduler, no daemon, no automatic action.
