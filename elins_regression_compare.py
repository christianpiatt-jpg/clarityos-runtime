"""
elins_regression_compare.py — ELINS Unit 5.

Read-only analytical layer that runs both regression validators (Unit 1
single-party fear, Unit 4 economic coercion) and produces a structured
side-by-side comparison.

ROLE
----
This module compares regression OUTPUTS, not the underlying timeline
data. The two timelines live in different domains (political-fear vs
political-economy), have different field sets, and may have different
lengths or time indices. The comparison is a layer above the validators
and never tries to align or transform the raw inputs.

Pure, deterministic, side-effect-free.

PUBLIC API
----------
    compare_regressions(timeline_single_party, timeline_economic)
        -> RegressionComparisonResult

CONVENTIONS
-----------
    score_delta = economic_coercion_score - single_party_score
    band_delta  ∈ {"up", "down", "same"} — direction of the band ranking
                  (Strong > Acceptable > Weak > Fails core logic) for
                  economic coercion vs single-party fear.

NOT INCLUDED
------------
    Derived series (large; callers can fetch them via the per-regression
    validators directly).
"""
from __future__ import annotations

from dataclasses import dataclass

from elins_regression_economic_coercion import (
    SCORE_ACCEPTABLE_FLOOR,
    SCORE_STRONG_FLOOR,
    SCORE_WEAK_FLOOR,
    TimelineEconomic,
    run_economic_coercion_regression,
)
from elins_regression_single_party import (
    Timeline,
    run_single_party_fear_regression,
)


# Locked human-readable band labels (parallel to elins_timeline_dashboard
# but defined here too so the comparison module is independent of the
# dashboard wrapper).
_BAND_STRONG: str = "Strong"
_BAND_ACCEPTABLE: str = "Acceptable"
_BAND_WEAK: str = "Weak"
_BAND_FAILS: str = "Fails core logic"

# Locked band ranking: higher rank = better band. Used to compute the
# direction of band_delta.
_BAND_RANK: dict = {
    _BAND_FAILS:      0,
    _BAND_WEAK:       1,
    _BAND_ACCEPTABLE: 2,
    _BAND_STRONG:     3,
}

_BAND_DELTA_UP: str   = "up"
_BAND_DELTA_DOWN: str = "down"
_BAND_DELTA_SAME: str = "same"


# ===========================================================================
# Result schema
# ===========================================================================
@dataclass(frozen=True)
class RegressionComparisonResult:
    """Structured side-by-side comparison of the two regression outputs.

    Read-only. Carries scalar scores, score band labels, the direction
    of the band-rank delta, and pass-through assertion + scenario state
    from each regression. Derived series are intentionally omitted —
    callers that want them can run the validators directly.
    """
    single_party_score:               int
    economic_coercion_score:          int
    score_delta:                      int
    single_party_band:                str
    economic_coercion_band:           str
    band_delta:                       str   # "up" / "down" / "same"
    assertions_failed_single_party:   tuple
    assertions_failed_economic:       tuple
    scenario_results_single_party:    dict
    scenario_results_economic:        dict


# ===========================================================================
# Helpers
# ===========================================================================
def _band_for(score: int) -> str:
    """Pure mapping from a 0-10 score to a human-readable band label.

    Matches the Unit 1 / Unit 2 / Unit 4 thresholds exactly:
        9-10 → "Strong"
        7-8  → "Acceptable"
        5-6  → "Weak"
        0-4  → "Fails core logic"
    """
    if score >= SCORE_STRONG_FLOOR:
        return _BAND_STRONG
    if score >= SCORE_ACCEPTABLE_FLOOR:
        return _BAND_ACCEPTABLE
    if score >= SCORE_WEAK_FLOOR:
        return _BAND_WEAK
    return _BAND_FAILS


def _band_delta(sp_band: str, ec_band: str) -> str:
    """Direction of the economic-coercion band relative to the single-
    party band, using the locked _BAND_RANK ordering.

    Returns "up" / "down" / "same".
    """
    sp_rank = _BAND_RANK[sp_band]
    ec_rank = _BAND_RANK[ec_band]
    if ec_rank > sp_rank:
        return _BAND_DELTA_UP
    if ec_rank < sp_rank:
        return _BAND_DELTA_DOWN
    return _BAND_DELTA_SAME


# ===========================================================================
# Public API — compare_regressions
# ===========================================================================
def compare_regressions(
    timeline_single_party: Timeline,
    timeline_economic: TimelineEconomic,
) -> RegressionComparisonResult:
    """Pure comparison harness. Runs both regression validators on their
    respective timelines and returns a structured RegressionComparisonResult.

    Args:
        timeline_single_party: A Timeline (Unit 1 dataclass).
        timeline_economic:     A TimelineEconomic (Unit 4 dataclass).

    Returns:
        RegressionComparisonResult with scalar scores, band labels,
        score + band deltas, and pass-through assertion / scenario state.

    Raises:
        ValueError if either timeline is the wrong type (propagated from
        the underlying validators).

    Notes:
        * The two timelines may have different lengths and time indices.
          This module does NOT align them — it compares regression
          outputs only.
        * Empty timelines (Unit 3 convention) are accepted: each
          validator yields a vacuous score-0 result and the comparison
          reports score_delta=0, band_delta="same".
    """
    sp = run_single_party_fear_regression(timeline_single_party)
    ec = run_economic_coercion_regression(timeline_economic)

    sp_band = _band_for(sp.score)
    ec_band = _band_for(ec.score)

    return RegressionComparisonResult(
        single_party_score=sp.score,
        economic_coercion_score=ec.score,
        score_delta=ec.score - sp.score,
        single_party_band=sp_band,
        economic_coercion_band=ec_band,
        band_delta=_band_delta(sp_band, ec_band),
        assertions_failed_single_party=sp.assertions_failed,
        assertions_failed_economic=ec.assertions_failed,
        scenario_results_single_party=dict(sp.scenario_results),
        scenario_results_economic=dict(ec.scenario_results),
    )


def compare_regressions_batch(
    pairs: list,
) -> list:
    """Pure batch comparison harness — runs ``compare_regressions`` over
    each ``(Timeline, TimelineEconomic)`` pair and returns the results
    in input order.

    Args:
        pairs: list of 2-tuples (or 2-element sequences) where the
            first element is a Timeline and the second is a
            TimelineEconomic.

    Returns:
        list[RegressionComparisonResult] in the same order as ``pairs``.

    Raises:
        ValueError if `pairs` is not a list, if any entry is not a
        2-element tuple/sequence, or if either timeline in any pair
        is the wrong type (propagated from ``compare_regressions``).

    Notes:
        * Empty input list returns empty output list.
        * Pure: no I/O, no logging, no network, no LLM, no mutation.
        * Each pair is independent; a malformed late entry only fails
          when its position is reached during iteration. Callers that
          need transactional semantics should validate up front.
    """
    if not isinstance(pairs, list):
        raise ValueError(
            f"compare_regressions_batch expected a list of pairs, "
            f"got {type(pairs).__name__}"
        )

    out: list = []
    for i, pair in enumerate(pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(
                f"compare_regressions_batch: pairs[{i}] must be a "
                f"2-element tuple/list of (Timeline, TimelineEconomic)"
            )
        sp, ec = pair[0], pair[1]
        out.append(compare_regressions(sp, ec))
    return out
