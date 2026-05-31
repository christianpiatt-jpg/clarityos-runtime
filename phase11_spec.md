# Phase 11 — Operator Action Recommendations (Spec)

**Status:** Complete (11.0–11.2 implemented — the action recommendation engine,
the recommendation narrative, and the tri-surface surfacing). Phase 11 complete.
**Surfaces:** Backend (Python) + clients (web, desktop, phone — 11.2 only).

Phase 7 forecast time, Phase 8 reasoned about causal structure, Phase 9 detected
behavioral motifs, and Phase 10 forecast behaviour (forecast / deltas /
stability / narrative). Phase 11 is the (optional) **recommendation** layer: it
turns those signals into concrete operator-action recommendations — the
structural leverage points in the behavioral system.

It introduces **no** inference, ML, or speculation. Every recommendation is a
deterministic function of the engines already built: the 10.1 deltas, the 10.2
stability, the 9.4 motifs, the 10.0 forecast, and the 10.3 narrative. No
psychology, no advice, no guesswork — just structural leverage surfaced as
suggested actions.

Like Phase 6/7/8/9/10, this track lives as flat repo-root modules
(`phase11_*.py`) with tests in `tests/test_phase11_*.py`. It is additive and
**does not touch** the CI-gated runtime spine, the vault, or `operator_state`.

---

## Phase 11.0 — Action Recommendation Engine

`phase11_recommendations.py` produces a deterministic, ranked list of
recommended operator actions that reduce drift, break loops, stabilize motifs,
and improve coherence — each grounded in a structural signal, not inference.

```python
compute_action_recommendations(deltas, motifs, stability, forecast) -> list[dict]
```

Each recommendation:

```
{"action_id": <str>,
 "label": <str>,
 "reason": "habit_weakening" | "trigger_volatility" | "loop_break"
         | "bottleneck_relief" | "attractor_alignment" | "forecast_alignment",
 "score": <float in [0, 1]>}
```

### Recommendation types (deterministic)

| # | Reason | Trigger | Score | Source |
| --- | --- | --- | --- | --- |
| 1 | `habit_weakening` | a label whose frequency dropped (`delta < 0`) | `\|frequency delta\|` | 10.1 `deltas.frequency` |
| 2 | `trigger_volatility` | a trigger chain | `\|likelihood\|` | 10.0 `forecast.trigger_likelihood` |
| 3 | `loop_break` | a loop | `1 − continuation_probability` | 10.0 `forecast.loop_continuation` |
| 4 | `bottleneck_relief` | a 9.4 action bottleneck | normalized list rank | 9.4 `motifs.action_bottlenecks` |
| 5 | `attractor_alignment` | a 9.4 action attractor | normalized list rank | 9.4 `motifs.action_attractors` |
| 6 | `forecast_alignment` | a predicted next action | forecast `score` | 10.0 `forecast.next_actions` |

Every score is clamped to `[0, 1]`.

**Identity / dedupe.** `habit_weakening` and `forecast_alignment` both key by the
action **label** (so the same action appearing as a weakening habit *and* a
predicted next action dedupes to one recommendation); `loop_break` /
`trigger_volatility` key by the joined sequence (`"a → b"`); `bottleneck_relief`
/ `attractor_alignment` key by node id.

**Rank scoring (4 & 5).** 9.4 already sorts bottlenecks by centrality descending
and attractors by influence descending, so the list position *is* the
inbound-influence / attractor-strength ranking. The score is the normalized rank
`(N − i) / N` (the strongest scores 1.0); this needs no raw-influence dict and
always surfaces a present bottleneck / attractor.

**Trigger note.** No *temporal* trigger-likelihood delta is produced upstream
(see 10.2), so the trigger volatility signal is the 10.0 trigger likelihood
itself (`|likelihood|`).

**`stability`** is accepted for signature parity with the Phase-10 API (and
future instability-weighting); the six types derive from `deltas` + `motifs` +
`forecast` only.

### Final list

Drop zero-score candidates → sort by descending score (ties by `action_id` then
`reason`) → dedupe by `action_id` keeping the highest-scoring reason → cap at the
top **10**. Fully deterministic; output is JSON-serialisable.

### Determinism

Every score is pure arithmetic over the inputs; the list is fully sorted with
total tiebreakers. No randomness, no wall-clock, no ML, no inference, no
psychological language.

---

## Phase 11.1 — Recommendation Narrative

`phase11_narrative.py` is the explanation layer for the 11.0 engine — the
recommendation analogue of the 7.3 / 8.9-8.10 / 10.3 narratives. Where 11.0 says
*what to do*, 11.1 says *why these actions*: a deterministic, operator-facing
account of why each recommendation was generated, the structural drivers, and
the stability context. No inference, no ML, no speculation, no psychological
language.

```python
compute_recommendation_narrative(recommendations, deltas, motifs, stability) -> dict
```

Output:

```
{"summary": "...",
 "recommendations": [{action_id, label, reason, score, explanation}],
 "drivers": {"habit", "triggers", "loops",
             "bottlenecks", "attractors", "forecast_alignment"},  # [{action_id, metric, reason}]
 "stability_context": {"score", "drivers"},      # the full 10.2 object
 "raw": {"recommendations", "deltas", "motifs"}}  # inputs, verbatim
```

The explanations and driver buckets derive from the `recommendations` list (the
function does not receive the 10.0 forecast); `deltas` / `motifs` feed only the
`raw` transparency section; `stability` feeds the summary + the embedded context.

### Summary

2-3 deterministic, factual sentences:

1. **Stability** — `score > 0.7` → "Behavioral system is stable; recommendations
   focus on optimization."; `score < 0.4` → "...shows instability; recommendations
   target stabilization."; otherwise → "...shows moderate variability;
   recommendations address key leverage points." (`0.7` / `0.4` → moderate.)
2. **Counts** — "Generated N recommendation(s) across M reason type(s)."
3. **Top** (when present) — "Top recommendation: {label} — {reason} (score X.XX)."

No psychological or speculative language.

### Recommendation explanations

Each 11.0 recommendation (preserving its descending-score order) gains a
deterministic `explanation` keyed by `reason`:

| reason | explanation |
| --- | --- |
| habit_weakening | "This action is recommended because its habit strength is decreasing." |
| trigger_volatility | "This action is recommended due to volatility in its associated trigger chain." |
| loop_break | "This action is recommended to interrupt a weakening or unstable loop." |
| bottleneck_relief | "This action is recommended because it is a bottleneck with high inbound influence." |
| attractor_alignment | "This action aligns with a strong behavioral attractor." |
| forecast_alignment | "This action is predicted as likely in the near future." |

An unknown reason yields an empty explanation.

### Drivers

The recommendations partitioned by reason into six buckets — `habit` ←
`habit_weakening`, `triggers` ← `trigger_volatility`, `loops` ← `loop_break`,
`bottlenecks` ← `bottleneck_relief`, `attractors` ← `attractor_alignment`,
`forecast_alignment` ← `forecast_alignment`. Each entry `{action_id, metric,
reason}`, where `metric` is the 11.0 leverage score; the 11.0 score-descending
order is preserved within each bucket.

### Stability context + raw

`stability_context` embeds the full 10.2 `{score, drivers}`; `raw` carries the
`recommendations` / `deltas` / `motifs` inputs verbatim for transparency. This
object feeds 11.2 (surfacing).

---

## Phase 11.2 — Tri-Surface Recommendation Surfacing

The analogue of Phase 8.11 (causal surfacing) and 10.4 (behavioral forecast
surfacing): a **UI-only** pass that surfaces the 11.0 recommendations + 11.1
narrative to the operator across all three clients. No backend / Python / engine
changes — the tiles only render.

**Surfaces:** WEB, DESKTOP, PHONE. **Backend:** none (read-only).

| Surface | Tile | File |
| --- | --- | --- |
| Web | "Recommendations" | `web/src/routes/OperatorConsole.tsx` |
| Desktop | "Recommendations" | `desktop/src/OperatorConsoleShell.tsx` |
| Phone | "Actions" | `phone/app/operator_console.tsx` |

### Data source

A single read-only `telemetry.recommendation_narrative` object — the 11.1
`compute_recommendation_narrative` output, which already embeds the 11.0
recommendations (with explanations), the drivers partition, and the 10.2
stability context. The endpoint does not yet emit this key (11.2 makes **no
backend change**), so in the live app every section collapses until a later
backend integration populates it; the web / desktop tests stub it with the exact
11.1 shape.

### Sections (deterministic order)

| Section | Source | Shown |
| --- | --- | --- |
| A. Top Recommendations | `recommendations` | label · reason · score (desc) |
| B. Drivers | `drivers` (six buckets) | `action_id — reason (metric)` per entry |
| C. Stability Context | `stability_context` | score · four drivers |
| D. Narrative Summary | `summary` + top-3 `recommendations` | summary · top-3 explanations |

### Rules

- **Deterministic ordering** — every section renders its backend array verbatim
  (the engines already sort); section D shows the first three explanations.
- **Empty sections collapse** (web / desktop) — an empty section is omitted; each
  empty driver bucket is skipped, and the whole Drivers section collapses when
  all six are empty; an all-empty tile shows only its heading. A web / desktop
  list over 10 rows scrolls.
- **Phone** — one section per screen via a horizontal paging `ScrollView` (swipe
  navigation); four pages (Recommendations / Drivers / Stability / Narrative),
  each empty section showing a `None` sentinel. The phone tile is titled
  "Actions".
- No animations, no inference / psychological text.

### Tri-surface parity

All three surfaces read the identical `recommendation_narrative` object and
render the same sections in the same order; only the layout differs (collapsing
sections on web / desktop, a swipe pager on phone). Web
(`OperatorConsole.test.tsx`) and desktop (`OperatorConsoleShell.test.tsx`) each
add four tests (renders / backend shape, ordering, empty-collapse, scroll);
phone has no harness.

---

## Constraints (current scope: 11.0–11.2)

- **Deterministic only** — no randomness, no ML, no probabilistic inference, no
  psychological / speculative language, no wall-clock.
- **No runtime-spine imports** — `phase11_recommendations.py` and
  `phase11_narrative.py` import nothing beyond builtins.
- No `operator_state` writes, no new continuity buckets, no graph mutation.
- 11.2 is **UI-only** — no backend / Python / engine changes; the tiles render
  the 11.0 + 11.1 outputs read from `telemetry.recommendation_narrative`.
- **Flat root**: `phase11_*.py` live at the repo root, like Phase 6/7/8/9/10.

## Acceptance

- 11.0 — action recommendation engine: `compute_action_recommendations` →
  ranked `[{action_id, label, reason, score}]` over the six reason types
  (habit_weakening / trigger_volatility / loop_break / bottleneck_relief /
  attractor_alignment / forecast_alignment); deduped by `action_id`, top 10.
- 11.1 — recommendation narrative: `compute_recommendation_narrative` →
  `{summary, recommendations (+explanation), drivers, stability_context, raw}`
  (deterministic templates; no inference / ML / psychology).
- 11.2 — tri-surface surfacing: read-only "Recommendations" (web / desktop) /
  "Actions" (phone) tiles reading `telemetry.recommendation_narrative`
  (deterministic order; empty sections collapse on web/desktop, one-section-per-
  screen swipe on phone; no backend change); web + desktop vitest green.
- `pytest tests/test_phase11_recommendations.py tests/test_phase11_narrative.py`
  is green.
- This spec matches the code.
- No regressions in 7.0–10.4; no CI-gated runtime files changed.

## Next cards (not in scope here)

- Phase 12 — hardening + release.
