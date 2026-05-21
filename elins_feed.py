"""
elins_feed.py — ELINS4 Unit 15.

Rolling intelligence feed. Newsfeed-style projection over the most
recent N runs, with severity + tags + a short headline derived
deterministically from the per-run signals.

ROLE
----
Operator-facing feed surface. Pure composition over Units 2 / 3 / 5
/ 6 / 13 — every signal is sourced from an earlier unit. Entries are
ordered newest-first; analytics run over the chronological reversal
internally so prefix trend / cluster math see the right ordering.

PUBLIC API
----------
    build_intelligence_feed(limit: int = 50) -> dict
    feed_entry_for_run(run_id: str) -> dict
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, query_runs
from elins_timeline import build_intelligence_timeline


# Default page size.
DEFAULT_LIMIT: int = 50

# Severity vocabulary (locked).
_SEV_INFO:     str = "info"
_SEV_WARNING:  str = "warning"
_SEV_CRITICAL: str = "critical"

# Anomaly level vocabulary (mirror Unit 5).
_LEVEL_HIGH:   str = "high"
_LEVEL_MEDIUM: str = "medium"
_LEVEL_NONE:   str = "none"

# Cluster labels (mirror Unit 2).
_CLUSTER_STABLE:   str = "stable"
_CLUSTER_UPWARD:   str = "upward drift"
_CLUSTER_DOWNWARD: str = "downward drift"
_CLUSTER_OSCILLN:  str = "oscillation"
_CLUSTER_ANOMALY:  str = "anomaly"

# Tag vocabulary (locked).
_TAG_ANOMALY:          str = "anomaly"
_TAG_UPWARD_CLUSTER:   str = "upward_cluster"
_TAG_DOWNWARD_CLUSTER: str = "downward_cluster"
_TAG_STABLE_CLUSTER:   str = "stable_cluster"
_TAG_OSCILLATION:      str = "oscillation"
_TAG_LEGACY:           str = "legacy"


def _validate_limit(limit) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError(
            f"limit must be a positive int, got {type(limit).__name__}"
        )
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    return limit


def _severity_for_entry(anomaly_level: str, cluster_label: str) -> str:
    """Pick a severity based on the per-run signals. High anomaly is
    always ``critical``; medium is ``warning``; otherwise ``info``.
    Cluster label only affects the headline + tags."""
    if anomaly_level == _LEVEL_HIGH:
        return _SEV_CRITICAL
    if anomaly_level == _LEVEL_MEDIUM:
        return _SEV_WARNING
    return _SEV_INFO


def _tags_for_entry(anomaly_level: str,
                    cluster_label: str,
                    is_legacy: bool) -> list:
    """Deterministic alphabetic-sorted tag list. ``anomaly`` fires on
    any non-none level; cluster tag follows the label vocabulary;
    legacy runs get their own marker so feed renderers can show a
    different icon."""
    tags: list = []
    if anomaly_level != _LEVEL_NONE:
        tags.append(_TAG_ANOMALY)
    if cluster_label == _CLUSTER_UPWARD:
        tags.append(_TAG_UPWARD_CLUSTER)
    elif cluster_label == _CLUSTER_DOWNWARD:
        tags.append(_TAG_DOWNWARD_CLUSTER)
    elif cluster_label == _CLUSTER_STABLE:
        tags.append(_TAG_STABLE_CLUSTER)
    elif cluster_label == _CLUSTER_OSCILLN:
        tags.append(_TAG_OSCILLATION)
    if is_legacy:
        tags.append(_TAG_LEGACY)
    tags.sort()
    return tags


def _headline_for_entry(rid: str,
                        anomaly_level: str,
                        cluster_label: str,
                        trend: str,
                        is_legacy: bool) -> str:
    """Short deterministic 1-sentence headline for the feed row.

    The headline biases toward the strongest signal: anomaly first,
    then cluster + trend, with a generic fallback for legacy / clean
    runs."""
    if is_legacy:
        return f"Run {rid}: legacy run — intelligence signals unavailable."
    if anomaly_level == _LEVEL_HIGH:
        return f"Run {rid}: critical anomaly detected."
    if anomaly_level == _LEVEL_MEDIUM:
        return f"Run {rid}: anomaly flagged."
    if cluster_label == _CLUSTER_UPWARD:
        if trend == "monotonic_increase":
            return f"Run {rid}: upward drift continues."
        return f"Run {rid}: in upward-drift cluster."
    if cluster_label == _CLUSTER_DOWNWARD:
        if trend == "monotonic_decrease":
            return f"Run {rid}: downward drift continues."
        return f"Run {rid}: in downward-drift cluster."
    if cluster_label == _CLUSTER_OSCILLN:
        return f"Run {rid}: oscillating sequence."
    if cluster_label == _CLUSTER_STABLE:
        if trend == "plateau":
            return f"Run {rid}: stable plateau."
        return f"Run {rid}: stable cluster."
    return f"Run {rid}: no significant signal."


def _entry_from_timeline(timeline_entry: dict) -> dict:
    rid = timeline_entry["run_id"]
    anomaly_level = timeline_entry["anomaly_level"]
    cluster_label = timeline_entry["cluster_label"]
    trend = timeline_entry["trend"]
    is_legacy = timeline_entry["is_legacy"]
    return {
        "run_id":    rid,
        "timestamp": timeline_entry["timestamp"],
        "headline":  _headline_for_entry(
            rid, anomaly_level, cluster_label, trend, is_legacy,
        ),
        "severity":  _severity_for_entry(anomaly_level, cluster_label),
        "tags":      _tags_for_entry(
            anomaly_level, cluster_label, is_legacy,
        ),
        "details": {
            "health":        timeline_entry["health"],
            "anomaly_level": anomaly_level,
            "cluster_label": cluster_label,
            "trend":         trend,
        },
    }


def build_intelligence_feed(limit: int = DEFAULT_LIMIT) -> dict:
    """Build the rolling intelligence feed over the most recent runs.

    Args:
        limit: max number of entries to surface (>= 1). Default 50.

    Returns:
        Locked-shape dict::

            {
              "entries": [
                {
                  "run_id":    str,
                  "timestamp": str | None,
                  "headline":  str,
                  "severity":  "info | warning | critical",
                  "tags":      list[str],
                  "details": {
                    "health":        float,
                    "anomaly_level": "none | medium | high",
                    "cluster_label": <Unit 2 label>,
                    "trend":         <Unit 3 class>,
                  },
                },
                ...
              ],
              "meta": {"limit": int, "count": int},
            }

        Entries are ordered newest-first by ``metadata.created_at``;
        legacy runs (no timestamp) fall to the end of the feed.

    Raises:
        ValueError if `limit` is invalid.
    """
    limit = _validate_limit(limit)

    # Fetch the newest `limit` runs in descending timestamp order;
    # legacy runs sort to the end inside query_runs.
    rows = query_runs(
        sort="created_at", order="desc", limit=limit,
    )
    newest_first_ids = [row["run_id"] for row in rows]
    # The timeline engine wants chronological order so prefix trend /
    # cluster math see the right sequence.
    chronological_ids = list(reversed(newest_first_ids))

    if not chronological_ids:
        return {
            "entries": [],
            "meta":    {"limit": limit, "count": 0},
        }

    timeline = build_intelligence_timeline(chronological_ids)
    by_run_id = {e["run_id"]: e for e in timeline["timeline"]}

    entries: list = [
        _entry_from_timeline(by_run_id[rid])
        for rid in newest_first_ids
        if rid in by_run_id
    ]
    return {
        "entries": entries,
        "meta":    {"limit": limit, "count": len(entries)},
    }


def feed_entry_for_run(run_id) -> dict:
    """Return the single-run feed entry for `run_id`.

    Equivalent to looking up the run in
    ``build_intelligence_feed(limit=...)["entries"]``, but works
    directly on one id (no DB scan).

    Args:
        run_id: validated run identifier.

    Returns:
        Locked-shape entry — same keys as the elements of
        ``build_intelligence_feed(...)["entries"]``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    timeline = build_intelligence_timeline([run_id])
    return _entry_from_timeline(timeline["timeline"][0])
