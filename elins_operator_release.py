"""
elins_operator_release.py — ELINS6 Unit 20.

Operator-facing release actions on top of Unit 19's gate. Three
helpers that turn the gate decision into action (tag mutations) or
distribution (structured report).

ROLE
----
Operator surface for release management. Pure composition over
Units 9 / 14 / 16 / 17 / 19. Tag mutations are dedupe-aware
(Unit 27/28 ``get_tags`` / ``set_tags`` invariants) and idempotent.

PUBLIC API
----------
    apply_release_gate(run_ids: list[str]) -> dict
    tag_release_decision(run_ids: list[str], decision: str) -> dict
    generate_release_report(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_alerts import generate_alerts
from elins_intel_diff import diff_intelligence
from elins_intelligence import intelligence_for_run_ids
from elins_pair_deep import pair_deep_all
from elins_persistence import _validate_run_id, get_tags, set_tags
from elins_release_gate import evaluate_release_gate


# Locked tag vocabulary.
TAG_RELEASE_BLOCKED: str = "release_blocked"
TAG_RELEASE_WARN:    str = "release_warn"
TAG_RELEASE_ALLOWED: str = "release_allowed"

# Decision → tag map.
_DECISION_TAG_MAP: dict = {
    "block": TAG_RELEASE_BLOCKED,
    "warn":  TAG_RELEASE_WARN,
    "allow": TAG_RELEASE_ALLOWED,
}

_VALID_DECISIONS: tuple = ("allow", "warn", "block")


def _validate_run_ids(run_ids, fn_name: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected a list, got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _validate_decision(decision) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"decision must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _append_tag(run_id: str, tag: str) -> bool:
    """Dedupe-aware tag append. Returns True if the run was mutated."""
    existing = get_tags(run_id)
    if tag in existing:
        return False
    set_tags(run_id, existing + [tag])
    return True


def apply_release_gate(run_ids) -> dict:
    """Evaluate the Unit 19 gate and apply the matching tag to every
    run in `run_ids`.

    Args:
        run_ids: chronologically ordered run identifiers.

    Returns:
        ``{
            "decision":    "allow | warn | block",
            "tagged_runs": [<rid>, ...],   # alpha-sorted, only runs
                                           # actually mutated this call
        }``.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "apply_release_gate")
    gate = evaluate_release_gate(run_ids)
    decision = gate["decision"]
    tag = _DECISION_TAG_MAP[decision]

    tagged_runs: list = []
    for rid in run_ids:
        if _append_tag(rid, tag):
            tagged_runs.append(rid)
    return {
        "decision":    decision,
        "tagged_runs": sorted(tagged_runs),
    }


def tag_release_decision(run_ids, decision: str) -> dict:
    """Idempotent tag mutation for an explicit decision.

    Args:
        run_ids: chronologically ordered run identifiers.
        decision: one of ``"allow"``, ``"warn"``, ``"block"``.

    Returns:
        ``{"decision": <str>, "applied": True, "tagged_runs": [<rid>, ...]}``.
        ``applied`` is always ``True`` — the call is the action.
        ``tagged_runs`` lists the runs that received the tag this call
        (skipping runs that already carried it).

    Raises:
        ValueError on a malformed run_ids list or invalid decision.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "tag_release_decision")
    _validate_decision(decision)
    tag = _DECISION_TAG_MAP[decision]

    tagged_runs: list = []
    for rid in run_ids:
        if _append_tag(rid, tag):
            tagged_runs.append(rid)
    return {
        "decision":    decision,
        "applied":     True,
        "tagged_runs": sorted(tagged_runs),
    }


def _empty_release_report() -> dict:
    return {
        "headline":  "No runs available for release evaluation.",
        "decision":  "warn",
        "metrics": {
            "health":           0.0,
            "anomaly_fraction": 0.0,
            "trend_shift":      "neutral",
            "cluster_shift":    "neutral",
            "regressions":      0,
            "promoted_pairs":   [],
        },
        "alerts":   [],
        "pairs":    {"pairs": {}, "run_ids": []},
        "diff":     None,
    }


def _headline_for_decision(decision: str,
                            intel_headline: str,
                            metrics: dict) -> str:
    """Compose a short top-line summary keyed off the gate decision."""
    health = float(metrics.get("health", 0.0))
    if decision == "block":
        return (
            f"Release BLOCKED. Health {health:.2f}, "
            f"{metrics['regressions']} pair regression(s)."
        )
    if decision == "warn":
        return f"Release flagged for review. Health {health:.2f}."
    return f"Release allowed. Health {health:.2f}."


def generate_release_report(run_ids) -> dict:
    """Bundle Units 9 / 14 / 16 / 17 / 19 into a single structured
    release report.

    The diff section compares the first half of `run_ids` against the
    second half (``mid = len(run_ids) // 2``). With fewer than 2 runs
    ``diff`` is ``None``.

    Args:
        run_ids: chronologically ordered run identifiers.

    Returns:
        Locked-shape dict with keys ``headline``, ``decision``,
        ``metrics``, ``alerts``, ``pairs``, ``diff``. Empty input
        returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "generate_release_report")
    if not run_ids:
        return _empty_release_report()

    intel  = intelligence_for_run_ids(run_ids)
    gate   = evaluate_release_gate(run_ids)
    alerts = generate_alerts(run_ids)
    pairs  = pair_deep_all(run_ids)

    diff = None
    if len(run_ids) >= 2:
        mid = len(run_ids) // 2
        diff = diff_intelligence(run_ids[:mid], run_ids[mid:])

    headline = _headline_for_decision(
        gate["decision"],
        intel.get("narratives", {}).get("runs", {}).get("headline", ""),
        gate["metrics"],
    )

    return {
        "headline": headline,
        "decision": gate["decision"],
        "metrics":  gate["metrics"],
        "alerts":   alerts["alerts"],
        "pairs":    pairs,
        "diff":     diff,
    }
