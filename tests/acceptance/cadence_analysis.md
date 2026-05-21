# Run Cadence & Operator Rhythm

How often the operator runs the harness, how regularly, and what
"healthy cadence" looks like. The math lives in `cadence_math.py` at
the repo root (Phase 6C). Surfaced via
`GET /founder/analytics/cadence`.

---

## What we measure

`compute_cadence(records)` reports run-spacing in minutes:

| field | definition |
|---|---|
| `n_runs` | number of records examined |
| `n_gaps` | `n_runs - 1` (number of intervals between consecutive runs) |
| `avg_spacing_minutes` | arithmetic mean of gaps |
| `median_spacing_minutes` | median gap |
| `longest_gap_minutes` | the single longest interval |
| `shortest_gap_minutes` | the single shortest interval |
| `stddev_minutes` | gap standard deviation (0 when n_gaps < 2) |
| `coefficient_of_variation` | `stddev / mean` — the cadence's "shape" |
| `classification` | `regular`, `clustered`, `erratic`, or `insufficient data` |

Gaps are computed from each record's `finished_at` field, falling back
to `started_at` if `finished_at` is absent.

`detect_irregularities(records)` reports outlier gaps and clusters:

| field | definition |
|---|---|
| `outlier_gaps[]` | gaps where `gap > 3 × median_gap` |
| `cluster_count` | number of "burst" sequences (consecutive gaps below `median / 2`) |
| `classification` | echoes `compute_cadence`'s classification |

---

## Classification thresholds

The coefficient of variation (CV = stddev / mean) classifies the cadence:

| CV | classification | semantics |
|---|---|---|
| ≤ 0.5  | `regular`   | gaps are within ±50% of the mean — predictable rhythm |
| ≤ 1.0  | `clustered` | gaps cluster around the mean but with frequent bursts and pauses |
| > 1.0  | `erratic`   | gaps are irregular; runs come in bursts followed by long silences |
| (n<2)  | `insufficient data` | not enough gaps to classify |

---

## Healthy vs erratic cadence

| pattern | typical CV | what it looks like | typical context |
|---|---|---|---|
| **healthy** | 0.0–0.4 | gaps cluster tightly around mean | cron-driven, CI on schedule, daily manual rhythm |
| **clustered** | 0.4–0.8 | bursts during work hours + overnight gaps | manual operator running multiple times per work session |
| **erratic** | > 1.0 | days of silence punctuated by 10-runs-in-an-hour bursts | operator chasing a regression; investigation cluster |

A clustered cadence is normal and expected during day-to-day operator
work. Erratic cadence is a signal worth interpreting: usually a P1/P2
investigation cluster (good) or a stalled pipeline that ran 200 times
in a CI loop debugging a flake (bad).

---

## Outlier gaps and clusters

An **outlier gap** is a single interval that is at least 3× the
median. Common causes:

- weekend gap on a weekday-cron schedule
- an outage paused the cadence
- the operator was on vacation
- CI was broken; nothing ran

A **cluster** is a sequence of runs separated by less-than-half-the-median
gaps. Common causes:

- operator triaging an incident (re-running rapidly to isolate a fault)
- CI loop on a PR (fast feedback)
- pre-launch validation push

Neither outlier gaps nor clusters are inherently bad. They become
worth flagging when:

| signal | action |
|---|---|
| 3+ outlier gaps in the last 20 runs | investigate why the cadence keeps stalling |
| cluster_count grows without a corresponding incident posted | the operator is rerunning blindly — a hint that a flake is being masked |
| classification flips from `regular` to `erratic` for 5+ runs | the rhythm has changed; root-cause it |

---

## Interpretation guide

When you read `/founder/analytics/cadence`:

1. Look at `classification` first. `regular` and `clustered` are
   normal; `erratic` warrants a glance.
2. Look at `avg_spacing_minutes` and `median_spacing_minutes`. Big
   divergence between mean and median = a few outliers are pulling
   the mean.
3. Look at `outlier_gaps`. If the list is empty, the cadence is
   smooth. If it has entries, decide whether each was deliberate
   (vacation) or unexpected (CI broken).
4. Look at `cluster_count`. One or two clusters is normal. More than
   3–4 clusters across recent history suggests rapid re-running.

The cadence module does not auto-incident; the dashboard renders the
classification + outlier list and the operator decides whether to act.

---

## What this module does NOT do

- It does not analyze run *content* — only timestamps. A run that
  passed and a run that failed look identical to cadence math.
- It does not infer operator intent. A burst could be diligence or
  desperation; the math reports the burst, not the meaning.
- It does not predict the next run. There is no forecasting. There is
  no "expected next run time" — only the historical pattern.

For richer signals, the per-run quality + drift modules
(`run_quality.py`, `narrative_drift.py`) provide the content-aware
view.

---

## Anti-execution boundary

`cadence_math.py` is pure stdlib and stateless. The dashboard endpoint
reads `acceptance_runs.jsonl` on the live request path and computes
results on demand. No background scheduler, no cached state.
