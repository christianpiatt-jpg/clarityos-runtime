"""
elins_regime_comparison.py — ELINS11 Unit 29.

Regime comparison engine. Compares two Unit 27 structural snapshots
(baseline vs candidate) and emits a structured delta: regime
direction, volatility shifts, breakpoint counts, event set diffs, and
a deterministic risk verdict.

ROLE
----
Operator-grade regime-to-regime comparative intelligence. Pure
composition over Unit 27 outputs — no I/O, no persistence, no
randomness. Same inputs always produce byte-equal output.

REGIME ORDERING (locked)
------------------------
The regime classes are ranked by structural risk::

    stable  <  transition  <  unstable

``regime_delta`` reflects the candidate's move relative to baseline:

    candidate < baseline   →  "improved"
    candidate > baseline   →  "degraded"
    candidate == baseline  →  "same"

RISK ASSESSMENT (locked)
------------------------
::

    high   if  regime_delta == "degraded"
           or  volatility_delta.absolute >= 0.02
           or  breakpoint_delta.delta    >= 2

    low    if  regime_delta == "improved"
           and volatility_delta.absolute <= 0.005
           and breakpoint_delta.delta    <= 0

    medium otherwise

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "baseline":          <full Unit 27 dict>,
      "candidate":         <full Unit 27 dict>,
      "regime_delta":      "same | improved | degraded",
      "volatility_delta": {"absolute": float, "relative": float},
      "breakpoint_delta": {
        "baseline_count":  int,
        "candidate_count": int,
        "delta":           int,
      },
      "event_summary": {
        "new_events":        list[str],
        "resolved_events":   list[str],
        "persistent_events": list[str],
      },
      "risk_assessment": "low | medium | high",
      "summary":         str,
    }

PUBLIC API
----------
    compare_regimes(baseline: dict, candidate: dict) -> dict
"""
from __future__ import annotations


# Locked regime ordering for delta resolution.
_REGIME_ORDER: dict = {
    "stable":     0,
    "transition": 1,
    "unstable":   2,
}

# Locked delta vocabulary.
_DELTA_SAME:      str = "same"
_DELTA_IMPROVED:  str = "improved"
_DELTA_DEGRADED:  str = "degraded"

# Locked risk vocabulary.
_RISK_LOW:    str = "low"
_RISK_MEDIUM: str = "medium"
_RISK_HIGH:   str = "high"

# Locked risk thresholds (mirror the spec's v52 lockfile).
_HIGH_VOLATILITY_ABS:  float = 0.02
_LOW_VOLATILITY_ABS:   float = 0.005
_HIGH_BREAKPOINT_DELTA: int = 2

# Safety floor for relative volatility delta when baseline is near zero.
_VOLATILITY_EPSILON: float = 1e-6

# Required Unit 27 contract keys.
_REQUIRED_UNIT_27_KEYS: tuple = (
    "regime_class",
    "volatility_variance",
    "breakpoints",
    "structural_events",
)


def _validate_unit_27_payload(payload, label: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(
            f"{label} must be a dict (Unit 27 output), "
            f"got {type(payload).__name__}"
        )
    for key in _REQUIRED_UNIT_27_KEYS:
        if key not in payload:
            raise ValueError(
                f"{label} missing required Unit 27 key {key!r}"
            )
    regime = payload["regime_class"]
    if regime not in _REGIME_ORDER:
        raise ValueError(
            f"{label}['regime_class'] must be one of "
            f"{tuple(_REGIME_ORDER.keys())}, got {regime!r}"
        )
    if not isinstance(payload["breakpoints"], list):
        raise ValueError(
            f"{label}['breakpoints'] must be a list, "
            f"got {type(payload['breakpoints']).__name__}"
        )
    if not isinstance(payload["structural_events"], list):
        raise ValueError(
            f"{label}['structural_events'] must be a list, "
            f"got {type(payload['structural_events']).__name__}"
        )


def _classify_regime_delta(baseline_regime: str,
                           candidate_regime: str) -> str:
    b = _REGIME_ORDER[baseline_regime]
    c = _REGIME_ORDER[candidate_regime]
    if c == b:
        return _DELTA_SAME
    if c < b:
        return _DELTA_IMPROVED
    return _DELTA_DEGRADED


def _volatility_delta(baseline_var: float,
                       candidate_var: float) -> dict:
    abs_delta = candidate_var - baseline_var
    denom = max(abs(baseline_var), _VOLATILITY_EPSILON)
    rel_delta = abs_delta / denom
    return {"absolute": abs_delta, "relative": rel_delta}


def _breakpoint_delta(baseline_bps: list,
                      candidate_bps: list) -> dict:
    b_count = len(baseline_bps)
    c_count = len(candidate_bps)
    return {
        "baseline_count":  b_count,
        "candidate_count": c_count,
        "delta":           c_count - b_count,
    }


def _event_summary(baseline_events: list,
                   candidate_events: list) -> dict:
    b_set = set(baseline_events)
    c_set = set(candidate_events)
    return {
        "new_events":        sorted(c_set - b_set),
        "resolved_events":   sorted(b_set - c_set),
        "persistent_events": sorted(b_set & c_set),
    }


def _classify_risk(regime_delta: str,
                   volatility_abs: float,
                   breakpoint_delta_value: int) -> str:
    # v53 lock: low-risk gate uses abs() so a big volatility DROP on
    # an improved regime still has to register as small in magnitude.
    # The high gate stays signed (only rising volatility blocks).
    if (
        regime_delta == _DELTA_DEGRADED
        or volatility_abs >= _HIGH_VOLATILITY_ABS
        or breakpoint_delta_value >= _HIGH_BREAKPOINT_DELTA
    ):
        return _RISK_HIGH
    if (
        regime_delta == _DELTA_IMPROVED
        and abs(volatility_abs) <= _LOW_VOLATILITY_ABS
        and breakpoint_delta_value <= 0
    ):
        return _RISK_LOW
    return _RISK_MEDIUM


def _build_summary(baseline_regime: str,
                   candidate_regime: str,
                   regime_delta: str,
                   volatility_abs: float,
                   breakpoint_delta_value: int) -> str:
    """Deterministic English summary combining regime, volatility,
    and breakpoint signals. Matches the spec's example format:
    ``"Regime degraded: stable → unstable; volatility +0.021;
    breakpoints +2."``
    """
    return (
        f"Regime {regime_delta}: {baseline_regime} → {candidate_regime}; "
        f"volatility {volatility_abs:+.3f}; "
        f"breakpoints {breakpoint_delta_value:+d}."
    )


def compare_regimes(baseline, candidate) -> dict:
    """Compare two Unit 27 structural snapshots and emit a structured
    regime-comparison payload.

    Args:
        baseline:  Unit 27 ``analyze_structural_trends`` output for
            the reference period.
        candidate: Unit 27 ``analyze_structural_trends`` output for
            the period under comparison.

    Returns:
        Locked-shape dict — see module docstring for the full schema.

    Raises:
        ValueError if either payload is missing the Unit 27 contract.
    """
    _validate_unit_27_payload(baseline, "baseline")
    _validate_unit_27_payload(candidate, "candidate")

    regime_delta = _classify_regime_delta(
        baseline["regime_class"],
        candidate["regime_class"],
    )
    vol_delta = _volatility_delta(
        float(baseline["volatility_variance"]),
        float(candidate["volatility_variance"]),
    )
    bp_delta = _breakpoint_delta(
        baseline["breakpoints"],
        candidate["breakpoints"],
    )
    events = _event_summary(
        baseline["structural_events"],
        candidate["structural_events"],
    )
    risk = _classify_risk(
        regime_delta,
        vol_delta["absolute"],
        bp_delta["delta"],
    )
    summary = _build_summary(
        baseline["regime_class"],
        candidate["regime_class"],
        regime_delta,
        vol_delta["absolute"],
        bp_delta["delta"],
    )
    return {
        "baseline":         baseline,
        "candidate":        candidate,
        "regime_delta":     regime_delta,
        "volatility_delta": vol_delta,
        "breakpoint_delta": bp_delta,
        "event_summary":    events,
        "risk_assessment":  risk,
        "summary":          summary,
    }
