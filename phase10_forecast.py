# phase10_forecast.py
"""
Phase 10.0 — Behavioral Forecast Engine.

The behavioral analogue of Phase 7.0 (temporal forecast) and Phase 8.7 (causal
stability forecast), but for *actions*: a deterministic, local forecast of
near-future operator behaviour from the action stream, the 9.4 behavioral
motifs, and the action-causal structure (graph + 8.2 influence).

    forecast_next_actions(actions, motifs, graph, influence) -> list[dict]
    forecast_habit_trajectory(actions) -> list[dict]
    forecast_trigger_likelihood(motifs, influence) -> list[dict]
    forecast_loop_continuation(motifs, actions) -> list[dict]
    compute_behavioral_forecast(actions, motifs, graph, influence) -> dict

Deterministic, local, rule-based — **NOT** ML, **NOT** probabilistic inference.
No randomness, no wall-clock (the action timestamps are the only temporal
signal, all caller-supplied), no inference. Imports only the stdlib + the 8.0
primitive type — nothing from the CI-gated runtime spine, vault, or
operator_state; no operator_state writes, no new continuity buckets.

Inputs (all caller-supplied, mirroring the 9.4 motif API):
  * ``actions``   — recent ``ActionEvent``s (``.id`` / ``.label`` / ``.timestamp``).
  * ``motifs``    — the 9.4 ``analyze_behavioral_motifs`` dict. ``action_loops`` +
                    ``habits`` are action *labels*; ``trigger_chains`` +
                    ``action_bottlenecks`` + ``action_attractors`` are node *ids*.
  * ``graph``     — the action-augmented ``CausalGraph`` (accepted for signature
                    parity with the 9.4 API + future cross-graph scoring; 10.0
                    reads actions / motifs / influence only).
  * ``influence`` — the 8.2 ``propagate_influence`` dict (``node_id -> [0, 1]``).

See ``phase10_spec.md`` ("Phase 10.0 — Behavioral Forecast Engine").
"""
import statistics
from collections import Counter

from phase8_structures import CausalGraph

# Next-action scoring weights (sum = 1.0).
LOOP_WEIGHT = 0.4
HABIT_WEIGHT = 0.3
TRIGGER_WEIGHT = 0.2
INFLUENCE_WEIGHT = 0.1

# Result cap + recurrence threshold.
TOP_K = 5
MIN_RECURRENCE = 3        # a label must recur this many times to have a trajectory


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ordered(actions) -> list:
    """Actions in deterministic ``(timestamp, id)`` order."""
    return sorted(actions or [], key=lambda a: (a.timestamp, a.id))


def _representative_ids(ordered) -> dict:
    """Map each action label to a representative action id — the *latest*
    occurrence (``ordered`` is ascending, so the last write wins)."""
    rep = {}
    for action in ordered:
        rep[action.label] = action.id
    return rep


def forecast_next_actions(actions, motifs, graph: CausalGraph, influence) -> list:
    """Predict the next likely actions (top 5) by a deterministic weighted sum.

    Each distinct action label is a candidate, scored::

        score = 0.4*loop + 0.3*habit + 0.2*trigger + 0.1*influence

    where each component is in ``[0, 1]``:
      * ``loop``      — 1.0 if the label is the cyclic *successor* of the
                        most-recent action in a detected loop, else 0.0.
      * ``habit``     — the label's frequency normalized by the strongest
                        habit's frequency (only when it is a 9.4 habit), else 0.0.
      * ``trigger``   — 1.0 if the label participates (as an action endpoint) in
                        a trigger chain, else 0.0.
      * ``influence`` — the action's 8.2 influence value, normalized across
                        candidates.

    Candidates scoring 0 are dropped; the rest sort by score desc (ties by
    label) and cap at 5. ``drivers`` lists which of ``loop`` / ``habit`` /
    ``trigger`` fired (a purely influence-driven candidate has an empty list).
    ``graph`` is accepted for signature parity but unread in 10.0.
    """
    motifs = motifs or {}
    influence = influence or {}
    ordered = _ordered(actions)
    if not ordered:
        return []

    labels = [a.label for a in ordered]
    freq = Counter(labels)
    rep_id = _representative_ids(ordered)
    id_to_label = {a.id: a.label for a in ordered}
    last_label = labels[-1]

    loops = motifs.get("action_loops") or []            # label sequences
    habits = set(motifs.get("habits") or [])            # labels
    trigger_chains = motifs.get("trigger_chains") or []  # [action_id, factor_id, action_id]

    # Cyclic successors of the most-recent action across the detected loops.
    loop_next = set()
    for loop in loops:
        n = len(loop)
        for i, label in enumerate(loop):
            if label == last_label:
                loop_next.add(loop[(i + 1) % n])

    # Labels that appear as an action endpoint (position 0 or 2) of a trigger chain.
    trigger_labels = set()
    for chain in trigger_chains:
        for pos in (0, 2):
            if pos < len(chain):
                label = id_to_label.get(chain[pos])
                if label is not None:
                    trigger_labels.add(label)

    # Habit strength = frequency normalized by the strongest habit's frequency.
    habit_freqs = {label: freq[label] for label in habits if label in freq}
    max_habit_freq = max(habit_freqs.values()) if habit_freqs else 0

    # Influence = the action's own 8.2 influence value, normalized across candidates.
    infl_by_label = {label: float(influence.get(rep_id[label], 0.0)) for label in freq}
    max_infl = max(infl_by_label.values()) if infl_by_label else 0.0

    results = []
    for label in sorted(freq):
        loop_score = 1.0 if label in loop_next else 0.0
        habit_score = (habit_freqs.get(label, 0) / max_habit_freq) if max_habit_freq > 0 else 0.0
        trigger_score = 1.0 if label in trigger_labels else 0.0
        influence_score = (infl_by_label[label] / max_infl) if max_infl > 0 else 0.0
        score = _clamp(
            LOOP_WEIGHT * loop_score
            + HABIT_WEIGHT * habit_score
            + TRIGGER_WEIGHT * trigger_score
            + INFLUENCE_WEIGHT * influence_score,
            0.0, 1.0,
        )
        if score <= 0.0:
            continue
        drivers = []
        if loop_score > 0.0:
            drivers.append("loop")
        if habit_score > 0.0:
            drivers.append("habit")
        if trigger_score > 0.0:
            drivers.append("trigger")
        results.append({
            "action_id": rep_id[label],
            "label": label,
            "score": score,
            "drivers": drivers,
        })

    results.sort(key=lambda r: (-r["score"], r["label"]))
    return results[:TOP_K]


def _trend_for(timestamps) -> str:
    """Classify a label's trajectory from its occurrence timestamps.

    Splits the inter-event gaps into an earlier and a later half and compares::

        strengthening — frequency up AND spacing down (events tightening)
        weakening     — frequency down AND spacing up (events loosening)
        stable        — otherwise (spacing unchanged)

    Frequency is the reciprocal of mean spacing, so the two conditions are
    consistent by construction; ``stable`` is the no-change case.
    """
    ordered_ts = sorted(timestamps)
    gaps = [ordered_ts[i + 1] - ordered_ts[i] for i in range(len(ordered_ts) - 1)]
    if len(gaps) < 2:
        return "stable"
    half = len(gaps) // 2
    spacing_early = statistics.mean(gaps[:half])
    spacing_late = statistics.mean(gaps[half:])
    delta_spacing = spacing_late - spacing_early
    freq_early = 1.0 / spacing_early if spacing_early > 0 else 0.0
    freq_late = 1.0 / spacing_late if spacing_late > 0 else 0.0
    delta_frequency = freq_late - freq_early
    if delta_frequency > 0 and delta_spacing < 0:
        return "strengthening"
    if delta_frequency < 0 and delta_spacing > 0:
        return "weakening"
    return "stable"


def forecast_habit_trajectory(actions) -> list:
    """Predict whether each recurring action is strengthening / weakening /
    stable.

    Considers any label recurring ``>= MIN_RECURRENCE`` (3) times — a superset
    of the strict 9.4 *habit* (which requires *low* spacing variance and would
    reject a trending habit), so the trajectory can actually see the change.
    Returns ``{"action_id": <latest event id>, "trend": <str>}`` per label,
    sorted by label. Deterministic.
    """
    ordered = _ordered(actions)
    by_label = {}
    for action in ordered:
        by_label.setdefault(action.label, []).append(action.timestamp)
    rep_id = _representative_ids(ordered)

    trajectory = []
    for label in sorted(by_label):
        timestamps = by_label[label]
        if len(timestamps) < MIN_RECURRENCE:
            continue
        trajectory.append({"action_id": rep_id[label], "trend": _trend_for(timestamps)})
    return trajectory


def forecast_trigger_likelihood(motifs, influence) -> list:
    """Likelihood of each trigger chain firing (top 5).

    For each ``action -> factor -> action`` chain,
    ``likelihood = normalized(influence[action] + influence[factor])`` —
    normalized by the maximum raw sum across chains (→ ``[0, 1]``). Sorted by
    likelihood desc (ties by chain), capped at 5. Each entry:
    ``{"chain": [action_id, factor_id, action_id], "likelihood": <float>}``.
    Deterministic.
    """
    motifs = motifs or {}
    influence = influence or {}
    chains = motifs.get("trigger_chains") or []

    scored = []
    for chain in chains:
        if len(chain) < 2:
            continue
        raw = float(influence.get(chain[0], 0.0)) + float(influence.get(chain[1], 0.0))
        scored.append((list(chain), raw))

    max_raw = max((raw for _, raw in scored), default=0.0)
    results = [
        {
            "chain": chain,
            "likelihood": _clamp(raw / max_raw, 0.0, 1.0) if max_raw > 0 else 0.0,
        }
        for chain, raw in scored
    ]
    results.sort(key=lambda r: (-r["likelihood"], r["chain"]))
    return results[:TOP_K]


def _loop_continuation_probability(loop, ordered, stream) -> float:
    """Continuation probability of one loop — the mean of three deterministic
    ``[0, 1]`` signals: spacing regularity, recent adherence, and visit
    tightness (see ``forecast_loop_continuation``)."""
    loop_labels = set(loop)
    k = len(loop)

    # (1) Regularity — from the spacing variance of the loop's participants.
    part_ts = [a.timestamp for a in ordered if a.label in loop_labels]
    if len(part_ts) >= 2:
        spacings = [part_ts[i + 1] - part_ts[i] for i in range(len(part_ts) - 1)]
        mean_spacing = statistics.mean(spacings)
        cv = (statistics.pstdev(spacings) / mean_spacing) if mean_spacing > 0 else 0.0
        regularity = 1.0 / (1.0 + cv)
    else:
        regularity = 0.0

    # (2) Recent adherence — of the last k stream labels, the fraction in the loop.
    recent = stream[-k:] if k > 0 else []
    adherence = (sum(1 for label in recent if label in loop_labels) / k) if k > 0 else 0.0

    # (3) Tightness — balance of visit counts across the loop's labels.
    counts = [stream.count(label) for label in loop]
    max_count = max(counts) if counts else 0
    tightness = (min(counts) / max_count) if max_count > 0 else 0.0

    return _clamp((regularity + adherence + tightness) / 3.0, 0.0, 1.0)


def forecast_loop_continuation(motifs, actions) -> list:
    """Continuation probability for each detected loop.

    Combines three deterministic ``[0, 1]`` signals (equal weights):
      * **regularity** — ``1 / (1 + cv)`` of the loop participants' spacing
        (coefficient of variation ``cv``); a perfectly regular loop → 1.0.
      * **adherence** — of the last *k* stream labels (``k`` = loop length), the
        fraction belonging to the loop (recency: still cycling?).
      * **tightness** — ``min / max`` visit count across the loop's labels.

    ``continuation_probability = clamp((regularity + adherence + tightness)/3)``.
    Sorted by probability desc (ties by loop). Each entry:
    ``{"loop": [<labels>], "continuation_probability": <float>}``. Deterministic.
    """
    motifs = motifs or {}
    ordered = _ordered(actions)
    stream = [a.label for a in ordered]
    loops = motifs.get("action_loops") or []

    results = [
        {
            "loop": list(loop),
            "continuation_probability": _loop_continuation_probability(loop, ordered, stream),
        }
        for loop in loops
    ]
    results.sort(key=lambda r: (-r["continuation_probability"], r["loop"]))
    return results


def compute_behavioral_forecast(actions, motifs, graph: CausalGraph, influence) -> dict:
    """The unified behavioral forecast — all four sub-forecasts in one read-only
    dict (the object 10.4 will surface on ``/operator/telemetry``)."""
    return {
        "next_actions": forecast_next_actions(actions, motifs, graph, influence),
        "habit_trajectory": forecast_habit_trajectory(actions),
        "trigger_likelihood": forecast_trigger_likelihood(motifs, influence),
        "loop_continuation": forecast_loop_continuation(motifs, actions),
    }
