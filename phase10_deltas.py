# phase10_deltas.py
"""
Phase 10.1 — Action-Causal Deltas (temporal change in the behavioral layer).

The behavioral analogue of Phase 7.1 (temporal deltas) and Phase 8.6 (causal
deltas), but for *actions*: it compares the most-recent window of behaviour
against the window before it and reports how four behavioral quantities moved —
action **frequency**, **spacing**, **influence**, and **centrality**.

    compute_action_frequency_delta(actions, window) -> dict
    compute_action_spacing_delta(actions, window) -> dict
    compute_action_influence_delta(influence_records, window) -> dict
    compute_action_centrality_delta(centrality, prev_centrality) -> dict
    compute_behavioral_deltas(actions, influence, centrality, window, prev_centrality=None) -> dict

Window semantics (deterministic, **no wall-clock**): the window is anchored at
the *latest timestamp in the input* — ``t_ref = max(timestamps)``. The current
window is ``(t_ref - window, t_ref]`` and the previous window is
``(t_ref - 2*window, t_ref - window]``. Empty input → empty result.

Keying: ``frequency`` + ``spacing`` are keyed by action **label** — the
recurring behavioral identity you can actually *count* / *space* (an event id is
unique, so its frequency is always 1). ``influence`` + ``centrality`` are keyed
by the action node **id** their 9.3 ``InfluenceRecord`` / 8.2 centrality inputs
carry. The unified object's four sub-dicts therefore use the identity natural to
each metric.

Pure / deterministic: no I/O, wall-clock, randomness, ML, or inference. Imports
only the stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state; no operator_state writes, no new continuity buckets.

See ``phase10_spec.md`` ("Phase 10.1 — Action-Causal Deltas").
"""
import statistics
from collections import Counter


def _split_by_window(items, get_ts, window) -> tuple:
    """Partition ``items`` into the (current, previous) trailing windows anchored
    at the latest timestamp.

    ``current = (t_ref - window, t_ref]``; ``previous = (t_ref - 2*window,
    t_ref - window]``, where ``t_ref = max(timestamp)``. Items older than the
    previous window are dropped. Empty input → ``([], [])``.
    """
    items = list(items)
    if not items:
        return [], []
    timestamps = [get_ts(it) for it in items]
    t_ref = max(timestamps)
    curr_lo = t_ref - window
    prev_lo = t_ref - 2.0 * window
    current = [it for it in items if curr_lo < get_ts(it) <= t_ref]
    previous = [it for it in items if prev_lo < get_ts(it) <= curr_lo]
    return current, previous


def _mean_spacing(timestamps) -> float:
    """Mean inter-event spacing of ``timestamps`` (0.0 when there is no gap —
    i.e. fewer than two events)."""
    ordered = sorted(timestamps)
    gaps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
    return statistics.mean(gaps) if gaps else 0.0


def compute_action_frequency_delta(actions, window) -> dict:
    """Per-label change in occurrence count between the current and previous
    windows::

        delta = (current - previous) / max(previous, 1)

    Keyed by action label, in sorted-label order. Labels active in neither
    window are omitted. Deterministic.
    """
    current, previous = _split_by_window(actions or [], lambda a: a.timestamp, window)
    curr_counts = Counter(a.label for a in current)
    prev_counts = Counter(a.label for a in previous)

    result = {}
    for label in sorted(set(curr_counts) | set(prev_counts)):
        c = curr_counts.get(label, 0)
        p = prev_counts.get(label, 0)
        result[label] = {"current": c, "previous": p, "delta": (c - p) / max(p, 1)}
    return result


def compute_action_spacing_delta(actions, window) -> dict:
    """Per-label change in mean inter-event spacing between the windows::

        delta = (previous_spacing - current_spacing) / max(previous_spacing, 1)

    A **positive** delta means spacing decreased — the action is *tightening*.
    A window with fewer than two occurrences has spacing 0.0 (no gap to measure).
    Keyed by action label, in sorted-label order. Deterministic.
    """
    current, previous = _split_by_window(actions or [], lambda a: a.timestamp, window)

    curr_ts, prev_ts = {}, {}
    for action in current:
        curr_ts.setdefault(action.label, []).append(action.timestamp)
    for action in previous:
        prev_ts.setdefault(action.label, []).append(action.timestamp)

    result = {}
    for label in sorted(set(curr_ts) | set(prev_ts)):
        curr_spacing = _mean_spacing(curr_ts.get(label, []))
        prev_spacing = _mean_spacing(prev_ts.get(label, []))
        result[label] = {
            "current_spacing": curr_spacing,
            "previous_spacing": prev_spacing,
            "delta": (prev_spacing - curr_spacing) / max(prev_spacing, 1),
        }
    return result


def compute_action_influence_delta(influence_records, window) -> dict:
    """Per-action change in summed influence weight between the windows::

        delta = (current - previous) / max(previous, 1)

    ``influence_records`` is the 9.3 ``InfluenceRecord`` stream (each has
    ``action_id`` / ``weight`` / ``timestamp``); ``current`` / ``previous`` are
    the sum of an action's record weights in each window. Keyed by action id, in
    sorted-id order. Deterministic.
    """
    current, previous = _split_by_window(influence_records or [], lambda r: r.timestamp, window)

    curr_sum, prev_sum = {}, {}
    for record in current:
        curr_sum[record.action_id] = curr_sum.get(record.action_id, 0.0) + float(record.weight)
    for record in previous:
        prev_sum[record.action_id] = prev_sum.get(record.action_id, 0.0) + float(record.weight)

    result = {}
    for action_id in sorted(set(curr_sum) | set(prev_sum)):
        c = curr_sum.get(action_id, 0.0)
        p = prev_sum.get(action_id, 0.0)
        result[action_id] = {"current": c, "previous": p, "delta": (c - p) / max(p, 1)}
    return result


def compute_action_centrality_delta(centrality, prev_centrality) -> dict:
    """Per-node change in centrality between two snapshots::

        delta = current - previous

    Compared over the union of node ids (a node present in only one snapshot
    deltas against 0). Keyed by node id, in sorted-id order. Deterministic.
    """
    centrality = centrality or {}
    prev_centrality = prev_centrality or {}

    result = {}
    for node_id in sorted(set(centrality) | set(prev_centrality)):
        c = float(centrality.get(node_id, 0.0))
        p = float(prev_centrality.get(node_id, 0.0))
        result[node_id] = {"current": c, "previous": p, "delta": c - p}
    return result


def compute_behavioral_deltas(actions, influence, centrality, window, prev_centrality=None) -> dict:
    """The unified behavioral-delta object — all four sub-deltas in one read-only
    dict (consumed by 10.2 stability / 10.3 narrative / 10.4 surfacing).

    ``influence`` is the 9.3 ``InfluenceRecord`` stream (not the 8.2 influence
    dict — see ``compute_action_influence_delta``). ``centrality`` is the current
    8.2 centrality dict; ``prev_centrality`` is the previous snapshot, defaulting
    to an empty baseline when absent (so every current node reads as newly
    present — consistent with the window-based deltas, where the absence of a
    previous window also surfaces as positive change).
    """
    return {
        "frequency": compute_action_frequency_delta(actions, window),
        "spacing": compute_action_spacing_delta(actions, window),
        "influence": compute_action_influence_delta(influence, window),
        "centrality": compute_action_centrality_delta(centrality, prev_centrality or {}),
    }
