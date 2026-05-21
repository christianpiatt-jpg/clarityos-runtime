"""
elins_trends.py — ELINS2 Unit 3.

Long-arc trend detection across a chronological run sequence. Classifies
the OVERALL behaviour of a sequence into one of six categories, with a
confidence score that prefers low-volatility monotonic motion.

ROLE
----
First temporal-intelligence primitive on top of the ELINS2 Unit 1+2
foundation (similarity + clustering). Where Unit 13 classifies drift
per-pair, Unit 3 classifies the SEQUENCE itself by aggregating to a
single "run signature" scalar per timestamp and analysing its
trajectory.

TREND CLASSES
-------------
    "monotonic_increase"  — slope > +ε, low volatility
    "monotonic_decrease"  — slope < -ε, low volatility
    "plateau"             — |slope| < ε, low volatility
    "oscillation"         — |slope| ≈ 0, high volatility
    "volatile"            — large |slope| AND high volatility
    "insufficient_data"   — < 3 non-legacy runs after filtering

ALGORITHM
---------
1. Validate run_ids and drop legacy runs (metadata=None).
2. If < 3 runs remain → return ``insufficient_data``.
3. For each remaining run compute a signature scalar — the mean of
   every non-bool numeric score (sp + ec) across pairs in the run.
   Empty runs → 0.
4. Slope = ordinary-least-squares slope of the signature vector vs.
   run-index.
5. Volatility = stddev of the first-order differences (n-1 deltas).
6. Classify via the cutoffs above.
7. Score = ``normalised(|slope|) * (1 - normalised(volatility))``,
   clamped to [0, 1].

I/O CONTRACT
------------
Loads each requested run once via persistence. No drift/magnitude
re-computation — operates directly on the score signatures. No
logging, no network, no randomness.

PUBLIC API
----------
    trend_for_run_sequence(run_ids) -> dict
    detect_trends(run_ids) -> dict          # alias of trend_for_run_sequence
    trend_score(run_ids) -> float           # convenience: returns just "score"
"""
from __future__ import annotations

import math

from elins_persistence import _validate_run_id, load_comparison_result


# Locked classification thresholds.
_EPSILON_SLOPE:        float = 0.5
_VOLATILITY_THRESHOLD: float = 1.0

# Locked score normalisation (slope is in score-units / run-index;
# volatility is in score-units). Each metric is clamped to [0, 1]
# for the trend-score combination.
_MAX_SLOPE_NORM:      float = 5.0
_MAX_VOLATILITY_NORM: float = 5.0

# Locked trend class strings.
_TREND_INSUFFICIENT_DATA: str = "insufficient_data"
_TREND_MONOTONIC_INCREASE: str = "monotonic_increase"
_TREND_MONOTONIC_DECREASE: str = "monotonic_decrease"
_TREND_PLATEAU:            str = "plateau"
_TREND_OSCILLATION:        str = "oscillation"
_TREND_VOLATILE:           str = "volatile"

# Minimum non-legacy run count required to classify a trend.
_MIN_RUNS_FOR_TREND: int = 3


def _is_numeric_score(v) -> bool:
    """True iff `v` is int/float (not bool, not None, not string)."""
    return (
        v is not None
        and not isinstance(v, bool)
        and isinstance(v, (int, float))
    )


def _run_signature(run_payload) -> float:
    """Aggregate a single run's pair scores into a single scalar.

    Returns the arithmetic mean of every non-bool numeric score in the
    run (across both sp and ec dimensions). Empty runs and runs with
    no numeric scores return 0.0.
    """
    if not isinstance(run_payload, list):
        return 0.0
    scores: list = []
    for entry in run_payload:
        if not isinstance(entry, dict):
            continue
        for field in ("single_party_score", "economic_coercion_score"):
            v = entry.get(field)
            if _is_numeric_score(v):
                scores.append(float(v))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _ordinary_least_squares_slope(ys: list) -> float:
    """Slope of the OLS line ``y ~ x`` where x = 0..n-1. Zero if n<2 or
    the x variance is zero (impossible here since x is strictly
    increasing)."""
    n = len(ys)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(ys) / n
    num = sum((i - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _stddev_of_deltas(ys: list) -> float:
    """Population stddev of consecutive deltas. Zero if fewer than 2
    deltas exist."""
    if len(ys) < 2:
        return 0.0
    deltas = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    if not deltas:
        return 0.0
    mean_d = sum(deltas) / len(deltas)
    var = sum((d - mean_d) ** 2 for d in deltas) / len(deltas)
    return math.sqrt(var)


def _classify(slope: float, volatility: float) -> str:
    """Apply the locked cutoffs. Order of checks matters: low-volatility
    monotonic wins over volatile classification."""
    low_vol = volatility < _VOLATILITY_THRESHOLD
    if abs(slope) < _EPSILON_SLOPE and low_vol:
        return _TREND_PLATEAU
    if slope >= _EPSILON_SLOPE and low_vol:
        return _TREND_MONOTONIC_INCREASE
    if slope <= -_EPSILON_SLOPE and low_vol:
        return _TREND_MONOTONIC_DECREASE
    if abs(slope) < _EPSILON_SLOPE:
        return _TREND_OSCILLATION
    return _TREND_VOLATILE


def _normalised_trend_score(slope: float, volatility: float) -> float:
    """Confidence in a monotonic-trend reading: large normalised slope
    boosts the score, large normalised volatility deflates it."""
    norm_slope = min(abs(slope) / _MAX_SLOPE_NORM, 1.0)
    norm_vol   = min(volatility / _MAX_VOLATILITY_NORM, 1.0)
    return max(0.0, min(1.0, norm_slope * (1.0 - norm_vol)))


def _filter_non_legacy(run_ids: list) -> list:
    """Drop run_ids whose envelope is in the Unit 10 legacy shape
    (``metadata=None``). Order is preserved — caller is responsible for
    timestamp ordering."""
    out: list = []
    for rid in run_ids:
        env = load_comparison_result(rid)
        meta = env.get("metadata") if isinstance(env, dict) else None
        if isinstance(meta, dict):
            out.append((rid, env))
    return out


def _empty_response(run_ids: list) -> dict:
    return {
        "trend":      _TREND_INSUFFICIENT_DATA,
        "slope":      0.0,
        "volatility": 0.0,
        "score":      0.0,
        "run_ids":    list(run_ids),
    }


def trend_for_run_sequence(run_ids) -> dict:
    """Classify the long-arc trend across a chronological run sequence.

    Args:
        run_ids: list of run identifiers in chronological order (caller
            is responsible for ordering — use ``sort_run_ids_by_timestamp``
            from Unit 23 if needed).

    Returns:
        dict with the locked shape::

            {
                "trend":      "<one of six trend classes>",
                "slope":      <float>,
                "volatility": <float>,
                "score":      <float in [0, 1]>,
                "run_ids":    <list of non-legacy ids actually analysed>,
            }

        Insufficient data (< 3 non-legacy runs) yields the
        ``insufficient_data`` trend with zero metrics.

    Raises:
        ValueError if `run_ids` is not a list or contains a malformed id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"trend_for_run_sequence expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    pairs = _filter_non_legacy(run_ids)
    if len(pairs) < _MIN_RUNS_FOR_TREND:
        return _empty_response([rid for rid, _ in pairs])

    signatures = [_run_signature(env.get("result")) for _, env in pairs]
    slope      = _ordinary_least_squares_slope(signatures)
    volatility = _stddev_of_deltas(signatures)
    trend      = _classify(slope, volatility)
    score      = _normalised_trend_score(slope, volatility)

    return {
        "trend":      trend,
        "slope":      slope,
        "volatility": volatility,
        "score":      score,
        "run_ids":    [rid for rid, _ in pairs],
    }


# Alias — spec lists both names as part of the public surface.
detect_trends = trend_for_run_sequence


def trend_score(run_ids) -> float:
    """Convenience wrapper returning just the score field."""
    return trend_for_run_sequence(run_ids)["score"]
