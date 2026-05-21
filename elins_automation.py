"""
elins_automation.py — ELINS5 Unit 18.

Operator automation hooks. Three high-level helpers that compose the
ELINS intelligence stack into actionable workflows:

    1. auto_flag_regressions      — diff last 5 vs previous 5, tag flagged runs
    2. auto_promote_stable_pairs  — promote pairs meeting deep-stability criteria
    3. auto_generate_weekly_report — bundle Unit 9/13/14/15/16 outputs

ROLE
----
Bridge layer between intelligence (Units 9-16) and operator action
(Unit 12 tag mutators). Pure composition — no new heuristics — and
fully deterministic so the same run set always produces the same
report and the same tag mutations.

PUBLIC API
----------
    auto_flag_regressions(run_ids: list[str]) -> dict
    auto_promote_stable_pairs(run_ids: list[str]) -> dict
    auto_generate_weekly_report(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_alerts import generate_alerts
from elins_feed import build_intelligence_feed, feed_entry_for_run
from elins_intel_diff import diff_intelligence
from elins_intelligence import intelligence_for_run_ids
from elins_pair_deep import pair_deep_all
from elins_persistence import (
    _validate_run_id,
    get_tags,
    load_comparison_result,
    set_tags,
)
from elins_timeline import build_intelligence_timeline


# Locked tag vocabulary (mirror Unit 12).
TAG_REGRESSION_FLAG: str = "regression_flag"
TAG_STABLE_PAIR:     str = "stable_pair"

# Regression-detection thresholds.
_REGRESSION_WINDOW:           int   = 5
_PAIR_STABILITY_DROP_LIMIT:   float = 0.20

# Stable-pair promotion thresholds.
_STABLE_PAIR_STABILITY_MIN:   float = 0.85
_STABLE_PAIR_VOLATILITY_MAX:  float = 0.10
_STABLE_PAIR_TREND_VOCAB:     tuple = ("upward", "flat")


def _validate_run_ids(run_ids, fn_name: str) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"{fn_name} expected a list, got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _append_tag(run_id: str, tag: str) -> bool:
    """Dedupe-aware tag append. Returns True when the run was mutated."""
    existing = get_tags(run_id)
    if tag in existing:
        return False
    set_tags(run_id, existing + [tag])
    return True


# ===========================================================================
# 1. auto_flag_regressions
# ===========================================================================
def _regression_split(run_ids: list) -> tuple:
    """Return the (previous, last) halves used for the regression diff.

    Default window is 5; if the input is shorter we use the largest
    symmetric split available. With fewer than 2 runs no comparison
    is possible.
    """
    n = len(run_ids)
    if n < 2:
        return [], []
    window = min(_REGRESSION_WINDOW, n // 2)
    if window < 1:
        window = 1
    last = run_ids[-window:]
    previous = run_ids[-2 * window:-window]
    return previous, last


def _has_regression_signal(diff: dict) -> bool:
    """True when the diff carries any of the regression signals the
    spec defines:
        * cluster_shift == "more_downward"
        * trend_shift   == "toward_volatility"
        * any pair stability_delta < -_PAIR_STABILITY_DROP_LIMIT
    """
    summary = diff["summary"]
    if summary["cluster_shift"] == "more_downward":
        return True
    if summary["trend_shift"] == "toward_volatility":
        return True
    for pid, data in diff["pairs"].items():
        if float(data.get("stability_delta", 0.0)) < -_PAIR_STABILITY_DROP_LIMIT:
            return True
    return False


def auto_flag_regressions(run_ids) -> dict:
    """Diff the last ``_REGRESSION_WINDOW`` runs against the preceding
    window and, if any regression signal fires, apply
    ``"regression_flag"`` to every run in the "last" window.

    Args:
        run_ids: chronologically ordered run_ids.

    Returns:
        ``{"flagged": [<rid>, ...], "skipped": [<rid>, ...]}`` —
        ``flagged`` is the runs that received the tag (sorted alpha),
        ``skipped`` covers the rest of the input.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "auto_flag_regressions")
    if not run_ids:
        return {"flagged": [], "skipped": []}

    previous, last = _regression_split(run_ids)
    if not previous or not last:
        # Not enough runs to diff — every run is skipped.
        return {"flagged": [], "skipped": sorted(run_ids)}

    diff = diff_intelligence(previous, last)
    flagged: list = []
    skipped: list = []
    if _has_regression_signal(diff):
        target_set = set(last)
        for rid in run_ids:
            if rid in target_set:
                mutated = _append_tag(rid, TAG_REGRESSION_FLAG)
                (flagged if mutated else skipped).append(rid)
            else:
                skipped.append(rid)
    else:
        skipped = list(run_ids)

    flagged.sort()
    skipped.sort()
    return {"flagged": flagged, "skipped": skipped}


# ===========================================================================
# 2. auto_promote_stable_pairs
# ===========================================================================
def _pair_meets_stable_criteria(trajectory: dict) -> bool:
    if float(trajectory.get("stability_score", 0.0)) <= \
            _STABLE_PAIR_STABILITY_MIN:
        return False
    if float(trajectory.get("volatility_score", 1.0)) >= \
            _STABLE_PAIR_VOLATILITY_MAX:
        return False
    if trajectory.get("trend_direction", "flat") not in \
            _STABLE_PAIR_TREND_VOCAB:
        return False
    return True


def _runs_containing_pair(run_ids: list, pair_id: str) -> list:
    """Return the subset of `run_ids` whose envelope includes a pair
    entry for `pair_id`. Used to locate the runs that should receive
    the ``stable_pair`` tag when a pair gets promoted."""
    out: list = []
    for rid in run_ids:
        env = load_comparison_result(rid)
        payload = env.get("result")
        if not isinstance(payload, list):
            continue
        for entry in payload:
            if isinstance(entry, dict) and entry.get("pair_id") == pair_id:
                out.append(rid)
                break
    return out


def auto_promote_stable_pairs(run_ids) -> dict:
    """Identify pairs that meet the deep-stability criteria and tag
    the runs containing them with ``"stable_pair"``.

    Criteria (locked):
        stability_score   > 0.85
        volatility_score  < 0.10
        trend_direction   in {"upward", "flat"}

    Args:
        run_ids: chronologically ordered run_ids.

    Returns:
        ``{
            "promoted": [<pair_id>, ...],  # alphabetical
            "tagged_runs": [<rid>, ...],   # runs that received the tag
        }``

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "auto_promote_stable_pairs")
    if not run_ids:
        return {"promoted": [], "tagged_runs": []}

    deep = pair_deep_all(run_ids)
    promoted: list = []
    tagged_run_set: set = set()
    for pid, data in deep["pairs"].items():
        if _pair_meets_stable_criteria(data["trajectory"]):
            promoted.append(pid)
            for rid in _runs_containing_pair(run_ids, pid):
                if _append_tag(rid, TAG_STABLE_PAIR):
                    tagged_run_set.add(rid)
    promoted.sort()
    return {
        "promoted":    promoted,
        "tagged_runs": sorted(tagged_run_set),
    }


# ===========================================================================
# 3. auto_generate_weekly_report
# ===========================================================================
def _empty_weekly_report() -> dict:
    return {
        "headline":  "No runs available for this period.",
        "health":    0.0,
        "anomalies": {"runs": {}, "thresholds": {"high": 0.7, "medium": 0.4}},
        "trends":    {"sequence": {
            "trend": "insufficient_data", "slope": 0.0,
            "volatility": 0.0, "score": 0.0, "run_ids": [],
        }, "pairs": {}},
        "clusters":  {
            "assignments": {}, "cluster_summary": {},
            "cluster_centroids": {}, "silhouette": None, "k": 0,
        },
        "pairs":     {"pairs": {}, "run_ids": []},
        "alerts":    [],
        "timeline":  [],
        "diff":      None,
    }


def auto_generate_weekly_report(run_ids) -> dict:
    """Bundle Units 9 / 13 / 14 / 15 / 16 into a single structured
    weekly report.

    The diff section compares the first half of `run_ids` against the
    second half (mid = ``len(run_ids) // 2``). With fewer than 2
    runs ``diff`` is ``None``.

    Args:
        run_ids: chronologically ordered run_ids.

    Returns:
        Locked-shape dict with keys ``headline``, ``health``,
        ``anomalies``, ``trends``, ``clusters``, ``pairs``,
        ``alerts``, ``timeline``, ``diff``. Empty input returns the
        well-formed empty-report shape.

    Raises:
        ValueError on a malformed run_ids list.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids, "auto_generate_weekly_report")
    if not run_ids:
        return _empty_weekly_report()

    intel    = intelligence_for_run_ids(run_ids)
    timeline = build_intelligence_timeline(run_ids)
    alerts   = generate_alerts(run_ids)
    pairs    = pair_deep_all(run_ids)

    diff = None
    if len(run_ids) >= 2:
        mid = len(run_ids) // 2
        a_ids = run_ids[:mid]
        b_ids = run_ids[mid:]
        diff = diff_intelligence(a_ids, b_ids)

    headline = (
        intel.get("narratives", {})
             .get("runs", {})
             .get("headline", "")
    )

    return {
        "headline":  headline,
        "health":    intel["scores"]["overall_health"],
        "anomalies": intel["anomalies"],
        "trends":    intel["trends"],
        "clusters":  intel["clustering"],
        "pairs":     pairs,
        "alerts":    alerts["alerts"],
        "timeline":  timeline["timeline"],
        "diff":      diff,
    }
