"""
elins_operator_cross_batch.py — ELINS8 Unit 24.

Operator-facing workflows on top of Unit 23's cross-batch engine. Three
helpers that turn cross-batch results into action (per-batch verdict
tags) or distribution (structured cross-batch report).

ROLE
----
Operator workflow surface for multi-batch comparison. Pure composition
over Units 21 + 23 + their data lineage. Tags are conceptual (applied
to BATCH NAMES, not run_ids) — this layer doesn't mutate per-run tags
because the cross-batch operation reasons over higher-level aggregates.

VERDICT LOGIC (locked, deterministic)
-------------------------------------
For each batch, count wins / losses / ties across every comparison it
participates in:

    net = wins - losses
    net > 0  → "winner"
    net < 0  → "loser"
    net == 0 → "tie"

A single-batch input produces an empty comparison set and every
batch's verdict defaults to ``"tie"``.

PUBLIC API
----------
    apply_cross_batch(batches: dict[str, dict]) -> dict
    tag_cross_batch(batches: dict[str, dict],
                    decisions: dict[str, str]) -> dict
    generate_cross_batch_report(batches: dict[str, dict]) -> dict
"""
from __future__ import annotations

from elins_cross_batch import compare_batches


# Locked tag vocabulary.
TAG_CROSS_BATCH_WINNER: str = "cross_batch_winner"
TAG_CROSS_BATCH_LOSER:  str = "cross_batch_loser"
TAG_CROSS_BATCH_TIE:    str = "cross_batch_tie"

# Verdict vocabulary.
_VERDICT_WINNER: str = "winner"
_VERDICT_LOSER:  str = "loser"
_VERDICT_TIE:    str = "tie"

_VERDICT_TAG_MAP: dict = {
    _VERDICT_WINNER: TAG_CROSS_BATCH_WINNER,
    _VERDICT_LOSER:  TAG_CROSS_BATCH_LOSER,
    _VERDICT_TIE:    TAG_CROSS_BATCH_TIE,
}

_VALID_VERDICTS: tuple = (_VERDICT_WINNER, _VERDICT_LOSER, _VERDICT_TIE)

# Comparison key infix (mirror Unit 23).
_VS_INFIX: str = "_vs_"


def _validate_batches(batches, fn_name: str) -> None:
    if not isinstance(batches, dict):
        raise ValueError(
            f"{fn_name} expected batches to be a dict, "
            f"got {type(batches).__name__}"
        )
    for name, payload in batches.items():
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"batch name must be a non-empty string, got {name!r}"
            )
        if not isinstance(payload, dict):
            raise ValueError(
                f"batches[{name!r}] must be a dict (Unit 21 output), "
                f"got {type(payload).__name__}"
            )


def _validate_verdict(verdict, label: str) -> None:
    if not isinstance(verdict, str) or verdict not in _VALID_VERDICTS:
        raise ValueError(
            f"{label} must be one of {_VALID_VERDICTS}, got {verdict!r}"
        )


def _verdicts_from_comparisons(batch_names: list, comparisons: dict) -> dict:
    """Aggregate per-batch wins / losses / ties from the Unit 23
    ``comparisons`` section and return ``{batch_name: verdict}``."""
    score: dict = {name: 0 for name in batch_names}
    for key, entry in comparisons.items():
        if _VS_INFIX not in key:
            continue
        x, y = key.split(_VS_INFIX, 1)
        winner = entry.get("winner", "tie")
        if winner == x:
            score[x] = score.get(x, 0) + 1
            score[y] = score.get(y, 0) - 1
        elif winner == y:
            score[y] = score.get(y, 0) + 1
            score[x] = score.get(x, 0) - 1
        # Ties leave scores unchanged.
    verdicts: dict = {}
    for name in batch_names:
        s = score.get(name, 0)
        if s > 0:
            verdicts[name] = _VERDICT_WINNER
        elif s < 0:
            verdicts[name] = _VERDICT_LOSER
        else:
            verdicts[name] = _VERDICT_TIE
    return verdicts


def apply_cross_batch(batches) -> dict:
    """Evaluate Unit 23 and emit per-batch verdicts + tags.

    Args:
        batches: ``dict[str, dict]`` of batch_name → Unit 21
            ``evaluate_batch`` output.

    Returns:
        ``{
            "batches": {
                "<name>": {
                    "decision": "winner | loser | tie",
                    "tags":     [<cross_batch_* tag>],
                },
                ...
            },
        }``.

    Raises:
        ValueError on a malformed batches mapping.
    """
    _validate_batches(batches, "apply_cross_batch")
    if not batches:
        return {"batches": {}}

    xb = compare_batches(batches)
    names = sorted(batches.keys())
    verdicts = _verdicts_from_comparisons(names, xb["comparisons"])

    out: dict = {}
    for name in names:
        verdict = verdicts[name]
        out[name] = {
            "decision": verdict,
            "tags":     [_VERDICT_TAG_MAP[verdict]],
        }
    return {"batches": out}


def tag_cross_batch(batches, decisions) -> dict:
    """Apply caller-supplied per-batch verdicts as ``cross_batch_*``
    tags.

    Args:
        batches: ``dict[str, dict]`` of batch_name → Unit 21 output.
        decisions: ``dict[str, str]`` mapping batch name → verdict in
            ``{"winner", "loser", "tie"}``. Must have exactly the same
            keys as `batches`.

    Returns:
        ``{
            "applied": True,
            "tagged": {
                "<name>": [<cross_batch_* tag>],
                ...
            },
        }``.

    Raises:
        ValueError if `batches` or `decisions` is malformed, or the
            two mappings have different key sets.
    """
    _validate_batches(batches, "tag_cross_batch")
    if not isinstance(decisions, dict):
        raise ValueError(
            f"tag_cross_batch expected decisions to be a dict, "
            f"got {type(decisions).__name__}"
        )
    if set(decisions.keys()) != set(batches.keys()):
        raise ValueError(
            "decisions must map exactly the same batch names as batches; "
            f"got batches={sorted(batches.keys())}, "
            f"decisions={sorted(decisions.keys())}"
        )
    for name, v in decisions.items():
        _validate_verdict(v, f"decisions[{name!r}]")

    tagged: dict = {}
    for name in sorted(batches.keys()):
        tag = _VERDICT_TAG_MAP[decisions[name]]
        tagged[name] = [tag]
    return {"applied": True, "tagged": tagged}


def _empty_report() -> dict:
    return {
        "headline":    "No batches supplied for cross-batch evaluation.",
        "batches":     {},
        "comparisons": {},
        "alerts":      {},
        "pairs":       {},
        "diffs":       {},
    }


def _alerts_for_batch(batch_payload: dict) -> list:
    """Aggregate alert-like signals from a Unit 21 batch output. Each
    block / warn group becomes one entry in the cross-batch alerts list
    so operators see per-batch trouble spots at a glance."""
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
    """Aggregate the de-duplicated set of pair_ids that appeared in any
    within-batch comparison's ``pair_regressions`` list."""
    seen: set = set()
    comparisons = batch_payload.get("comparisons", {}) or {}
    for entry in comparisons.values():
        for pid in entry.get("pair_regressions", []) or []:
            seen.add(pid)
    return sorted(seen)


def _headline_for_cross_batch(verdicts: dict,
                               xb: dict) -> str:
    """Compose a short one-liner summarising the cross-batch
    verdicts. Mirrors the spec example::

        train_A wins over train_B
        (3 group wins vs 1; health +0.12, anomalies -0.03)
    """
    winners = [n for n, v in verdicts.items() if v == _VERDICT_WINNER]
    losers  = [n for n, v in verdicts.items() if v == _VERDICT_LOSER]

    # Single-comparison fast path — surface delta details for clarity.
    if len(xb["comparisons"]) == 1:
        key, entry = next(iter(xb["comparisons"].items()))
        winner = entry["winner"]
        if winner == "tie":
            return (
                f"{key}: tie "
                f"(health {entry['health_delta']:+.2f}, "
                f"anomalies {entry['anomaly_delta']:+.2f})."
            )
        x, y = key.split(_VS_INFIX, 1)
        loser = y if winner == x else x
        wins = entry["group_wins"][winner]
        losses = entry["group_wins"][loser]
        return (
            f"{winner} wins over {loser} "
            f"({wins} group wins vs {losses}; "
            f"health {entry['health_delta']:+.2f}, "
            f"anomalies {entry['anomaly_delta']:+.2f})."
        )

    if not winners and not losers:
        return f"All {len(verdicts)} batch(es) tie."
    if winners and not losers:
        return f"{len(winners)} batch(es) winning, no losers."
    if losers and not winners:
        return f"{len(losers)} batch(es) losing, no clear winners."
    return (
        f"{len(winners)} winner(s) "
        f"({', '.join(sorted(winners))}); "
        f"{len(losers)} loser(s) "
        f"({', '.join(sorted(losers))})."
    )


def generate_cross_batch_report(batches) -> dict:
    """Bundle Units 21 + 23 (with per-batch alert / pair / diff
    aggregates) into a single locked-shape report.

    Args:
        batches: ``dict[str, dict]`` of batch_name → Unit 21 output.

    Returns:
        Locked-shape dict::

            {
              "headline":    str,
              "batches":     <Unit 23 batches summary>,
              "comparisons": <Unit 23 comparisons>,
              "alerts":      {batch_name: [<alert dict>, ...]},
              "pairs":       {batch_name: [<pair_id>, ...]},
              "diffs":       {"<x>_vs_<y>": <Unit 23 comparison entry>},
            }

        Empty input returns the well-formed empty-report shape.

    Raises:
        ValueError on a malformed batches mapping.
    """
    _validate_batches(batches, "generate_cross_batch_report")
    if not batches:
        return _empty_report()

    xb = compare_batches(batches)
    names = sorted(batches.keys())
    verdicts = _verdicts_from_comparisons(names, xb["comparisons"])

    alerts_by_batch: dict = {}
    pairs_by_batch:  dict = {}
    for name in names:
        alerts_by_batch[name] = _alerts_for_batch(batches[name])
        pairs_by_batch[name]  = _pairs_for_batch(batches[name])

    # Diffs section: surface the Unit 23 comparison entries under a
    # diffs alias so callers expecting Unit 14-style payloads get a
    # consistent place to find per-pair deltas.
    diffs_by_pair = dict(xb["comparisons"])

    headline = _headline_for_cross_batch(verdicts, xb)

    return {
        "headline":    headline,
        "batches":     xb["batches"],
        "comparisons": xb["comparisons"],
        "alerts":      alerts_by_batch,
        "pairs":       pairs_by_batch,
        "diffs":       diffs_by_pair,
    }
