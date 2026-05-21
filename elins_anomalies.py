"""
elins_anomalies.py — ELINS2 Unit 5.

Anomaly detection over runs and run sequences. Fuses four signals from
the ELINS2 stack into a composite anomaly score per run:

    1. Similarity outliers      (Unit 1)  — low max similarity to peers
    2. Clustering outliers      (Unit 2)  — singleton clusters
    3. Trend extremity          (Unit 3)  — residual deviation from OLS line
    4. Pair volatility outliers (Unit 4)  — max per-pair z-score of volatility

ROLE
----
Operator-facing flag for "this run looks unusual; investigate." Reuses
the deterministic primitives built in Units 1-4 — no new heuristics,
just composition.

LEGACY HANDLING
---------------
Legacy runs (metadata=None) are excluded from similarity / clustering
math because their feature vectors are unstable. They DO appear in the
output, scored as 1.0 ``high`` anomalies with the
``legacy_run`` reason — the operator gets a useful signal that a run
predates the metadata layer.

PUBLIC API
----------
    detect_run_anomalies(run_ids) -> dict
    detect_sequence_anomalies(run_ids, window=3) -> dict
    is_anomalous_run(run_id, run_ids=None) -> bool
"""
from __future__ import annotations

import math

from elins_clustering import cluster_runs
from elins_multi_summary import multi_run_summary
from elins_persistence import _validate_run_id, load_comparison_result
from elins_similarity import similarity_matrix
from elins_trends import (
    _MAX_VOLATILITY_NORM,
    _ordinary_least_squares_slope,
    _run_signature,
    trend_for_run_sequence,
)


# ---- Locked module constants ----------------------------------------------
# Composite weights — sum to 1.0 so the composite stays in [0, 1].
_W_SIM:     float = 0.40
_W_CLUSTER: float = 0.30
_W_TREND:   float = 0.20
_W_PAIRS:   float = 0.10

# Classification thresholds.
_HIGH_THRESHOLD:   float = 0.7
_MEDIUM_THRESHOLD: float = 0.4

# "Small cluster" cutoff for cluster-based anomaly: when the cluster
# size is <= this AND the total universe is much larger, the runs in
# that cluster get the cluster signal.
_SMALL_CLUSTER_SIZE: int = 1  # singleton is the strict spec
_LARGER_UNIVERSE_FACTOR: int = 3  # universe must be >= 3x small_cluster_size

# Z-score normalisation: 3 sigma → maxed out signal.
_MAX_Z_SCORE: float = 3.0

# Reason strings (locked vocabulary).
_REASON_LOW_SIMILARITY:    str = "low_similarity"
_REASON_SINGLETON_CLUSTER: str = "singleton_cluster"
_REASON_EXTREME_TREND:     str = "extreme_trend"
_REASON_VOLATILE_PAIRS:    str = "volatile_pairs"
_REASON_LEGACY_RUN:        str = "legacy_run"

# Signal-strength threshold above which a reason is recorded.
_REASON_THRESHOLD: float = 0.5

# Sequence-anomaly defaults.
_DEFAULT_WINDOW: int = 3

# Anomaly levels.
_LEVEL_HIGH:   str = "high"
_LEVEL_MEDIUM: str = "medium"
_LEVEL_NONE:   str = "none"


def _classify_score(score: float) -> str:
    if score >= _HIGH_THRESHOLD:
        return _LEVEL_HIGH
    if score >= _MEDIUM_THRESHOLD:
        return _LEVEL_MEDIUM
    return _LEVEL_NONE


def _partition_legacy(run_ids: list) -> tuple:
    """Split into (modern_ids, legacy_ids) by loading each envelope."""
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


def _similarity_signal(modern_ids: list) -> dict:
    """For each modern run, ``s_sim = 1 - max(similarity to others)``.
    Single-modern-run universe yields 0 (no comparison available)."""
    if len(modern_ids) < 2:
        return {rid: 0.0 for rid in modern_ids}
    matrix = similarity_matrix(modern_ids)
    out: dict = {}
    for rid in modern_ids:
        max_sim = max(
            matrix[(rid, other)]
            for other in modern_ids if other != rid
        )
        out[rid] = max(0.0, 1.0 - max_sim)
    return out


def _cluster_signal(modern_ids: list) -> dict:
    """``s_cluster`` per run: 1.0 if the run is in a singleton cluster
    AND the universe is at least 3x that size, else 0.0.

    The universe-size guard prevents 2-run universes from auto-flagging
    every run as anomalous (clustering 2 runs almost always produces
    two singletons under hierarchical agglomerative)."""
    if len(modern_ids) < 2:
        return {rid: 0.0 for rid in modern_ids}
    if len(modern_ids) < _LARGER_UNIVERSE_FACTOR * (_SMALL_CLUSTER_SIZE + 1):
        # Universe too small to identify "outlier" clusters meaningfully.
        return {rid: 0.0 for rid in modern_ids}
    clustered = cluster_runs(modern_ids)
    out: dict = {rid: 0.0 for rid in modern_ids}
    for cid, summary in clustered["cluster_summary"].items():
        if summary["size"] <= _SMALL_CLUSTER_SIZE:
            for member in summary["members"]:
                out[member] = 1.0
    return out


def _trend_signal(modern_ids: list) -> dict:
    """``s_trend`` per run: residual from the OLS line of run signatures,
    normalised by the max residual in the sequence. Requires >= 3
    modern runs (matches Unit 3's minimum)."""
    if len(modern_ids) < 3:
        return {rid: 0.0 for rid in modern_ids}
    envelopes = [load_comparison_result(rid) for rid in modern_ids]
    signatures = [_run_signature(env.get("result")) for env in envelopes]
    n = len(signatures)
    slope = _ordinary_least_squares_slope(signatures)
    mean_y = sum(signatures) / n
    intercept = mean_y - slope * (n - 1) / 2.0
    residuals = [
        abs(signatures[i] - (intercept + slope * i)) for i in range(n)
    ]
    max_res = max(residuals)
    if max_res == 0.0:
        return {rid: 0.0 for rid in modern_ids}
    return {
        modern_ids[i]: residuals[i] / max_res for i in range(n)
    }


def _pair_volatility_signal(modern_ids: list) -> float:
    """``s_pairs``: max per-pair volatility z-score across the sequence,
    normalised to [0, 1] by dividing by 3 sigma and clamping. A
    constant — every run in the sequence shares the value."""
    if len(modern_ids) < 2:
        return 0.0
    summary = multi_run_summary(modern_ids)
    pair_summaries = summary["pair_summaries"]
    if not pair_summaries:
        return 0.0
    vols = [
        data["volatility_score"] for data in pair_summaries.values()
    ]
    if len(vols) < 2:
        return 0.0
    mean_v = sum(vols) / len(vols)
    var = sum((v - mean_v) ** 2 for v in vols) / len(vols)
    stddev = math.sqrt(var)
    if stddev == 0.0:
        return 0.0
    max_v = max(vols)
    z = (max_v - mean_v) / stddev
    return min(z / _MAX_Z_SCORE, 1.0)


def _collect_reasons(s_sim: float, s_cluster: float,
                     s_trend: float, s_pairs: float) -> list:
    reasons: list = []
    if s_sim >= _REASON_THRESHOLD:
        reasons.append(_REASON_LOW_SIMILARITY)
    if s_cluster >= _REASON_THRESHOLD:
        reasons.append(_REASON_SINGLETON_CLUSTER)
    if s_trend >= _REASON_THRESHOLD:
        reasons.append(_REASON_EXTREME_TREND)
    if s_pairs >= _REASON_THRESHOLD:
        reasons.append(_REASON_VOLATILE_PAIRS)
    return reasons


def _thresholds_dict() -> dict:
    return {"high": _HIGH_THRESHOLD, "medium": _MEDIUM_THRESHOLD}


def detect_run_anomalies(run_ids) -> dict:
    """Score each run for anomaly likelihood.

    Args:
        run_ids: list of run identifiers. Order should be chronological
            so the trend signal is meaningful.

    Returns:
        ``{"runs": {run_id: {"score": <float>, "level": <str>,
        "reasons": [...]}}, "thresholds": {...}}``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"detect_run_anomalies expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    if not run_ids:
        return {"runs": {}, "thresholds": _thresholds_dict()}

    modern_ids, legacy_ids = _partition_legacy(run_ids)

    sim_signals     = _similarity_signal(modern_ids)
    cluster_signals = _cluster_signal(modern_ids)
    trend_signals   = _trend_signal(modern_ids)
    s_pairs         = _pair_volatility_signal(modern_ids)

    runs_out: dict = {}
    for rid in modern_ids:
        s_sim     = sim_signals.get(rid, 0.0)
        s_cluster = cluster_signals.get(rid, 0.0)
        s_trend   = trend_signals.get(rid, 0.0)
        score = (
            _W_SIM * s_sim
            + _W_CLUSTER * s_cluster
            + _W_TREND * s_trend
            + _W_PAIRS * s_pairs
        )
        score = max(0.0, min(1.0, score))
        level = _classify_score(score)
        # Reasons are only emitted for actually-flagged runs (medium /
        # high). Non-anomalous runs return an empty list so dashboards
        # don't surface "near-miss" signals as alerts.
        reasons = (
            _collect_reasons(s_sim, s_cluster, s_trend, s_pairs)
            if level != _LEVEL_NONE else []
        )
        runs_out[rid] = {
            "score":   score,
            "level":   level,
            "reasons": reasons,
        }

    for rid in legacy_ids:
        runs_out[rid] = {
            "score":   1.0,
            "level":   _LEVEL_HIGH,
            "reasons": [_REASON_LEGACY_RUN],
        }

    return {"runs": runs_out, "thresholds": _thresholds_dict()}


def detect_sequence_anomalies(run_ids, window: int = _DEFAULT_WINDOW) -> dict:
    """Score sliding windows of `run_ids` for anomaly likelihood.

    Each window's score reflects the trend's normalised score from
    Unit 3 (high slope or high volatility → high anomaly signal).

    Args:
        run_ids: chronologically-ordered list. Caller responsible for
            sort order.
        window: window size (>= 2). Default 3.

    Returns:
        ``{"windows": {<idx>: {...}}, "thresholds": {...}, "window": int}``.
        Empty ``windows`` dict when `run_ids` is shorter than the
        window or contains too few modern runs.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"detect_sequence_anomalies expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if isinstance(window, bool) or not isinstance(window, int):
        raise ValueError(
            f"window must be a positive int, got {type(window).__name__}"
        )
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    for rid in run_ids:
        _validate_run_id(rid)

    windows_out: dict = {}
    if len(run_ids) < window:
        return {
            "windows": windows_out,
            "thresholds": _thresholds_dict(),
            "window": window,
        }
    for start in range(len(run_ids) - window + 1):
        slice_ids = run_ids[start: start + window]
        # Use trend's "score" as the sequence-anomaly proxy. The trend
        # score peaks for strong monotonic motion in low-noise data;
        # we INVERT it so that low-score (volatile / plateau /
        # insufficient_data) sequences register as anomalies.
        trend = trend_for_run_sequence(slice_ids)
        if trend["trend"] == "insufficient_data":
            # Indeterminate window: don't flag.
            anomaly_score = 0.0
            reasons: list = []
        elif trend["trend"] in ("oscillation", "volatile"):
            # High volatility → anomaly signal proportional to volatility.
            norm_vol = min(trend["volatility"] / _MAX_VOLATILITY_NORM, 1.0)
            anomaly_score = norm_vol
            reasons = [_REASON_VOLATILE_PAIRS] if norm_vol >= _REASON_THRESHOLD else []
        else:
            # Monotonic / plateau → not anomalous.
            anomaly_score = 0.0
            reasons = []
        windows_out[f"window_{start}"] = {
            "run_ids": list(slice_ids),
            "score":   anomaly_score,
            "level":   _classify_score(anomaly_score),
            "reasons": reasons,
        }
    return {
        "windows":    windows_out,
        "thresholds": _thresholds_dict(),
        "window":     window,
    }


def is_anomalous_run(run_id: str, run_ids=None) -> bool:
    """Return ``True`` if `run_id` scores at the ``medium`` level or
    higher within `run_ids`. When `run_ids` is omitted, the universe
    is just the single run (which is never anomalous on its own
    unless legacy)."""
    _validate_run_id(run_id)
    universe = list(run_ids) if run_ids is not None else [run_id]
    if run_id not in universe:
        universe = list(universe) + [run_id]
    result = detect_run_anomalies(universe)
    info = result["runs"].get(run_id)
    if info is None:
        return False
    return info["level"] in (_LEVEL_MEDIUM, _LEVEL_HIGH)
