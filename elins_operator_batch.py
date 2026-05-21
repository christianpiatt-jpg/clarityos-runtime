"""
elins_operator_batch.py — ELINS7 Unit 22.

Operator-facing batch actions on top of Unit 21's evaluator. Three
helpers that turn batch evaluation into action (per-group tag
mutation) or distribution (structured batch report).

ROLE
----
Operator workflow surface for multi-run batch flows. Pure composition
over Units 9 / 14 / 16 / 17 / 19 / 21. Tag mutations are dedupe-aware
and idempotent — repeated calls are safe.

PUBLIC API
----------
    apply_batch_gate(groups: dict[str, list[str]]) -> dict
    tag_batch_decisions(groups, decisions: dict[str, str]) -> dict
    generate_batch_report(groups: dict[str, list[str]]) -> dict
"""
from __future__ import annotations

from elins_alerts import generate_alerts
from elins_batch_eval import evaluate_batch
from elins_intel_diff import diff_intelligence
from elins_intelligence import intelligence_for_run_ids
from elins_pair_deep import pair_deep_all
from elins_persistence import _validate_run_id, get_tags, set_tags


# Locked tag vocabulary.
TAG_BATCH_BLOCKED: str = "batch_blocked"
TAG_BATCH_WARN:    str = "batch_warn"
TAG_BATCH_ALLOWED: str = "batch_allowed"

# Decision → tag map.
_DECISION_TAG_MAP: dict = {
    "block": TAG_BATCH_BLOCKED,
    "warn":  TAG_BATCH_WARN,
    "allow": TAG_BATCH_ALLOWED,
}

_VALID_DECISIONS: tuple = ("allow", "warn", "block")


def _validate_groups(groups, fn_name: str) -> None:
    if not isinstance(groups, dict):
        raise ValueError(
            f"{fn_name} expected groups to be a dict, "
            f"got {type(groups).__name__}"
        )
    for name, run_ids in groups.items():
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"group name must be a non-empty string, got {name!r}"
            )
        if not isinstance(run_ids, list):
            raise ValueError(
                f"groups[{name!r}] must be a list, "
                f"got {type(run_ids).__name__}"
            )
        for rid in run_ids:
            _validate_run_id(rid)


def _validate_decision(decision, label: str) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"{label} must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _append_tag(run_id: str, tag: str) -> bool:
    """Dedupe-aware tag append. Returns True when the run was mutated."""
    existing = get_tags(run_id)
    if tag in existing:
        return False
    set_tags(run_id, existing + [tag])
    return True


def apply_batch_gate(groups) -> dict:
    """Evaluate the Unit 21 batch + apply the matching ``batch_*`` tag
    to every run in each group.

    Args:
        groups: ``dict[str, list[str]]`` mapping group names to
            chronologically ordered run_ids.

    Returns:
        ``{
            "groups": {
                "<name>": {
                    "decision":    "allow | warn | block",
                    "tagged_runs": [<rid>, ...],   # alpha-sorted, only
                                                   # runs mutated this call
                },
                ...
            },
        }``.

    Raises:
        ValueError on a malformed groups mapping.
        FileNotFoundError if any run does not exist.
    """
    _validate_groups(groups, "apply_batch_gate")
    batch = evaluate_batch(groups)
    out: dict = {}
    for name in sorted(groups.keys()):
        decision = batch["groups"][name]["decision"]
        tag = _DECISION_TAG_MAP[decision]
        tagged: list = []
        for rid in groups[name]:
            if _append_tag(rid, tag):
                tagged.append(rid)
        out[name] = {
            "decision":    decision,
            "tagged_runs": sorted(tagged),
        }
    return {"groups": out}


def tag_batch_decisions(groups, decisions) -> dict:
    """Apply caller-supplied per-group decisions as ``batch_*`` tags.

    Args:
        groups: ``dict[str, list[str]]`` of group runs.
        decisions: ``dict[str, str]`` mapping group name → decision in
            ``{"allow", "warn", "block"}``. Every group in `groups`
            must have a matching entry; extra keys in `decisions`
            raise.

    Returns:
        ``{
            "applied": True,
            "tagged": {
                "<group_name>": [<rid>, ...],   # alpha-sorted, runs
                                                # mutated this call
                ...
            },
        }``.

    Raises:
        ValueError on a malformed groups / decisions mapping.
        FileNotFoundError if any run does not exist.
    """
    _validate_groups(groups, "tag_batch_decisions")
    if not isinstance(decisions, dict):
        raise ValueError(
            f"tag_batch_decisions expected decisions to be a dict, "
            f"got {type(decisions).__name__}"
        )
    if set(decisions.keys()) != set(groups.keys()):
        raise ValueError(
            "decisions must map exactly the same group names as groups; "
            f"got groups={sorted(groups.keys())}, "
            f"decisions={sorted(decisions.keys())}"
        )
    for name, dec in decisions.items():
        _validate_decision(dec, f"decisions[{name!r}]")

    tagged: dict = {}
    for name in sorted(groups.keys()):
        tag = _DECISION_TAG_MAP[decisions[name]]
        mutated: list = []
        for rid in groups[name]:
            if _append_tag(rid, tag):
                mutated.append(rid)
        tagged[name] = sorted(mutated)
    return {"applied": True, "tagged": tagged}


def _empty_batch_report() -> dict:
    return {
        "headline":    "No groups supplied for batch evaluation.",
        "groups":      {},
        "comparisons": {},
        "alerts":      {},
        "pairs":       {},
        "diffs":       {},
    }


def _headline_for_batch(batch_groups: dict) -> str:
    """Compose a short one-liner summarising the batch decisions."""
    if not batch_groups:
        return "No groups supplied for batch evaluation."
    counts: dict = {"allow": 0, "warn": 0, "block": 0}
    for data in batch_groups.values():
        d = data.get("decision", "warn")
        counts[d] = counts.get(d, 0) + 1
    total = sum(counts.values())
    if counts["block"] > 0:
        return (
            f"{counts['block']} of {total} group(s) BLOCKED; "
            f"{counts['warn']} warn, {counts['allow']} allow."
        )
    if counts["warn"] > 0:
        return (
            f"{counts['warn']} of {total} group(s) flagged for review; "
            f"{counts['allow']} allow."
        )
    return f"All {total} group(s) allowed."


def generate_batch_report(groups) -> dict:
    """Bundle Units 9 / 14 / 16 / 17 / 19 / 21 into a single
    structured batch report.

    Args:
        groups: ``dict[str, list[str]]`` mapping group names to
            chronologically ordered run_ids.

    Returns:
        Locked-shape dict with keys ``headline``, ``groups``,
        ``comparisons``, ``alerts``, ``pairs``, ``diffs``::

            * groups / comparisons mirror Unit 21's evaluator output
            * alerts is keyed by group name → Unit 16 alerts list
            * pairs  is keyed by group name → Unit 17 pair_deep_all
            * diffs  is keyed by comparison key → Unit 14 full diff
                     (the comparisons section already carries the
                     summary slice; diffs surfaces the per-pair
                     payload for richer rendering)

        Empty input returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed groups mapping.
        FileNotFoundError if any run does not exist.
    """
    _validate_groups(groups, "generate_batch_report")
    if not groups:
        return _empty_batch_report()

    batch = evaluate_batch(groups)

    # Per-group enrichment (alerts + pair deep + intelligence-derived
    # headline material).
    alerts_by_group: dict = {}
    pairs_by_group:  dict = {}
    for name in sorted(groups.keys()):
        run_ids = groups[name]
        alerts_by_group[name] = generate_alerts(run_ids)["alerts"]
        pairs_by_group[name]  = pair_deep_all(run_ids)
        # Touch intelligence so the cache warms; not surfaced as raw.
        intelligence_for_run_ids(run_ids)

    # Per-comparison diff payloads (alpha-sorted pairs).
    diffs_by_pair: dict = {}
    names = sorted(groups.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x, y = names[i], names[j]
            diffs_by_pair[f"{x}_vs_{y}"] = diff_intelligence(
                groups[x], groups[y],
            )

    headline = _headline_for_batch(batch["groups"])

    return {
        "headline":    headline,
        "groups":      batch["groups"],
        "comparisons": batch["comparisons"],
        "alerts":      alerts_by_group,
        "pairs":       pairs_by_group,
        "diffs":       diffs_by_pair,
    }
