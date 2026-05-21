"""
elins_release_gate.py — ELINS6 Unit 19.

Release-gate engine. Converts the ELINS intelligence stack into a
binary (allow / warn / block) decision over a chronological run set.

ROLE
----
First "hard decision" module — the one that says "this release is
safe" or "this release is blocked." Pure composition over Units
14 / 17 / 18 — no new heuristics. Same inputs always produce
byte-equal output.

DECISION RULES (locked, deterministic)
---------------------------------------
Block (any of):
    * health_delta < -0.10                        (health drop > 0.10)
    * anomaly_delta > +0.15                       (anomaly spike > 0.15)
    * cluster_shift == "more_downward"
    * trend_shift   == "toward_volatility"
    * any pair stability_delta < -0.20

Warn (no block, any of):
    * health_delta < -0.05                        (health drop > 0.05)
    * anomaly_delta > +0.10                       (anomaly spike > 0.10)
    * any pair volatility event detected
    * any pair stability_score < 0.50

Allow:
    * none of the above fire

The presence of promoted-stable pairs is informational — it does NOT
gate allow on its own (small universes routinely have no pair
qualifying, so making it required would over-block valid releases).

SMALL N
-------
For ``len(run_ids) < 2`` no diff is possible — the decision falls
back to ``"warn"`` with a single reason ``"insufficient_data"``. All
other sub-2 paths in the locked metrics block stay well-formed
(zero / empty defaults).

PUBLIC API
----------
    evaluate_release_gate(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_intel_diff import diff_intelligence
from elins_intelligence import intelligence_for_run_ids
from elins_pair_deep import pair_deep_all
from elins_persistence import _validate_run_id


# Locked decision vocabulary.
_DECISION_ALLOW: str = "allow"
_DECISION_WARN:  str = "warn"
_DECISION_BLOCK: str = "block"

# Block-tier thresholds.
_BLOCK_HEALTH_DROP:        float = 0.10
_BLOCK_ANOMALY_SPIKE:      float = 0.15
_BLOCK_PAIR_STABILITY_DEL: float = 0.20

# Warn-tier thresholds.
_WARN_HEALTH_DROP:    float = 0.05
_WARN_ANOMALY_SPIKE:  float = 0.10
_WARN_LOW_STABILITY: float = 0.50

# Stable-pair promotion criteria (mirror Unit 18).
_STABLE_PAIR_STABILITY_MIN:  float = 0.85
_STABLE_PAIR_VOLATILITY_MAX: float = 0.10
_STABLE_PAIR_TREND_VOCAB:    tuple = ("upward", "flat")

# Reason codes (locked).
_R_INSUFFICIENT_DATA:    str = "insufficient_data"
_R_HEALTH_DROP_BLOCK:    str = "health_drop_block"
_R_HEALTH_DROP_WARN:     str = "health_drop_warn"
_R_ANOMALY_SPIKE_BLOCK:  str = "anomaly_spike_block"
_R_ANOMALY_SPIKE_WARN:   str = "anomaly_spike_warn"
_R_CLUSTER_DOWNWARD:     str = "cluster_shift_downward"
_R_TREND_VOLATILITY:     str = "trend_shift_volatility"
_R_PAIR_REGRESSION:      str = "pair_regression"
_R_VOLATILITY_EVENTS:    str = "volatility_events"
_R_LOW_STABILITY:        str = "low_pair_stability"


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"evaluate_release_gate expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _split_ab(run_ids: list) -> tuple:
    """Symmetric mid-split: A=first half, B=second half. Both halves
    are non-empty for N >= 2."""
    mid = len(run_ids) // 2
    return run_ids[:mid], run_ids[mid:]


def _pair_regressions(diff: dict) -> int:
    """Count pairs whose stability_delta crosses the block threshold."""
    return sum(
        1 for data in diff["pairs"].values()
        if float(data.get("stability_delta", 0.0))
            < -_BLOCK_PAIR_STABILITY_DEL
    )


def _volatility_event_count(pair_deep: dict) -> int:
    """Total Unit 17 volatility events across all pairs."""
    return sum(
        len(data["anomalies"]["volatility_events"])
        for data in pair_deep["pairs"].values()
    )


def _min_pair_stability(pair_deep: dict) -> float:
    """Lowest pair stability score in the deep payload. Returns 1.0
    when no pairs are present so empty input doesn't trip the warn
    threshold."""
    pairs = pair_deep["pairs"]
    if not pairs:
        return 1.0
    return min(
        float(data["trajectory"].get("stability_score", 1.0))
        for data in pairs.values()
    )


def _promoted_pairs(pair_deep: dict) -> list:
    """Apply Unit 18's stable-pair criteria over the deep payload."""
    out: list = []
    for pid, data in pair_deep["pairs"].items():
        traj = data["trajectory"]
        if float(traj.get("stability_score", 0.0)) <= \
                _STABLE_PAIR_STABILITY_MIN:
            continue
        if float(traj.get("volatility_score", 1.0)) >= \
                _STABLE_PAIR_VOLATILITY_MAX:
            continue
        if traj.get("trend_direction", "flat") not in \
                _STABLE_PAIR_TREND_VOCAB:
            continue
        out.append(pid)
    return sorted(out)


def _empty_metrics(intel: dict, run_ids: list) -> dict:
    return {
        "health":           float(
            intel.get("scores", {}).get("overall_health", 0.0)
        ),
        "anomaly_fraction": float(
            intel.get("sequences", {})
                 .get("analysis", {})
                 .get("anomaly_fraction", 0.0)
        ),
        "trend_shift":      "neutral",
        "cluster_shift":    "neutral",
        "regressions":      0,
        "promoted_pairs":   [],
    }


def evaluate_release_gate(run_ids) -> dict:
    """Evaluate the release-gate decision for `run_ids`.

    Args:
        run_ids: chronologically ordered run identifiers.

    Returns:
        Locked-shape dict::

            {
              "decision": "allow | warn | block",
              "reasons":  list[str]   # locked reason codes, alpha-sorted
              "metrics": {
                "health":           float,
                "anomaly_fraction": float,
                "trend_shift":      <Unit 14 vocabulary>,
                "cluster_shift":    <Unit 14 vocabulary>,
                "regressions":      int,
                "promoted_pairs":   list[str],
              },
            }

        Sub-2 inputs fall back to ``decision="warn"`` with reason
        ``"insufficient_data"``. The metrics block always carries
        every locked key.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)

    intel = intelligence_for_run_ids(run_ids)

    if len(run_ids) < 2:
        return {
            "decision": _DECISION_WARN,
            "reasons":  [_R_INSUFFICIENT_DATA],
            "metrics":  _empty_metrics(intel, run_ids),
        }

    a_ids, b_ids = _split_ab(run_ids)
    diff = diff_intelligence(a_ids, b_ids)
    pair_deep = pair_deep_all(run_ids)

    health_delta  = float(diff["summary"]["health_delta"])
    anomaly_delta = float(diff["summary"]["anomaly_delta"])
    trend_shift   = diff["summary"]["trend_shift"]
    cluster_shift = diff["summary"]["cluster_shift"]
    regressions   = _pair_regressions(diff)
    volatility_events = _volatility_event_count(pair_deep)
    min_stability = _min_pair_stability(pair_deep)
    promoted      = _promoted_pairs(pair_deep)

    block_reasons: list = []
    if health_delta < -_BLOCK_HEALTH_DROP:
        block_reasons.append(_R_HEALTH_DROP_BLOCK)
    if anomaly_delta > _BLOCK_ANOMALY_SPIKE:
        block_reasons.append(_R_ANOMALY_SPIKE_BLOCK)
    if cluster_shift == "more_downward":
        block_reasons.append(_R_CLUSTER_DOWNWARD)
    if trend_shift == "toward_volatility":
        block_reasons.append(_R_TREND_VOLATILITY)
    if regressions > 0:
        block_reasons.append(_R_PAIR_REGRESSION)

    warn_reasons: list = []
    if health_delta < -_WARN_HEALTH_DROP:
        warn_reasons.append(_R_HEALTH_DROP_WARN)
    if anomaly_delta > _WARN_ANOMALY_SPIKE:
        warn_reasons.append(_R_ANOMALY_SPIKE_WARN)
    if volatility_events > 0:
        warn_reasons.append(_R_VOLATILITY_EVENTS)
    if min_stability < _WARN_LOW_STABILITY:
        warn_reasons.append(_R_LOW_STABILITY)

    if block_reasons:
        decision = _DECISION_BLOCK
        reasons  = sorted(set(block_reasons))
    elif warn_reasons:
        decision = _DECISION_WARN
        reasons  = sorted(set(warn_reasons))
    else:
        decision = _DECISION_ALLOW
        reasons  = []

    metrics = {
        "health":           float(intel["scores"]["overall_health"]),
        "anomaly_fraction": float(
            intel["sequences"]["analysis"]["anomaly_fraction"]
        ),
        "trend_shift":      trend_shift,
        "cluster_shift":    cluster_shift,
        "regressions":      regressions,
        "promoted_pairs":   promoted,
    }
    return {
        "decision": decision,
        "reasons":  reasons,
        "metrics":  metrics,
    }
