# Phase 8 — Structural Causal Chains (Spec)

**Status:** In progress (8.0–8.10 implemented — primitives + full inference
stack: graph, propagation, motifs, multi-chain explanations; operator-facing
surfacing in all consoles (8.5 chains+motifs, 8.8 stability); temporal causal
deltas (8.6); causal stability forecast (8.7); unified causal narrative (8.9);
unified temporal-causal narrative (8.10)).
**Surfaces:** Backend (Python); consoles (8.5, 8.8).

Phase 7 answered *what happened* (temporal intelligence). Phase 8 answers *why
it happened* — modeling identity movement as a causal graph. It is additive and
**does not touch** the CI-gated runtime spine (`app.py`, `intelligence_kernel.py`,
`model_router.py`, `operator_state.py`, `memory_vault.py`, `runtime_privacy.py`),
the vault, or `operator_state`.

This track lives as flat repo-root modules (`phase8_*.py`) with tests in
`tests/test_phase8_*.py`, like the Phase 6/7 modules.

---

## Phase 8.0 — Structural Causal Primitives

`phase8_structures.py` defines the data model — the "AST" the 8.1–8.4 inference
engine and 8.5+ surfacing layers build on. **8.0 defines primitives only; it
computes no inference.** Pure and deterministic: no I/O, wall-clock, randomness,
or side effects.

### Primitives (dataclasses)

| Type | Fields | Notes |
| --- | --- | --- |
| `CausalNode` | `id: str`, `type: str`, `label: str`, `timestamp: float \| None = None`, `value: float \| None = None` | an event / action / state; `value` (8.2a) = normalized intrinsic magnitude in `[0, 1]` |
| `CausalEdge` | `source: str`, `target: str`, `weight: float` | directional influence `source → target`; `weight ∈ [-1, 1]` |
| `CausalChain` | `nodes: list[CausalNode]`, `edges: list[CausalEdge]`, `score: float` | ordered chain + `[0, 1]` confidence |
| `CausalGraph` | `nodes: dict[str, CausalNode]`, `edges: list[CausalEdge]` | nodes keyed by id |

**Node types.** `type` is a free string tag — Phase 8 uses values like
`"action"`, `"state"`, `"drift"`, `"coherence"`, and `"alert"`. `timestamp` is
caller-supplied (no wall-clock) and optional. `value` (Phase 8.2a) is the
optional normalized intrinsic magnitude in `[0, 1]` that downstream reasoning
reads directly instead of parsing the label (both default to `None`).

**Edge semantics.** An edge is a directed `source → target` influence. `weight`
is the signed strength in `[-1, 1]` (positive = reinforcing, negative =
counteracting); `make_edge` clamps out-of-range weights.

### Utilities

```python
make_node(id, type, label, timestamp=None, value=None) -> CausalNode
make_edge(source, target, weight) -> CausalEdge          # clamps weight to [-1, 1]
score_chain(edges) -> float                              # mean |weight|, in [0, 1]; [] -> 0.0
build_chain(nodes, edges) -> CausalChain                 # score = score_chain(edges)
build_graph(nodes, edges) -> CausalGraph                 # nodes keyed by id (last write wins)
chain_to_dict(chain) -> dict
graph_to_dict(graph) -> dict
```

**Chain scoring.** `score` is the **mean absolute edge weight** — a deterministic
structural aggregate (an edgeless chain scores `0.0`), clamped to `[0, 1]`. This
is a structural placeholder; true confidence inference is 8.1–8.4.

**Serialization format.** JSON-serialisable dicts via `dataclasses.asdict`:

```json
// chain_to_dict
{ "nodes": [{"id","type","label","timestamp","value"}, ...],
  "edges": [{"source","target","weight"}, ...],
  "score": 0.0 }

// graph_to_dict
{ "nodes": {"<id>": {"id","type","label","timestamp","value"}, ...},
  "edges": [{"source","target","weight"}, ...] }
```

**Determinism.** All functions are pure; dict ordering follows insertion order;
serialization is stable for equal inputs.

---

## Phase 8.1 — First-Order Causal Chain Generation

`phase8_inference.py` populates the 8.0 primitives from Phase 7 signals — the
first machine-readable causal explanation. First-order only (shallow,
deterministic); deeper inference is 8.2–8.4.

    build_phase7_graph(history, analytics, alerts, causal_factors) -> CausalGraph
    extract_primary_chain(graph) -> CausalChain

(`history` is accepted for signature stability / future multi-hop inference;
the first-order rules use only `analytics`, `alerts`, and `causal_factors`.)

**Nodes.** The five analytics signals — `drift_velocity` (type `drift`),
`drift_acceleration` (`drift`), `coherence_trend` (`coherence`),
`stability_forecast` (`forecast`), `trajectory` (`trajectory`); one `alert` node
per alert (`alert_<i>`); one `action` node per *real* causal factor
(`factor_<i>` — the Phase 7.7 `"none"` sentinel is skipped); and a `narrative`
node.

**Edges (deterministic).**

| Rule | Edge | Weight |
| --- | --- | --- |
| alert text contains "drift" | `drift_velocity → alert_<i>` | `0.5` |
| alert text contains "coherence" | `coherence_trend → alert_<i>` | `0.5` |
| factor contribution `> 0.1` | `drift_velocity → factor_<i>` | contribution |
| every real factor | `factor_<i> → narrative` | contribution |
| always | `drift_velocity → narrative` | `0.3` |

All weights are clamped to `[-1, 1]` by `make_edge`.

**Primary chain.** `extract_primary_chain` starts from the strongest causal
factor (the `action` node whose `→ narrative` edge has the highest weight) and
follows it to the narrative — a single-hop `factor → narrative` chain. With no
causal factors it falls back to the analytics→narrative edge
(`drift_velocity → narrative`, score `0.3`). The chain `score` is the mean
absolute edge weight (8.0 `build_chain`); first-order weights are non-negative,
so this equals the average edge weight.

**Endpoint.** `GET /operator/telemetry` adds read-only `causal_graph`
(`graph_to_dict`) and `primary_chain` (`chain_to_dict`). With no action source,
`primary_chain` is the analytics→narrative fallback. Pure: no I/O, wall-clock,
randomness, or persistence.

---

## Phase 8.2 — Multi-Hop Causal Propagation

`phase8_propagation.py` reasons across the 8.1 graph — propagating influence,
scoring centrality, and ranking explanations. Pure / deterministic.

**Intrinsic weights** (each node's starting influence, in `[0, 1]`) — precedence
(Phase 8.2a):

1. **`node.value` when present** → `abs(value)` clamped to `[0, 1]`. This is the
   preferred path: 8.1 sets `value` on analytics nodes (`abs(metric)`) and on
   `action` (factor) nodes (`= contribution`), so propagation reads structured
   magnitudes with no coupling to label text.
2. type-fixed weights for structural nodes with no `value`: `alert` → `0.5`,
   `narrative` → `0.3` (8.1 leaves their `value` as `None`).
3. **DEPRECATED fallback** — `abs(magnitude)` parsed from the node label, for
   legacy / hand-built nodes that carry no `value`; a label with no number
   (e.g. `"Trajectory: Diverging"`) → `0.0`. This path will be removed once all
   producers set `value`.

**Propagation** — `propagate_influence(graph) -> dict[node_id, float]`. Start at
the intrinsic weights; for `MAX_STEPS = 3` iterations apply, synchronously (from
the start-of-step values, so the result is independent of edge order):

```
influence[target] += influence[source] * edge.weight
```

clamping every value to `[0, 1]` after each step. Returns a dict in sorted
node-id order.

**Centrality** — `compute_node_centrality(graph, influence) -> dict[node_id, float]`:

```
raw = inbound  (Σ influence[source] over edges into the node)
    + outbound (Σ influence[target] over edges out of the node)
    + intrinsic weight
```

normalized by the maximum `raw` across nodes (→ `[0, 1]`; all `0.0` when no node
has any).

**Ranked explanations** — `rank_causal_explanations(graph, influence, centrality)
-> list[dict]`. One entry per node `{node, label, influence, centrality, score}`
where `score = (influence + centrality) / 2`, sorted by `score` descending
(stable; ties keep sorted-node-id order).

**Endpoint.** `GET /operator/telemetry` adds read-only `causal_influence`
(`{node_id: float}`), `causal_centrality` (`{node_id: float}`), and
`ranked_explanations` (`[{node, label, influence, centrality, score}, ...]`).
Pure: no I/O, wall-clock, randomness, or persistence.

---

## Phase 8.3 — Structural Motif Detection

`phase8_motifs.py` recognizes structural shapes in the causal graph — the first
time ClarityOS sees the graph as a *shape*, not just weights. Pure /
deterministic.

**Feedback loops** — `detect_feedback_loops(graph) -> list[list[str]]`. Directed
simple cycles of length `2`–`6`. A deterministic DFS rooted at each cycle's
*minimum* node id (only nodes `>` the root are explored) finds every cycle
exactly once, already in canonical (min-first) form — no rotational duplicates.
Loops are sorted lexicographically and capped at `MAX_LOOPS = 10`. (The
first-order 8.1 graph is a DAG, so this is `[]` in practice; it matters once
deeper inference / an action source introduces cycles.)

**Bottlenecks** — `detect_bottlenecks(graph, influence, centrality) -> list[str]`.
A node qualifies when `centrality > 0.6` AND `inbound_edges + outbound_edges >=
3`. Returns the top `5` by centrality (ties → node id).

**Attractors** — `detect_attractors(graph, influence) -> list[str]`. A node
qualifies when `influence > 0.7` AND `inbound_edges > outbound_edges`. Returns
the top `5` by influence (ties → node id).

**`analyze_motifs(graph, influence, centrality)`** bundles all three:
`{"feedback_loops": [...], "bottlenecks": [...], "attractors": [...]}`.

**Endpoint.** `GET /operator/telemetry` adds a read-only `causal_motifs` block
(the `analyze_motifs` output). Pure: no I/O, wall-clock, randomness, or
persistence.

---

## Phase 8.4 — Multi-Chain Causal Explanations

`phase8_multichain.py` turns the full 8.0–8.3 stack into a **ranked set** of
structured explanations: multiple distinct, structurally-valid causal paths to
the narrative, each scored by strength and annotated with motif context. Where
8.1 extracts the single most-influential chain, 8.4 enumerates several. Pure /
deterministic.

    generate_causal_chains(graph, influence, centrality, motifs=None) -> list[dict]
    scored_chains_to_dicts(scored_chains) -> list[dict]   # JSON-serialisable

**Output shape (documented choice).** The card offered two options — extend the
8.0 `CausalChain` with a `metadata` dict, or return a parallel `list[dict]`.
This card takes the **`list[dict]`** form: `generate_causal_chains` returns
`[{"chain": CausalChain, "score": float, "motifs": {...}}, ...]`. The 8.0
primitive is left untouched. The built `CausalChain` carries the 8.4
influence-aware score in its `.score` field (an evolution of the 8.0 structural
placeholder — the 8.0 spec already anticipates "real confidence inference
arrives in 8.1–8.4"), so serialization is just `chain_to_dict` (which emits
`{nodes, edges, score}`) plus a `"motifs"` key.

**Target node.** The terminal summary node is the lexicographically-smallest
node whose `type` is `"narrative"`; if none carries that type, the node with id
`"narrative"`; otherwise there is no target and the result is `[]`.

**Start selection.** Candidate starts are the **top `N = 5`** nodes (excluding
the target) by the same importance score 8.2 uses for ranked explanations —
`(influence + centrality) / 2` — descending, ties broken by node id ascending.

**Path search.** For each start, find up to **`K = 3`** simple paths to the
target via deterministic depth-limited DFS:

- Neighbours are explored in ascending node-id order (adjacency is a sorted,
  de-duplicated target list, so parallel edges don't fork the traversal).
- No node repeats within a path (simple paths only).
- A path uses at most **`MAX_PATH_DEPTH = 6`** edges (≤ 7 nodes).
- Collection stops at the `K` cap, so the kept paths are the first `K` in DFS
  order.

**Chain scoring.** For a path:

```
edge_score = clamp( mean(edge weight along path), -1, 1 )   # signed; edgeless -> 0.0
node_score = mean( influence[node] for node on path )       # already in [0, 1]
chain_score = clamp( ((edge_score + 1) / 2 + node_score) / 2, 0, 1 )
```

The signed `edge_score ∈ [-1, 1]` is linearly remapped to `[0, 1]`
(`(edge_score + 1) / 2`), then averaged with `node_score`. A strongly
counteracting (negative-weight) path therefore scores lower than a reinforcing
one of the same magnitude. When parallel edges exist between two nodes, the
strongest (max-weight) edge is used both for scoring and as the chain's edge.

**Motif annotation.** Each chain carries `{passes_bottleneck, passes_attractor,
in_feedback_loop}` — each `True` iff **any** node on the path is, respectively, a
detected bottleneck, an attractor, or a member of any detected feedback loop
(`motifs["bottlenecks"]` / `["attractors"]` / `["feedback_loops"]`). A `None` or
empty `motifs` yields all `False`.

**Deduplication.** Chains with identical node sequences are merged (kept once).
With sorted-set adjacency and distinct starts the main search produces unique
sequences inherently; the merge is the guarantee that holds across the fallback
and any future multigraph inputs.

**Fallback.** When no start reaches the target (e.g. empty `influence`, or the
top-`N` starts are all sinks), the result is the single strongest edge into the
target (ties by source id). On the first-order 8.1 graph that is the
always-present `drift_velocity → narrative` analytics→narrative chain.

**Ordering.** The returned list is sorted by `score` descending; ties keep
node-id-sequence order (stable, deterministic).

**Endpoint.** `GET /operator/telemetry` adds a read-only `causal_chains` block —
`[{nodes, edges, score, motifs}, ...]` from `scored_chains_to_dicts`. With no
action source this is the single analytics→narrative chain. Pure: no I/O,
wall-clock, randomness, or persistence.

> Phase 8.5 (operator-facing surfacing — Causal Chains + Structural Motifs tiles
> in the web / desktop / phone consoles) is a clients-only card with no backend
> change, so it carries no section here.

---

## Phase 8.6 — Causal Deltas (Temporal Causal Change)

`phase8_deltas.py` is the causal analogue of Phase-7 drift: where 8.1–8.4 compute
the causal system at one instant, 8.6 compares two snapshots and reports how the
structure *moved* — the first time ClarityOS can say "a new bottleneck emerged",
"a feedback loop resolved", or "this causal chain is weakening". Pure /
deterministic; imports only the stdlib.

    compute_causal_deltas(prev, curr) -> dict

`prev` and `curr` are each a causal-state dict carrying `influence`
(`{node_id: float}`), `centrality` (`{node_id: float}`), `motifs` (the 8.3
`analyze_motifs` shape), and `chains` (the 8.4 `scored_chains_to_dicts` list).
All four keys are optional; missing pieces are treated as empty.

**Influence / centrality delta.** Per node, `curr - prev` over the **union** of
node ids, clamped to `[-1, 1]`, returned in sorted-key order:

```
delta[node] = clamp( curr.get(node, 0) - prev.get(node, 0), -1, 1 )
```

The union (not just `curr`'s keys) is used so a node present only in `prev`
deltas *down* to 0 (it dropped out) and a node only in `curr` deltas *up* from 0
(it appeared) — both are real causal movement. Influence/centrality live in
`[0, 1]`, so a difference is naturally in `[-1, 1]`; the clamp is a safety bound.

**Motif delta.** For each family, `new = curr − prev` and `resolved = prev −
curr`:

- **Feedback loops** are compared by node-sequence signature (each loop is a
  list of node ids → a tuple); outputs are loops (lists), sorted.
- **Bottlenecks / attractors** are compared as node-id sets; outputs sorted.

Yields `{new_loops, resolved_loops, new_bottlenecks, resolved_bottlenecks,
new_attractors, resolved_attractors}`.

**Chain delta.** Chains are compared by their **node-sequence signature**
(`tuple(node_id for node in chain.nodes)`):

```
new_chains      = sorted node-id sequences in curr but not prev
resolved_chains = sorted node-id sequences in prev but not curr
score_shift     = clamp( mean(curr chain scores) − mean(prev chain scores), -1, 1 )
```

An empty chain set has mean score `0.0`. `new_chains` / `resolved_chains` are
the node-id sequences (lists), not the full chain objects — the signature is the
identity that matters for "appeared / disappeared".

**Determinism.** Every collection is sorted (set differences sorted; loops/chains
sorted by signature) and every dict is built in sorted-key order. No randomness,
no wall-clock, no I/O. Output is JSON-serialisable.

**Snapshot sourcing + endpoint.** `GET /operator/telemetry` adds a read-only
`causal_deltas` block (`{influence_delta, centrality_delta, motif_delta,
chain_delta}`). `curr` is the current snapshot's `{influence, centrality,
motifs, chains}`; **`prev` is the causal state recomputed from the history minus
its most recent record** (`_causal_state(records[:-1])`) — deterministic, with
**no new persistence**, consistent with the no-vault / no-`operator_state`
constraint and mirroring the governance-diff "recompute the prior state" pattern.
With fewer than two records there is no previous snapshot, so `curr` is compared
against itself and every delta is zero / empty. Pure: no I/O, wall-clock,
randomness, or persistence.

---

## Phase 8.7 — Causal Stability Forecast

`phase8_stability.py` reads the 8.6 deltas and reports what they *mean*: is the
causal system stabilizing, destabilizing, entering a structural transition, or
steady? It is the causal analogue of Phase-7's stability forecast, but richer —
it folds in motif churn and multi-chain structure, not just drift. Pure /
deterministic; stdlib-only.

    compute_causal_stability(deltas, curr) -> dict

`deltas` is the 8.6 output; `curr` is the current causal state (`{influence,
centrality, motifs, chains}`). Output: `{stability_score, trend, drivers}`.

**Stability score** (each component in `[0, 1]`; final = their mean, clamped):

```
influence_score  = 1 - clamp(mean(|influence_delta[node]|),  0, 1)
centrality_score = 1 - clamp(mean(|centrality_delta[node]|), 0, 1)
motif_score      = 1 - clamp(motif_events / 10, 0, 1)   # motif_events = total new+resolved
                                                        # loops + bottlenecks + attractors
chain_score      = 1 - clamp(|chain_delta.score_shift|, 0, 1)
stability_score  = mean(influence_score, centrality_score, motif_score, chain_score)
```

An empty delta map has mean-abs `0.0` (→ component score `1.0`).

**Trend classification** (first matching rule wins — a documented precedence,
since the card's four rules leave gaps):

1. **steady** — *no movement at all*: zero influence/centrality volatility, zero
   motif events, zero chain shift. This is also the no-previous-snapshot
   fallback (all-zero deltas → `score = 1.0`, `trend = "steady"`). Semantically,
   no change is "steady", not "stabilizing".
2. **destabilizing** — `stability_score < 0.4` **OR** any new loop **OR** any new
   bottleneck. (A new loop/bottleneck forces this even at a high score.)
3. **stabilizing** — `stability_score > 0.7` **AND** `motif_events == 0` **AND**
   `|score_shift| < 0.1`.
4. **transitioning** — `0.4 ≤ stability_score ≤ 0.7` **AND** `motif_events > 0`.
5. **steady** — otherwise (covers the rule-gaps, e.g. a high score with only
   resolved-motif / attractor churn).

**Drivers** — the signals behind the score, each sorted deterministically:

| Driver | Source |
| --- | --- |
| `rising_influence` | nodes with `influence_delta > +0.1` |
| `falling_influence` | nodes with `influence_delta < -0.1` |
| `new_bottlenecks` / `resolved_bottlenecks` | the 8.6 `motif_delta` lists |
| `new_loops` / `resolved_loops` | the 8.6 `motif_delta` lists |
| `chain_strengthening` | current chain signatures when `score_shift > +0.1` |
| `chain_weakening` | current chain signatures when `score_shift < -0.1` |

**Chain-driver note.** 8.6 exposes only the *aggregate* `score_shift` (no
per-chain score deltas), which is why `compute_causal_stability` also takes
`curr`: when the aggregate shift crosses the ±0.1 driver threshold, the current
chain set is listed (by node-id signature) as strengthening / weakening.

**Determinism.** Every driver list is sorted; the score and trend are pure
functions of the inputs; no randomness, no wall-clock, no I/O. Output is
JSON-serialisable.

**Endpoint.** `GET /operator/telemetry` adds a read-only `causal_stability` block
(`{stability_score, trend, drivers}`) computed from the 8.6 `causal_deltas` + the
current causal state. With no previous snapshot it is `score = 1.0`,
`trend = "steady"`. Pure: no I/O, wall-clock, randomness, or persistence.

> Phase 8.8 (operator-facing surfacing — the Causal Stability tile in the web /
> desktop / phone consoles) is a clients-only card with no backend change, so it
> carries no section here.

---

## Phase 8.9 — Unified Causal Narrative

`phase8_narrative.py` is the causal counterpart to the Phase-7 narrative (7.9),
but structural and multi-layered: it weaves the strongest causal chain, the
structural motifs, the influence highlights, the temporal deltas, and the
stability forecast into one deterministic, text-only explanation. Pure /
deterministic; stdlib-only.

    generate_causal_narrative(curr, deltas, stability) -> str

`curr` is the current causal state (`{influence, centrality, motifs, chains}`);
`deltas` is the 8.6 output; `stability` is the 8.7 output. (In the endpoint this
is imported under an alias to avoid shadowing the 7.9 `generate_causal_narrative`.)

**Template** — five fixed sections, in this order:

```
Primary Causal Chain:
- <strongest chain's node labels, joined " → ">
- Chain score: <score, 2 decimals>

Structural Motifs:
- Feedback loops: <none | "a → b; c → d">
- Bottlenecks: <none | "x, y">
- Attractors: <none | "x, y">

Influence Highlights:
- Rising: <none | node ids>      # the 8.7 rising_influence driver
- Falling: <none | node ids>     # the 8.7 falling_influence driver

Causal Changes Since Last Snapshot:
- New motifs: loops: <…>; bottlenecks: <…>; attractors: <…>
- Resolved motifs: loops: <…>; bottlenecks: <…>; attractors: <…>
- Chain score shift: <value, 2 decimals>

Stability Forecast:
- Score: <stability_score, 2 decimals>
- Trend: <trend>
- Drivers: <count per driver category>
```

The **strongest chain** is `curr.chains[0]` (8.4 sorts chains by score
descending). The **drivers summary** is a count per category (`rising influence
(N), falling influence (N), …, chain weakening (N)`) — the full driver contents
already appear in the Influence Highlights / Causal Changes sections, so the
forecast line stays a compact magnitude read.

**Formatting + determinism.** No generative prose, no inference beyond the
template; every list is sorted; every numeric value is formatted to two
decimals. No randomness, no wall-clock, no I/O.

**Fallbacks.** Missing inputs degrade gracefully: no chains →
`(no causal chain detected)` + `0.00`; empty motif / influence / delta lists →
`none`; an absent stability block → `Score: 0.00`, `Trend: steady`. With no
previous snapshot the deltas are zero and the forecast reads `steady` at the
score the 8.7 fallback produced (`1.00` in the endpoint).

**Endpoint.** `GET /operator/telemetry` adds a read-only `causal_narrative`
string, placed after `causal_stability`. It is distinct from the Phase 7.9
`narrative` field (which explains temporal drift). Pure: no I/O, wall-clock,
randomness, or persistence.

---

## Phase 8.10 — Unified Temporal-Causal Narrative

`phase8_unified_narrative.py` is the synthesis layer: Phase 7 explained *what
happened over time*; Phase 8 explained *why, structurally*; 8.10 fuses both into
one deterministic, operator-grade explanation. Pure / deterministic; stdlib-only.

    generate_unified_narrative(temporal, causal) -> str

`temporal` and `causal` are structured **blocks** (dicts) bundling each phase's
narrative + the values the Integrated Interpretation reads:

```
temporal = {"narrative": <7.9 str>, "drift": float|None,
            "coherence_trend": float, "trust_band": str|None}
causal   = {"narrative": <8.9 str>, "chains": [...], "motifs": {...},
            "deltas": {...}, "stability": {...}}
```

**Template** — title + four sections:

```
Unified Temporal–Causal Narrative

Temporal Summary:
<temporal narrative | "(no temporal narrative)">

Causal Summary:
<causal narrative | "(no causal narrative)">

Integrated Interpretation:
- Drift level: <drift, 2dp>
- Coherence trend: <coherence_trend, 2dp>
- Trust band: <trust_band | "—">
- Primary causal chain: <strongest chain's node labels, joined " → " | "(none)">
- Structural motifs: loops: <…>; bottlenecks: <…>; attractors: <…>
- Key deltas: influence changes: <n>, centrality changes: <n>, motif events: <n>, chain score shift: <2dp>
- Stability forecast: <trend> (score <2dp>)

Overall Assessment:
<Stable | Shifting | Transitioning | Destabilizing>
```

`Drift level` is the latest record's drift; `Primary causal chain` is
`chains[0]` (8.4 sorts by score desc); `Key deltas` counts the nodes that
changed (non-zero delta) + total motif events + the chain score shift.

**Overall Assessment** — the card's rules overlap, so they are applied in a
documented severity precedence (first match wins):

1. **Destabilizing** — `drift > 0.6` OR `new_loops > 0` OR `new_bottlenecks > 0`
   OR `stability_score < 0.4`.
2. **Stable** — `drift < 0.3` AND `stability_score > 0.7` AND no new motifs
   (no new loops / bottlenecks / attractors).
3. **Transitioning** — `motif_events > 0` AND `0.4 ≤ stability_score ≤ 0.7`.
4. **Shifting** — `0.3 ≤ drift ≤ 0.6` OR `0.4 ≤ stability_score ≤ 0.7`, and the
   catch-all default for any case the first three don't claim.

**Determinism + formatting.** No generative prose, no inference beyond the
template; every list is sorted; every numeric value is formatted to two
decimals. No randomness, no wall-clock, no I/O. Missing pieces degrade to
`(no … narrative)` / `(none)` / `none` / `—` / `0.00`.

**Endpoint.** `GET /operator/telemetry` adds a read-only `unified_narrative`
string, placed after `causal_narrative`. The endpoint assembles the two blocks
from values it already computes (7.9 `narrative` + latest drift/trust + analytics
coherence trend; 8.9 `causal_narrative` + 8.3/8.4/8.6/8.7 outputs). With no
telemetry the assessment is `Stable` (drift 0, stability fallback 1.0, no
motifs). Pure: no I/O, wall-clock, randomness, or persistence.

---

## Constraints (enforced by this slice)

- **No imports from runtime-spine modules** — `phase8_structures.py` imports
  only the stdlib (`dataclasses`).
- No backend routes, console changes, persistence, vault, or `operator_state`.
- No wall-clock, no randomness; deterministic throughout.
- **Flat root**: `phase8_structures.py` lives at the repo root, like Phase 6/7.

## Acceptance

- All primitives + utilities defined; this spec matches the code.
- `pytest tests/test_phase8_structures.py` is green.
- No regressions in Phase 7; no CI-gated runtime files changed (the Phase 8
  test files carry none of the `runtime_spine` / `privacy_surface` /
  `determinism_surface` markers).

## Next cards (not in scope here)

- 8.11 — surface the 8.10 unified narrative in all consoles.
- Phase 9 — operator-action integration (real action nodes in the causal graph).
- (future) wire an operator-action source so the causal graph carries real
  action nodes — at which point 8.4's multi-chain explanations span richer,
  potentially cyclic paths instead of the analytics→narrative fallback, and the
  8.6 deltas surface real new/resolved loops + bottlenecks.
