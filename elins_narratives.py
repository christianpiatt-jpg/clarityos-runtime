"""
elins_narratives.py — ELINS2 Unit 7.

Narrative extraction. Composes the deterministic ELINS2 primitives
(Units 2-6) into short, structured, human-readable summaries: one for
a multi-run set, one for a cluster, one for an anomaly inventory.

ROLE
----
Operator-facing storytelling surface. Every numeric value the
narrative reports is sourced from an upstream unit; this module only
chooses *which* signals to surface and how to phrase them. No new
heuristics, no LLM calls, no randomness — same inputs always produce
byte-equal output.

NARRATIVE SHAPE
---------------
All three public functions return the same dict shape::

    {
      "headline": "<one-sentence summary>",
      "bullets":  [<short fact strings>],
      "details":  {<raw numeric / categorical signals>},
    }

``headline`` is always a single non-empty sentence; ``bullets`` is
always a non-empty list of non-empty strings; ``details`` always
exposes the same keys for a given function (locked vocabulary).

PUBLIC API
----------
    summarize_runs(run_ids: list[str]) -> dict
    summarize_cluster(cluster_id: str, cluster_info: dict) -> dict
    summarize_anomalies(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_clustering import cluster_runs
from elins_multi_summary import multi_run_summary
from elins_persistence import _validate_run_id
from elins_scoring import overall_health_score
from elins_trends import trend_for_run_sequence


# ---- Locked module constants ----------------------------------------------
# Health tone thresholds. Mirror Unit 5's anomaly thresholds so a
# "high" health reading aligns with "no high anomalies".
_HEALTH_HIGH:   float = 0.7
_HEALTH_MEDIUM: float = 0.4

_TONE_HIGH:   str = "high"
_TONE_MEDIUM: str = "medium"
_TONE_LOW:    str = "low"

# Trend → headline verb (for summarize_runs).
_TREND_HEADLINE: dict = {
    "monotonic_increase": "improving",
    "monotonic_decrease": "degrading",
    "plateau":            "holding steady",
    "oscillation":        "oscillating",
    "volatile":           "volatile",
    "insufficient_data":  "indeterminate",
}

# Cluster label vocabulary (mirror Unit 2).
_CLUSTER_STABLE:   str = "stable"
_CLUSTER_UPWARD:   str = "upward drift"
_CLUSTER_DOWNWARD: str = "downward drift"
_CLUSTER_OSCILLN:  str = "oscillation"
_CLUSTER_ANOMALY:  str = "anomaly"

_VALID_CLUSTER_LABELS: tuple = (
    _CLUSTER_STABLE,
    _CLUSTER_UPWARD,
    _CLUSTER_DOWNWARD,
    _CLUSTER_OSCILLN,
    _CLUSTER_ANOMALY,
)

# Pair-trend vocabulary (mirror Unit 4).
_PAIR_TREND_UP:   str = "upward"
_PAIR_TREND_FLAT: str = "flat"
_PAIR_TREND_DOWN: str = "downward"

# Anomaly reason → human phrase (mirror Unit 5's locked vocabulary).
_REASON_PHRASE: dict = {
    "low_similarity":    "low similarity to peers",
    "singleton_cluster": "singleton-cluster outliers",
    "extreme_trend":     "deviation from the trend line",
    "volatile_pairs":    "highly volatile pairs",
    "legacy_run":        "legacy (pre-metadata) runs",
}

# Anomaly levels (mirror Unit 5).
_LEVEL_HIGH:   str = "high"
_LEVEL_MEDIUM: str = "medium"
_LEVEL_NONE:   str = "none"

# Top-N anomalies to list in summarize_anomalies.
_TOP_ANOMALIES_N: int = 5
# Top-N volatile pairs to mention in summarize_runs.
_TOP_VOLATILE_PAIRS_N: int = 2


def _health_tone(health: float) -> str:
    """Bucket health into high/medium/low for headline tone selection."""
    if health >= _HEALTH_HIGH:
        return _TONE_HIGH
    if health >= _HEALTH_MEDIUM:
        return _TONE_MEDIUM
    return _TONE_LOW


def _validate_run_ids(run_ids, fn_name: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected a list, got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _empty_narrative_runs() -> dict:
    """Locked-shape response for empty input to summarize_runs."""
    return {
        "headline": "No runs available to summarize.",
        "bullets": [
            "Run count is zero — no signals to report.",
        ],
        "details": {
            "overall_health":         0.0,
            "num_runs":               0,
            "num_anomalies":          0,
            "dominant_trend":         "insufficient_data",
            "dominant_cluster_label": _CLUSTER_ANOMALY,
        },
    }


def _empty_narrative_anomalies() -> dict:
    """Locked-shape response for empty input to summarize_anomalies."""
    return {
        "headline": "No runs available to inspect for anomalies.",
        "bullets": [
            "Run count is zero — no signals to report.",
        ],
        "details": {
            "num_runs":       0,
            "num_anomalous":  0,
            "top_anomalies":  [],
            "reason_counts":  {},
        },
    }


def _dominant_cluster_label(cluster_assignments: dict,
                            cluster_summary: dict) -> str:
    """Find the cluster label held by the most run-ids. Ties broken
    alphabetically by label (deterministic)."""
    if not cluster_assignments or not cluster_summary:
        return _CLUSTER_ANOMALY
    counts: dict = {}
    for rid, cid in cluster_assignments.items():
        label = cluster_summary.get(cid, {}).get("label", _CLUSTER_ANOMALY)
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return _CLUSTER_ANOMALY
    return max(counts.keys(), key=lambda lbl: (counts[lbl], -ord(lbl[0])))


def _top_volatile_pairs(pair_summaries: dict, n: int) -> list:
    """Return up to `n` (pair_id, volatility) tuples sorted by
    volatility desc, then pair_id asc."""
    if not pair_summaries:
        return []
    items = [
        (pid, data["volatility_score"])
        for pid, data in pair_summaries.items()
    ]
    items.sort(key=lambda t: (-t[1], t[0]))
    return items[:n]


def _pair_trend_counts(pair_summaries: dict) -> dict:
    """Count {upward, flat, downward} across pair summaries. Missing
    keys default to 0."""
    counts = {
        _PAIR_TREND_UP:   0,
        _PAIR_TREND_FLAT: 0,
        _PAIR_TREND_DOWN: 0,
    }
    for data in pair_summaries.values():
        direction = data.get("trend_direction")
        if direction in counts:
            counts[direction] += 1
    return counts


def _anomaly_breakdown(anomaly_runs: dict) -> tuple:
    """Return (num_flagged, level_counts, reason_counts) over a Unit 5
    runs dict."""
    num_flagged = 0
    level_counts: dict = {
        _LEVEL_HIGH:   0,
        _LEVEL_MEDIUM: 0,
        _LEVEL_NONE:   0,
    }
    reason_counts: dict = {}
    for info in anomaly_runs.values():
        level = info.get("level", _LEVEL_NONE)
        level_counts[level] = level_counts.get(level, 0) + 1
        if level != _LEVEL_NONE:
            num_flagged += 1
        for r in info.get("reasons", []) or []:
            reason_counts[r] = reason_counts.get(r, 0) + 1
    return num_flagged, level_counts, reason_counts


def _format_health_bullet(health: float) -> str:
    tone = _health_tone(health)
    return f"Overall health is {tone} ({health:.2f})."


def _format_trend_bullet(trend: str, num_runs: int) -> str:
    descriptor = _TREND_HEADLINE.get(trend, trend)
    return f"Dominant trend across {num_runs} runs: {descriptor} ({trend})."


def _format_pair_trend_bullet(counts: dict) -> str:
    up   = counts.get(_PAIR_TREND_UP, 0)
    flat = counts.get(_PAIR_TREND_FLAT, 0)
    down = counts.get(_PAIR_TREND_DOWN, 0)
    total = up + flat + down
    if total == 0:
        return "No pair-level direction signals available."
    if up + flat >= down:
        return (
            f"Most pairs are upward or flat "
            f"({up} up, {flat} flat, {down} down)."
        )
    return (
        f"Most pairs are trending downward "
        f"({up} up, {flat} flat, {down} down)."
    )


def _format_anomaly_summary_bullet(num_anomalies: int,
                                   level_counts: dict,
                                   reason_counts: dict) -> str:
    if num_anomalies == 0:
        return "No anomalous runs detected."
    high = level_counts.get(_LEVEL_HIGH, 0)
    med  = level_counts.get(_LEVEL_MEDIUM, 0)
    if reason_counts:
        top_reason = max(
            reason_counts.keys(),
            key=lambda r: (reason_counts[r], -ord(r[0])),
        )
        phrase = _REASON_PHRASE.get(top_reason, top_reason)
        return (
            f"{num_anomalies} runs are anomalous "
            f"({high} high, {med} medium); "
            f"primary cause: {phrase}."
        )
    return f"{num_anomalies} runs are anomalous ({high} high, {med} medium)."


def _format_volatile_pairs_bullet(top_pairs: list) -> str:
    if not top_pairs:
        return "No pair-volatility signal available."
    parts = [
        f"{pid} ({vol:.2f})" for pid, vol in top_pairs
    ]
    return f"Top volatile pairs: {', '.join(parts)}."


def _format_runs_headline(tone: str, trend: str, num_runs: int) -> str:
    descriptor = _TREND_HEADLINE.get(trend, trend)
    if tone == _TONE_HIGH:
        return f"Drift across {num_runs} runs is {descriptor} and healthy."
    if tone == _TONE_MEDIUM:
        return f"Drift across {num_runs} runs is {descriptor} with mixed health."
    return f"Drift across {num_runs} runs is {descriptor} and under stress."


def summarize_runs(run_ids) -> dict:
    """Build a narrative summary across a run sequence.

    Args:
        run_ids: chronologically ordered run identifiers. Caller is
            responsible for ordering — use
            ``elins_run_ordering.sort_run_ids_by_timestamp`` if needed.

    Returns:
        Narrative dict with the locked ``{headline, bullets, details}``
        shape. ``details`` always contains ``overall_health``,
        ``num_runs``, ``num_anomalies``, ``dominant_trend``,
        ``dominant_cluster_label``.

    Raises:
        ValueError if ``run_ids`` is not a list or contains a malformed
            id.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "summarize_runs")
    if not run_ids:
        return _empty_narrative_runs()

    trend_result   = trend_for_run_sequence(run_ids)
    cluster_result = cluster_runs(run_ids)
    anomaly_result = detect_run_anomalies(run_ids)
    summary_result = multi_run_summary(run_ids)
    health         = overall_health_score(run_ids)

    dominant_trend   = trend_result["trend"]
    dominant_cluster = _dominant_cluster_label(
        cluster_result["assignments"],
        cluster_result["cluster_summary"],
    )
    num_runs = len(run_ids)
    pair_summaries = summary_result["pair_summaries"]
    top_pairs = _top_volatile_pairs(pair_summaries, _TOP_VOLATILE_PAIRS_N)
    pair_trend_counts = _pair_trend_counts(pair_summaries)
    num_anomalies, level_counts, reason_counts = _anomaly_breakdown(
        anomaly_result["runs"],
    )

    tone     = _health_tone(health)
    headline = _format_runs_headline(tone, dominant_trend, num_runs)

    bullets = [
        _format_health_bullet(health),
        _format_trend_bullet(dominant_trend, num_runs),
        f"Majority cluster label: {dominant_cluster}.",
        _format_pair_trend_bullet(pair_trend_counts),
        _format_anomaly_summary_bullet(
            num_anomalies, level_counts, reason_counts,
        ),
        _format_volatile_pairs_bullet(top_pairs),
    ]

    return {
        "headline": headline,
        "bullets":  bullets,
        "details": {
            "overall_health":         health,
            "num_runs":               num_runs,
            "num_anomalies":          num_anomalies,
            "dominant_trend":         dominant_trend,
            "dominant_cluster_label": dominant_cluster,
        },
    }


def _validate_cluster_info(cluster_info, fn_name: str) -> None:
    if not isinstance(cluster_info, dict):
        raise ValueError(
            f"{fn_name} expected cluster_info to be a dict, "
            f"got {type(cluster_info).__name__}"
        )
    if "members" not in cluster_info or "label" not in cluster_info:
        raise ValueError(
            f"{fn_name} expected cluster_info to include 'members' and "
            f"'label' keys"
        )
    members = cluster_info["members"]
    if not isinstance(members, list):
        raise ValueError(
            f"{fn_name} expected cluster_info['members'] to be a list, "
            f"got {type(members).__name__}"
        )
    label = cluster_info["label"]
    if not isinstance(label, str):
        raise ValueError(
            f"{fn_name} expected cluster_info['label'] to be a string, "
            f"got {type(label).__name__}"
        )


def _format_cluster_headline(cluster_id: str, label: str, size: int) -> str:
    if label == _CLUSTER_ANOMALY:
        return f"Cluster {cluster_id} (size {size}) is anomalous."
    if label == _CLUSTER_STABLE:
        return f"Cluster {cluster_id} (size {size}) is stable."
    if label == _CLUSTER_UPWARD:
        return f"Cluster {cluster_id} (size {size}) is drifting upward."
    if label == _CLUSTER_DOWNWARD:
        return f"Cluster {cluster_id} (size {size}) is drifting downward."
    if label == _CLUSTER_OSCILLN:
        return f"Cluster {cluster_id} (size {size}) is oscillating."
    return f"Cluster {cluster_id} (size {size}) carries label {label!r}."


def summarize_cluster(cluster_id, cluster_info) -> dict:
    """Build a narrative summary for a single cluster.

    Args:
        cluster_id: non-empty string identifier (e.g. ``c0``, ``c1``...).
        cluster_info: dict matching the per-cluster slice of
            ``cluster_runs(...)["cluster_summary"]``, i.e. ``{
                "members": [run_id, ...],
                "label":   "stable | upward drift | ...",
                "size":    int,  # optional — derived from members if absent
            }``. May additionally carry a ``representative`` key (the
            cluster's medoid run_id) — when present it's surfaced in
            the bullet list.

    Returns:
        Narrative dict with the locked ``{headline, bullets, details}``
        shape. ``details`` always contains ``cluster_id``, ``label``,
        ``size``, ``representative_run``, ``mostly_anomalous``.

    Raises:
        ValueError if ``cluster_id`` or ``cluster_info`` is malformed.
    """
    if not isinstance(cluster_id, str) or not cluster_id:
        raise ValueError(
            "summarize_cluster expected cluster_id to be a non-empty string, "
            f"got {cluster_id!r}"
        )
    _validate_cluster_info(cluster_info, "summarize_cluster")

    members: list = list(cluster_info["members"])
    label:   str  = cluster_info["label"]
    size = cluster_info.get("size")
    if not isinstance(size, int) or isinstance(size, bool):
        size = len(members)

    representative = cluster_info.get("representative")
    if not isinstance(representative, str) or not representative:
        # Fall back to the alphabetically-smallest member when no
        # explicit medoid was supplied.
        representative = sorted(members)[0] if members else ""

    mostly_anomalous = (
        label == _CLUSTER_ANOMALY or size <= 1
    )

    headline = _format_cluster_headline(cluster_id, label, size)

    bullets = [
        f"Label: {label}.",
        f"Size: {size} run(s).",
    ]
    if representative:
        bullets.append(f"Representative run: {representative}.")
    if mostly_anomalous:
        bullets.append("Cluster is mostly anomalous.")
    else:
        bullets.append("Cluster is mostly stable.")

    return {
        "headline": headline,
        "bullets":  bullets,
        "details": {
            "cluster_id":          cluster_id,
            "label":               label,
            "size":                size,
            "representative_run":  representative,
            "mostly_anomalous":    mostly_anomalous,
        },
    }


def _group_top_anomalies(anomaly_runs: dict, n: int) -> list:
    """Return up to `n` (run_id, score, reasons) tuples sorted by
    score desc, then run_id asc. Only flagged runs (level != "none")
    are surfaced — non-anomalous runs would dilute the list."""
    flagged: list = []
    for rid, info in anomaly_runs.items():
        level = info.get("level", _LEVEL_NONE)
        if level == _LEVEL_NONE:
            continue
        flagged.append((
            rid,
            float(info.get("score", 0.0)),
            list(info.get("reasons", []) or []),
        ))
    flagged.sort(key=lambda t: (-t[1], t[0]))
    return flagged[:n]


def _format_anomalies_headline(num_flagged: int,
                               num_runs: int,
                               level_counts: dict) -> str:
    if num_flagged == 0:
        return f"No anomalies detected across {num_runs} runs."
    high = level_counts.get(_LEVEL_HIGH, 0)
    if high > 0:
        return (
            f"{num_flagged} of {num_runs} runs are anomalous "
            f"({high} high)."
        )
    return f"{num_flagged} of {num_runs} runs are anomalous."


def _format_reason_bullets(reason_counts: dict) -> list:
    """Produce 1 bullet per reason category, sorted by count desc then
    reason string asc. The aggregate result is bounded by the size of
    Unit 5's locked reason vocabulary (5 entries)."""
    if not reason_counts:
        return []
    items = sorted(
        reason_counts.items(),
        key=lambda t: (-t[1], t[0]),
    )
    bullets: list = []
    for reason, count in items:
        phrase = _REASON_PHRASE.get(reason, reason)
        plural = "run" if count == 1 else "runs"
        bullets.append(f"{count} {plural} flagged for {phrase}.")
    return bullets


def summarize_anomalies(run_ids) -> dict:
    """Build a narrative summary of anomaly detection across a set of
    runs.

    Args:
        run_ids: list of run identifiers. Order is irrelevant — the
            output is a per-run inventory, not a sequence reading.

    Returns:
        Narrative dict with the locked ``{headline, bullets, details}``
        shape. ``details`` always contains ``num_runs``,
        ``num_anomalous``, ``top_anomalies`` (list of
        ``{run_id, score, level, reasons}`` dicts, longest first), and
        ``reason_counts`` (``{reason: count}``).

    Raises:
        ValueError if ``run_ids`` is not a list or contains a malformed
            id.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "summarize_anomalies")
    if not run_ids:
        return _empty_narrative_anomalies()

    anomaly_result = detect_run_anomalies(run_ids)
    runs_info = anomaly_result["runs"]

    num_runs = len(run_ids)
    num_flagged, level_counts, reason_counts = _anomaly_breakdown(runs_info)
    top = _group_top_anomalies(runs_info, _TOP_ANOMALIES_N)

    headline = _format_anomalies_headline(
        num_flagged, num_runs, level_counts,
    )
    bullets: list = []
    if num_flagged == 0:
        bullets.append(
            f"All {num_runs} run(s) passed the anomaly filter."
        )
    else:
        bullets.append(
            f"{num_flagged} of {num_runs} runs cleared the anomaly threshold."
        )
        bullets.extend(_format_reason_bullets(reason_counts))
        if top:
            top_phrase = ", ".join(
                f"{rid} ({score:.2f})" for rid, score, _ in top
            )
            bullets.append(f"Top anomalous runs: {top_phrase}.")

    top_serialised = [
        {
            "run_id":  rid,
            "score":   score,
            "level":   runs_info[rid].get("level", _LEVEL_NONE),
            "reasons": reasons,
        }
        for rid, score, reasons in top
    ]

    return {
        "headline": headline,
        "bullets":  bullets,
        "details": {
            "num_runs":      num_runs,
            "num_anomalous": num_flagged,
            "top_anomalies": top_serialised,
            "reason_counts": reason_counts,
        },
    }
