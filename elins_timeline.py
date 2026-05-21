"""
elins_timeline.py — ELINS3 Unit 13.

Intelligence timeline engine. Per-run intelligence snapshot built by
composing Units 2 / 3 / 5 / 6 / 7 into a chronological list, with an
aggregate summary block.

ROLE
----
Operator-facing timeline view. Each entry is one run, decorated with
the signals an operator wants to scan vertically: timestamp, cluster
membership, anomaly level, per-run health score, prefix trend class,
and a short deterministic narrative line. No new heuristics — every
signal is sourced from an earlier unit.

ORDERING
--------
Caller is responsible for supplying chronological run_ids (use
``elins_run_ordering.sort_run_ids_by_timestamp`` if needed). The
timeline list preserves input order. Legacy runs (metadata=None) are
included but flagged via ``is_legacy=True``; their timestamp is
``None`` and their narrative says so.

PUBLIC API
----------
    build_intelligence_timeline(run_ids: list[str]) -> dict
    timeline_for_run(run_id: str) -> dict
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_clustering import cluster_runs
from elins_narratives import _VALID_CLUSTER_LABELS
from elins_persistence import _validate_run_id, load_comparison_result
from elins_scoring import compute_run_scores
from elins_trends import trend_for_run_sequence


# Locked vocabulary.
_TREND_INSUFFICIENT_DATA: str = "insufficient_data"
_LEVEL_NONE:              str = "none"
_LEVEL_MEDIUM:            str = "medium"
_LEVEL_HIGH:              str = "high"

# Health tone thresholds (mirror Unit 7).
_HEALTH_HIGH:   float = 0.7
_HEALTH_MEDIUM: float = 0.4


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"build_intelligence_timeline expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _health_band(health: float) -> str:
    if health >= _HEALTH_HIGH:
        return "high"
    if health >= _HEALTH_MEDIUM:
        return "medium"
    return "low"


def _extract_timestamp(envelope: dict):
    """Return ISO timestamp string for an envelope, or ``None`` for
    legacy runs (Unit 10 format with metadata=None)."""
    if not isinstance(envelope, dict):
        return None
    meta = envelope.get("metadata")
    if not isinstance(meta, dict):
        return None
    ts = meta.get("created_at")
    return ts if isinstance(ts, str) else None


def _per_run_narrative(rid: str,
                       health: float,
                       anomaly_level: str,
                       cluster_label: str,
                       is_legacy: bool) -> str:
    """Build a short 1-2 sentence narrative for a single run.

    Pure string template — no LLM, no randomness. Length stays under
    ~160 characters so operators can scan a dense timeline."""
    if is_legacy:
        return (
            f"Run {rid} is legacy (pre-metadata) — "
            f"intelligence signals are not available."
        )
    band = _health_band(health)
    if anomaly_level == _LEVEL_NONE:
        return (
            f"Run {rid} reports {band} health ({health:.2f}); "
            f"cluster label {cluster_label!r}, no anomaly."
        )
    return (
        f"Run {rid} reports {band} health ({health:.2f}); "
        f"cluster label {cluster_label!r}; "
        f"flagged as {anomaly_level} anomaly."
    )


def _prefix_trend(run_ids: list, idx: int) -> str:
    """Trend class for the chronological prefix ending at `idx`
    (inclusive). For the first two runs Unit 3 reports
    ``insufficient_data`` — that's the expected reading early in the
    timeline."""
    if idx < 2:
        return _TREND_INSUFFICIENT_DATA
    prefix = run_ids[: idx + 1]
    return trend_for_run_sequence(prefix)["trend"]


def _dominant_value(counter: dict, default: str) -> str:
    """Return the key with the highest count. Ties broken
    alphabetically by key (deterministic)."""
    if not counter:
        return default
    return max(counter.keys(), key=lambda k: (counter[k], -ord(k[0]) if k else 0))


def _summary_for_timeline(entries: list) -> dict:
    """Aggregate the per-run entries into a single summary block."""
    num_runs = len(entries)
    num_anomalies = sum(
        1 for e in entries
        if e["anomaly_level"] in (_LEVEL_MEDIUM, _LEVEL_HIGH)
    )
    trend_counter: dict = {}
    cluster_label_counter: dict = {}
    for e in entries:
        t = e.get("trend", _TREND_INSUFFICIENT_DATA)
        if t and t != _TREND_INSUFFICIENT_DATA:
            trend_counter[t] = trend_counter.get(t, 0) + 1
        cl = e.get("cluster_label", "")
        if cl in _VALID_CLUSTER_LABELS:
            cluster_label_counter[cl] = (
                cluster_label_counter.get(cl, 0) + 1
            )
    dominant_trend = _dominant_value(
        trend_counter, _TREND_INSUFFICIENT_DATA,
    )
    dominant_cluster = _dominant_value(
        cluster_label_counter, "anomaly",
    )
    return {
        "num_runs":         num_runs,
        "num_anomalies":    num_anomalies,
        "dominant_trend":   dominant_trend,
        "dominant_cluster": dominant_cluster,
    }


def _empty_timeline() -> dict:
    return {
        "timeline": [],
        "summary": {
            "num_runs":         0,
            "num_anomalies":    0,
            "dominant_trend":   _TREND_INSUFFICIENT_DATA,
            "dominant_cluster": "anomaly",
        },
    }


def build_intelligence_timeline(run_ids) -> dict:
    """Build the per-run intelligence timeline across `run_ids`.

    Args:
        run_ids: chronologically-ordered list of run identifiers.

    Returns:
        Locked-shape dict::

            {
              "timeline": [
                {
                  "run_id":        str,
                  "timestamp":     str | None,
                  "trend":         <Unit 3 class for the prefix>,
                  "cluster":       str (cluster id),
                  "cluster_label": str (Unit 2 label),
                  "anomaly_level": "none|medium|high",
                  "health":        float in [0, 1],
                  "is_legacy":     bool,
                  "narrative":     str (1-2 sentence summary),
                },
                ...
              ],
              "summary": {
                "num_runs":         int,
                "num_anomalies":    int,
                "dominant_trend":   <Unit 3 class>,
                "dominant_cluster": <Unit 2 label>,
              },
            }

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)
    if not run_ids:
        return _empty_timeline()

    envelopes = [load_comparison_result(rid) for rid in run_ids]
    cluster_result = cluster_runs(run_ids)
    anomaly_result = detect_run_anomalies(run_ids)
    run_scores     = compute_run_scores(run_ids)["runs"]
    assignments    = cluster_result["assignments"]
    cluster_summary = cluster_result["cluster_summary"]

    timeline: list = []
    for idx, rid in enumerate(run_ids):
        envelope = envelopes[idx]
        meta = envelope.get("metadata") if isinstance(envelope, dict) else None
        is_legacy = not isinstance(meta, dict)
        timestamp = _extract_timestamp(envelope)
        cid = assignments.get(rid, "")
        cluster_label = (
            cluster_summary.get(cid, {}).get("label", "anomaly")
            if cid else "anomaly"
        )
        anomaly_info = anomaly_result["runs"].get(rid, {})
        anomaly_level = anomaly_info.get("level", _LEVEL_NONE)
        run_score_info = run_scores.get(rid, {})
        health = float(run_score_info.get("score", 0.0))
        trend = _prefix_trend(run_ids, idx)
        narrative = _per_run_narrative(
            rid, health, anomaly_level, cluster_label, is_legacy,
        )
        timeline.append({
            "run_id":        rid,
            "timestamp":     timestamp,
            "trend":         trend,
            "cluster":       cid,
            "cluster_label": cluster_label,
            "anomaly_level": anomaly_level,
            "health":        health,
            "is_legacy":     is_legacy,
            "narrative":     narrative,
        })

    return {
        "timeline": timeline,
        "summary":  _summary_for_timeline(timeline),
    }


def timeline_for_run(run_id) -> dict:
    """Return the single-run intelligence snapshot.

    Equivalent to ``build_intelligence_timeline([run_id])["timeline"][0]``.
    Same locked per-entry shape; ``trend`` is always
    ``insufficient_data`` for a single-run universe.

    Args:
        run_id: validated run identifier.

    Returns:
        Locked-shape per-run entry (see ``build_intelligence_timeline``).

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    return build_intelligence_timeline([run_id])["timeline"][0]
