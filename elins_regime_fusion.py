"""
elins_regime_fusion.py — ELINS12 Unit 31.

Multi-regime temporal fusion engine. Aggregates a time-ordered
sequence of Unit 29 regime comparisons into a single long-arc reading:
trajectory direction, oscillation/whipsaw detection, cumulative risk
posture, and an overall long-arc assessment.

ROLE
----
First long-arc primitive at the REGIME level. While Unit 25 reads
slope across batch aggregates and Unit 27 reads structural state of a
single timeline, this module reads the BEHAVIOUR of a sequence of
regime transitions — does the system keep degrading, does it
oscillate, is it stabilizing? Pure composition over Unit 29 outputs —
no I/O, no persistence, no randomness.

LOGIC (locked, deterministic)
-----------------------------
1. Trajectory
    - start_regime  = history[0].baseline.regime_class
    - end_regime    = history[-1].candidate.regime_class
    - regime_delta_counts = {same, improved, degraded} tally
    - dominant_direction:
        degrading   if degraded > improved AND degraded >= 2
        improving   if improved > degraded AND improved >= 2
        flat        if improved == 0 AND degraded == 0
        else oscillating

2. Oscillation / whipsaw
    - Filter out "same" deltas (they don't break or sustain oscillation).
    - Find every MAXIMAL alternating run between "improved" and
      "degraded" in the filtered sequence.
    - is_oscillating       = at least one such run of length >= 3
    - oscillation_count    = number of such runs (length >= 3)
    - max_back_and_forth_span = longest such run
    - whipsaw              = is_oscillating AND span >= 4

3. Cumulative risk
    - Weights: low=1, medium=2, high=3.
    - risk_score = mean weight across history.
    - risk_level:
        high   if risk_score >= 2.3 OR high_count >= 3
        low    if risk_score <= 1.3 AND high_count == 0
        else   medium

4. Long-arc assessment (priority-ordered)
    persistent_degradation   degrading direction + non-low risk
    stabilizing              improving direction + low risk
    oscillating_regime       whipsaw == True
    persistent_risk          high risk + (flat or oscillating direction)
    benign                   otherwise

OUTPUT SHAPE (LOCKED)
---------------------
See module test suite and v53/v54 lock for the full schema —
``trajectory``, ``oscillation``, ``cumulative_risk``,
``long_arc_assessment``, ``summary`` all hold locked keys.

PUBLIC API
----------
    fuse_regime_history(history: list[dict]) -> dict
"""
from __future__ import annotations


# Locked delta vocabulary (mirror Unit 29).
_DELTA_SAME:     str = "same"
_DELTA_IMPROVED: str = "improved"
_DELTA_DEGRADED: str = "degraded"

# Locked direction vocabulary.
_DIR_IMPROVING:    str = "improving"
_DIR_DEGRADING:    str = "degrading"
_DIR_OSCILLATING:  str = "oscillating"
_DIR_FLAT:         str = "flat"

# Locked risk vocabulary.
_RISK_LOW:    str = "low"
_RISK_MEDIUM: str = "medium"
_RISK_HIGH:   str = "high"

# Locked long-arc assessment vocabulary.
_LA_STABILIZING:           str = "stabilizing"
_LA_PERSISTENT_DEGRADATION: str = "persistent_degradation"
_LA_PERSISTENT_RISK:       str = "persistent_risk"
_LA_OSCILLATING_REGIME:    str = "oscillating_regime"
_LA_BENIGN:                str = "benign"

# Locked thresholds.
_RISK_WEIGHTS: dict = {_RISK_LOW: 1, _RISK_MEDIUM: 2, _RISK_HIGH: 3}
_RISK_HIGH_SCORE:  float = 2.3
_RISK_LOW_SCORE:   float = 1.3
_RISK_HIGH_COUNT:  int   = 3
_DOMINANT_MIN:     int   = 2
_OSCILLATION_MIN_RUN: int = 3
_WHIPSAW_MIN_RUN:     int = 4

# Required Unit 29 comparison keys.
_REQUIRED_KEYS: tuple = (
    "regime_delta",
    "risk_assessment",
    "baseline",
    "candidate",
)


def _validate_history(history) -> None:
    if not isinstance(history, list):
        raise ValueError(
            f"fuse_regime_history expected a list, "
            f"got {type(history).__name__}"
        )
    for i, entry in enumerate(history):
        if not isinstance(entry, dict):
            raise ValueError(
                f"history[{i}] must be a dict (Unit 29 output), "
                f"got {type(entry).__name__}"
            )
        for key in _REQUIRED_KEYS:
            if key not in entry:
                raise ValueError(
                    f"history[{i}] missing required Unit 29 key {key!r}"
                )
        if entry["regime_delta"] not in (
            _DELTA_SAME, _DELTA_IMPROVED, _DELTA_DEGRADED,
        ):
            raise ValueError(
                f"history[{i}]['regime_delta'] must be one of "
                f"(same, improved, degraded), got "
                f"{entry['regime_delta']!r}"
            )
        if entry["risk_assessment"] not in _RISK_WEIGHTS:
            raise ValueError(
                f"history[{i}]['risk_assessment'] must be one of "
                f"(low, medium, high), got "
                f"{entry['risk_assessment']!r}"
            )


def _empty_response(history: list) -> dict:
    """Locked-shape response for an empty history."""
    return {
        "history":  history,
        "trajectory": {
            "start_regime":         "",
            "end_regime":           "",
            "dominant_direction":   _DIR_FLAT,
            "regime_delta_counts": {
                _DELTA_SAME: 0, _DELTA_IMPROVED: 0, _DELTA_DEGRADED: 0,
            },
        },
        "oscillation": {
            "is_oscillating":        False,
            "oscillation_count":     0,
            "max_back_and_forth_span": 0,
            "whipsaw":               False,
        },
        "cumulative_risk": {
            "low_count":    0,
            "medium_count": 0,
            "high_count":   0,
            "risk_score":   0.0,
            "risk_level":   _RISK_LOW,
        },
        "long_arc_assessment": _LA_BENIGN,
        "summary":             "No comparisons supplied for fusion.",
    }


def _trajectory(history: list, delta_counts: dict) -> dict:
    start_regime = (
        history[0]["baseline"].get("regime_class", "")
        if isinstance(history[0].get("baseline"), dict) else ""
    )
    end_regime = (
        history[-1]["candidate"].get("regime_class", "")
        if isinstance(history[-1].get("candidate"), dict) else ""
    )
    improved = delta_counts[_DELTA_IMPROVED]
    degraded = delta_counts[_DELTA_DEGRADED]
    if improved == 0 and degraded == 0:
        direction = _DIR_FLAT
    elif degraded > improved and degraded >= _DOMINANT_MIN:
        direction = _DIR_DEGRADING
    elif improved > degraded and improved >= _DOMINANT_MIN:
        direction = _DIR_IMPROVING
    else:
        direction = _DIR_OSCILLATING
    return {
        "start_regime":         start_regime,
        "end_regime":           end_regime,
        "dominant_direction":   direction,
        "regime_delta_counts":  delta_counts,
    }


def _alternating_runs(deltas: list) -> list:
    """Return the lengths of every MAXIMAL alternating run between
    "improved" and "degraded" in the filtered (no "same") delta
    sequence, including runs of length 1 (an isolated entry).

    A run is "maximal" — extending in either direction would either
    fall off the sequence or hit a non-alternating neighbour.
    """
    if not deltas:
        return []
    lengths: list = []
    i = 0
    while i < len(deltas):
        j = i + 1
        while j < len(deltas) and deltas[j] != deltas[j - 1]:
            j += 1
        lengths.append(j - i)
        i = j
    return lengths


def _oscillation(history: list) -> dict:
    filtered = [
        e["regime_delta"] for e in history
        if e["regime_delta"] != _DELTA_SAME
    ]
    runs = _alternating_runs(filtered)
    qualifying = [r for r in runs if r >= _OSCILLATION_MIN_RUN]
    max_span = max(runs) if runs else 0
    # Only count "real" alternating runs (length >= 3) in
    # max_back_and_forth_span — isolated entries don't count.
    max_qualifying_span = max(qualifying) if qualifying else 0
    is_oscillating = len(qualifying) > 0
    whipsaw = is_oscillating and max_qualifying_span >= _WHIPSAW_MIN_RUN
    # Honour the spec's "max back-and-forth span" semantics: it is the
    # longest alternating run that crosses the oscillation threshold.
    # If none qualify, surface 0 (no oscillation detected).
    surfaced_span = max_qualifying_span if is_oscillating else 0
    _ = max_span  # retained for clarity even if not surfaced
    return {
        "is_oscillating":          is_oscillating,
        "oscillation_count":       len(qualifying),
        "max_back_and_forth_span": surfaced_span,
        "whipsaw":                 whipsaw,
    }


def _cumulative_risk(history: list) -> dict:
    counts: dict = {_RISK_LOW: 0, _RISK_MEDIUM: 0, _RISK_HIGH: 0}
    weighted_total = 0
    for entry in history:
        r = entry["risk_assessment"]
        counts[r] += 1
        weighted_total += _RISK_WEIGHTS[r]
    total = len(history)
    risk_score = weighted_total / total if total > 0 else 0.0
    high_count = counts[_RISK_HIGH]
    if risk_score >= _RISK_HIGH_SCORE or high_count >= _RISK_HIGH_COUNT:
        level = _RISK_HIGH
    elif risk_score <= _RISK_LOW_SCORE and high_count == 0:
        level = _RISK_LOW
    else:
        level = _RISK_MEDIUM
    return {
        "low_count":    counts[_RISK_LOW],
        "medium_count": counts[_RISK_MEDIUM],
        "high_count":   high_count,
        "risk_score":   risk_score,
        "risk_level":   level,
    }


def _long_arc_assessment(trajectory: dict,
                          oscillation: dict,
                          cumulative_risk: dict) -> str:
    direction = trajectory["dominant_direction"]
    risk_level = cumulative_risk["risk_level"]
    whipsaw = oscillation["whipsaw"]
    if direction == _DIR_DEGRADING and risk_level != _RISK_LOW:
        return _LA_PERSISTENT_DEGRADATION
    if direction == _DIR_IMPROVING and risk_level == _RISK_LOW:
        return _LA_STABILIZING
    if whipsaw:
        return _LA_OSCILLATING_REGIME
    if (
        risk_level == _RISK_HIGH
        and direction in (_DIR_FLAT, _DIR_OSCILLATING)
    ):
        return _LA_PERSISTENT_RISK
    return _LA_BENIGN


def _direction_phrase(direction: str) -> str:
    return {
        _DIR_IMPROVING:   "improving",
        _DIR_DEGRADING:   "degrading",
        _DIR_FLAT:        "flat",
        _DIR_OSCILLATING: "oscillating",
    }.get(direction, direction)


def _assessment_phrase(assessment: str) -> str:
    return {
        _LA_PERSISTENT_DEGRADATION: "persistent degradation",
        _LA_STABILIZING:            "stabilizing trajectory",
        _LA_OSCILLATING_REGIME:     "oscillating regime",
        _LA_PERSISTENT_RISK:        "persistent risk",
        _LA_BENIGN:                 "benign long-arc",
    }.get(assessment, assessment)


def _build_summary(history_len: int,
                   trajectory: dict,
                   oscillation: dict,
                   cumulative_risk: dict,
                   assessment: str) -> str:
    """Deterministic English summary matching the spec example::

        "Long-arc: persistent degradation with high risk; oscillating
         regime; 3 high-risk segments over 10 comparisons."
    """
    parts: list = [
        f"Long-arc: {_assessment_phrase(assessment)} "
        f"with {cumulative_risk['risk_level']} risk"
    ]
    if oscillation["whipsaw"]:
        parts.append("whipsaw oscillation")
    elif oscillation["is_oscillating"]:
        parts.append("oscillating regime")
    parts.append(
        f"{cumulative_risk['high_count']} high-risk segments "
        f"over {history_len} comparisons"
    )
    return "; ".join(parts) + "."


def fuse_regime_history(history) -> dict:
    """Fuse a time-ordered list of Unit 29 comparisons into a single
    long-arc reading.

    Args:
        history: time-ordered list (oldest → newest) of Unit 29
            ``compare_regimes`` outputs.

    Returns:
        Locked-shape dict with the keys documented in the module
        docstring.

    Raises:
        ValueError on a malformed history.
    """
    _validate_history(history)
    if not history:
        return _empty_response(history)

    delta_counts: dict = {
        _DELTA_SAME:     0,
        _DELTA_IMPROVED: 0,
        _DELTA_DEGRADED: 0,
    }
    for entry in history:
        delta_counts[entry["regime_delta"]] += 1

    trajectory     = _trajectory(history, delta_counts)
    oscillation    = _oscillation(history)
    cumulative_risk = _cumulative_risk(history)
    assessment     = _long_arc_assessment(
        trajectory, oscillation, cumulative_risk,
    )
    summary        = _build_summary(
        len(history), trajectory, oscillation,
        cumulative_risk, assessment,
    )

    return {
        "history":             list(history),
        "trajectory":          trajectory,
        "oscillation":         oscillation,
        "cumulative_risk":     cumulative_risk,
        "long_arc_assessment": assessment,
        "summary":             summary,
    }
