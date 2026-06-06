# ClarityOS — Unified Specification v1

**Status:** Release candidate (Phase 12 — Hardening + Release).
**Scope:** The ClarityOS operator-intelligence engine — runtime, telemetry,
continuity, operator state, and the temporal / causal / behavioral / forecasting
/ recommendation intelligence stack, plus its tri-surface (web / desktop / phone)
read-only surfacing.
**Authority:** This document is the single source of truth. It supersedes the
per-phase specs (`phase7_spec.md` … `phase11_spec.md`), which remain as
historical detail. Where this document and the code disagree, the code wins and
this document shall be corrected.

This specification is formal and deterministic. It contains no narrative, no
psychological language, no inference, and no speculation.

---

## 0. Determinism Doctrine (system-wide)

The intelligence engines (Phases 5–11) **shall** be pure and deterministic. Every
engine function **must**:

- be a pure function of its arguments — **no** I/O, **no** wall-clock, **no**
  randomness, **no** hidden global state;
- contain **no** machine learning and **no** probabilistic inference;
- perform **no** `operator_state` writes and open **no** new continuity buckets;
- return JSON-serialisable, fully-sorted output (every list ordered, every dict
  keyed in a deterministic order) so identical inputs yield byte-identical output.

The storage layers are the only stateful components and are explicitly scoped:

- **Telemetry** (Phase 2) persists `TelemetryRecord`s; timestamps are
  **caller-supplied** (no wall-clock inside the engine).
- **Continuity** (Phase 3) is an append-only action log; timestamps are
  caller-supplied.
- **Operator State** (Phase 4) is the one component permitted to use the
  wall-clock (`time.time()`) and to persist; it is **metadata-only** and never
  stores raw prompt/response text.

### Phase-numbering reconciliation

The conceptual phases below (1–12) are the authoritative organisation. The
implementation files carry historical `phaseN_` prefixes that do **not** map 1:1
to the conceptual numbers. The mapping is fixed and is as follows:

| Conceptual phase | Implementing modules (file prefix) |
| --- | --- |
| 1 — Runtime | `phase6_contracts.py`, `phase6_pipeline.py` (Engine V1) |
| 2 — Telemetry | `phase7_storage.py`, `phase7_telemetry.py` |
| 3 — Continuity | `phase9_actions.py`, `phase9_ingest.py` |
| 4 — Operator State | `operator_state.py` |
| 5 — Temporal Engine | `phase7_drift.py`, `phase7_analytics.py` |
| 6 — Temporal Surfacing | `phase7_endpoint.py` + operator consoles |
| 7 — Temporal Intelligence | `phase7_alerts.py`, `phase7_causality.py`, `phase7_explanation.py` |
| 8 — Causal Intelligence | `phase8_*.py` |
| 9 — Behavioral Intelligence | `phase9_integration.py`, `phase9_influence.py`, `phase9_behavioral_motifs.py` |
| 10 — Behavioral Forecasting | `phase10_*.py` |
| 11 — Recommendations | `phase11_*.py` |
| 12 — Hardening + Release | test suites + this spec |

All implementation modules live at the repository root (flat layout), import only
the stdlib + sibling phase modules + the 8.0 primitive type, and **shall not**
import from the CI-gated runtime spine, the vault (except `operator_state` and
the regression-chain store), or skills/plugins.

---

## Phase 1 — Runtime

**Purpose.** Compute the operator **superstructure** — the structured identity
state that every downstream phase reads. This is Engine V1.

**Inputs.** A metadata map (`Dict[str, str]`) of operator signals.

**Outputs.** A `SuperstructureState`.

**Modules.** `phase6_contracts.py` (data model), `phase6_pipeline.py`
(orchestration). The web/desktop operator consoles wrap this via the
`EngineV1OperatorAPI` (`createEngineV1OperatorAPI()` in `web/src/lib/api.ts`).

**Data structures.**

```python
@dataclass
class SuperstructureState:
    pattern:     SuperPatternState       # dominant_pattern, pattern_strength, pattern_stability, pattern_coherence, pattern_identity
    integration: SuperIntegrationState   # integration_strength, cross_layer_alignment, integration_identity
    coherence:   SuperCoherenceState     # coherence_level, drift_resistance, load_resilience, coherence_identity
    essence:     SuperEssenceState       # essence_signal, invariant_identity, essence_clarity
    identity:    SuperIdentityState      # operator_identity, identity_strength, identity_stability, identity_projection
```

**Deterministic rules.** `run_superstructure(meta)` composes the five sub-states
in fixed order (pattern → integration → coherence → essence → identity). It is a
pure function of `meta`; it uses no wall-clock and no randomness.

**Constraints.** No I/O, no randomness, no wall-clock, no `operator_state` writes.

**Acceptance.** `run_superstructure` is deterministic; identical `meta` yields an
identical `SuperstructureState`.

---

## Phase 2 — Telemetry

**Purpose.** Durably record operator superstructure snapshots and expose their
history.

**Inputs.** `record_snapshot(operator_id, snapshot: SuperstructureState, timestamp: float)`
— the timestamp is caller-supplied.

**Outputs.** `get_history(operator_id, limit=100) -> list[TelemetryRecord]`,
chronological (oldest first).

**Modules.** `phase7_storage.py`, `phase7_telemetry.py`.

**Data structures.**

```python
@dataclass
class TelemetryRecord:
    timestamp:        float
    superstructure:   SuperstructureState
    drift:            float | None
    coherence_health: float | None
    trust_band:       str | None
```

- `OPERATOR_ID` must match `^[A-Za-z0-9_.\-]{1,128}$`.
- Backends: `JsonlTelemetryStore` (durable, append-only JSONL at
  `data/telemetry/<operator_id>.jsonl`, default) and `MemoryTelemetryStore`
  (selected under `TESTING=1`).
- `record_to_dict` / `record_to_json` serialise with sorted keys; `DEFAULT_LIMIT`
  for the surfacing endpoint is `100`.

**Deterministic rules.** Serialisation is sorted-key (reproducible). Reads are
ordered. The store persists but the timestamp is never read from the wall-clock.

**Constraints.** No randomness; deterministic serialisation; timestamps
caller-supplied.

**Acceptance.** A recorded record round-trips through
`record_to_dict`/`record_from_dict` unchanged; history is returned oldest-first
capped at `limit`.

---

## Phase 3 — Continuity

**Purpose.** Ingest operator **actions** as first-class, append-only events that
later phases read.

**Inputs.** `ingest_action(raw: dict) -> ActionEvent`; `store_action(event, continuity)`.

**Outputs.** `load_recent_actions(continuity, now, window) -> list[ActionEvent]`;
`get_action_continuity() -> dict`.

**Modules.** `phase9_actions.py`, `phase9_ingest.py`.

**Data structures.**

```python
@dataclass
class ActionEvent:
    id:        str
    label:     str
    timestamp: float
    magnitude: float | None = None     # optional, validated to [-1.0, 1.0]
```

The continuity log is the single bucket `{"actions": [ActionEvent, ...]}`. No new
continuity buckets shall be added by any engine phase.

**Deterministic rules.** `ingest_action` validates `id`/`label`/`timestamp`
(non-negative) and clamps/validates `magnitude` to `[-1, 1]` (invalid → raises
`ValueError`). `store_action` appends and stable-sorts by `timestamp`.
`load_recent_actions` returns actions with `timestamp >= now - window`, sorted;
`now` is caller-supplied (no wall-clock).

**Constraints.** No wall-clock, no inference, no randomness; validation only;
append-only (no mutation or deletion).

**Acceptance.** Invalid actions raise `ValueError`; the log is timestamp-ordered;
`load_recent_actions` is a pure function of `(continuity, now, window)`.

---

## Phase 4 — Operator State

**Purpose.** Persist per-operator **metadata** continuity (preferences, history
of ELINS/#G runs, model selection) used to contextualise prompt-bearing runs.

**Inputs.** `update_operator_state(user_id, patch)`,
`record_elins_interaction(user_id, elins_id, context)`,
`record_g_run(user_id, g_id, context)`, `set_preferred_model`, `record_model_used`,
`bump_local_model_usage`, `set_external_signal_mode`.

**Outputs.** `get_operator_state(user_id) -> dict`; read helpers
`related_runs`, `continuity_section`, `continuity_context`.

**Modules.** `operator_state.py` (vault-backed; `STATE_VERSION =
"operator_state.v46.1"`).

**Data structures.** State dict keys: `user_id`, `created_ts`, `last_active_ts`,
`external_signal_mode` (∈ `{"cloud_only","cloud_perplexity"}`),
`preferred_domains`, `preferred_regions`, `preferred_model`, `last_model_used`,
`local_model_usage_count`, `el_ins_per_turn`, `elins_history`, `g_history`,
`version`. Constants: `HISTORY_MAX = 200`, `PREFERRED_DECAY = 0.9`,
`TOPIC_MAX_LEN = 200`.

**Deterministic rules.** Preference weighting applies exponential decay
(`× 0.9`) + increment, floor-pruned below `0.001`; history is pruned to
`HISTORY_MAX` oldest-first. Context is **metadata-only** — raw text fields are
rejected/stripped.

**Constraints.** This is the **only** component permitted to use the wall-clock
(for `created_ts` / `last_active_ts` / entry `ts`) and to persist. It stores **no**
raw prompt/response text. The intelligence engines (Phases 5–11) **must not**
write operator state.

**Acceptance.** State is metadata-only; history is bounded at `HISTORY_MAX`;
preference decay/prune is deterministic.

---

## Phase 5 — Temporal Engine

**Purpose.** Quantify identity movement over time: drift, coherence health, trust
band, and the forward stability forecast.

**Inputs.** `SuperstructureState` snapshots (drift) and `list[TelemetryRecord]`
(analytics).

**Outputs.** Drift / coherence-health / trust-band floats, and the analytics
block `{drift_velocity, drift_acceleration, coherence_trend, stability_forecast, trajectory}`.

**Modules.** `phase7_drift.py`, `phase7_analytics.py`.

**Deterministic rules.**

- `compute_drift(prev, curr)` ∈ `[0,1]` = `0.7·numeric_drift + 0.3·label_drift`
  over the 13 numeric signals + 3 identity anchors.
- `compute_coherence_health(history)` ∈ `[0,1]` = mean of the 9 coherence-bearing
  fields across snapshots (empty → `0.0`).
- `compute_trust_band(drift, coherence)` = `"HIGH"` if `coherence·(1−drift) ≥ 0.66`,
  `"MEDIUM"` if `≥ 0.33`, else `"LOW"`.
- Analytics over a regression `WINDOW = 5`: `drift_velocity` /
  `drift_acceleration` / `coherence_trend` are least-squares slopes (∈ `[-1,1]`;
  insufficient points → `0.0`).
- `stability_forecast` ∈ `[0,1]` = `0.4·(1−|velocity|) + 0.3·((1−acceleration)/2) + 0.3·((coherence_trend+1)/2)`.
- `classify_trajectory(forecast)`: `≥0.75 → "Stable"`, `≥0.50 → "Recovering"`,
  `≥0.25 → "Wobbling"`, else `"Diverging"`. Empty-history baseline: all `0.0`,
  trajectory `"Stable"`.

**Constraints.** Pure; no wall-clock, no randomness, no inference, no ML, no
`operator_state` writes.

**Acceptance.** Each statistic is a deterministic function of its inputs; the
empty-history baseline is exactly the stated neutral block.

---

## Phase 6 — Temporal Surfacing

**Purpose.** Expose the recorded telemetry + all computed intelligence read-only
over HTTP and render it identically across the three surfaces.

**Inputs.** None from the client (read-only `GET`).

**Outputs.** `GET /operator/telemetry` — the unified telemetry payload (see the
JSON Shape Index, §B.1). The endpoint writes nothing and mutates nothing.

**Modules.** `phase7_endpoint.py` (`router` mounted at `/operator`,
`OPERATOR_ID = "clarityos-operator"`, `DEFAULT_LIMIT = 100`); web
`OperatorConsole.tsx`, desktop `OperatorConsoleShell.tsx`, phone
`operator_console.tsx`.

**Deterministic rules.** The endpoint recomputes every block as a pure function of
the stored history on each request. Every list/dict is backend-sorted; the
consoles render in backend array order and never re-sort. The temporal tiles
(Operator Continuity, Operator Forecast, Operator Stability Alerts, Causal Drift
Factors, Causal Narrative) read the corresponding payload keys and collapse/clamp
per the Tri-Surface Parity rules (§A).

**Constraints.** Read-only; no animations; no inference text; deterministic
ordering.

**Acceptance.** The endpoint is side-effect-free; tile bindings resolve against
every payload key; empty history yields the neutral baseline.

---

## Phase 7 — Temporal Intelligence

**Purpose.** Interpret the temporal statistics into operator-facing alerts, the
causal drift factors behind movement, and a deterministic narrative.

**Inputs.** The analytics dict, telemetry history, and recent `OperatorAction`s.

**Outputs.** `alerts: list[str]`, `causal_factors: list[CausalFactor]`,
`narrative: str`.

**Modules.** `phase7_alerts.py`, `phase7_causality.py`, `phase7_explanation.py`.

**Data structures.**

```python
@dataclass
class CausalFactor:
    action:       str     # action name, or the sentinel "none"
    correlation:  float   # [-1, 1] signed drift shift after the action
    contribution: float   # [0, 1] destabilising magnitude
```

**Deterministic rules.**

- `compute_alerts(analytics)` fires one message per matched rule (Diverging
  trajectory; `stability_forecast < 0.40`; `drift_velocity > 0.20`;
  `drift_acceleration > 0.15`; `coherence_trend < -0.10`); no match → the single
  `"No alerts — operator trajectory stable"` sentinel.
- `compute_causal_factors(history, recent_actions)` considers the most-recent
  `WINDOW = 10` actions, scores each by before/after drift+coherence shift, drops
  `contribution < 0.05`, sorts by contribution descending; empty → the
  `[CausalFactor("none", 0.0, 0.0)]` sentinel.
- `generate_causal_narrative(analytics, alerts, causal_factors)` emits a
  fixed four-section template (Identity Movement Summary / Key Alerts / Likely
  Contributing Actions / Overall Interpretation); floats formatted to 2 decimals;
  the trajectory selects one of four fixed interpretation paragraphs.

**Constraints.** Pure; no wall-clock, no randomness, no ML, no inference beyond
the fixed rules, no psychological language, no `operator_state` writes.

**Acceptance.** Alerts, factors, and narrative are deterministic functions of
their inputs; the `"none"` sentinel paths are exercised on empty input.

---

## Phase 8 — Causal Intelligence

**Purpose.** Build and reason over a causal graph of the operator's temporal +
action signals: propagation, motifs, multi-chain explanations, deltas, stability,
and unified narrative.

**Inputs.** The Phase 5/7 analytics + alerts + causal factors (graph build);
recent actions (action augmentation, Phase 9).

**Outputs.** `causal_graph`, `primary_chain`, `causal_influence`,
`causal_centrality`, `ranked_explanations`, `causal_motifs`, `causal_chains`,
`causal_deltas`, `causal_stability`, `causal_narrative`, `unified_narrative`
(see §B.2).

**Modules + sub-phases.**

| Sub-phase | Module | Public surface |
| --- | --- | --- |
| 8.0 Structures | `phase8_structures.py` | `CausalNode`/`CausalEdge`/`CausalChain`/`CausalGraph`; `make_node`/`make_edge`/`build_graph`/`graph_to_dict`/`chain_to_dict`; `ACTION_NODE_TYPE = "action"` |
| 8.1 Inference | `phase8_inference.py` | `build_phase7_graph(history, analytics, alerts, causal_factors)`, `extract_primary_chain(graph)` |
| 8.2 Propagation | `phase8_propagation.py` | `propagate_influence` (`MAX_STEPS = 3`), `compute_node_centrality`, `rank_causal_explanations` |
| 8.3 Motifs | `phase8_motifs.py` | `analyze_motifs` → `{feedback_loops, bottlenecks, attractors}` (centrality `>0.6` & degree `≥3`; influence `>0.7`) |
| 8.4 Multi-chain | `phase8_multichain.py` | `generate_causal_chains`, `scored_chains_to_dicts` (chain + `{passes_bottleneck, passes_attractor, in_feedback_loop}`) |
| 8.6 Deltas | `phase8_deltas.py` | `compute_causal_deltas(prev, curr)` → `{influence_delta, centrality_delta, motif_delta, chain_delta}` |
| 8.7 Stability | `phase8_stability.py` | `compute_causal_stability(deltas, curr)` → `{stability_score, trend, drivers}` |
| 8.9 Narrative | `phase8_narrative.py` | `generate_phase8_causal_narrative(curr, deltas, stability)` |
| 8.10 Unified | `phase8_unified_narrative.py` | `generate_unified_narrative(temporal, causal)` |

**Deterministic rules.** Influence/centrality ∈ `[0,1]`, sorted by node id;
propagation is synchronous (edge-order-independent) over `MAX_STEPS = 3`; intrinsic
weight precedence is `node.value` → type-fixed (`alert 0.5`, `narrative 0.3`) →
deprecated label-parse. Loops are canonical min-rooted cycles (len 2–6, cap 10).
Stability `trend ∈ {steady, destabilizing, stabilizing, transitioning}` by the
fixed precedence (destabilizing forced on any new loop/bottleneck or score `<0.4`;
stabilizing requires score `>0.7` & zero motif events & `|shift|<0.1`). Narratives
are fixed-section templates; the Phase-8.10 Overall Assessment is one of
`{Stable, Shifting, Transitioning, Destabilizing}`.

**Constraints.** Pure; no I/O, wall-clock, randomness, ML, inference, or
`operator_state` writes; stdlib + 8.0 primitives only.

**Acceptance.** Every 8.x output is JSON-serialisable and deterministic; the
no-previous-snapshot path yields zero deltas and a `steady` trend.

---

## Phase 9 — Behavioral Intelligence

**Purpose.** Make operator actions first-class causal atoms and detect behavioral
**motifs** over the action-augmented graph.

**Inputs.** `ActionEvent`s (Phase 3); the Phase-8 `CausalGraph`; the 8.2
`influence` / `centrality` dicts.

**Outputs.** `behavioral_motifs` = `{action_loops, trigger_chains, habits,
action_bottlenecks, action_attractors}` (see §B.3).

**Modules + sub-phases.**

| Sub-phase | Module | Public surface |
| --- | --- | --- |
| 9.0 Primitive | `phase9_actions.py` | `ActionEvent`, `make_action_node` |
| 9.1 Ingest | `phase9_ingest.py` | (Phase 3 continuity) |
| 9.2 Integration | `phase9_integration.py` | `action_event_to_causal_node`, `integrate_action_node`, `link_action_to_variables`, `integrate_recent_actions` (action → variable edges only; `SYSTEM_VARIABLE_IDS`) |
| 9.3 Influence | `phase9_influence.py` | `InfluenceRecord(action_id, variable_id, weight, timestamp)`, `propagate_action_influence`, `propagate_recent_actions` (single-hop; weight = clamped magnitude) |
| 9.4 Motifs | `phase9_behavioral_motifs.py` | `analyze_behavioral_motifs(actions, graph, influence, centrality)` |
| 9.5 Surfacing | operator consoles | "Behavioral Motifs" (web) / "Behavioral Patterns" (desktop) / "Behavior" (phone) tile |

**Deterministic rules.** `action_loops` + `habits` are keyed by action **label**
(the recurring identity); `trigger_chains` (`[action_id, factor_id, action_id]`),
`action_bottlenecks`, `action_attractors` are keyed by node **id**. Loops are
canonical min-rotation simple cycles (len 2–6, cap 10). Habits recur `≥3` times
with spacing CV `<0.2` (top 5 by count). Bottlenecks: action nodes with
centrality `>0.6` & degree `≥3`; attractors: action nodes with influence `>0.7` &
inbound `>` outbound. Action nodes are graph **sources** (action → variable only).

**Constraints.** Pure; no wall-clock, randomness, ML, inference, `operator_state`
writes, or new continuity buckets; the graph is never mutated by 9.3+.

**Acceptance.** With no stored actions every motif family is `[]`; outputs are
deterministic and JSON-serialisable.

---

## Phase 10 — Behavioral Forecasting

**Purpose.** Predict near-future behaviour deterministically: next actions, habit
trajectories, trigger likelihood, loop continuation; the deltas, stability, and
narrative over those.

**Inputs.** `actions`, the 9.4 `motifs`, the action-augmented `graph`, the 8.2
`influence` dict (forecast); the 9.3 `InfluenceRecord` stream + 8.2 centrality
(deltas); the prior outputs (stability/narrative).

**Outputs.** `behavioral_forecast` (10.0), `behavioral_deltas` (10.1),
`behavioral_stability` (10.2), `behavioral_narrative` (10.3) — see §B.4.

**Modules + sub-phases.**

| Sub-phase | Module | Public surface |
| --- | --- | --- |
| 10.0 Forecast | `phase10_forecast.py` | `forecast_next_actions`, `forecast_habit_trajectory`, `forecast_trigger_likelihood`, `forecast_loop_continuation`, `compute_behavioral_forecast` |
| 10.1 Deltas | `phase10_deltas.py` | `compute_action_frequency_delta`, `compute_action_spacing_delta`, `compute_action_influence_delta`, `compute_action_centrality_delta`, `compute_behavioral_deltas` |
| 10.2 Stability | `phase10_stability.py` | `compute_behavioral_stability` → `{score, drivers{habit_stability, trigger_stability, loop_persistence, action_variance}}` |
| 10.3 Narrative | `phase10_narrative.py` | `compute_behavioral_narrative` |
| 10.4 Surfacing | operator consoles | "Behavioral Forecast" tile (all three surfaces) |

**Deterministic rules.**

- Next-action score = `0.4·loop + 0.3·habit + 0.2·trigger + 0.1·influence`,
  clamped `[0,1]`; zero-score candidates dropped; top 5 by score (ties by label);
  `drivers ⊆ {loop, habit, trigger}`.
- Habit trajectory ∈ `{strengthening, weakening, stable}` from earlier-vs-later
  inter-event gap halves (frequency = 1/spacing).
- Trigger likelihood = `normalized(influence[action] + influence[factor])`, top 5.
- Loop continuation = `mean(regularity, adherence, tightness)` ∈ `[0,1]`.
- Deltas anchored at the latest input timestamp (no wall-clock): current window
  `(t_ref−w, t_ref]`, previous `(t_ref−2w, t_ref−w]`. Frequency/spacing keyed by
  label; influence/centrality keyed by id.
- Behavioral stability = `0.35·habit_stability + 0.25·trigger_stability +
  0.25·loop_persistence + 0.15·action_variance`, each clamped `[0,1]`; all-empty
  input scores `0.75`.
- Narrative is a fixed-section object (`summary`, `habit_changes`,
  `trigger_changes`, `loop_changes`, `stability`, `forecast_highlights`, `raw`);
  summary phrase by stability score (`>0.7` stable / `<0.4` shifting / else
  moderate).

**Constraints.** Pure; no wall-clock (action timestamps are the only temporal
input), randomness, ML, inference, psychological language, `operator_state`
writes, or new continuity buckets. `phase10_forecast.py` imports only stdlib +
`phase8_structures.CausalGraph`; the others import only stdlib.

**Acceptance.** Each function is deterministic and JSON-serialisable; empty inputs
yield the documented neutral results.

---

## Phase 11 — Recommendations

**Purpose.** Surface deterministic structural leverage points as recommended
operator actions, with a deterministic explanation narrative.

**Inputs.** The 10.1 `deltas`, the 9.4 `motifs`, the 10.2 `stability`, the 10.0
`forecast` (engine); the resulting `recommendations` + `deltas`/`motifs`/`stability`
(narrative).

**Outputs.** `recommendations` (11.0), `recommendation_narrative` (11.1) — see §B.5.

**Modules + sub-phases.**

| Sub-phase | Module | Public surface |
| --- | --- | --- |
| 11.0 Engine | `phase11_recommendations.py` | `compute_action_recommendations(deltas, motifs, stability, forecast)` |
| 11.1 Narrative | `phase11_narrative.py` | `compute_recommendation_narrative(recommendations, deltas, motifs, stability)` |
| 11.2 Surfacing | operator consoles | "Recommendations" (web/desktop) / "Actions" (phone) tile |

**Deterministic rules.** Six reason types, each clamped `[0,1]`:
`habit_weakening` (`|frequency delta|`, delta `<0`), `trigger_volatility`
(`|likelihood|`), `loop_break` (`1−continuation`), `bottleneck_relief` /
`attractor_alignment` (normalized 9.4 list rank), `forecast_alignment`
(`forecast score`). Drop zero-score → sort by `(−score, action_id, reason)` →
dedupe by `action_id` (keep highest-scoring reason) → top 10. `habit_weakening` &
`forecast_alignment` key by label so they dedupe; `loop`/`trigger` by joined
sequence; `bottleneck`/`attractor` by node id. `stability` is accepted for
signature parity (reserved). The narrative attaches a fixed explanation template
per reason and partitions the recommendations into six driver buckets.

**Constraints.** Pure; no wall-clock, randomness, ML, inference, psychological
language, `operator_state` writes, or new continuity buckets; builtins only.

**Acceptance.** All six reason types are produced; output is deterministic, top-10,
deduped, JSON-serialisable; empty inputs → `[]`.

---

## Phase 12 — Hardening + Release

**Purpose.** Validate the system end-to-end, certify determinism, consolidate the
spec, and package the release candidate.

**Deliverables (12.0 complete).** Full test sweep: backend `pytest` (all tests
pass), web + desktop vitest (all pass), phone static certification (typecheck +
structure). The single historical flake (regression-chain newest-first ordering)
is resolved by the lock-guarded monotonic `seq` (`(created_at, seq, chain_id)
DESC`).

**Constraints.** Documentation / verification only — no new features, logic,
modules, data structures, inference, ML, psychological language, wall-clock
dependencies, or `operator_state` writes. Only regressions/test failures may be
fixed.

**Acceptance.** Backend / web / desktop suites pass; phone smoke (static) passes;
no regressions; no nondeterminism; no broken bindings; no missing fields; this
unified spec exists and matches the implementation.

---

## §A. Tri-Surface Parity

For every surfacing phase the three clients **shall** render the same sections, in
the same backend-determined order, from the same read-only payload. Layout differs
only as noted. All surfaces: **no animations, no inference text, no psychological
language, deterministic ordering.**

| Surfacing | Web tile | Desktop tile | Phone tile | Source key |
| --- | --- | --- | --- | --- |
| Temporal (6) | Operator Continuity / Forecast / Stability Alerts / Causal Drift Factors / Causal Narrative | same | same (vertical) | telemetry top-level keys |
| Causal (8.11) | Causal Chains / Structural Motifs / Causal Stability / Unified Narrative | same | same (vertical) | `causal_chains`, `causal_motifs`, `causal_stability`, `unified_narrative` |
| Behavioral motifs (9.5) | "Behavioral Motifs" | "Behavioral Patterns" | "Behavior" (swipe pager) | `behavioral_motifs` |
| Behavioral forecast (10.4) | "Behavioral Forecast" | "Behavioral Forecast" | "Behavioral Forecast" (swipe pager) | `behavioral_forecast` |
| Recommendations (11.2) | "Recommendations" | "Recommendations" | "Actions" (swipe pager) | `recommendation_narrative` |

**Ordering rules.** Tiles render the backend array verbatim (engines pre-sort);
"top N" sections slice the first N.

**Collapse rules (web / desktop).** A section with no data is omitted entirely;
each empty sub-bucket is skipped; an all-empty tile shows only its heading. A list
exceeding 10 rows becomes independently scrollable (`max-height: 20rem; overflow-y:
auto`).

**Phone rules.** One section per screen via a horizontal `pagingEnabled`
`ScrollView` (swipe navigation); empty sections show a `None` sentinel so the page
count stays stable.

**Surfacing-readiness note.** `behavioral_motifs` is emitted live by
`GET /operator/telemetry`. The `behavioral_forecast` (10.x) and
`recommendation_narrative` (11.x) tiles are implemented and tested against the
exact engine shapes but read telemetry keys **not yet emitted** by the endpoint
(10.4/11.2 were UI-only by mandate); they render live data once a backend-wiring
step adds those two keys to the telemetry payload. Until then those tiles collapse
to their heading. This is the one known release-deferred integration.

---

## §B. JSON Shape Index

All shapes are JSON-serialisable and deterministically ordered.

### B.1 `GET /operator/telemetry` (top-level keys)

| Key | Shape |
| --- | --- |
| `history` | `list[TelemetryRecord-dict]` (oldest first, ≤100) |
| `latest` | newest record dict, or `null` |
| `analytics` | `{drift_velocity, drift_acceleration, coherence_trend, stability_forecast, trajectory}` |
| `alerts` | `list[str]` |
| `causal_factors` | `[{action, correlation, contribution}]` (or `"none"` sentinel) |
| `narrative` | `str` (Phase 7 template) |
| `causal_graph` | `{nodes:{id:{id,type,label,timestamp,value}}, edges:[{source,target,weight}]}` |
| `primary_chain` | `{nodes:[…], edges:[…], score}` |
| `causal_influence` | `{node_id: float}` |
| `causal_centrality` | `{node_id: float}` |
| `ranked_explanations` | `[{node,label,influence,centrality,score}]` |
| `causal_motifs` | `{feedback_loops:[[id]], bottlenecks:[id], attractors:[id]}` |
| `causal_chains` | `[{nodes:[…], edges:[…], score, motifs:{passes_bottleneck,passes_attractor,in_feedback_loop}}]` |
| `causal_deltas` | `{influence_delta:{id:float}, centrality_delta:{id:float}, motif_delta:{…}, chain_delta:{new_chains,resolved_chains,score_shift}}` |
| `causal_stability` | `{stability_score, trend, drivers:{rising_influence,falling_influence,new_bottlenecks,resolved_bottlenecks,new_loops,resolved_loops,chain_strengthening,chain_weakening}}` |
| `causal_narrative` | `str` (Phase 8.9) |
| `unified_narrative` | `str` (Phase 8.10) |
| `behavioral_motifs` | `{action_loops:[[label]], trigger_chains:[[id]], habits:[label], action_bottlenecks:[id], action_attractors:[id]}` |

### B.2 Telemetry record

`{timestamp, superstructure:{pattern,integration,coherence,essence,identity}, drift, coherence_health, trust_band}`

### B.3 Behavioral forecast (`behavioral_forecast`, 10.x — UI-ready, pending wiring)

```
{forecast:  {next_actions:[{action_id,label,score,drivers:[str]}],
             habit_trajectory:[{action_id,trend}],
             trigger_likelihood:[{chain:[id],likelihood}],
             loop_continuation:[{loop:[label],continuation_probability}]},
 deltas:    {frequency:{label:{current,previous,delta}}, spacing:{label:{current_spacing,previous_spacing,delta}},
             influence:{id:{current,previous,delta}}, centrality:{id:{current,previous,delta}}},
 stability: {score, drivers:{habit_stability,trigger_stability,loop_persistence,action_variance}},
 narrative: {summary, habit_changes:[{action_id,trend,delta}], trigger_changes:[{chain,delta}],
             loop_changes:[{loop,continuation_probability}], stability:{score,drivers},
             forecast_highlights:[{action_id,score,drivers}], raw:{deltas,motifs,forecast}}}
```

### B.4 Recommendations + narrative (`recommendation_narrative`, 11.x — UI-ready, pending wiring)

```
{summary,
 recommendations:[{action_id,label,reason,score,explanation}],
 drivers:{habit:[…],triggers:[…],loops:[…],bottlenecks:[…],attractors:[…],forecast_alignment:[…]},   # entries {action_id,metric,reason}
 stability_context:{score,drivers},
 raw:{recommendations,deltas,motifs}}
```
`reason ∈ {habit_weakening, trigger_volatility, loop_break, bottleneck_relief, attractor_alignment, forecast_alignment}`.

---

## §C. Module Index

| Module | Path | Purpose | Inputs | Outputs |
| --- | --- | --- | --- | --- |
| `phase6_contracts` | `phase6_contracts.py` | Runtime data model | — | `SuperstructureState` + 5 sub-states |
| `phase6_pipeline` | `phase6_pipeline.py` | Engine V1 superstructure pipeline | `meta: Dict[str,str]` | `SuperstructureState` |
| `phase7_storage` | `phase7_storage.py` | Telemetry persistence (JSONL/memory) | `TelemetryRecord` | records / dicts |
| `phase7_telemetry` | `phase7_telemetry.py` | Recording API | `SuperstructureState`, ts | `TelemetryRecord` |
| `phase9_actions` | `phase9_actions.py` | Action primitive | `ActionEvent` | `CausalNode` |
| `phase9_ingest` | `phase9_ingest.py` | Action continuity log | raw action dict | `ActionEvent` / continuity |
| `operator_state` | `operator_state.py` | Per-operator metadata memory | user_id, patch/context | state dict |
| `phase7_drift` | `phase7_drift.py` | Drift / coherence / trust | `SuperstructureState`(s) | floats |
| `phase7_analytics` | `phase7_analytics.py` | Forecast + trajectory | `list[TelemetryRecord]` | analytics dict |
| `phase7_endpoint` | `phase7_endpoint.py` | `/operator/telemetry` surfacing | — | telemetry payload |
| `phase7_alerts` | `phase7_alerts.py` | Stability alerts | analytics dict | `list[str]` |
| `phase7_causality` | `phase7_causality.py` | Causal drift factors | history, actions | `list[CausalFactor]` |
| `phase7_explanation` | `phase7_explanation.py` | Temporal narrative | analytics, alerts, factors | `str` |
| `phase8_structures` | `phase8_structures.py` | Causal primitives | — | graph/node/edge/chain |
| `phase8_inference` | `phase8_inference.py` | First-order graph build | analytics/alerts/factors | `CausalGraph`, chain |
| `phase8_propagation` | `phase8_propagation.py` | Influence / centrality / ranking | `CausalGraph` | dicts / list |
| `phase8_motifs` | `phase8_motifs.py` | Causal motifs | graph, influence, centrality | motifs dict |
| `phase8_multichain` | `phase8_multichain.py` | Ranked multi-chains | graph, influence, centrality, motifs | chain dicts |
| `phase8_deltas` | `phase8_deltas.py` | Causal deltas | prev, curr states | deltas dict |
| `phase8_stability` | `phase8_stability.py` | Causal stability forecast | deltas, curr | stability dict |
| `phase8_narrative` | `phase8_narrative.py` | Causal narrative | curr, deltas, stability | `str` |
| `phase8_unified_narrative` | `phase8_unified_narrative.py` | Temporal-causal narrative | temporal, causal | `str` |
| `phase9_integration` | `phase9_integration.py` | Action → graph integration | event, graph | edges/None |
| `phase9_influence` | `phase9_influence.py` | Single-hop action influence | node, graph, continuity | `InfluenceRecord`s |
| `phase9_behavioral_motifs` | `phase9_behavioral_motifs.py` | Behavioral motifs | actions, graph, influence, centrality | motifs dict |
| `phase10_forecast` | `phase10_forecast.py` | Behavioral forecast | actions, motifs, graph, influence | forecast dict |
| `phase10_deltas` | `phase10_deltas.py` | Behavioral deltas | actions, influence-records, centrality, window | deltas dict |
| `phase10_stability` | `phase10_stability.py` | Behavioral stability | deltas, motifs, forecast | `{score,drivers}` |
| `phase10_narrative` | `phase10_narrative.py` | Behavioral narrative | deltas, motifs, forecast, stability | narrative dict |
| `phase11_recommendations` | `phase11_recommendations.py` | Recommendation engine | deltas, motifs, stability, forecast | `list[rec]` |
| `phase11_narrative` | `phase11_narrative.py` | Recommendation narrative | recommendations, deltas, motifs, stability | narrative dict |

---

## §D. Acceptance (release gate)

The release candidate is certified when, and only when:

- the full backend `pytest` suite passes (deterministically) and the web + desktop
  vitest suites pass; the phone surface is type-clean and structurally complete;
- every engine function is pure and deterministic per §0 (no wall-clock,
  randomness, ML, inference, psychological language, or `operator_state` writes);
- every surfacing tile binds against the documented JSON shapes (§B) and obeys the
  Tri-Surface Parity rules (§A);
- no deprecated structures, no missing phases, no missing modules (§C), and no
  missing JSON shapes (§B) remain;
- the single known release-deferred item (wiring `behavioral_forecast` and
  `recommendation_narrative` into `/operator/telemetry`) is tracked.

This document is complete, deterministic, drift-free, and ready for release
packaging.
