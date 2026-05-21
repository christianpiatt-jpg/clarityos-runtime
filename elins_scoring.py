"""
elins_scoring.py — ELINS2 Unit 6.

Operator-level KPI surface over a set of runs. Composes signals from
Units 2–5 into:

    * per-run scores (stability / improvement / regression / anomaly
      penalty → composite ∈ [0, 1])
    * per-pair scores (stability / trend / volatility → composite)
    * a single overall health score ∈ [0, 1]

ROLE
----
Top-level summary for dashboards. Does not introduce new heuristics —
every signal is sourced from an earlier ELINS2 unit, and the per-run /
per-pair formulas are linear combinations with locked weights so the
KPIs are stable and auditable.

LEGACY HANDLING
---------------
Legacy runs (Unit 10, metadata=None) are skipped from numeric
aggregation. They appear in the per-run output with ``stability=0``,
``improvement=0``, ``regression=0``, ``anomaly_penalty=1`` and
composite ``score=0`` so dashboards know they're inactive.

PUBLIC API
----------
    compute_run_scores(run_ids) -> dict
    compute_pair_scores(run_ids) -> dict
    overall_health_score(run_ids) -> float
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_clustering import cluster_runs
from elins_multi_summary import multi_run_summary
from elins_persistence import _validate_run_id, load_comparison_result
from elins_trends import _MAX_VOLATILITY_NORM, _stddev_of_deltas, _run_signature


# ---- Locked weights -------------------------------------------------------
# Per-run composite: stability + improvement - regression - anomaly.
_RUN_ALPHA: float = 0.5  # stability boost
_RUN_BETA:  float = 0.5  # improvement boost (upward-drift cluster)
_RUN_GAMMA: float = 0.5  # regression penalty (downward-drift cluster)
_RUN_DELTA: float = 0.5  # anomaly penalty

# Per-pair composite.
_PAIR_W_STABILITY:  float = 0.5
_PAIR_W_TREND:      float = 0.4
_PAIR_W_VOLATILITY: float = 0.5

# Overall health adjustments.
_HEALTH_ANOMALY_PENALTY: float  = 0.2  # subtract per fraction-of-high-anomalies
_HEALTH_DOWNWARD_PENALTY: float = 0.1  # subtract per fraction-of-downward-runs
_HEALTH_STABLE_BOOST:     float = 0.1  # add if majority of pairs are stable/upward

# Cluster labels (mirror Unit 2 vocabulary).
_LABEL_UPWARD:   str = "upward drift"
_LABEL_DOWNWARD: str = "downward drift"

# Pair trend numeric encoding (upward > flat > downward).
_TREND_NUMERIC: dict = {
    "upward":   1.0,
    "flat":     0.5,
    "downward": 0.0,
}


def _clamp_unit(x: float) -> float:
    return max(0.0, min(1.0, x))


def _partition_legacy(run_ids: list) -> tuple:
    modern: list = []
    legacy: list = []
    for rid in run_ids:
        env = load_comparison_result(rid)
        meta = env.get("metadata") if isinstance(env, dict) else None
        if isinstance(meta, dict):
            modern.append(rid)
        else:
            legacy.append(rid)
    return modern, legacy


def _sequence_stability(modern_ids: list) -> float:
    """1 - normalised volatility of the run-signature trajectory."""
    if len(modern_ids) < 2:
        return 1.0  # nothing to be volatile over
    envelopes = [load_comparison_result(rid) for rid in modern_ids]
    signatures = [_run_signature(env.get("result")) for env in envelopes]
    vol = _stddev_of_deltas(signatures)
    norm = min(vol / _MAX_VOLATILITY_NORM, 1.0)
    return max(0.0, 1.0 - norm)


def _cluster_label_per_run(modern_ids: list) -> dict:
    """Map each modern run to its cluster's drift label."""
    if not modern_ids:
        return {}
    if len(modern_ids) == 1:
        return {modern_ids[0]: "anomaly"}
    clustered = cluster_runs(modern_ids)
    labels: dict = {}
    for cid, summary in clustered["cluster_summary"].items():
        for m in summary["members"]:
            labels[m] = summary["label"]
    return labels


def _zero_run_entry() -> dict:
    return {
        "stability":       0.0,
        "improvement":     0.0,
        "regression":      0.0,
        "anomaly_penalty": 1.0,
        "score":           0.0,
    }


def compute_run_scores(run_ids) -> dict:
    """Compute a per-run scorecard across `run_ids`.

    Each entry has:
        * stability       — sequence-level stability (same for all runs)
        * improvement     — 1.0 if the run's cluster is upward-drift
        * regression      — 1.0 if the run's cluster is downward-drift
        * anomaly_penalty — Unit 5 anomaly score for this run
        * score           — composite, clamped to [0, 1]

    Legacy runs are returned with zero-valued metrics and ``score=0``.

    Returns:
        ``{"runs": {run_id: {...}}}``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"compute_run_scores expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    if not run_ids:
        return {"runs": {}}

    modern_ids, legacy_ids = _partition_legacy(run_ids)

    stability = _sequence_stability(modern_ids)
    cluster_labels = _cluster_label_per_run(modern_ids)
    anomaly_result = detect_run_anomalies(run_ids)
    anomaly_scores = {
        rid: info["score"]
        for rid, info in anomaly_result["runs"].items()
    }

    runs_out: dict = {}
    for rid in modern_ids:
        label = cluster_labels.get(rid, "")
        improvement = 1.0 if label == _LABEL_UPWARD   else 0.0
        regression  = 1.0 if label == _LABEL_DOWNWARD else 0.0
        anomaly = anomaly_scores.get(rid, 0.0)
        composite = (
            _RUN_ALPHA * stability
            + _RUN_BETA  * improvement
            - _RUN_GAMMA * regression
            - _RUN_DELTA * anomaly
        )
        runs_out[rid] = {
            "stability":       stability,
            "improvement":     improvement,
            "regression":      regression,
            "anomaly_penalty": anomaly,
            "score":           _clamp_unit(composite),
        }
    for rid in legacy_ids:
        runs_out[rid] = _zero_run_entry()

    return {"runs": runs_out}


def compute_pair_scores(run_ids) -> dict:
    """Compute a per-pair scorecard across the run sequence.

    Each entry has:
        * stability  — Unit 4 stability_score
        * volatility — Unit 4 volatility_score
        * trend      — Unit 4 trend_direction ("upward" / "flat" /
                       "downward")
        * score      — composite, clamped to [0, 1]

    Returns:
        ``{"pairs": {pair_id: {...}}}``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"compute_pair_scores expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    summary = multi_run_summary(run_ids)
    pair_summaries = summary["pair_summaries"]
    pairs_out: dict = {}
    for pid, data in pair_summaries.items():
        stability  = data["stability_score"]
        volatility = data["volatility_score"]
        trend      = data["trend_direction"]
        trend_num  = _TREND_NUMERIC.get(trend, 0.5)
        composite = (
            _PAIR_W_STABILITY * stability
            + _PAIR_W_TREND * trend_num
            - _PAIR_W_VOLATILITY * volatility
        )
        pairs_out[pid] = {
            "stability":  stability,
            "volatility": volatility,
            "trend":      trend,
            "score":      _clamp_unit(composite),
        }
    return {"pairs": pairs_out}


def overall_health_score(run_ids) -> float:
    """Aggregate run + pair scores into a single health float.

    Algorithm:
        1. Mean of per-run scores (modern runs only).
        2. Subtract ``_HEALTH_ANOMALY_PENALTY * fraction_of_high_anomalies``.
        3. Subtract ``_HEALTH_DOWNWARD_PENALTY * fraction_of_downward_runs``.
        4. Add ``_HEALTH_STABLE_BOOST`` if a majority of pairs are
           stable (trend != "downward").
        5. Clamp to [0, 1].

    Returns 0.0 for empty input or all-legacy input.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"overall_health_score expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    if not run_ids:
        return 0.0

    modern_ids, _ = _partition_legacy(run_ids)
    if not modern_ids:
        return 0.0

    run_result = compute_run_scores(run_ids)
    modern_run_scores = [
        run_result["runs"][rid]["score"] for rid in modern_ids
    ]
    if not modern_run_scores:
        return 0.0
    base = sum(modern_run_scores) / len(modern_run_scores)

    # Adjust by anomaly + downward fractions.
    anomaly_result = detect_run_anomalies(run_ids)
    high_count = sum(
        1 for rid in modern_ids
        if anomaly_result["runs"].get(rid, {}).get("level") == "high"
    )
    high_fraction = high_count / len(modern_ids)

    downward_count = sum(
        1 for rid in modern_ids
        if run_result["runs"][rid]["regression"] >= 1.0
    )
    downward_fraction = downward_count / len(modern_ids)

    # Pair-level stability bonus.
    pair_result = compute_pair_scores(run_ids)
    pairs = pair_result["pairs"]
    stable_pairs = sum(
        1 for data in pairs.values()
        if data["trend"] in ("upward", "flat")
    )
    majority_stable = (
        len(pairs) >= 1 and stable_pairs / len(pairs) > 0.5
    )

    health = base
    health -= _HEALTH_ANOMALY_PENALTY  * high_fraction
    health -= _HEALTH_DOWNWARD_PENALTY * downward_fraction
    if majority_stable:
        health += _HEALTH_STABLE_BOOST
    return _clamp_unit(health)
