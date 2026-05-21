# Identity Coherence

A read-only descriptive layer that summarizes how *consistently* the
acceptance harness has been behaving across runs (and, when records
carry a `surface` tag, across surfaces). The math lives in
`identity_engine.py` at the repo root (Phase 8B); surfaced at
`/founder/identity`.

> **What this is, and what it isn't.** "Identity coherence" here is a
> metaphor borrowed for a structural reading of harness telemetry. It
> describes the *system's* identity as observed through its behaviour
> over time — not the operator's identity, not any human's traits, not
> any psychological profile. The model uses only the metrics already
> ingested via `post_run_ingest.py`. It introduces no new logging, no
> PII, no behavioural tracking.

---

## Dimensions

Five dimensions, each scored 0–100 with a one-word descriptor. Every
dimension is derived from existing metrics — no new measurements.

| dimension | what it measures | derived from |
|---|---|---|
| `tone` | how consistent is the run-quality band over time? | `run_quality.score_series` — stddev of per-run scores |
| `timing` | cadence regularity + cross-run drift | `cadence_math.compute_cadence` (CV) + `stability_math.compute_timing_drift` (drift_pct) |
| `decision_style` | how concentrated is the fast/full mode mix? | per-record `mode` field |
| `escalation_style` | how often does run-quality cross into critical? | `run_quality.score_series.summary.n_critical_fail / n_runs` |
| `trust_posture` | what level does the trust signal hold? | `trust_center_math.compute_trust_signal.level` |

---

## Per-dimension scoring

### `tone`

Stddev of the run-quality scores across the series. A lower stddev
indicates a tighter, more consistent band; a higher one indicates
swings between healthy / warning / critical.

| stddev (run_quality.score) | score | descriptor |
|---|---|---|
| 0 | 100 | consistent |
| 5 | ~83 | consistent |
| 15 | ~50 | varied |
| 25 | ~17 | erratic |
| 30+ | 0 | erratic |

Returns 50 / "insufficient data" if fewer than 2 runs are available.

### `timing`

Equal-weight average of two sub-scores:

- **cadence sub-score** — `100 · (1 − CV)`, clipped to [0, 100],
  where `CV` is `cadence_math.compute_cadence.coefficient_of_variation`.
- **drift sub-score** — bucketed mapping of
  `compute_timing_drift.drift_pct`:

| drift_pct | drift sub-score |
|---|---|
| ≤ +0.05 | 100 |
| +0.05 to +0.15 | 75 |
| +0.15 to +0.30 | 50 |
| > +0.30 | 25 |

Final descriptor:

| score | descriptor |
|---|---|
| ≥ 80 | steady |
| 50–79 | shifting |
| < 50 | unsteady |

### `decision_style`

The system has two modes (`fast` and `full`). The decision-style
dimension measures how concentrated the choice is.

`concentration = |p_fast − 0.5| · 2`, where `p_fast` is the share of
fast-mode runs. Range 0.0 (perfect 50/50 mix) to 1.0 (every run in
one mode).

```
score = 60 + concentration · 20
```

Score range: 60 (balanced) to 80 (focused). Descriptors:

| concentration | descriptor |
|---|---|
| ≤ 0.30 | balanced |
| 0.30 – 0.70 | adaptive |
| > 0.70 | focused |

This dimension is intentionally bounded narrowly — the harness rarely
benefits from "erratic mode-switching" being penalized severely. It
exists primarily to surface bias, not to grade.

### `escalation_style`

Critical-fail rate per run from `run_quality.score_series`.

```
crit_rate = n_critical_fail / n_runs
score = 100 − (crit_rate / 0.20) · 100   (clipped to [0, 100])
```

| crit_rate | score | descriptor |
|---|---|---|
| 0% | 100 | restrained |
| 5% | 75 | restrained |
| 10% | 50 | responsive |
| 15% | 25 | responsive |
| ≥ 20% | 0 | alarmed |

This is **escalation rate observed in run quality**, not the operator's
incident-posting style. The harness does not auto-incident; this
dimension cannot read intent.

### `trust_posture`

Maps `trust_center_math.compute_trust_signal.level` to a posture word
and uses the underlying `signal_score` as the dimension's score:

| trust_signal.level | descriptor |
|---|---|
| stable | confident |
| degrading | guarded |
| critical | defensive |

The numeric score equals `trust_signal.signal_score` directly so this
dimension stays interpretable against the trust gauge on
`/founder/telemetry`.

---

## Composite coherence score

```
coherence = mean(score for each dimension where score is not None)
```

Equal weights. Bands:

| coherence | band |
|---|---|
| ≥ 80 | high coherence |
| 50 – 79 | medium coherence |
| < 50 | low coherence |

The composite is intentionally simple — it is a glance summary, not a
gating mechanism. The dimension table beneath it carries the texture.

---

## Cross-surface comparison

`compare_surfaces(records_by_surface)` accepts a dict keyed by surface
name with a list of records per surface. It returns:

- `per_surface[name]` — full identity profile for that surface
- `cross_surface_delta` — `{n_surfaces, max_score, min_score, spread, interpretation}`

`spread` = max overall score − min overall score, in points.

| spread | interpretation |
|---|---|
| ≤ 5 | aligned |
| 5–15 | mild divergence |
| 15–30 | noticeable divergence |
| > 30 | significant divergence |

**Today's data caveat.** The current JSONL records do not carry a
per-record `surface` field — every record is a whole-run record. The
endpoint groups by `record.get("surface", "global")`, so all records
land in a single "global" group and the cross-surface delta degenerates
to the single-surface case. The infrastructure is in place for a
future schema in which records carry a surface label, but today's
view is single-surface by construction.

---

## Three example profiles

### High coherence (≥ 80)

```jsonc
{
  "score": 87.4,
  "dimensions": {
    "tone":             { "score": 92.0, "descriptor": "consistent" },
    "timing":           { "score": 88.0, "descriptor": "steady" },
    "decision_style":   { "score": 76.0, "descriptor": "focused" },
    "escalation_style": { "score": 95.0, "descriptor": "restrained" },
    "trust_posture":    { "score": 86.0, "descriptor": "confident" }
  },
  "notes": [],
  "n_runs": 28
}
```

Read: tight quality band, regular cadence, low drift, focused on
fast-mode runs (probably CI), almost no critical fails, trust signal
steadily stable.

### Medium coherence (50–79)

```jsonc
{
  "score": 64.2,
  "dimensions": {
    "tone":             { "score": 70.0, "descriptor": "varied" },
    "timing":           { "score": 55.0, "descriptor": "shifting" },
    "decision_style":   { "score": 64.0, "descriptor": "adaptive" },
    "escalation_style": { "score": 80.0, "descriptor": "restrained" },
    "trust_posture":    { "score": 52.0, "descriptor": "guarded" }
  },
  "notes": [],
  "n_runs": 12
}
```

Read: quality drifts a bit, cadence is irregular, mode mix is roughly
balanced, escalations are rare but trust signal is degrading.
Investigate trust signal first.

### Low coherence (< 50)

```jsonc
{
  "score": 38.1,
  "dimensions": {
    "tone":             { "score": 30.0, "descriptor": "erratic" },
    "timing":           { "score": 35.0, "descriptor": "unsteady" },
    "decision_style":   { "score": 64.0, "descriptor": "adaptive" },
    "escalation_style": { "score": 20.0, "descriptor": "alarmed" },
    "trust_posture":    { "score": 41.0, "descriptor": "defensive" }
  },
  "notes": [],
  "n_runs": 41
}
```

Read: the harness is unstable across multiple dimensions. Critical
fails are recurring (escalation_style "alarmed"). This is the kind of
pattern that warrants pausing feature work to root-cause.

---

## What this model does NOT do

- It does not type personalities. There is no Big-5, MBTI, or other
  taxonomy. The "descriptor" words are summary labels, not categories.
- It does not infer operator intent. A burst of runs can be diligence
  or panic; the model reports the burst, not the meaning.
- It does not track individuals. The records carry no operator PII.
  "Identity" here is the harness's behaviour, not anyone's identity.
- It does not predict. There is no forecast. There is no "expected
  next coherence score" — only the current observation.
- It does not gate. No deploy is blocked by a low coherence score.
  This is a glance for the founder, not a CI signal.
- It does not memoize. Each request recomputes from the JSONL.

---

## Anti-execution boundary

`identity_engine.py` is pure stdlib + sibling repo-root imports
(`run_quality`, `cadence_math`, `stability_math`,
`trust_center_math`). The dashboard endpoint reads
`acceptance_runs.jsonl` on the live request path and computes results
on demand. No scheduler, no daemon, no automatic action.
