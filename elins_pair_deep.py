"""
elins_pair_deep.py — ELINS5 Unit 17.

Pair-level deep analytics engine. High-resolution per-pair intelligence
deeper than Unit 4's multi_run_summary: trajectory + anomaly inventory
(spikes / drops / volatility events) + deterministic narrative.

ROLE
----
"Microscope" layer. Pure composition over Units 4 / 5 — no new
heuristics. Anomalies are extracted from the pair's magnitude
trajectory using the Unit 4 severity bucket cutoffs, so callers see
the same vocabulary across the stack.

THRESHOLDS
----------
* Spike  — magnitude jumped UP   by more than ``_STRONG_SEVERITY_THRESHOLD``
* Drop   — magnitude dropped DOWN by more than ``_STRONG_SEVERITY_THRESHOLD``
* Volatility event — that transition's Unit 4 severity is ``"strong"``
  (overlaps with spike/drop by definition; surfaced separately so
  downstream consumers can filter without re-deriving)

NARRATIVE
---------
Templated 1-sentence headline + bullets, mirroring Unit 7's tone.
Tells the operator:
    * stability band (high/medium/low)
    * trend direction
    * recent anomaly inventory (count of spikes/drops/events)

PUBLIC API
----------
    pair_deep_analysis(run_ids: list[str], pair_id: str) -> dict
    pair_deep_all(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_multi_summary import (
    _SEVERITY_MODERATE_MAX,
    multi_run_summary,
)
from elins_persistence import _validate_run_id


# Locked thresholds.
_STRONG_SEVERITY_THRESHOLD: float = _SEVERITY_MODERATE_MAX  # = 4.0
_SEVERITY_STRONG_LABEL:     str   = "strong"

# Stability bands (mirror Unit 7's tone vocabulary).
_STABILITY_HIGH:   float = 0.85
_STABILITY_MEDIUM: float = 0.50

# Pair trend vocabulary (mirror Unit 4).
_TREND_UP:   str = "upward"
_TREND_FLAT: str = "flat"
_TREND_DOWN: str = "downward"


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"pair_deep expected run_ids to be a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _validate_pair_id(pair_id) -> None:
    if not isinstance(pair_id, str) or not pair_id:
        raise ValueError(
            f"pair_id must be a non-empty string, got {pair_id!r}"
        )


def _stability_band(stability: float) -> str:
    if stability >= _STABILITY_HIGH:
        return "high"
    if stability >= _STABILITY_MEDIUM:
        return "medium"
    return "low"


def _build_anomaly_inventory(filtered_ids: list,
                             magnitudes: list,
                             severities: list) -> dict:
    """Walk the per-transition (i -> i+1) series and emit
    spike/drop/volatility events keyed by the destination run_id.

    Each event carries the index, run_id, magnitude before/after, and
    the signed delta. Volatility events are emitted whenever Unit 4
    classified the transition as ``"strong"`` severity.
    """
    spikes: list = []
    drops:  list = []
    volatility_events: list = []
    for i in range(len(magnitudes) - 1):
        delta = magnitudes[i + 1] - magnitudes[i]
        rid_after = filtered_ids[i + 1] if i + 1 < len(filtered_ids) else ""
        if delta > _STRONG_SEVERITY_THRESHOLD:
            spikes.append({
                "run_id":    rid_after,
                "delta":     delta,
                "magnitude": magnitudes[i + 1],
            })
        elif delta < -_STRONG_SEVERITY_THRESHOLD:
            drops.append({
                "run_id":    rid_after,
                "delta":     delta,
                "magnitude": magnitudes[i + 1],
            })
        if (
            i < len(severities)
            and severities[i] == _SEVERITY_STRONG_LABEL
        ):
            volatility_events.append({
                "run_id":   rid_after,
                "severity": severities[i],
            })
    return {
        "spikes":            spikes,
        "drops":             drops,
        "volatility_events": volatility_events,
    }


def _build_pair_narrative(pair_id: str,
                          stability: float,
                          volatility: float,
                          trend: str,
                          anomalies: dict) -> dict:
    band = _stability_band(stability)
    if band == "high":
        verb = "shows improving stability"
        tone = "high stability"
    elif band == "medium":
        verb = "holds moderate stability"
        tone = "moderate stability"
    else:
        verb = "shows low stability"
        tone = "low stability"

    headline = f"Pair {pair_id} {verb}."

    bullets: list = [
        (
            f"Stability score {stability:.2f}; volatility score "
            f"{volatility:.2f} ({tone})."
        ),
        f"Trend direction: {trend}.",
    ]
    num_spikes = len(anomalies["spikes"])
    num_drops  = len(anomalies["drops"])
    num_events = len(anomalies["volatility_events"])
    if num_spikes == 0 and num_drops == 0:
        bullets.append("No magnitude spikes or drops detected.")
    else:
        bullets.append(
            f"{num_spikes} spike(s) and {num_drops} drop(s) above the "
            f"strong-severity threshold."
        )
    if num_events == 0:
        bullets.append("No volatility events detected.")
    else:
        bullets.append(f"{num_events} volatility event(s) recorded.")
    return {"headline": headline, "bullets": bullets}


def _empty_pair_response(pair_id: str) -> dict:
    """Locked-shape response for a pair with no usable data (e.g.
    fewer than 2 modern runs). Trajectory + anomalies are still
    well-formed (empty lists / zero scores)."""
    return {
        "pair_id": pair_id,
        "trajectory": {
            "direction_over_time": [],
            "magnitude_over_time": [],
            "severity_over_time":  [],
            "stability_score":     0.0,
            "volatility_score":    0.0,
            "trend_direction":     _TREND_FLAT,
        },
        "anomalies": {
            "spikes":            [],
            "drops":             [],
            "volatility_events": [],
        },
        "narrative": {
            "headline": (
                f"Pair {pair_id} has insufficient data for deep analysis."
            ),
            "bullets": [
                "Fewer than 2 non-legacy runs include this pair.",
            ],
        },
    }


def pair_deep_analysis(run_ids, pair_id: str) -> dict:
    """Return the deep-analytics payload for a single pair across a
    chronological run sequence.

    Args:
        run_ids: chronologically ordered run identifiers. Caller's
            responsibility — use ``sort_run_ids_by_timestamp`` if
            needed.
        pair_id: target pair identifier. Must exist in at least one
            non-legacy run; otherwise the function returns the locked
            empty-shape response with an explanatory narrative.

    Returns:
        Locked-shape dict — see module docstring for the full schema.

    Raises:
        ValueError on a malformed run_ids list or pair_id.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)
    _validate_pair_id(pair_id)

    summary = multi_run_summary(run_ids)
    pair_summaries = summary["pair_summaries"]
    filtered_ids = summary["run_ids"]

    pair_summary = pair_summaries.get(pair_id)
    if pair_summary is None:
        return _empty_pair_response(pair_id)

    magnitudes = list(pair_summary.get("magnitude_over_time", []))
    directions = list(pair_summary.get("direction_over_time", []))
    severities = list(pair_summary.get("severity_over_time", []))
    stability  = float(pair_summary.get("stability_score", 0.0))
    volatility = float(pair_summary.get("volatility_score", 0.0))
    trend      = pair_summary.get("trend_direction", _TREND_FLAT)

    anomalies = _build_anomaly_inventory(filtered_ids, magnitudes, severities)
    narrative = _build_pair_narrative(
        pair_id, stability, volatility, trend, anomalies,
    )

    return {
        "pair_id": pair_id,
        "trajectory": {
            "direction_over_time": directions,
            "magnitude_over_time": magnitudes,
            "severity_over_time":  severities,
            "stability_score":     stability,
            "volatility_score":    volatility,
            "trend_direction":     trend,
        },
        "anomalies":  anomalies,
        "narrative":  narrative,
    }


def pair_deep_all(run_ids) -> dict:
    """Run ``pair_deep_analysis`` for every pair_id that appears in
    any non-legacy run.

    Args:
        run_ids: chronologically ordered run identifiers.

    Returns:
        ``{"pairs": {pair_id: <pair_deep_analysis output>, ...},
           "run_ids": [<filtered modern ids>]}``.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)
    summary = multi_run_summary(run_ids)
    pair_summaries = summary["pair_summaries"]
    out: dict = {}
    for pid in sorted(pair_summaries.keys()):
        out[pid] = pair_deep_analysis(run_ids, pid)
    return {"pairs": out, "run_ids": list(summary["run_ids"])}
