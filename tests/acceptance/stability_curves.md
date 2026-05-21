# Acceptance Harness — Stability Curves & Longitudinal Metrics

Definitions and interpretation rules for the longitudinal metrics
exposed via `/founder/acceptance/stability/curve` (the Phase 5C
endpoint) and rendered at the `/founder/acceptance/curve` web view.

The math is implemented as pure-stdlib functions in `stability_math.py`
at the repo root (Phase 5B; see Phase 1 path adaptation — no `backend/`
directory exists, so backend modules live at the repo root alongside
`incident_store.py` and `acceptance_dashboard.py`).

---

## What is a stability curve?

A stability curve is the **time-series projection** of scenario 05's
per-iteration metrics across all ingested runs. Each point on the
curve corresponds to one run; the y-axis carries one of:

- `mean_ms` — average per-iteration duration of scenario 05 in that run
- `max_ms` — worst single-iteration duration in that run
- `stddev_ms` — within-run variance of per-iteration duration
- `monotonicity_pass` — boolean (pass/fail) for the per-iteration
  artifact-count monotonicity check

The x-axis is the run index (newest run on the right). Time spacing
between points is non-uniform — runs are operator-triggered and may
cluster.

A **healthy** curve is roughly flat. A **drifting** curve shows a
sustained slope. A **broken** curve shows monotonicity failures or a
spike in `max_ms` past 2× the surrounding `mean_ms`.

---

## Monotonicity expectations

Scenario 05 runs three iterations of scenario 04. Across iterations,
the per-operator artifact count must not decrease (`monotonicity_pass`
in the per-run details). At the longitudinal level we track:

- `monotonicity_pass_count` — runs where monotonicity held
- `monotonicity_fail_count` — runs where it broke
- `monotonicity_pass_rate` — pass / total

| pass rate | interpretation | action |
|---|---|---|
| 1.00 | clean | no action |
| 0.95–0.99 | rare flake | track; if next 5 runs all pass, ignore |
| 0.80–0.94 | sustained instability | open P1; root-cause state leakage |
| < 0.80 | broken | open P0; halt feature work; stability is a precondition |

---

## Timing drift thresholds

Drift is the change in per-iteration mean duration from a baseline
window to a current window. Defaults:

- baseline window: first 5 runs (or all if fewer)
- current window: last 5 runs (or all if fewer)
- drift = `(current_mean - baseline_mean) / baseline_mean`

| drift_pct | interpretation | action |
|---|---|---|
| ≤ +5% | normal jitter | no action |
| +5%–+15% | mild drift | track; investigate if sustained |
| +15%–+30% | meaningful slowdown | open P2; profile slowest endpoint |
| > +30% | severe slowdown | open P1; this will cross the scenario-05 2× ratio gate soon |
| < −5% | improvement | desirable; no action beyond noting |

The slope of a simple linear regression of `mean_ms` over run index
gives a complementary view: positive slope = drifting up, negative =
drifting down. The slope is reported in milliseconds-per-run.

---

## Surface-specific curves

The longitudinal JSONL records carry only run-level scenario timings,
not per-surface breakdowns. The Phase 5B `compute_surface_health`
function therefore reports a **proxy**: per-scenario pass rate and
mean duration over the last N runs (default N = 20).

Surface mapping (proxy):

- `01_onboarding_per_surface` runs all three surfaces — its duration
  is the sum of web + phone + desktop onboardings for both operators.
  A sustained increase here usually means one specific surface is
  getting slower.
- `02_cross_surface_jump` is dominated by surface-jump latency on the
  slowest of the three surfaces.
- `03_two_operators_concurrent` is web-only — useful as a backend-load
  proxy.
- `04_artifact_presence` exercises all three surfaces sequentially.
- `05_stability_window` is a re-run of `04`, so its drift mirrors `04`.

For true per-surface granularity (web mean separately from phone mean
separately from desktop mean), the operator must re-ingest the full
`report.json` files — a future enhancement, not yet wired. The
function's response includes a `surface_proxy_note` string making this
explicit.

---

## How to interpret a regression

A regression in this context is any of:

1. **Monotonicity break.** A previously-passing operator+scenario
   combination starts failing the per-iteration count check. Almost
   always a substrate-layer bug (vault eviction, FSM reset). P1.

2. **Timing drift > +15%.** Per-iteration mean climbed more than 15%
   from baseline. Likely backend latency growing under accumulated
   data or an endpoint degrading. P2 first, P1 if it's still climbing
   over the next 5 runs.

3. **Variance spike.** A single run shows `max_ms > 2 × mean_ms`
   while neighbours are clean. Usually environmental (CI runner
   contention). P3; track but don't act unless reproducible.

4. **Variance pattern.** `stddev_ms` is climbing run-over-run while
   means stay flat. The system is becoming less predictable. P2.

5. **Scenario pass rate degradation.** A scenario that used to pass
   100% of runs starts dropping below 95%. Read the failing runs'
   `messages` arrays — usually selector drift (P2) or genuine
   surface regression (P1).

---

## Reading the dashboard view

The `/founder/acceptance/curve` web view renders three blocks:

1. **Curve chart.** SVG line chart of `mean_ms` over the last N runs.
   Y-axis ranges over the actual data (not zero-anchored). Look for
   slope, spikes, and the position of the latest point relative to
   the trend.

2. **Drift table.** Single-row table showing `baseline_ms`,
   `current_ms`, `drift_pct`, and `slope_ms_per_run`. Cross-reference
   against the threshold table above.

3. **Surface health summary.** Per-scenario pass rate and mean
   duration over the last 20 runs. The fastest way to see "which
   scenario is the canary" — usually scenario 01 because it touches
   all three surfaces.

The endpoint also returns a `monotonicity` block consumed by the page
header: a one-line "X / Y runs passed monotonicity (Z% pass rate)".

---

## What stability_math.py does NOT do

The Phase 5B `stability_math.py` is intentionally narrow:

- No fitting of complex models (no ARIMA, no exponential smoothing).
- No outlier rejection.
- No automatic incident posting.
- No third-party imports beyond stdlib (`statistics`, `math`).
- No mutation of the JSONL or any file.
- No execution of anything when imported.

When richer analysis is wanted (forecasting, anomaly detection,
per-surface decomposition), it lands in a separate Phase ≥6 module —
not here.

---

## Anti-execution boundary

This document describes interpretation. The math runs in the live
backend when an operator hits `/stability/curve`. Materialization
wrote no JSONL and computed no curves.
