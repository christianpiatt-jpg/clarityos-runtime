"""
elins_alerts.py — ELINS4 Unit 16.

Operator alerts engine. Compares the first half of a run sequence
("before") against the second half ("after") through the Unit 14 diff
and surfaces actionable alerts.

ROLE
----
First step toward automated operator workflows. Pure composition over
Units 5 / 14 — no new heuristics, every signal sourced from an earlier
unit. Same inputs always produce byte-equal output.

SPLIT
-----
For an input of N runs (chronological), we compare ``A = run_ids[:mid]``
against ``B = run_ids[mid:]`` where ``mid = N // 2``. For N >= 2 this
always gives at least 1 run on each side. For N < 2 no comparison
alerts fire.

ALERT TYPES
-----------
    anomaly_spike       — anomaly_fraction jumps by more than 0.15
    health_drop         — overall_health drops by more than 0.10
    volatility_surge    — trend_shift is "toward_volatility"
    cluster_inversion   — upward→downward or downward→upward
    pair_regression     — any pair's stability drops by more than 0.20
    legacy_contamination — at least one legacy run appears in the input

SEVERITY MAPPING
----------------
Within each numeric alert type, large deltas escalate to ``critical``;
moderate deltas stay at ``warning``; the small-delta tier is not
emitted (we'd just be reporting noise). Categorical alerts
(``volatility_surge``, ``cluster_inversion``) carry a fixed severity.

DEDUPLICATION
-------------
Alerts are deduped by ``(type, target)``: at most one
``anomaly_spike`` / ``health_drop`` / etc. per call, and at most one
``pair_regression`` per pair_id.

PUBLIC API
----------
    generate_alerts(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_intel_diff import diff_intelligence
from elins_persistence import _validate_run_id, load_comparison_result


# Locked alert-type vocabulary.
_TYPE_ANOMALY_SPIKE:        str = "anomaly_spike"
_TYPE_HEALTH_DROP:          str = "health_drop"
_TYPE_VOLATILITY_SURGE:     str = "volatility_surge"
_TYPE_CLUSTER_INVERSION:    str = "cluster_inversion"
_TYPE_PAIR_REGRESSION:      str = "pair_regression"
_TYPE_LEGACY_CONTAMINATION: str = "legacy_contamination"

# Severity vocabulary (locked).
_SEV_INFO:     str = "info"
_SEV_WARNING:  str = "warning"
_SEV_CRITICAL: str = "critical"

# Numeric thresholds (locked).
_ANOMALY_SPIKE_THRESHOLD: float = 0.15
_HEALTH_DROP_THRESHOLD:   float = 0.10
_PAIR_REGRESS_THRESHOLD:  float = 0.20

# Critical-tier multipliers — when the delta exceeds the base
# threshold by 2x or more, escalate from warning to critical.
_CRITICAL_MULTIPLIER: float = 2.0

# Cluster-inversion vocabulary (mirror Unit 14).
_CLUSTER_SHIFT_MORE_UPWARD:   str = "more_upward"
_CLUSTER_SHIFT_MORE_DOWNWARD: str = "more_downward"


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"generate_alerts expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _classify_numeric_severity(delta_abs: float,
                                threshold: float) -> str:
    """Numeric alerts: above threshold → warning; above threshold *
    critical-multiplier → critical."""
    if delta_abs >= threshold * _CRITICAL_MULTIPLIER:
        return _SEV_CRITICAL
    return _SEV_WARNING


def _detect_legacy_runs(run_ids: list) -> list:
    """Return run_ids whose envelope is in the Unit 10 legacy format
    (metadata=None). Pure I/O — one load per id."""
    out: list = []
    for rid in run_ids:
        env = load_comparison_result(rid)
        meta = env.get("metadata") if isinstance(env, dict) else None
        if not isinstance(meta, dict):
            out.append(rid)
    return out


def _anomaly_spike_alert(diff: dict, all_ids: list) -> dict | None:
    """Anomaly_fraction jumped above the locked threshold → alert."""
    delta = float(diff["summary"]["anomaly_delta"])
    if delta <= _ANOMALY_SPIKE_THRESHOLD:
        return None
    severity = _classify_numeric_severity(delta, _ANOMALY_SPIKE_THRESHOLD)
    return {
        "type":     _TYPE_ANOMALY_SPIKE,
        "severity": severity,
        "delta":    delta,
        "message":  f"Anomaly fraction rose by {delta:+.2f}.",
        "run_ids":  list(all_ids),
    }


def _health_drop_alert(diff: dict, all_ids: list) -> dict | None:
    """Overall health dropped by more than the locked threshold."""
    delta = float(diff["summary"]["health_delta"])
    if delta >= -_HEALTH_DROP_THRESHOLD:
        return None
    severity = _classify_numeric_severity(abs(delta), _HEALTH_DROP_THRESHOLD)
    return {
        "type":     _TYPE_HEALTH_DROP,
        "severity": severity,
        "delta":    delta,
        "message":  f"Overall health dropped by {delta:+.2f}.",
        "run_ids":  list(all_ids),
    }


def _volatility_surge_alert(diff: dict, all_ids: list) -> dict | None:
    if diff["summary"]["trend_shift"] != "toward_volatility":
        return None
    return {
        "type":     _TYPE_VOLATILITY_SURGE,
        "severity": _SEV_WARNING,
        "message":  "Trend shifted from stable to volatile between periods.",
        "run_ids":  list(all_ids),
    }


def _cluster_inversion_alert(diff: dict, all_ids: list) -> dict | None:
    shift = diff["summary"]["cluster_shift"]
    if shift not in (_CLUSTER_SHIFT_MORE_UPWARD,
                     _CLUSTER_SHIFT_MORE_DOWNWARD):
        return None
    direction = (
        "downward to upward"
        if shift == _CLUSTER_SHIFT_MORE_UPWARD
        else "upward to downward"
    )
    # Inverting from downward → upward is informational (good news);
    # the inverse (upward → downward) is a warning.
    severity = (
        _SEV_INFO if shift == _CLUSTER_SHIFT_MORE_UPWARD
        else _SEV_WARNING
    )
    return {
        "type":     _TYPE_CLUSTER_INVERSION,
        "severity": severity,
        "shift":    shift,
        "message":  f"Cluster mix inverted from {direction}.",
        "run_ids":  list(all_ids),
    }


def _pair_regression_alerts(diff: dict) -> list:
    """One alert per pair whose stability dropped below the locked
    threshold. Sorted by stability_delta ascending (worst first); ties
    broken alphabetically by pair_id."""
    alerts: list = []
    for pid, data in diff["pairs"].items():
        delta = float(data.get("stability_delta", 0.0))
        if delta >= -_PAIR_REGRESS_THRESHOLD:
            continue
        severity = _classify_numeric_severity(
            abs(delta), _PAIR_REGRESS_THRESHOLD,
        )
        alerts.append({
            "type":     _TYPE_PAIR_REGRESSION,
            "severity": severity,
            "pair_id":  pid,
            "delta":    delta,
            "message":  f"Pair {pid} stability dropped by {delta:+.2f}.",
        })
    alerts.sort(key=lambda a: (a["delta"], a["pair_id"]))
    return alerts


def _legacy_contamination_alert(legacy_ids: list) -> dict | None:
    if not legacy_ids:
        return None
    return {
        "type":     _TYPE_LEGACY_CONTAMINATION,
        "severity": _SEV_WARNING,
        "message":  (
            f"Legacy run(s) detected in the sequence: "
            f"{', '.join(sorted(legacy_ids))}."
        ),
        "run_ids":  sorted(legacy_ids),
    }


def _empty_result() -> dict:
    return {"alerts": []}


def _alert_sort_key(alert: dict) -> tuple:
    """Stable ordering: by type, then severity (critical < warning <
    info), then alphabetically by message."""
    type_order = {
        _TYPE_HEALTH_DROP:          0,
        _TYPE_ANOMALY_SPIKE:        1,
        _TYPE_VOLATILITY_SURGE:     2,
        _TYPE_CLUSTER_INVERSION:    3,
        _TYPE_PAIR_REGRESSION:      4,
        _TYPE_LEGACY_CONTAMINATION: 5,
    }
    sev_order = {_SEV_CRITICAL: 0, _SEV_WARNING: 1, _SEV_INFO: 2}
    return (
        type_order.get(alert.get("type", ""), 99),
        sev_order.get(alert.get("severity", ""), 99),
        alert.get("pair_id", ""),
        alert.get("message", ""),
    )


def generate_alerts(run_ids) -> dict:
    """Produce a deduped, severity-sorted alert list for `run_ids`.

    Args:
        run_ids: chronologically-ordered list of run identifiers.

    Returns:
        ``{"alerts": [<alert dict>, ...]}``. The alert dicts share a
        locked top-level shape::

            {
              "type":     <one of the locked types>,
              "severity": "info | warning | critical",
              "message":  str,
              "run_ids":  list[str]  # (most types; pair_regression
                                     #  carries pair_id+delta instead)
            }

        Pair-regression alerts add ``pair_id`` and ``delta``;
        anomaly-spike / health-drop / cluster-inversion also surface
        their numeric delta or shift label.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)
    if not run_ids:
        return _empty_result()

    legacy_ids = _detect_legacy_runs(run_ids)

    alerts: list = []

    if len(run_ids) >= 2:
        mid = len(run_ids) // 2
        a_ids = run_ids[:mid]
        b_ids = run_ids[mid:]
        diff = diff_intelligence(a_ids, b_ids)

        for fn in (
            _anomaly_spike_alert,
            _health_drop_alert,
            _volatility_surge_alert,
            _cluster_inversion_alert,
        ):
            alert = fn(diff, run_ids)
            if alert is not None:
                alerts.append(alert)
        alerts.extend(_pair_regression_alerts(diff))

    legacy = _legacy_contamination_alert(legacy_ids)
    if legacy is not None:
        alerts.append(legacy)

    # Dedupe by (type, target) — last alert for a given key wins. For
    # most types target = type itself; for pair_regression target =
    # (type, pair_id).
    seen: dict = {}
    for a in alerts:
        key = (a["type"], a.get("pair_id", ""))
        seen[key] = a
    deduped = list(seen.values())
    deduped.sort(key=_alert_sort_key)
    return {"alerts": deduped}
