"""
elins_sequences.py — ELINS2 Unit 8.

Sequence intelligence. Higher-order reasoning over chronological run
sequences: aggregate signals across the whole sequence, and sweep
fixed-width windows to find the healthiest / unhealthiest stretches.

ROLE
----
Pure composition over the ELINS2 Units 2-6 stack. No new heuristics:
``analyze_sequence`` produces six fractional readings sourced from
Units 2-6, and ``best_sequence`` / ``worst_sequence`` evaluate
``overall_health_score`` across sliding windows. Deterministic by
construction — same inputs always yield byte-equal output.

PUBLIC API
----------
    analyze_sequence(run_ids: list[str]) -> dict
    best_sequence(run_ids: list[str], window: int = 5) -> dict
    worst_sequence(run_ids: list[str], window: int = 5) -> dict
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_clustering import cluster_runs
from elins_multi_summary import multi_run_summary
from elins_persistence import _validate_run_id
from elins_scoring import overall_health_score
from elins_trends import trend_for_run_sequence


# ---- Locked module constants ----------------------------------------------
_DEFAULT_WINDOW: int = 5
_MIN_WINDOW:     int = 2

# Trend / cluster vocabulary mirrors Units 2-3.
_TREND_INSUFFICIENT_DATA: str = "insufficient_data"
_CLUSTER_STABLE:          str = "stable"

_PAIR_TREND_UP:   str = "upward"
_PAIR_TREND_DOWN: str = "downward"

# Anomaly levels (mirror Unit 5).
_LEVEL_NONE: str = "none"


def _validate_run_ids(run_ids, fn_name: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected a list, got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _validate_window(window, run_ids, fn_name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, int):
        raise ValueError(
            f"{fn_name} expected window to be a positive int, "
            f"got {type(window).__name__}"
        )
    if window < _MIN_WINDOW:
        raise ValueError(
            f"{fn_name} requires window >= {_MIN_WINDOW}, got {window}"
        )
    if window > len(run_ids):
        raise ValueError(
            f"{fn_name} window ({window}) cannot exceed "
            f"len(run_ids) ({len(run_ids)})"
        )


def _empty_analysis() -> dict:
    """Locked-shape response for empty input to analyze_sequence."""
    return {
        "trend":                   _TREND_INSUFFICIENT_DATA,
        "overall_health":          0.0,
        "anomaly_fraction":        0.0,
        "upward_fraction":         0.0,
        "downward_fraction":       0.0,
        "stable_cluster_fraction": 0.0,
    }


def _anomaly_fraction(anomaly_runs: dict, num_runs: int) -> float:
    if num_runs <= 0:
        return 0.0
    flagged = sum(
        1 for info in anomaly_runs.values()
        if info.get("level", _LEVEL_NONE) != _LEVEL_NONE
    )
    return flagged / num_runs


def _pair_trend_fractions(pair_summaries: dict) -> tuple:
    """Return (upward_fraction, downward_fraction) over all pair
    directions in the multi-run summary. Each is normalised by the
    total pair count."""
    if not pair_summaries:
        return 0.0, 0.0
    total = len(pair_summaries)
    up   = sum(
        1 for data in pair_summaries.values()
        if data.get("trend_direction") == _PAIR_TREND_UP
    )
    down = sum(
        1 for data in pair_summaries.values()
        if data.get("trend_direction") == _PAIR_TREND_DOWN
    )
    return up / total, down / total


def _stable_cluster_fraction(cluster_assignments: dict,
                             cluster_summary: dict) -> float:
    """Fraction of runs whose assigned cluster carries the
    ``"stable"`` label."""
    if not cluster_assignments:
        return 0.0
    total = len(cluster_assignments)
    stable = 0
    for cid in cluster_assignments.values():
        label = cluster_summary.get(cid, {}).get("label", "")
        if label == _CLUSTER_STABLE:
            stable += 1
    return stable / total if total > 0 else 0.0


def analyze_sequence(run_ids) -> dict:
    """Aggregate-sequence reading across `run_ids`.

    Args:
        run_ids: chronologically ordered run identifiers. Caller is
            responsible for ordering.

    Returns:
        Locked-shape dict::

            {
                "trend":                   <Unit 3 trend class>,
                "overall_health":          <Unit 6 health ∈ [0, 1]>,
                "anomaly_fraction":        <fraction of flagged runs>,
                "upward_fraction":         <fraction of upward pairs>,
                "downward_fraction":       <fraction of downward pairs>,
                "stable_cluster_fraction": <fraction of stable-clustered runs>,
            }

        Empty input yields all-zero fractions and an
        ``insufficient_data`` trend.

    Raises:
        ValueError if `run_ids` is not a list or contains a malformed
            id.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "analyze_sequence")
    if not run_ids:
        return _empty_analysis()

    trend_result   = trend_for_run_sequence(run_ids)
    health         = overall_health_score(run_ids)
    anomaly_result = detect_run_anomalies(run_ids)
    summary_result = multi_run_summary(run_ids)
    cluster_result = cluster_runs(run_ids)

    anomaly_frac = _anomaly_fraction(
        anomaly_result["runs"], len(run_ids),
    )
    up_frac, down_frac = _pair_trend_fractions(
        summary_result["pair_summaries"],
    )
    stable_frac = _stable_cluster_fraction(
        cluster_result["assignments"],
        cluster_result["cluster_summary"],
    )

    return {
        "trend":                   trend_result["trend"],
        "overall_health":          health,
        "anomaly_fraction":        anomaly_frac,
        "upward_fraction":         up_frac,
        "downward_fraction":       down_frac,
        "stable_cluster_fraction": stable_frac,
    }


def _window_metrics(window_ids: list) -> dict:
    """Compute the locked-shape per-window report:
    ``{run_ids, overall_health, trend, anomaly_fraction}``."""
    health = overall_health_score(window_ids)
    trend_result = trend_for_run_sequence(window_ids)
    anomaly_result = detect_run_anomalies(window_ids)
    anomaly_frac = _anomaly_fraction(
        anomaly_result["runs"], len(window_ids),
    )
    return {
        "run_ids":          list(window_ids),
        "overall_health":   health,
        "trend":            trend_result["trend"],
        "anomaly_fraction": anomaly_frac,
    }


def _sweep_windows(run_ids: list, window: int) -> list:
    """Return the per-window metrics for every sliding window of size
    `window` over `run_ids`. Windows are produced in left-to-right
    order so ties can be broken by earliest start index."""
    out: list = []
    for start in range(len(run_ids) - window + 1):
        slice_ids = run_ids[start: start + window]
        out.append(_window_metrics(slice_ids))
    return out


def best_sequence(run_ids, window: int = _DEFAULT_WINDOW) -> dict:
    """Slide a fixed window over `run_ids` and return the window with
    the highest ``overall_health_score``.

    Args:
        run_ids: chronologically ordered run identifiers.
        window: integer window size, >= 2 and <= len(run_ids).
            Defaults to 5.

    Returns:
        Locked-shape dict mirroring the per-window report::

            {
                "run_ids":          [<window slice>],
                "overall_health":   <float in [0, 1]>,
                "trend":            <Unit 3 trend class>,
                "anomaly_fraction": <float in [0, 1]>,
            }

        Ties in health are broken by the earliest start index, so
        repeated calls always return the same window.

    Raises:
        ValueError if `run_ids` is not a list, contains a malformed
            id, or `window` is invalid (non-int, < 2, or larger than
            the sequence).
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "best_sequence")
    _validate_window(window, run_ids, "best_sequence")

    windows = _sweep_windows(run_ids, window)
    # First max wins → earliest start when there's a tie.
    best = max(windows, key=lambda w: w["overall_health"])
    return best


def worst_sequence(run_ids, window: int = _DEFAULT_WINDOW) -> dict:
    """Slide a fixed window over `run_ids` and return the window with
    the lowest ``overall_health_score``.

    Same shape and tie-breaking rules as ``best_sequence``: ties go to
    the earliest start index for deterministic output.

    Raises:
        ValueError if `run_ids` is not a list, contains a malformed
            id, or `window` is invalid (non-int, < 2, or larger than
            the sequence).
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "worst_sequence")
    _validate_window(window, run_ids, "worst_sequence")

    windows = _sweep_windows(run_ids, window)
    worst = min(windows, key=lambda w: w["overall_health"])
    return worst
