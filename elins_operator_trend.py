"""
elins_operator_trend.py — ELINS9 Unit 26.

Operator-facing workflows on top of Unit 25's temporal trend engine.
Three helpers that turn trend analysis into action (verdict tags) or
distribution (structured trend report).

ROLE
----
Operator workflow surface for cross-batch temporal intelligence. Pure
composition over Units 21 + 25 + their data lineage. Tags are
conceptual (applied to TIMELINE labels, not run_ids) — the temporal
operation reasons over per-time-step aggregates.

DECISION RULES (locked, deterministic)
--------------------------------------
* health direction == "down" → "warn"
* anomaly direction == "up"  → "warn"
* regressions direction == "up" → "warn"
* otherwise, all directions in {"flat", improving} → "allow"

Tags emitted track the per-metric direction:

    "trend_health_up"        health direction up
    "trend_health_down"      health direction down
    "trend_anomaly_up"       anomaly direction up
    "trend_anomaly_down"     anomaly direction down
    "trend_regressions_up"   regressions direction up
    "trend_regressions_down" regressions direction down
    "trend_flat"             all three directions flat

PUBLIC API
----------
    apply_trend_analysis(timeline) -> dict
    tag_trend_decisions(timeline, decisions) -> dict
    generate_trend_report(timeline) -> dict
"""
from __future__ import annotations

from elins_trend import analyze_trends


# Locked tag vocabulary.
TAG_TREND_HEALTH_UP:        str = "trend_health_up"
TAG_TREND_HEALTH_DOWN:      str = "trend_health_down"
TAG_TREND_ANOMALY_UP:       str = "trend_anomaly_up"
TAG_TREND_ANOMALY_DOWN:     str = "trend_anomaly_down"
TAG_TREND_REGRESSIONS_UP:   str = "trend_regressions_up"
TAG_TREND_REGRESSIONS_DOWN: str = "trend_regressions_down"
TAG_TREND_FLAT:             str = "trend_flat"

_DECISION_ALLOW: str = "allow"
_DECISION_WARN:  str = "warn"
_DECISION_BLOCK: str = "block"

_VALID_DECISIONS: tuple = (_DECISION_ALLOW, _DECISION_WARN, _DECISION_BLOCK)


def _validate_timeline_shape(timeline, fn_name: str) -> None:
    """Cheap structural pre-validation. Full schema checks happen inside
    Unit 25's analyze_trends."""
    if not isinstance(timeline, list):
        raise ValueError(
            f"{fn_name} expected timeline to be a list, "
            f"got {type(timeline).__name__}"
        )


def _validate_decision(decision, label: str) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"{label} must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _tags_from_directions(trend_vectors: dict) -> list:
    """Map per-metric directions to the locked tag vocabulary."""
    h_dir = trend_vectors.get("health",      {}).get("direction", "flat")
    a_dir = trend_vectors.get("anomaly",     {}).get("direction", "flat")
    r_dir = trend_vectors.get("regressions", {}).get("direction", "flat")
    tags: list = []
    if h_dir == "up":
        tags.append(TAG_TREND_HEALTH_UP)
    elif h_dir == "down":
        tags.append(TAG_TREND_HEALTH_DOWN)
    if a_dir == "up":
        tags.append(TAG_TREND_ANOMALY_UP)
    elif a_dir == "down":
        tags.append(TAG_TREND_ANOMALY_DOWN)
    if r_dir == "up":
        tags.append(TAG_TREND_REGRESSIONS_UP)
    elif r_dir == "down":
        tags.append(TAG_TREND_REGRESSIONS_DOWN)
    if h_dir == "flat" and a_dir == "flat" and r_dir == "flat":
        tags.append(TAG_TREND_FLAT)
    return sorted(tags)


def _decision_from_directions(trend_vectors: dict) -> str:
    """Apply the locked decision rules: any down-health, up-anomaly, or
    up-regressions trend → warn. Otherwise allow."""
    h_dir = trend_vectors.get("health",      {}).get("direction", "flat")
    a_dir = trend_vectors.get("anomaly",     {}).get("direction", "flat")
    r_dir = trend_vectors.get("regressions", {}).get("direction", "flat")
    if h_dir == "down" or a_dir == "up" or r_dir == "up":
        return _DECISION_WARN
    return _DECISION_ALLOW


def apply_trend_analysis(timeline) -> dict:
    """Evaluate Unit 25 and emit decision + tags + trend_vectors.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples.

    Returns:
        ``{
            "decision":      "allow | warn | block",
            "tags":          list[str],   # alpha-sorted
            "trend_vectors": <Unit 25 trend_vectors section>,
        }``.

    Raises:
        ValueError on a malformed timeline (forwarded from Unit 25).
    """
    _validate_timeline_shape(timeline, "apply_trend_analysis")
    trend = analyze_trends(timeline)
    decision = _decision_from_directions(trend["trend_vectors"])
    tags     = _tags_from_directions(trend["trend_vectors"])
    return {
        "decision":      decision,
        "tags":          tags,
        "trend_vectors": trend["trend_vectors"],
    }


def tag_trend_decisions(timeline, decisions) -> dict:
    """Apply caller-supplied trend decisions as tags.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples — kept for symmetry with the other operator helpers
            and for caller-supplied validation.
        decisions: ``dict[str, str]`` mapping timestamp → decision in
            ``{"allow", "warn", "block"}``. Every timestamp from the
            timeline must appear; extra keys raise.

    Returns:
        ``{
            "applied": True,
            "tags": {
                "<timestamp>": [<tag>],
                ...
            },
        }``.

    Raises:
        ValueError on a malformed timeline or decisions mapping.
    """
    _validate_timeline_shape(timeline, "tag_trend_decisions")
    # Surface Unit 25's full validation by running through analyze_trends
    # — cheap and ensures decisions are keyed against a known timeline
    # shape.
    trend = analyze_trends(timeline)

    if not isinstance(decisions, dict):
        raise ValueError(
            f"tag_trend_decisions expected decisions to be a dict, "
            f"got {type(decisions).__name__}"
        )
    timestamps = [entry["timestamp"] for entry in trend["timeline"]]
    if set(decisions.keys()) != set(timestamps):
        raise ValueError(
            "decisions must map exactly the same timestamps as the "
            f"timeline; got timeline={sorted(timestamps)}, "
            f"decisions={sorted(decisions.keys())}"
        )
    for ts, dec in decisions.items():
        _validate_decision(dec, f"decisions[{ts!r}]")

    decision_tag_map = {
        _DECISION_ALLOW: TAG_TREND_FLAT,
        _DECISION_WARN:  TAG_TREND_HEALTH_DOWN,
        _DECISION_BLOCK: TAG_TREND_HEALTH_DOWN,
    }
    tags_by_ts: dict = {}
    for ts in sorted(timestamps):
        tags_by_ts[ts] = [decision_tag_map[decisions[ts]]]
    return {"applied": True, "tags": tags_by_ts}


def _empty_report() -> dict:
    return {
        "headline":      "No batches supplied for trend analysis.",
        "trend_vectors": {
            "health":      {"slope": 0.0, "direction": "flat"},
            "anomaly":     {"slope": 0.0, "direction": "flat"},
            "regressions": {"slope": 0.0, "direction": "flat"},
        },
        "events":   ["insufficient_data"],
        "timeline": [],
        "alerts":   {},
        "pairs":    {},
        "diffs":    {},
    }


def _alerts_for_batch(batch_payload: dict) -> list:
    """Per-batch alert aggregation (mirror Unit 24's pattern)."""
    alerts: list = []
    groups = batch_payload.get("groups", {}) or {}
    for group_name in sorted(groups.keys()):
        data = groups[group_name]
        decision = data.get("decision", "warn")
        if decision == "block":
            alerts.append({
                "type":     "blocked_group",
                "severity": "critical",
                "group":    group_name,
                "reasons":  list(data.get("reasons", [])),
            })
        elif decision == "warn":
            alerts.append({
                "type":     "warned_group",
                "severity": "warning",
                "group":    group_name,
                "reasons":  list(data.get("reasons", [])),
            })
    return alerts


def _pairs_for_batch(batch_payload: dict) -> list:
    seen: set = set()
    comparisons = batch_payload.get("comparisons", {}) or {}
    for entry in comparisons.values():
        for pid in entry.get("pair_regressions", []) or []:
            seen.add(pid)
    return sorted(seen)


def _diffs_for_batch(batch_payload: dict) -> dict:
    """Surface the within-batch comparisons under a diffs alias so
    callers get a consistent place to find per-pair deltas."""
    return dict(batch_payload.get("comparisons", {}) or {})


def _headline_for_trend(trend: dict, n_batches: int) -> str:
    """Compose a short one-liner from the Unit 25 output."""
    if n_batches < 2:
        return "Insufficient data to derive a trend."
    vectors = trend["trend_vectors"]
    h_dir = vectors["health"]["direction"]
    a_dir = vectors["anomaly"]["direction"]
    r_dir = vectors["regressions"]["direction"]
    if (h_dir, a_dir, r_dir) == ("flat", "flat", "flat"):
        return (
            f"Stable trend across {n_batches} batches "
            f"(flat health, flat anomalies)."
        )
    if h_dir == "down":
        return (
            f"Health deteriorating over {n_batches} batches "
            f"(anomaly slope {vectors['anomaly']['slope']:+.2f}; "
            f"regressions slope "
            f"{vectors['regressions']['slope']:+.2f})."
        )
    if h_dir == "up":
        return (
            f"Health improving over {n_batches} batches "
            f"(anomaly slope {vectors['anomaly']['slope']:+.2f}; "
            f"regressions slope "
            f"{vectors['regressions']['slope']:+.2f})."
        )
    # Health flat but anomalies / regressions moving.
    return (
        f"Mixed trend across {n_batches} batches "
        f"(health flat, anomalies {a_dir}, regressions {r_dir})."
    )


def generate_trend_report(timeline) -> dict:
    """Bundle Units 21 + 25 (with per-timestamp alert / pair / diff
    aggregates) into a locked-shape report.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples.

    Returns:
        Locked-shape dict::

            {
              "headline":      str,
              "trend_vectors": <Unit 25 trend_vectors>,
              "events":        <Unit 25 events>,
              "timeline":      <Unit 25 timeline>,
              "alerts":        {timestamp: [<alert dict>, ...]},
              "pairs":         {timestamp: [<pair_id>, ...]},
              "diffs":         {timestamp: {<within-batch comparisons>}},
            }

        Empty input returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed timeline.
    """
    _validate_timeline_shape(timeline, "generate_trend_report")
    if not timeline:
        return _empty_report()

    trend = analyze_trends(timeline)

    # Normalise entries — the analyze_trends call already validated
    # shape, so we trust it.
    normalised = [(entry[0], entry[1]) for entry in timeline]

    alerts_by_ts: dict = {}
    pairs_by_ts:  dict = {}
    diffs_by_ts:  dict = {}
    for ts, payload in normalised:
        alerts_by_ts[ts] = _alerts_for_batch(payload)
        pairs_by_ts[ts]  = _pairs_for_batch(payload)
        diffs_by_ts[ts]  = _diffs_for_batch(payload)

    headline = _headline_for_trend(trend, len(normalised))

    return {
        "headline":      headline,
        "trend_vectors": trend["trend_vectors"],
        "events":        trend["events"],
        "timeline":      trend["timeline"],
        "alerts":        alerts_by_ts,
        "pairs":         pairs_by_ts,
        "diffs":         diffs_by_ts,
    }
