"""
elins_batch_eval.py — ELINS7 Unit 21.

Multi-run batch evaluator. Composes Units 14 + 19 over a named-group
mapping to produce per-group release decisions AND pairwise
comparisons (with a deterministic winner verdict).

ROLE
----
Batch-intelligence layer for operators comparing multiple branches /
environments / release trains / model versions / time slices in a
single call. Pure composition over the existing intelligence stack —
same input mapping always produces byte-equal output.

WINNER LOGIC (locked, deterministic)
-------------------------------------
For each unordered pair of groups (alpha-sorted, ``x < y`` by name):

    diff = diff_intelligence(group_x_ids, group_y_ids)
    score = diff.health_delta
          - diff.anomaly_delta
          - 0.1 * len(pair_regressions)

    score > +epsilon   →  y wins
    score < -epsilon   →  x wins
    abs(score) <= eps  →  tie

``epsilon = 0.05`` matches the Unit 19 warn threshold so a comparison
labelled ``tie`` would never have crossed any gate's hard rule.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "groups": {
        "<name>": {
          "decision": "allow | warn | block",
          "reasons":  [...],
          "metrics":  {...},   # mirrors Unit 19's metrics block
        },
        ...
      },
      "comparisons": {
        "<x>_vs_<y>": {        # x and y are alpha-sorted
          "health_delta":     float,
          "anomaly_delta":    float,
          "cluster_shift":    <Unit 14 vocab>,
          "trend_shift":      <Unit 14 vocab>,
          "pair_regressions": [<pair_id>, ...],
          "winner":           "<x> | <y> | tie",
        },
        ...
      },
    }

PUBLIC API
----------
    evaluate_batch(groups: dict[str, list[str]]) -> dict
"""
from __future__ import annotations

from elins_intel_diff import diff_intelligence
from elins_persistence import _validate_run_id
from elins_release_gate import evaluate_release_gate


# Locked thresholds.
_WINNER_EPSILON: float = 0.05
_PAIR_REGRESSION_WEIGHT: float = 0.1
_PAIR_STABILITY_DROP_LIMIT: float = 0.20

# Winner vocabulary.
_TIE: str = "tie"

# Comparison key format.
_VS_INFIX: str = "_vs_"


def _validate_groups(groups) -> None:
    if not isinstance(groups, dict):
        raise ValueError(
            f"evaluate_batch expected a dict, got {type(groups).__name__}"
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


def _pair_regressions(diff: dict) -> list:
    """Return alpha-sorted pair_ids whose stability_delta crosses the
    block threshold from Unit 19."""
    out: list = []
    for pid, data in diff["pairs"].items():
        if float(data.get("stability_delta", 0.0)) < \
                -_PAIR_STABILITY_DROP_LIMIT:
            out.append(pid)
    out.sort()
    return out


def _winner_for_pair(x_name: str,
                      y_name: str,
                      diff: dict,
                      regressions: list) -> str:
    """Apply the locked winner formula. ``y`` wins when B is healthier
    than A net of anomalies + regression pressure. Ties (within
    ``_WINNER_EPSILON``) stay as ``"tie"`` for clean operator
    reporting."""
    health_delta  = float(diff["summary"]["health_delta"])
    anomaly_delta = float(diff["summary"]["anomaly_delta"])
    score = (
        health_delta
        - anomaly_delta
        - _PAIR_REGRESSION_WEIGHT * len(regressions)
    )
    if score > _WINNER_EPSILON:
        return y_name
    if score < -_WINNER_EPSILON:
        return x_name
    return _TIE


def _comparison_key(x: str, y: str) -> str:
    """Alpha-sorted ``"<x>_vs_<y>"`` so unordered pairs collapse to one
    canonical comparison key."""
    a, b = sorted((x, y))
    return f"{a}{_VS_INFIX}{b}"


def _build_groups_section(groups: dict) -> dict:
    """One Unit 19 gate evaluation per group, ordered alphabetically."""
    out: dict = {}
    for name in sorted(groups.keys()):
        gate = evaluate_release_gate(groups[name])
        out[name] = {
            "decision": gate["decision"],
            "reasons":  list(gate["reasons"]),
            "metrics":  dict(gate["metrics"]),
        }
    return out


def _build_comparisons_section(groups: dict) -> dict:
    """One pairwise diff per unordered group pair."""
    out: dict = {}
    names = sorted(groups.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x, y = names[i], names[j]
            diff = diff_intelligence(groups[x], groups[y])
            regressions = _pair_regressions(diff)
            out[_comparison_key(x, y)] = {
                "health_delta":     float(diff["summary"]["health_delta"]),
                "anomaly_delta":    float(diff["summary"]["anomaly_delta"]),
                "cluster_shift":    diff["summary"]["cluster_shift"],
                "trend_shift":      diff["summary"]["trend_shift"],
                "pair_regressions": regressions,
                "winner":           _winner_for_pair(x, y, diff, regressions),
            }
    return out


def evaluate_batch(groups) -> dict:
    """Evaluate a named-group mapping into per-group decisions plus
    pairwise comparisons.

    Args:
        groups: ``dict[str, list[str]]`` mapping group names to
            chronologically ordered run_ids. Empty groups are allowed
            (they receive ``decision="warn"`` /
            ``reasons=["insufficient_data"]`` via Unit 19's fall-back
            path).

    Returns:
        Locked-shape dict — see module docstring for the full schema.

    Raises:
        ValueError on a malformed groups mapping.
        FileNotFoundError if any referenced run does not exist.
    """
    _validate_groups(groups)
    return {
        "groups":      _build_groups_section(groups),
        "comparisons": _build_comparisons_section(groups),
    }
