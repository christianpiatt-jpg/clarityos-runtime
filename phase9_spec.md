# Phase 9 — Operator Action Integration (Spec)

**Status:** In progress (9.0–9.5 implemented — the action primitive, the
ingestion stream, causal-graph integration, single-hop influence propagation,
behavioral motif detection, and the operator-facing behavioral tiles). Phase 9
complete; Phase 10 (behavioral forecasting) follows.
**Surfaces:** Backend (Python) + clients (web, desktop, phone — 9.5 only).

Phase 7 answered *what is happening over time*; Phase 8 answered *why,
structurally* — but the Phase-8 causal graph had no real **action** source, so
its multi-chain explanations (8.4) and deltas (8.6) fell back to the
analytics→narrative path. Phase 9 introduces operator **actions** as first-class
causal atoms — the missing primitive that turns the causal engine from passive
analysis into a behavioral model.

This track lives as flat repo-root modules (`phase9_*.py`) with tests in
`tests/test_phase9_*.py`, like Phase 6/7/8. It is additive and **does not touch**
the CI-gated runtime spine, the vault, or `operator_state`.

---

## Phase 9.0 — Action Primitive Specification

`phase9_actions.py` defines the action primitive: an `ActionEvent` record and
its deterministic mapping to an `"action"`-type `CausalNode`. **9.0 defines the
primitive only** — no ingestion, graph integration, propagation, motifs, or UI.
Pure and deterministic: no I/O, wall-clock, randomness, or side effects.

### Action node type

`phase8_structures.py` exposes the canonical constant `ACTION_NODE_TYPE =
"action"`. An action node is a structurally ordinary `CausalNode` with stricter
field semantics:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | `str` | yes | unique action identifier |
| `type` | `"action"` | yes | node category (`ACTION_NODE_TYPE`) |
| `label` | `str` | yes | human-readable action description |
| `timestamp` | `float` | **yes** | when the action occurred |
| `value` | `float \| None` | optional | magnitude / intensity (if applicable) |

The only difference from other causal nodes is the **required timestamp** —
enforced at the `ActionEvent` boundary (the field has no default) and carried
through unchanged by `make_action_node`.

### Primitives

```python
@dataclass
class ActionEvent:
    id: str
    label: str
    timestamp: float          # required — actions are inherently temporal
    magnitude: float | None = None

make_action_node(event) -> CausalNode   # deterministic 1:1 mapping
```

`make_action_node` maps `id → id`, `type → "action"`, `label → label`,
`timestamp → timestamp`, `magnitude → value`. No inference, no transformation,
no randomness — it reuses the 8.0 `make_node` factory, so action nodes are
byte-for-byte ordinary `CausalNode`s and slot into the Phase-8 graph machinery
unchanged (once 9.2 wires them in).

### Action semantics

1. **Actions are first-class causal primitives** — they participate in the
   causal graph exactly like analytics, alerts, and factors.
2. **Actions always have timestamps** — unlike analytics or factors, actions are
   inherently temporal (`ActionEvent.timestamp` is required).
3. **Actions may have magnitude** — e.g. "Opened app" → `None`; "Adjusted
   parameter by +0.7" → `0.7`.
4. **Actions influence system state** — they may influence drift, coherence,
   alerts, causal factors, and other actions (habit loops). *(Wiring is 9.2+.)*
5. **Actions do not receive influence from system-generated nodes** — narrative,
   stability, and system-summary nodes never point *into* an action; this
   preserves causal directionality. *(Enforced when edges are built in 9.2+.)*

### Determinism

`ActionEvent` is a plain dataclass; `make_action_node` is a pure mapping over its
fields. Equal events produce equal nodes; output is JSON-serialisable via
`dataclasses.asdict`. No randomness, no wall-clock, no I/O.

---

## Phase 9.1 — Action Stream Ingestion

`phase9_ingest.py` is the first moment ClarityOS sees operator behaviour as a
*stream*: raw actions are validated, normalized into `ActionEvent` (9.0), and
appended to an append-only continuity log, ready for the 9.2 graph integration.
**9.1 does not enter the causal graph** — that is 9.2.

    ingest_action(raw) -> ActionEvent
    store_action(event, continuity) -> None
    load_recent_actions(continuity, now, window) -> list[ActionEvent]

**Normalization + validation.** `ingest_action` maps a raw dict to an
`ActionEvent`, rejecting (with `ValueError`) any of:

| Field | Rule |
| --- | --- |
| `id` | required, must be a string |
| `label` | required, must be a string |
| `timestamp` | required, must be a number (int/float, not bool), `>= 0` |
| `magnitude` | optional — `None`, or a number within `[-1, 1]` |

A numeric `timestamp` / `magnitude` is coerced to `float`. No inference, no
randomness, no wall-clock.

**Continuity storage.** `continuity` is a plain dict with an `"actions"` list —
`{"actions": [ActionEvent, ...]}`. `store_action` appends and keeps the log
**sorted by timestamp** (stable — equal timestamps keep insertion order). It is
**append-only**: events are never mutated, deleted, or reordered beyond the
canonical timestamp sort. This mirrors the Phase-7 telemetry continuity
mechanism but is kept Phase-9-local (a parallel in-memory log) rather than
retrofitting the telemetry-specific `phase7_storage` — **no new persistence
layer, no schema changes**. A process-wide default lives in `phase9_ingest`
(`get_action_continuity`) for the endpoint.

**Recent-window load.** `load_recent_actions(continuity, now, window)` returns
every action with `timestamp >= now - window` (cutoff inclusive), sorted by
timestamp. `now` is **caller-supplied** — there is no wall-clock inside the
function (the card's signature line omitted `now`; the rules require it, so it
is an explicit parameter).

**Endpoint.** `POST /operator/action` — body `{"id", "label", "timestamp",
"magnitude"}` — validates + normalizes via `ingest_action`, appends via
`store_action`, and returns `{"status": "ok"}` (an invalid action → `400`). The
only side effect is the append-only continuity write. The route is added to the
already-mounted `phase7_endpoint` `/operator` router, so **`app.py` (the runtime
spine) is untouched**. The Phase-7 telemetry `GET /operator/telemetry` is
unchanged — actions are exposed to 9.2 via `load_recent_actions`, not surfaced
here.

**Determinism.** Validation + normalization are pure; storage order is the
canonical timestamp sort; `load_recent_actions` re-sorts. No randomness, no
wall-clock inside ingestion.

---

## Phase 9.2 — Action -> Causal Graph Integration

`phase9_integration.py` folds ingested actions into the **existing** Phase-8
`CausalGraph` as `CausalNode`s of type `"action"` (9.0), wired to the system
variables they influence with ordinary `CausalEdge`s. There is **no parallel
"action graph"**: actions become first-class citizens of the one graph that 8.2
propagation, 8.3 motifs, 8.4 multi-chains, 8.6 deltas, 8.7 stability, and 8.10
narrative already read — fulfilling 9.0 §3.1. **Pure structure only**: nodes +
edges, no propagation / influence / motif detection (9.3/9.4).

    action_event_to_causal_node(event) -> CausalNode      # = make_action_node (9.0)
    resolve_action_targets(node, graph) -> list[str]
    integrate_action_node(node, graph) -> None
    link_action_to_variables(node, graph) -> list[CausalEdge]
    integrate_recent_actions(continuity, graph, now, window) -> None

**Reconciliation note.** This card was originally drafted against a different
graph model (a frozen `ActionNode` class, `CausalEdge` with `type`/`timestamp`,
separate `action_nodes`/`action_edges` buckets, `StateNode`/`TelemetryNode`
conventions). None of those exist in ClarityOS — the graph is a single
`CausalNode` (with a `type` tag), `CausalEdge(source, target, weight)`, and
`CausalGraph = {nodes: dict, edges: list}`, and 9.0 already maps actions to
`CausalNode`s. 9.2 is implemented against that real model so actions are visible
to the Phase-8 engine rather than living in a shadow graph.

**Node mapping.** `action_event_to_causal_node` is a thin alias over the 9.0
`make_action_node` — one mapping, `magnitude -> value`, `type = "action"`. No new
node class, no `payload` dict (the real `CausalNode` carries `value`).

**Variable registry.** `SYSTEM_VARIABLE_IDS` is the Phase-8 analytics registry —
`drift_velocity`, `drift_acceleration`, `coherence_trend`, `stability_forecast`,
`trajectory`. `resolve_action_targets` returns the registry variables **present
in the graph**, sorted (deterministic, no inference).

**Edges.** `link_action_to_variables` creates one `CausalEdge(action_id,
variable_id, ACTION_EDGE_WEIGHT)` per resolved target, where
`ACTION_EDGE_WEIGHT = 1.0` is a **structural placeholder** (9.3 replaces it with
real influence weights). Edges are **append-only and deduplicated** by
`(source, target)` — repeated integration never accumulates duplicates — and the
edge list is kept sorted by `(source, target)`. Only `action -> variable` edges
are created; never the reverse (directionality per 9.0 §3.5 — reverse/weighted
edges are 9.3).

**Insertion + batch.** `integrate_action_node` inserts the action into
`graph.nodes` keyed by id (idempotent on id; never mutates other nodes; no
deletion). `integrate_recent_actions` pulls recent actions via 9.1's
`load_recent_actions(continuity, now, window)`, processes them in `(timestamp,
id)` order, and integrates + links each. `now` is caller-supplied (no
wall-clock).

**No endpoint / continuity change.** 9.2 adds no route and no continuity bucket;
actions still live in the 9.1 `"actions"` log, and the graph is the in-memory
Phase-8 structure. Integration happens on-demand via `integrate_recent_actions`
(consumed by 9.3+); `GET /operator/telemetry` is unchanged.

**Determinism.** Mapping is pure; node order follows `(timestamp, id)` processing;
edges are sorted by `(source, target)`; no randomness, no wall-clock.

---

## Phase 9.3 — Influence Propagation

`phase9_influence.py` is the first flow of *behavioral* influence through the
graph: each action node (9.2) exerts a deterministic, **single-hop** influence on
the variables it points at, recorded as `InfluenceRecord` snapshots in the
continuity log. Intentionally conservative — **plumbing, not semantics**.

    compute_influence_weight(action, variable=None) -> float
    InfluenceRecord(action_id, variable_id, weight, timestamp)
    propagate_action_influence(node, graph, continuity) -> list[InfluenceRecord]
    propagate_recent_actions(continuity, graph, now, window) -> list[InfluenceRecord]

**Weight model.** `compute_influence_weight` returns the action's magnitude
(`CausalNode.value`) clamped to `[-1, 1]`, or `0.0` when magnitude is `None`. The
`variable` argument is accepted for signature stability but unused — 9.3 has **no
cross-variable effects**; weight depends only on the action.

**`InfluenceRecord`** (frozen, hashable): `{action_id, variable_id, weight,
timestamp}` — one single-hop influence snapshot (`timestamp` = the action's
time). Stored in `continuity["influence"]`: append-only, deduplicated, sorted by
`(timestamp, action_id, variable_id)`; no mutation, no deletion.

**Propagation.** `propagate_action_influence(node, graph, continuity)` walks the
action node's outgoing `action -> variable` edges (9.2), computes each weight,
and appends an `InfluenceRecord` to `continuity["influence"]`. It is
**single-hop only** — no variable->variable, no action->action, no multi-hop —
and **never mutates the graph** (no node/edge attribute changes, no new edges;
records go only to continuity). Re-propagation is idempotent (duplicate
snapshots are skipped). `propagate_recent_actions(continuity, graph, now,
window)` pulls the graph's action nodes with `timestamp >= now - window`,
processes them in `(timestamp, id)` order, and propagates each. `now` is
caller-supplied (no wall-clock).

**Reconciliation note.** Like 9.2, this is implemented against the real graph:
"`ActionNode`" is a `CausalNode(type="action")` and its magnitude is `value`;
weights operate on the existing `CausalEdge` model. The `InfluenceRecord` log is
a Phase-9-local continuity bucket (parallel to the actions log), not a new graph
schema.

**Determinism.** Weight is a pure function of magnitude; record order is the
canonical `(timestamp, action_id, variable_id)` sort; no randomness, no
wall-clock.

---

## Phase 9.4 — Behavioral Motif Detection

`phase9_behavioral_motifs.py` is the action-layer analogue of Phase 8.3: where
8.3 saw the causal *graph* as a shape, 9.4 sees operator *behaviour* as geometry
— loops, triggers, habits, bottlenecks, attractors. Pure / deterministic;
imports only the 8.0 primitive + stdlib.

    detect_action_loops(actions) -> list[list[str]]
    detect_trigger_chains(graph) -> list[list[str]]
    detect_habits(actions) -> list[str]
    detect_action_bottlenecks(graph, influence, centrality) -> list[str]
    detect_action_attractors(graph, influence) -> list[str]
    analyze_behavioral_motifs(actions, graph, influence, centrality) -> dict

**Reconciliation.** An action is a `CausalNode(type="action")`; its recurring
identity (for loops/habits) is the **`label`** (event ids are unique). A
*causal-factor* node is the Phase-8.1 `factor_*` node (also `type="action"`),
distinguished by id prefix; an *action* node is `type="action"` and **not** a
factor.

**Action loops.** Over the timestamp-ordered action labels, a loop of length
`L` (2–6) exists where a label recurs after `L` steps (`labels[i] ==
labels[i+L]`) and the `L` intervening labels are distinct (a simple cycle). Each
loop is canonicalized to its lexicographically-smallest rotation; loops are
de-duplicated, sorted, and capped at 10.

**Trigger chains.** `action -> causal_factor -> action` paths over
**positive-weight** edges only; sorted, de-duplicated, capped at 10. (The 9.2
graph has no `action -> factor` edges, so this is `[]` until such edges exist.)

**Habits.** An action label is a habit candidate when it recurs `>= 3` times
**and** `pstdev(inter-event spacing) < 20% of mean spacing`. Top 5 by occurrence
count (ties by label).

**Bottlenecks / attractors** (action-filtered analogues of 8.3): an action node
is a **bottleneck** when `centrality > 0.6` and total degree `>= 3` (top 5 by
centrality); an **attractor** when `influence > 0.7` and `inbound > outbound`
(top 5 by influence). 9.2 action nodes are sources (outbound only), so they are
attractors only once reverse/action→action edges exist.

**Determinism.** Every list is sorted; loops canonicalized; no randomness, no
wall-clock.

**Endpoint.** `GET /operator/telemetry` adds a read-only `behavioral_motifs`
block (`{action_loops, trigger_chains, habits, action_bottlenecks,
action_attractors}`). It is computed on an **action-augmented copy** of the
graph (the main `causal_*` fields stay action-free, recomputed against the
action-free graph as before), using **all** stored actions (no wall-clock — no
`now`/window in the endpoint). Empty until actions are POSTed via
`/operator/action`.

---

## Phase 9.5 — Operator-Facing Behavioral Tiles

**Surfaces:** WEB, DESKTOP, PHONE. **Backend:** none — 9.5 is a pure UI pass
that surfaces the 9.4 `behavioral_motifs` block already returned by
`GET /operator/telemetry`. No Python, no causal / propagation / motif changes,
no deltas / stability / narrative.

Each console gains one read-only behavioral tile, the action-layer analogue of
the Phase-8 causal tiles (Structural Motifs / Causal Stability):

| Surface | Tile | File |
| --- | --- | --- |
| Web | "Behavioral Motifs" | `web/src/routes/OperatorConsole.tsx` |
| Desktop | "Behavioral Patterns" | `desktop/src/OperatorConsoleShell.tsx` |
| Phone | "Behavior" | `phone/app/operator_console.tsx` |

**Sections.** Five, one per `behavioral_motifs` family, in this fixed order:

1. **Action Loops** (`action_loops`) — loop label sequences, rendered `a → b`.
2. **Trigger Chains** (`trigger_chains`) — `action → factor → action` id
   sequences, rendered `a → b → c`.
3. **Habits** (`habits`) — action labels.
4. **Action Bottlenecks** (`action_bottlenecks`) — action node ids.
5. **Action Attractors** (`action_attractors`) — action node ids.

On phone the labels shorten to Loops / Triggers / Habits / Bottlenecks /
Attractors.

**Data source.** `GET /operator/telemetry` → `telemetry.behavioral_motifs`. The
tile rides the same read-only mount fetch the Phase-7/8 tiles use; it never
computes or writes — the backend owns the behavioral reasoning. Before the fetch
resolves (or when the backend omits the block) it falls back to an empty motif
set.

**Deterministic ordering.** The backend already sorts every family (9.4); the
clients render each array **verbatim, in backend order** — no client-side
re-sort. Loops / chains join with ` → `.

**Rendering rules.**
- *Web / Desktop:* empty sections **collapse** (header + list omitted; an
  all-empty tile shows only its heading). A section over 10 rows becomes
  independently scrollable (`max-height` + overflow). No animations, no
  inference / narrative text.
- *Phone:* **one section per screen** via a horizontal paging `ScrollView` —
  swipe between the five sections; each empty section shows a `None` sentinel so
  the five pages stay stable. No animations, no inference text.

**Tri-surface parity.** All three surfaces read the identical `behavioral_motifs`
shape and render the same five families in the same order; only the tile title,
the phone section labels, and the phone swipe layout differ.

**Tests.** Web (`web/src/routes/__tests__/OperatorConsole.test.tsx`) and desktop
(`desktop/src/__tests__/OperatorConsoleShell.test.tsx`) each add four tests:
the tile renders all five sections from the backend shape, empty sections
collapse, ordering is preserved verbatim, and a > 10-row section scrolls
(desktop) without regressing the existing causal tiles. Phone has no harness.

---

## Constraints (current scope: 9.0–9.5)

- **No imports from runtime-spine modules** — `phase9_actions.py` imports only
  the 8.0 primitive (`phase8_structures`); `phase9_ingest.py` imports only the
  9.0 primitive + stdlib; `phase9_integration.py` + `phase9_influence.py` import
  only the 8.0 primitives + 9.0/9.1 + stdlib. The `POST /operator/action` route
  rides the already-mounted `phase7_endpoint` router, so `app.py` is untouched.
  `phase9_behavioral_motifs.py` imports only the 8.0 primitive + stdlib.
- 9.5 is the UI pass — read-only tri-surface tiles surfacing the 9.4
  `behavioral_motifs` block; no backend / Python / causal changes. 9.3 influence
  is **single-hop only** (no multi-hop / variable->variable / action->action);
  9.4 detection mutates nothing.
- No new persistence layer (the action + influence continuity is in-memory,
  append-only), no new graph schema / buckets, no vault, no `operator_state`
  writes. 9.3 never mutates the graph; 9.4 builds a throwaway augmented graph
  copy for motifs, leaving the main fields action-free.
- No wall-clock inside ingestion / integration / propagation / motif detection,
  no randomness; deterministic throughout.
- **Flat root**: `phase9_*.py` live at the repo root, like Phase 6/7/8.

## Acceptance

- 9.0 — action primitive (`ActionEvent` + `make_action_node`) defined and
  deterministic.
- 9.1 — ingestion pipeline (`ingest_action` / `store_action` /
  `load_recent_actions`) + append-only continuity + `POST /operator/action`.
- 9.2 — action -> causal-graph integration: `CausalNode(type="action")` into the
  existing `CausalGraph` + `action -> variable` `CausalEdge`s; deterministic,
  idempotent, visible to the Phase-8 engine.
- 9.3 — influence propagation: `compute_influence_weight` + `InfluenceRecord` +
  single-hop `propagate_action_influence` / `propagate_recent_actions` writing
  influence snapshots to `continuity["influence"]`; no graph mutation.
- 9.4 — behavioral motifs: action loops / trigger chains / habits / action
  bottlenecks / attractors + `behavioral_motifs` on `/operator/telemetry`
  (computed on a throwaway action-augmented graph; main fields unchanged).
- 9.5 — operator-facing behavioral tiles on web / desktop / phone reading
  `telemetry.behavioral_motifs` (read-only; deterministic backend order; empty
  sections collapse on web/desktop, one-section-per-screen swipe on phone); web
  + desktop vitest green; no backend / Python changes.
- `pytest tests/test_phase9_actions.py tests/test_phase9_ingest.py
  tests/test_phase9_integration.py tests/test_phase9_propagation.py
  tests/test_phase9_behavioral_motifs.py` is green.
- This spec matches the code.
- No regressions in 7.0–8.11; no CI-gated runtime files changed.

## Next cards (not in scope here)

- Phase 10 — behavioral forecasting (the final intelligence phase).
