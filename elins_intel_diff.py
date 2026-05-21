"""
elins_intel_diff.py — ELINS3 Unit 14.

Intelligence diff engine. Compare two run sets (A vs B) and produce a
structured delta: aggregate summary deltas, per-pair changes, and a
deterministic narrative.

ROLE
----
Operator-grade "compare two time periods" surface. Pure composition
over the ELINS2 intelligence stack (Units 1-9): both sides go through
``intelligence_for_run_ids`` once, then we diff the resulting payloads.
No new heuristics, no randomness, byte-equal output for the same
inputs.

OVERLAP
-------
The two sets may overlap or be disjoint — they're compared as-is. The
diff is asymmetric: ``diff_intelligence(A, B)`` reports how B differs
FROM A. Reversing the arguments negates every numeric delta.

PUBLIC API
----------
    diff_intelligence(a_run_ids, b_run_ids) -> dict

OUTPUT SHAPE (locked)
---------------------
::

    {
      "a_run_ids": [...],
      "b_run_ids": [...],
      "summary": {
        "health_delta":   <float in [-1, 1]>,
        "anomaly_delta":  <float in [-1, 1]>,
        "trend_shift":    "toward_stability | toward_volatility | neutral",
        "cluster_shift":  "more_upward | more_downward | neutral",
      },
      "pairs": {
        pair_id: {
          "stability_delta":  <float>,
          "volatility_delta": <float>,
          "trend_change":     "<from>_to_<to>" | "<unchanged>",
        },
        ...
      },
      "narrative": {
        "headline": str,
        "bullets":  list[str],
      },
    }
"""
from __future__ import annotations

from elins_intelligence import intelligence_for_run_ids
from elins_persistence import _validate_run_id


# Locked shift vocabulary.
_SHIFT_TOWARD_STABILITY:  str = "toward_stability"
_SHIFT_TOWARD_VOLATILITY: str = "toward_volatility"
_SHIFT_MORE_UPWARD:       str = "more_upward"
_SHIFT_MORE_DOWNWARD:     str = "more_downward"
_SHIFT_NEUTRAL:           str = "neutral"

# Stable trend classes — high stability, low volatility.
_STABLE_TRENDS: tuple = (
    "monotonic_increase", "monotonic_decrease", "plateau",
)
# Volatile trend classes — caller-relevant change.
_VOLATILE_TRENDS: tuple = ("volatile", "oscillation")

# Min absolute fraction-delta required to call out a directional shift.
_SHIFT_EPSILON: float = 0.05


def _validate_run_ids(run_ids, fn_name: str, side: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected {side}_run_ids to be a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _health_of(intel: dict) -> float:
    return float(intel.get("scores", {}).get("overall_health", 0.0))


def _anomaly_fraction(intel: dict) -> float:
    return float(
        intel.get("sequences", {}).get("analysis", {}).get(
            "anomaly_fraction", 0.0,
        )
    )


def _upward_fraction(intel: dict) -> float:
    return float(
        intel.get("sequences", {}).get("analysis", {}).get(
            "upward_fraction", 0.0,
        )
    )


def _downward_fraction(intel: dict) -> float:
    return float(
        intel.get("sequences", {}).get("analysis", {}).get(
            "downward_fraction", 0.0,
        )
    )


def _sequence_trend(intel: dict) -> str:
    return intel.get("trends", {}).get(
        "sequence", {},
    ).get("trend", "insufficient_data")


def _classify_trend_shift(a_trend: str, b_trend: str) -> str:
    """Map (A trend, B trend) -> shift label.

    Rules:
        A volatile/oscillation -> B stable/plateau/monotonic → toward_stability
        A stable/plateau/monotonic -> B volatile/oscillation → toward_volatility
        otherwise → neutral
    """
    a_vol = a_trend in _VOLATILE_TRENDS
    b_vol = b_trend in _VOLATILE_TRENDS
    a_stb = a_trend in _STABLE_TRENDS
    b_stb = b_trend in _STABLE_TRENDS
    if a_vol and b_stb:
        return _SHIFT_TOWARD_STABILITY
    if a_stb and b_vol:
        return _SHIFT_TOWARD_VOLATILITY
    return _SHIFT_NEUTRAL


def _classify_cluster_shift(a_up: float, b_up: float,
                            a_down: float, b_down: float) -> str:
    """Compare upward/downward fractions of pairs between A and B.

    Returns ``more_upward`` if upward share grew by at least
    ``_SHIFT_EPSILON``; ``more_downward`` if downward share grew by
    the same threshold; otherwise ``neutral``.
    """
    delta_up   = b_up   - a_up
    delta_down = b_down - a_down
    if delta_up >= _SHIFT_EPSILON and delta_up > delta_down:
        return _SHIFT_MORE_UPWARD
    if delta_down >= _SHIFT_EPSILON and delta_down > delta_up:
        return _SHIFT_MORE_DOWNWARD
    return _SHIFT_NEUTRAL


def _pair_summaries(intel: dict) -> dict:
    """Locate the per-pair Unit 4 summaries inside the intelligence
    payload."""
    return intel.get("trends", {}).get("pairs", {}) or {}


def _trend_change_label(a_dir: str, b_dir: str) -> str:
    """Render a pair-trend transition as ``"a_to_b"`` or ``"unchanged"``."""
    if a_dir == b_dir:
        return "unchanged"
    return f"{a_dir}_to_{b_dir}"


def _build_pair_deltas(a_pairs: dict, b_pairs: dict) -> dict:
    """Per-pair deltas covering the union of pair_ids in A and B.

    Pairs missing from one side get a 0.0 baseline for that side —
    matching Unit 4's "missing pair → magnitude 0" rule. The trend
    direction for a missing pair defaults to ``"flat"`` so the
    transition is well-defined.
    """
    out: dict = {}
    for pid in sorted(set(a_pairs.keys()) | set(b_pairs.keys())):
        a = a_pairs.get(pid, {})
        b = b_pairs.get(pid, {})
        a_stb = float(a.get("stability_score", 0.0))
        b_stb = float(b.get("stability_score", 0.0))
        a_vol = float(a.get("volatility_score", 0.0))
        b_vol = float(b.get("volatility_score", 0.0))
        a_dir = a.get("trend_direction", "flat")
        b_dir = b.get("trend_direction", "flat")
        out[pid] = {
            "stability_delta":  b_stb - a_stb,
            "volatility_delta": b_vol - a_vol,
            "trend_change":     _trend_change_label(a_dir, b_dir),
        }
    return out


def _format_headline(health_delta: float,
                     trend_shift: str,
                     cluster_shift: str) -> str:
    """Top-line one-sentence summary of B vs A."""
    if health_delta >= _SHIFT_EPSILON:
        verb = "improved"
    elif health_delta <= -_SHIFT_EPSILON:
        verb = "regressed"
    else:
        verb = "held steady"
    descriptor = ""
    if trend_shift == _SHIFT_TOWARD_STABILITY:
        descriptor = " with a shift toward stability"
    elif trend_shift == _SHIFT_TOWARD_VOLATILITY:
        descriptor = " with a shift toward volatility"
    elif cluster_shift == _SHIFT_MORE_UPWARD:
        descriptor = " with more upward-trending pairs"
    elif cluster_shift == _SHIFT_MORE_DOWNWARD:
        descriptor = " with more downward-trending pairs"
    return f"System health {verb} between period A and period B{descriptor}."


def _format_bullets(a_intel: dict, b_intel: dict,
                    pair_deltas: dict) -> list:
    a_health = _health_of(a_intel)
    b_health = _health_of(b_intel)
    a_anom   = _anomaly_fraction(a_intel)
    b_anom   = _anomaly_fraction(b_intel)
    a_anom_n = int(
        a_intel.get("narratives", {}).get(
            "runs", {},
        ).get("details", {}).get("num_anomalies", 0)
    )
    b_anom_n = int(
        b_intel.get("narratives", {}).get(
            "runs", {},
        ).get("details", {}).get("num_anomalies", 0)
    )

    bullets: list = [
        f"Overall health moved from {a_health:.2f} to {b_health:.2f}.",
        f"Anomaly fraction moved from {a_anom:.2f} to {b_anom:.2f}.",
        f"Anomaly count: {a_anom_n} → {b_anom_n}.",
    ]

    # Top pair improvement bullet — biggest stability gain across pairs.
    improvers = sorted(
        pair_deltas.items(),
        key=lambda kv: (-kv[1]["stability_delta"], kv[0]),
    )
    if improvers and improvers[0][1]["stability_delta"] >= _SHIFT_EPSILON:
        pid, d = improvers[0]
        bullets.append(
            f"Pair {pid} stability improved by "
            f"{d['stability_delta']:+.2f} and volatility shifted by "
            f"{d['volatility_delta']:+.2f}."
        )
    # Top pair regression bullet — biggest stability drop.
    regressors = sorted(
        pair_deltas.items(),
        key=lambda kv: (kv[1]["stability_delta"], kv[0]),
    )
    if regressors and regressors[0][1]["stability_delta"] <= -_SHIFT_EPSILON:
        pid, d = regressors[0]
        bullets.append(
            f"Pair {pid} stability declined by "
            f"{d['stability_delta']:+.2f} and volatility shifted by "
            f"{d['volatility_delta']:+.2f}."
        )
    return bullets


def diff_intelligence(a_run_ids, b_run_ids) -> dict:
    """Compute the structured intelligence diff between two run sets.

    Args:
        a_run_ids: chronologically-ordered "before" run identifiers.
        b_run_ids: chronologically-ordered "after" run identifiers.

    Both lists may be empty, may overlap, and may include legacy runs.

    Returns:
        Locked-shape dict — see module docstring for full schema.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(a_run_ids, "diff_intelligence", "a")
    _validate_run_ids(b_run_ids, "diff_intelligence", "b")

    a_intel = intelligence_for_run_ids(a_run_ids)
    b_intel = intelligence_for_run_ids(b_run_ids)

    health_delta  = _health_of(b_intel) - _health_of(a_intel)
    anomaly_delta = _anomaly_fraction(b_intel) - _anomaly_fraction(a_intel)
    trend_shift = _classify_trend_shift(
        _sequence_trend(a_intel), _sequence_trend(b_intel),
    )
    cluster_shift = _classify_cluster_shift(
        _upward_fraction(a_intel),  _upward_fraction(b_intel),
        _downward_fraction(a_intel), _downward_fraction(b_intel),
    )

    pair_deltas = _build_pair_deltas(
        _pair_summaries(a_intel), _pair_summaries(b_intel),
    )

    headline = _format_headline(health_delta, trend_shift, cluster_shift)
    bullets  = _format_bullets(a_intel, b_intel, pair_deltas)

    return {
        "a_run_ids": list(a_run_ids),
        "b_run_ids": list(b_run_ids),
        "summary": {
            "health_delta":  health_delta,
            "anomaly_delta": anomaly_delta,
            "trend_shift":   trend_shift,
            "cluster_shift": cluster_shift,
        },
        "pairs":      pair_deltas,
        "narrative": {
            "headline": headline,
            "bullets":  bullets,
        },
    }
