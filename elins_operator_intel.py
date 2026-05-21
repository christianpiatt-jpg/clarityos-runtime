"""
elins_operator_intel.py — ELINS2 Unit 12.

Operator action helpers built on top of the ELINS2 intelligence stack.
Each helper takes raw run_ids (and sometimes a cluster context), pulls
the relevant intelligence signal, and applies the appropriate tag via
Unit 27/28 ``get_tags`` / ``set_tags``.

ROLE
----
Operator-facing actions — small, focused mutators that "act on" the
read-only intelligence surface. Tags are append-only with dedupe:
existing tags are preserved, the action tag is added once even if the
run already carries it.

INVALIDATION
------------
Each helper that mutates a run's tags also invalidates the Unit 11
intelligence cache for that run's identifier appearing alone — the
cache stores the full payload keyed by the input run_ids list, so a
narrow per-run invalidation is best-effort. Callers that care about
freshness after a bulk tagging operation should explicitly invalidate
the (run_ids, ...) keys they're about to re-read.

PUBLIC API
----------
    flag_anomalous_runs(run_ids) -> dict
    pin_best_sequence(run_ids, window=5) -> dict
    tag_cluster_runs(cluster_id, cluster_info, tag) -> dict
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_persistence import _validate_run_id, get_tags, set_tags
from elins_sequences import best_sequence


# Locked tag vocabulary.
TAG_ANOMALY:          str = "anomaly"
TAG_PINNED_SEQUENCE: str = "pinned_sequence"

# Anomaly levels we flag.
_FLAGGED_LEVELS: tuple = ("medium", "high")


def _validate_run_ids(run_ids, fn_name: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected run_ids to be a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _append_tag(run_id: str, tag: str) -> bool:
    """Add `tag` to `run_id`'s tag list if not already present.
    Returns True when the run was mutated (tag added), False if the tag
    was already there. Order of existing tags is preserved.

    Raises:
        FileNotFoundError if the run does not exist.
        ValueError on a malformed run_id.
    """
    existing = get_tags(run_id)
    if tag in existing:
        return False
    set_tags(run_id, existing + [tag])
    return True


def flag_anomalous_runs(run_ids) -> dict:
    """Tag every run whose Unit 5 level is medium/high with the
    ``"anomaly"`` tag.

    Args:
        run_ids: validated list of run_ids.

    Returns:
        ``{"flagged": [<run_id>, ...], "skipped": [<run_id>, ...]}``.
        ``flagged`` lists every run that received the tag during this
        call (alphabetically sorted). ``skipped`` lists every other
        run in the input — either because its anomaly level was
        ``"none"`` or because it already carried the tag.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run_id does not exist.
    """
    _validate_run_ids(run_ids, "flag_anomalous_runs")
    if not run_ids:
        return {"flagged": [], "skipped": []}

    anomaly_result = detect_run_anomalies(run_ids)
    runs_info = anomaly_result["runs"]

    flagged: list = []
    skipped: list = []
    for rid in run_ids:
        info = runs_info.get(rid, {})
        level = info.get("level", "none")
        if level in _FLAGGED_LEVELS:
            mutated = _append_tag(rid, TAG_ANOMALY)
            if mutated:
                flagged.append(rid)
            else:
                skipped.append(rid)
        else:
            skipped.append(rid)

    flagged.sort()
    skipped.sort()
    return {"flagged": flagged, "skipped": skipped}


def pin_best_sequence(run_ids, window: int = 5) -> dict:
    """Tag every run in the Unit 8 best window with
    ``"pinned_sequence"``.

    Args:
        run_ids: validated chronological run_ids list.
        window: integer window size (>= 2 and <= len(run_ids)) —
            forwarded to ``best_sequence``. Default 5.

    Returns:
        ``{"pinned": [<run_id>, ...]}``. ``pinned`` lists the run_ids
        in the best window that received the tag in this call (input
        order). Empty list if the input is smaller than the window
        (no best window available) or every member already carried
        the tag.

    Raises:
        ValueError on a malformed run_ids list or invalid window.
        FileNotFoundError if any run_id does not exist.
    """
    _validate_run_ids(run_ids, "pin_best_sequence")
    if not run_ids:
        return {"pinned": []}
    if len(run_ids) < window:
        return {"pinned": []}

    best = best_sequence(run_ids, window=window)
    pinned: list = []
    for rid in best["run_ids"]:
        if _append_tag(rid, TAG_PINNED_SEQUENCE):
            pinned.append(rid)
    return {"pinned": pinned}


def _validate_tag(tag) -> None:
    if not isinstance(tag, str):
        raise ValueError(
            f"tag must be a string, got {type(tag).__name__}"
        )
    if not tag:
        raise ValueError("tag must be non-empty")


def tag_cluster_runs(cluster_id, cluster_info, tag) -> dict:
    """Apply `tag` to every member of a cluster.

    Args:
        cluster_id: non-empty string identifier (e.g. ``"c0"``). Echoed
            in the response but otherwise informational.
        cluster_info: dict with a ``"members"`` list — typically the
            ``cluster_summary[cluster_id]`` slice of a ``cluster_runs``
            call.
        tag: non-empty string tag to apply to every member.

    Returns:
        ``{"cluster_id": <id>, "tag": <tag>, "run_ids": [<sorted member ids>]}``.

    Raises:
        ValueError if any argument is malformed.
        FileNotFoundError if any cluster member does not exist.
    """
    if not isinstance(cluster_id, str) or not cluster_id:
        raise ValueError(
            "tag_cluster_runs expected cluster_id to be a non-empty string"
        )
    if not isinstance(cluster_info, dict):
        raise ValueError(
            f"tag_cluster_runs expected cluster_info to be a dict, "
            f"got {type(cluster_info).__name__}"
        )
    members = cluster_info.get("members")
    if not isinstance(members, list):
        raise ValueError(
            "tag_cluster_runs expected cluster_info['members'] to be a list"
        )
    _validate_tag(tag)
    _validate_run_ids(members, "tag_cluster_runs.members")

    applied: list = []
    for rid in members:
        if _append_tag(rid, tag):
            applied.append(rid)
    return {
        "cluster_id": cluster_id,
        "tag":        tag,
        "run_ids":    sorted(members),
        "applied":    sorted(applied),
    }
