# Phase 10 — Behavioral Forecasting (Spec)

**Status:** Complete (10.0–10.4 implemented — the behavioral forecast engine, the
action-causal deltas, the behavioral stability forecast, the unified behavioral
narrative, and the tri-surface surfacing). Phase 10 complete.
**Surfaces:** Backend (Python) + clients (web, desktop, phone — 10.4 only).

Phase 7 forecast *time* (the drift trajectory); Phase 8.7 forecast *causal
structure* (stabilizing / destabilizing / transitioning). Phase 9 introduced
operator **actions** as first-class causal atoms and detected their **motifs**
(loops / triggers / habits / bottlenecks / attractors). Phase 10 closes the
loop: it **forecasts behaviour** — what the operator is likely to do next — from
the action stream, the 9.4 motifs, and the action-causal structure.

Like Phase 6/7/8/9, this track lives as flat repo-root modules (`phase10_*.py`)
with tests in `tests/test_phase10_*.py`. It is additive and **does not touch**
the CI-gated runtime spine, the vault, or `operator_state`.

---

## Phase 10.0 — Behavioral Forecast Engine

`phase10_forecast.py` is the behavioral analogue of Phase 7.0 (temporal
forecast) and Phase 8.7 (causal stability forecast), but for **actions**. It is
a **deterministic, local, rule-based** forecast — *not* ML, *not* probabilistic
inference, *no* randomness, *no* wall-clock, *no* inference.

```python
forecast_next_actions(actions, motifs, graph, influence) -> list[dict]
forecast_habit_trajectory(actions) -> list[dict]
forecast_trigger_likelihood(motifs, influence) -> list[dict]
forecast_loop_continuation(motifs, actions) -> list[dict]
compute_behavioral_forecast(actions, motifs, graph, influence) -> dict
```

### Inputs

All caller-supplied (the engine computes none of them — the same contract the
9.4 motif API uses):

| Input | Shape | Source |
| --- | --- | --- |
| `actions` | recent `ActionEvent`s (`.id` / `.label` / `.timestamp`) | 9.1 continuity |
| `motifs` | the 9.4 `analyze_behavioral_motifs` dict | 9.4 |
| `graph` | the action-augmented `CausalGraph` | 9.2 |
| `influence` | the 8.2 `propagate_influence` dict (`node_id -> [0, 1]`) | 8.2 |

`action_loops` + `habits` are action **labels**; `trigger_chains` +
`action_bottlenecks` + `action_attractors` are node **ids**. `graph` is accepted
for signature parity with the 9.4 API + future cross-graph scoring; 10.0's math
reads `actions` / `motifs` / `influence` only.

### `forecast_next_actions` — next likely actions (top 5)

Each distinct action label is a candidate, scored by a **deterministic weighted
sum** of four components (each in `[0, 1]`):

```
score = 0.4·loop_score + 0.3·habit_score + 0.2·trigger_score + 0.1·influence_score
```

* **loop_score** — `1.0` if the label is the cyclic *successor* of the
  most-recent action in a detected loop (the loop's "next" label), else `0.0`.
* **habit_score** — the label's frequency normalized by the strongest habit's
  frequency, when the label is a 9.4 habit; else `0.0`.
* **trigger_score** — `1.0` if the label participates (as an action endpoint —
  position 0 or 2) in a trigger chain, else `0.0`.
* **influence_score** — the action's 8.2 influence value, normalized across
  candidates.

Clamped to `[0, 1]`. Candidates scoring `0` are dropped; the rest sort by score
desc (ties by label) and cap at 5. Each entry:

```
{"action_id": <latest event id for the label>,
 "label": <str>,
 "score": <float in [0, 1]>,
 "drivers": [<subset of "loop" / "habit" / "trigger", in that order>]}
```

`drivers` lists which of loop / habit / trigger fired; a purely
influence-driven candidate has an empty `drivers` list.

### `forecast_habit_trajectory` — strengthening / weakening / stable

For each action label recurring `>= 3` times, split its inter-event gaps into an
earlier and a later half and compare:

```
strengthening  if Δfrequency > 0 AND Δspacing < 0   (events tightening)
weakening      if Δfrequency < 0 AND Δspacing > 0   (events loosening)
stable         otherwise                            (spacing unchanged)
```

Frequency is the reciprocal of mean spacing, so the two conditions are
consistent by construction; `stable` is the no-change case. Each entry:
`{"action_id": <latest event id>, "trend": <str>}`, sorted by label.

Note: the strict 9.4 *habit* filter requires *low* spacing variance and would
reject a trending habit, so the trajectory deliberately considers any label
recurring `>= 3` times (a superset) — otherwise it could never see a change.

### `forecast_trigger_likelihood` — trigger chain likelihood (top 5)

For each trigger chain `action → factor → action`:

```
likelihood = normalized(influence[action] + influence[factor])
```

normalized by the maximum raw sum across chains (→ `[0, 1]`). Sorted by
likelihood desc (ties by chain), capped at 5. Each entry:
`{"chain": [action_id, factor_id, action_id], "likelihood": <float in [0, 1]>}`.
(Trigger chains require `action → factor` edges, which the live 9.2 graph does
not yet produce, so this is empty until such edges exist — see 9.4.)

### `forecast_loop_continuation` — loop continuation probability

For each detected loop, combine three deterministic `[0, 1]` signals (equal
weights):

* **regularity** — `1 / (1 + cv)` of the loop participants' spacing
  (coefficient of variation `cv`); a perfectly regular loop → `1.0`.
* **adherence** — of the last *k* stream labels (`k` = loop length), the
  fraction that belong to the loop (recency: is the operator still cycling?).
* **tightness** — `min / max` visit count across the loop's labels (balance).

```
continuation_probability = clamp((regularity + adherence + tightness) / 3, 0, 1)
```

Sorted by probability desc (ties by loop). Each entry:
`{"loop": [<labels>], "continuation_probability": <float in [0, 1]>}`.

### `compute_behavioral_forecast` — unified forecast object

```
{"next_actions": [...],
 "habit_trajectory": [...],
 "trigger_likelihood": [...],
 "loop_continuation": [...]}
```

This is the object 10.4 will surface on `/operator/telemetry`.

### Determinism

Every list is sorted; scores are pure arithmetic over the inputs; the only
temporal signal is the caller-supplied action timestamps. No randomness, no
wall-clock, no ML, no inference.

---

## Phase 10.1 — Action-Causal Deltas

`phase10_deltas.py` is the behavioral analogue of Phase 7.1 (temporal deltas)
and Phase 8.6 (causal deltas), but for **actions**. It compares the most-recent
window of behaviour against the window before it and reports how four behavioral
quantities moved. Deterministic, mechanical — no ML, no randomness, no
wall-clock, no inference.

```python
compute_action_frequency_delta(actions, window) -> dict
compute_action_spacing_delta(actions, window) -> dict
compute_action_influence_delta(influence_records, window) -> dict
compute_action_centrality_delta(centrality, prev_centrality) -> dict
compute_behavioral_deltas(actions, influence, centrality, window, prev_centrality=None) -> dict
```

### Window semantics

The window is anchored at the **latest timestamp in the input** (no wall-clock):
`t_ref = max(timestamps)`. Then:

```
current  window = (t_ref - window,    t_ref]
previous window = (t_ref - 2*window,  t_ref - window]
```

Items older than the previous window are dropped; empty input → empty result.

### Keying

`frequency` + `spacing` are keyed by action **label** — the recurring behavioral
identity you can actually count / space (an event id is unique, so its frequency
is always 1). `influence` + `centrality` are keyed by the action node **id**
their 9.3 `InfluenceRecord` / 8.2 centrality inputs carry. The unified object's
four sub-dicts therefore use the identity natural to each metric. Every dict is
emitted in sorted-key order.

### Delta formulas

| Delta | Per key | Formula |
| --- | --- | --- |
| frequency | label | `(current − previous) / max(previous, 1)` over occurrence counts |
| spacing | label | `(previous_spacing − current_spacing) / max(previous_spacing, 1)` |
| influence | action id | `(current − previous) / max(previous, 1)` over summed record weights |
| centrality | node id | `current − previous` |

Spacing is the mean inter-event gap within a window (0.0 when a window has fewer
than two occurrences). A **positive spacing delta means spacing decreased — the
action is tightening**. Each entry carries its raw `current` / `previous` values
alongside the `delta`:

```
frequency / influence / centrality:  {key: {"current", "previous", "delta"}}
spacing:                             {label: {"current_spacing", "previous_spacing", "delta"}}
```

### Unified delta object

```
{"frequency": {...}, "spacing": {...}, "influence": {...}, "centrality": {...}}
```

`influence` here is the 9.3 `InfluenceRecord` stream (not the 8.2 influence dict
that 10.0 consumes). `centrality` is the current 8.2 centrality dict;
`prev_centrality` is the previous snapshot, defaulting to an empty baseline when
absent (so every current node reads as newly present — consistent with the
window-based deltas, where an absent previous window also surfaces as positive
change). This object feeds 10.2 (stability), 10.3 (narrative), 10.4 (surfacing).

---

## Phase 10.2 — Behavioral Stability Forecast

`phase10_stability.py` is the behavioral analogue of Phase 7.2 (temporal
stability) and Phase 8.7 (causal stability), but for **actions**. It folds the
10.1 deltas + the 9.4 motifs + the 10.0 forecast into a single `[0, 1]`
stability score plus the four drivers behind it.

```python
compute_behavioral_stability(deltas, motifs, forecast) -> dict
```

Output:

```
{"score": <float in [0, 1]>,
 "drivers": {"habit_stability", "trigger_stability",
             "loop_persistence", "action_variance"}}   # each in [0, 1]
```

### Components (each clamped to `[0, 1]`)

| Driver | Source | Formula |
| --- | --- | --- |
| habit_stability | 10.1 frequency deltas | `1 − mean(\|frequency delta\|)` |
| trigger_stability | 10.0 `trigger_likelihood` | `1 − mean(\|trigger likelihood\|)` |
| loop_persistence | 10.0 `loop_continuation` | `mean(continuation_probability)` |
| action_variance | 10.1 frequency deltas | `1 − variance(frequency delta)` |

`action_variance` uses the population variance of the frequency deltas; the
clamp normalizes it into `[0, 1]` (variance ≥ 1 → 0). Fewer than two frequency
deltas → variance 0 → `action_variance = 1.0`.

**Trigger driver note.** Neither 10.0 nor 10.1 produces a *temporal*
trigger-likelihood delta (no prior-forecast snapshot exists to diff against), so
trigger volatility is taken as the mean trigger-likelihood from the 10.0
forecast — each chain's likelihood is the magnitude of the behavioral shift it
would drive. A later card that snapshots forecasts can swap in a true temporal
delta without changing this contract. `motifs` is accepted for signature parity
(future motif-weighted scoring); the four components read the 10.1 deltas + 10.0
forecast only.

### Final score

```
score = 0.35*habit_stability + 0.25*trigger_stability
      + 0.25*loop_persistence + 0.15*action_variance
```

clamped to `[0, 1]` (weights sum to 1.0). An all-empty input scores **0.75** —
the three volatility drivers read 1.0 (no change is maximal stability) while
`loop_persistence` reads 0.0 (no detected loop = no demonstrated persistence).
This object feeds 10.3 (narrative) and 10.4 (surfacing).

---

## Phase 10.3 — Unified Behavioral Narrative

`phase10_narrative.py` is the behavioral analogue of Phase 7.3 (unified temporal
narrative) and Phase 8.9 + 8.10 (unified causal / temporal-causal narrative),
but for **actions**. It is the operator-facing explanation layer: a
deterministic account of what changed in behaviour, the drivers behind it, and
the patterns forming — assembled purely from 10.0 / 10.1 / 10.2 / 9.4. No
inference, no ML, no speculation, no psychological language.

```python
compute_behavioral_narrative(deltas, motifs, forecast, stability) -> dict
```

Output (mirrors the Phase-8 unified narrative shape):

```
{"summary": "...",
 "habit_changes":   [{action_id, trend, delta}],          # sorted by |delta| desc
 "trigger_changes": [{chain, delta}],                     # sorted by |delta| desc
 "loop_changes":    [{loop, continuation_probability}],   # sorted desc
 "stability": {"score", "drivers"},                       # the full 10.2 object
 "forecast_highlights": [{action_id, score, drivers}],    # top 3
 "raw": {"deltas", "motifs", "forecast"}}                 # inputs, verbatim
```

### Summary

2-3 deterministic, factual sentences:

1. **Stability** — `score > 0.7` → "Behavioral patterns are stable."; `score <
   0.4` → "Behavioral patterns are shifting."; otherwise → "Behavioral patterns
   show moderate change." (`0.7` / `0.4` fall in "otherwise" → moderate.)
2. **Counts** — "Detected N habit change(s), M trigger change(s), and K loop(s)."
3. **Forecast** (only when a highlight exists) — "Top predicted next action:
   {action_id} (score X.XX)."

No psychological or speculative language.

### Sections

| Section | Source | Ordering |
| --- | --- | --- |
| habit_changes | 10.0 `habit_trajectory` (`action_id` + `trend`) joined to the 10.1 `frequency` delta by `action_id` | `\|delta\|` desc, then `action_id` |
| trigger_changes | 10.0 `trigger_likelihood` (likelihood as the change signal) | `\|delta\|` desc, then chain |
| loop_changes | 10.0 `loop_continuation` | `continuation_probability` desc, then loop |
| stability | the full 10.2 `{score, drivers}` object, embedded verbatim | — |
| forecast_highlights | 10.0 `next_actions`, projected to `{action_id, score, drivers}` | `score` desc, top 3 |
| raw | the `deltas` / `motifs` / `forecast` inputs, verbatim | — |

**Join note.** `habit_changes` pairs the 10.0 trajectory `action_id` with the
10.1 frequency delta keyed by that `action_id`. Because the 10.1 frequency delta
is keyed by action *label* while the trajectory's `action_id` is a representative
event id, the caller (10.4) must key the frequency deltas under the trajectory's
identity — otherwise the trend is preserved and the delta reads 0.0.
`trigger_changes` reuses the 10.0 trigger likelihoods as the change signal (no
temporal trigger-likelihood delta is produced upstream — see 10.2). This object
feeds 10.4 (surfacing).

---

## Phase 10.4 — Tri-Surface Behavioral Forecast Surfacing

The behavioral analogue of Phase 7.4 (temporal surfacing) and Phase 8.11 (causal
surfacing): a **UI-only** pass that surfaces the 10.0-10.3 outputs to the
operator across all three clients. No backend / Python / engine changes — the
tiles only render.

**Surfaces:** WEB, DESKTOP, PHONE. **Backend:** none (read-only).

| Surface | Tile | File |
| --- | --- | --- |
| Web | "Behavioral Forecast" | `web/src/routes/OperatorConsole.tsx` |
| Desktop | "Behavioral Forecast" | `desktop/src/OperatorConsoleShell.tsx` |
| Phone | "Behavioral Forecast" | `phone/app/operator_console.tsx` |

### Data source

A single read-only envelope `telemetry.behavioral_forecast` (fetched on mount,
like every other operator tile):

```
{"forecast":  <10.0 output>,   # next_actions + loop_continuation rendered
 "stability": <10.2 output>,   # {score, drivers}
 "narrative": <10.3 output>}   # summary + habit/trigger changes + highlights
```

The 10.1 deltas surface through the narrative's per-change `delta` fields
(`habit_changes` / `trigger_changes`), so there is no standalone deltas section.
The endpoint does not yet emit this key (10.4 makes **no backend change**), so in
the live app every section collapses until a later backend integration populates
it; the web / desktop tests stub the envelope with the exact phase10 shapes.

### Sections (six, deterministic order)

| Section | Source | Shown |
| --- | --- | --- |
| A. Next Likely Actions | `forecast.next_actions` | label · score · drivers |
| B. Habit Trajectory | `narrative.habit_changes` | action · trend · delta |
| C. Trigger Likelihood | `narrative.trigger_changes` (top 3) | chain · delta |
| D. Loop Continuation | `forecast.loop_continuation` (top 3) | loop · probability |
| E. Stability | `stability` | score · four drivers |
| F. Narrative | `narrative.summary` + `forecast_highlights` (top 3) | summary · highlights |

### Rules

- **Deterministic ordering** — every section renders its backend array verbatim
  (the engines already sort); the top-3 sections slice the first three.
- **Empty sections collapse** (web / desktop) — a section with no data is omitted
  entirely; an all-empty tile shows only its heading. A web / desktop list over
  10 rows becomes independently scrollable.
- **Phone** — one section per screen via a horizontal paging `ScrollView` (swipe
  navigation); each empty section shows a `None` sentinel so the six pages stay
  stable. The phone tile is titled "Behavioral Forecast" to avoid colliding with
  the 9.5 "Behavior" (motifs) tile.
- No animations, no inference / psychological text.

### Tri-surface parity

All three surfaces read the identical `behavioral_forecast` envelope and render
the same six sections in the same order; only the layout differs (collapsing
sections on web / desktop, a swipe pager on phone). Web
(`OperatorConsole.test.tsx`) and desktop (`OperatorConsoleShell.test.tsx`) each
add four tests (renders / backend shape, top-3 caps + ordering, empty-collapse,
scroll); phone has no harness.

---

## Constraints (current scope: 10.0–10.4)

- **Deterministic only** — no randomness, no ML, no probabilistic inference, no
  psychological / speculative language, no wall-clock (action timestamps are the
  sole temporal input).
- **No runtime-spine imports** — `phase10_forecast.py` imports only the stdlib +
  the 8.0 primitive type (`phase8_structures.CausalGraph`); `phase10_deltas.py`
  and `phase10_stability.py` import only the stdlib; `phase10_narrative.py`
  imports nothing beyond builtins.
- No `operator_state` writes, no new continuity buckets, no graph mutation. 10.4
  is **UI-only** — no backend / Python / engine changes; the tiles render the
  10.0-10.3 outputs read from `telemetry.behavioral_forecast`.
- **Flat root**: `phase10_*.py` live at the repo root, like Phase 6/7/8/9.

## Acceptance

- 10.0 — behavioral forecast engine: `forecast_next_actions` (deterministic
  weighted scoring) + `forecast_habit_trajectory` + `forecast_trigger_likelihood`
  + `forecast_loop_continuation` + `compute_behavioral_forecast` (unified object).
- 10.1 — action-causal deltas: `compute_action_frequency_delta` +
  `compute_action_spacing_delta` + `compute_action_influence_delta` +
  `compute_action_centrality_delta` + `compute_behavioral_deltas` (unified object).
- 10.2 — behavioral stability forecast: `compute_behavioral_stability` →
  `{score, drivers}` over habit / trigger / loop / variance (weighted
  0.35 / 0.25 / 0.25 / 0.15).
- 10.3 — unified behavioral narrative: `compute_behavioral_narrative` →
  `{summary, habit_changes, trigger_changes, loop_changes, stability,
  forecast_highlights, raw}` (deterministic; no inference / ML / psychology).
- 10.4 — tri-surface surfacing: read-only "Behavioral Forecast" tiles on web /
  desktop / phone reading `telemetry.behavioral_forecast` (deterministic order;
  empty sections collapse on web/desktop, one-section-per-screen swipe on phone;
  no backend change); web + desktop vitest green.
- `pytest tests/test_phase10_forecast.py tests/test_phase10_deltas.py
  tests/test_phase10_stability.py tests/test_phase10_narrative.py` is green.
- This spec matches the code.
- No regressions in 7.0–9.5; no CI-gated runtime files changed.

## Next cards (not in scope here)

- Phase 11 — recommendations (the final optional intelligence layer).
