"""
elins_cross_batch.py — ELINS8 Unit 23.

Cross-batch intelligence engine. Compares multiple Unit 21 batch
evaluations against each other and emits a structured cross-batch
comparison with deterministic winner verdicts.

ROLE
----
Operator-grade comparative reasoning across multiple ELINS7 batch
outputs. Pure composition over the existing intelligence stack — no
new heuristics, no I/O, fully deterministic.

INPUT
-----
``dict[str, dict]`` mapping batch names to Unit 21 ``evaluate_batch``
return values. Each value must carry the locked ``{groups, comparisons}``
shape. Empty batches and partial-overlap batch sets are tolerated.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "batches": {
        "<batch_name>": {
          "decision_counts":      {"allow": int, "warn": int, "block": int},
          "mean_health":          float,
          "mean_anomaly_fraction": float,
          "total_regressions":    int,
          "group_count":          int,
        },
        ...
      },
      "comparisons": {
        "<x>_vs_<y>": {                       # x and y alpha-sorted
          "group_wins":             {<x>: int, <y>: int, "ties": int},
          "decision_counts": {
            <x>: {"allow": int, "warn": int, "block": int},
            <y>: {"allow": int, "warn": int, "block": int},
          },
          "health_delta":           float,    # mean across common groups
          "anomaly_delta":          float,    # mean across common groups
          "regression_count_delta": int,      # total Δregressions (y - x)
          "winner":                 "<x> | <y> | tie",
        },
        ...
      },
    }

PUBLIC API
----------
    compare_batches(batches: dict[str, dict]) -> dict
"""
from __future__ import annotations


# Locked thresholds (mirror Unit 21).
_WINNER_EPSILON: float = 0.05
_PAIR_REGRESSION_WEIGHT: float = 0.1

_TIE: str = "tie"
_VS_INFIX: str = "_vs_"

_VALID_DECISIONS: tuple = ("allow", "warn", "block")


def _validate_batches(batches) -> None:
    if not isinstance(batches, dict):
        raise ValueError(
            f"compare_batches expected a dict, "
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
        if "groups" not in payload:
            raise ValueError(
                f"batches[{name!r}] missing 'groups' key — expected "
                f"a Unit 21 evaluate_batch output"
            )
        if not isinstance(payload["groups"], dict):
            raise ValueError(
                f"batches[{name!r}]['groups'] must be a dict"
            )


def _zero_decision_counts() -> dict:
    return {"allow": 0, "warn": 0, "block": 0}


def _batch_summary(payload: dict) -> dict:
    """Per-batch summary used in the ``batches`` section of the output."""
    groups = payload.get("groups", {})
    decision_counts = _zero_decision_counts()
    healths:    list = []
    anomalies:  list = []
    regressions: int = 0
    for data in groups.values():
        d = data.get("decision", "warn")
        if d in decision_counts:
            decision_counts[d] += 1
        metrics = data.get("metrics", {}) or {}
        healths.append(float(metrics.get("health", 0.0)))
        anomalies.append(float(metrics.get("anomaly_fraction", 0.0)))
        regressions += int(metrics.get("regressions", 0))
    return {
        "decision_counts":      decision_counts,
        "mean_health":          (
            sum(healths) / len(healths) if healths else 0.0
        ),
        "mean_anomaly_fraction": (
            sum(anomalies) / len(anomalies) if anomalies else 0.0
        ),
        "total_regressions":    regressions,
        "group_count":          len(groups),
    }


def _group_score_delta(x_metrics: dict, y_metrics: dict) -> tuple:
    """Return (health_delta, anomaly_delta, regression_delta) where
    each delta is ``y - x``. Mirrors Unit 21's score formula."""
    hx = float(x_metrics.get("health", 0.0))
    hy = float(y_metrics.get("health", 0.0))
    ax = float(x_metrics.get("anomaly_fraction", 0.0))
    ay = float(y_metrics.get("anomaly_fraction", 0.0))
    rx = int(x_metrics.get("regressions", 0))
    ry = int(y_metrics.get("regressions", 0))
    return (hy - hx, ay - ax, ry - rx)


def _classify_winner(x_name: str, y_name: str,
                     health_delta: float, anomaly_delta: float,
                     regression_delta: int) -> str:
    """Apply the locked winner formula. y wins when B is better than
    A net of anomalies + regression pressure."""
    score = (
        health_delta
        - anomaly_delta
        - _PAIR_REGRESSION_WEIGHT * regression_delta
    )
    if score > _WINNER_EPSILON:
        return y_name
    if score < -_WINNER_EPSILON:
        return x_name
    return _TIE


def _comparison_key(x: str, y: str) -> str:
    a, b = sorted((x, y))
    return f"{a}{_VS_INFIX}{b}"


def _decision_counts_for_groups(payload: dict, group_names: set) -> dict:
    """Decision counts restricted to the named subset of groups."""
    counts = _zero_decision_counts()
    groups = payload.get("groups", {})
    for name in group_names:
        data = groups.get(name)
        if not isinstance(data, dict):
            continue
        d = data.get("decision", "warn")
        if d in counts:
            counts[d] += 1
    return counts


def _pairwise_comparison(x_name: str, y_name: str,
                         x_payload: dict, y_payload: dict) -> dict:
    """Build one cross-batch comparison entry."""
    x_groups = x_payload.get("groups", {})
    y_groups = y_payload.get("groups", {})
    common = set(x_groups.keys()) & set(y_groups.keys())

    group_wins = {x_name: 0, y_name: 0, "ties": 0}
    health_sum:    float = 0.0
    anomaly_sum:   float = 0.0
    regression_sum: int = 0
    for group_name in sorted(common):
        x_metrics = x_groups[group_name].get("metrics", {}) or {}
        y_metrics = y_groups[group_name].get("metrics", {}) or {}
        h_d, a_d, r_d = _group_score_delta(x_metrics, y_metrics)
        health_sum    += h_d
        anomaly_sum   += a_d
        regression_sum += r_d
        winner = _classify_winner(x_name, y_name, h_d, a_d, r_d)
        if winner == x_name:
            group_wins[x_name] += 1
        elif winner == y_name:
            group_wins[y_name] += 1
        else:
            group_wins["ties"] += 1

    if common:
        mean_health  = health_sum  / len(common)
        mean_anomaly = anomaly_sum / len(common)
    else:
        mean_health  = 0.0
        mean_anomaly = 0.0

    overall_winner = _classify_winner(
        x_name, y_name, mean_health, mean_anomaly, regression_sum,
    )
    return {
        "group_wins":             group_wins,
        "decision_counts": {
            x_name: _decision_counts_for_groups(x_payload, common),
            y_name: _decision_counts_for_groups(y_payload, common),
        },
        "health_delta":           mean_health,
        "anomaly_delta":          mean_anomaly,
        "regression_count_delta": regression_sum,
        "winner":                 overall_winner,
    }


def compare_batches(batches) -> dict:
    """Cross-batch comparison engine.

    Args:
        batches: ``dict[str, dict]`` of batch_name → Unit 21
            ``evaluate_batch`` output. Empty dict returns the
            well-formed empty-comparison shape.

    Returns:
        Locked-shape dict — see module docstring for the full schema.

    Raises:
        ValueError on a malformed batches mapping.
    """
    _validate_batches(batches)

    batches_section: dict = {}
    for name in sorted(batches.keys()):
        batches_section[name] = _batch_summary(batches[name])

    comparisons_section: dict = {}
    names = sorted(batches.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x, y = names[i], names[j]
            comparisons_section[_comparison_key(x, y)] = (
                _pairwise_comparison(x, y, batches[x], batches[y])
            )

    return {
        "batches":     batches_section,
        "comparisons": comparisons_section,
    }
