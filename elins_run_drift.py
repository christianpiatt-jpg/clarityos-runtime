"""
elins_run_drift.py — ELINS Unit 13.

Multi-run drift detection: classifies each pair_id's trajectory across
a sequence of stored runs as ``stable`` / ``trending_up`` /
``trending_down`` / ``volatile``.

ROLE
----
Pure higher-order temporal analytic. Builds on Unit 11's per-pair
identity convention: each entry must carry a ``pair_id`` (composite
``sp_id::ec_id``); legacy entries without one fall back to ``pos_<i>``
via the same normalisation Unit 11 uses.

Classification operates only on pairs present in EVERY run. Pairs with
gaps (present in some runs but not others) are silently dropped from
output — drift is a trajectory metric, and trajectories require
continuous data. Use Unit 11's diff engine for added/removed detection.

CLASSIFICATION RULES (per pair_id)
----------------------------------
Let ``sp = [sp_score_run_0, sp_score_run_1, ...]`` and similarly for
``ec``. Both lists have length == len(runs).

    stable        : all SP scores identical AND all EC scores identical
    trending_up   : (SP strictly increasing OR EC strictly increasing)
                    AND NOT SP strictly decreasing
                    AND NOT EC strictly decreasing
    trending_down : (SP strictly decreasing OR EC strictly decreasing)
                    AND NOT SP strictly increasing
                    AND NOT EC strictly increasing
    volatile      : anything else (mixed directions, oscillation,
                    flat-then-up, partial monotonicity, etc.)

"Strictly increasing" means every adjacent pair s[i] < s[i+1] (no
equal-adjacent values count). Same for strictly decreasing.

I/O CONTRACT
------------
``detect_drift`` is pure (no I/O). ``detect_drift_for_run_ids`` reads
via the persistence layer; that's the only I/O in this module. No
logging, no network, no LLM, no randomness.

PUBLIC API
----------
    detect_drift(runs) -> dict   (pure)
    detect_drift_for_run_ids(run_ids) -> dict  (loads via persistence)
"""
from __future__ import annotations

# Import the same normalisation helper used by Unit 11 — keeps
# pair_id semantics consistent across diff and drift.
from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_diff import _normalise_run


# Locked classification labels.
_LABEL_STABLE: str = "stable"
_LABEL_UP: str = "trending_up"
_LABEL_DOWN: str = "trending_down"
_LABEL_VOLATILE: str = "volatile"

# Locked field names extracted from each entry for classification.
_SP_FIELD: str = "single_party_score"
_EC_FIELD: str = "economic_coercion_score"


def _strictly_increasing(seq: list) -> bool:
    """True iff every adjacent pair satisfies s[i] < s[i+1]."""
    for i in range(len(seq) - 1):
        if not (seq[i] < seq[i + 1]):
            return False
    return True


def _strictly_decreasing(seq: list) -> bool:
    """True iff every adjacent pair satisfies s[i] > s[i+1]."""
    for i in range(len(seq) - 1):
        if not (seq[i] > seq[i + 1]):
            return False
    return True


def _all_identical(seq: list) -> bool:
    """True iff every value in the sequence equals the first."""
    if not seq:
        return True
    first = seq[0]
    for v in seq[1:]:
        if v != first:
            return False
    return True


def _classify_pair(sp_scores: list, ec_scores: list) -> str:
    """Apply the four-way drift rules to one pair's score series.

    Returns one of: ``stable`` / ``trending_up`` / ``trending_down`` /
    ``volatile``. If any score is None (incomplete data), classifies
    as ``volatile`` defensively.
    """
    if any(s is None for s in sp_scores) or any(s is None for s in ec_scores):
        return _LABEL_VOLATILE

    sp_const = _all_identical(sp_scores)
    ec_const = _all_identical(ec_scores)
    if sp_const and ec_const:
        return _LABEL_STABLE

    sp_inc = _strictly_increasing(sp_scores)
    sp_dec = _strictly_decreasing(sp_scores)
    ec_inc = _strictly_increasing(ec_scores)
    ec_dec = _strictly_decreasing(ec_scores)

    if (sp_inc or ec_inc) and not sp_dec and not ec_dec:
        return _LABEL_UP
    if (sp_dec or ec_dec) and not sp_inc and not ec_inc:
        return _LABEL_DOWN
    return _LABEL_VOLATILE


def detect_drift(runs: list) -> dict:
    """Pure multi-run drift classifier.

    Args:
        runs: list of stored-run payloads. Each run is a list[dict]
            (the shape produced by Unit 5/8 dashboard wrappers and
            persisted by Unit 10). Must contain at least 2 runs.

    Returns:
        dict with:
            * stable:        list[str] — pair_ids with no movement
            * trending_up:   list[str] — monotonic up trajectory
            * trending_down: list[str] — monotonic down trajectory
            * volatile:      list[str] — everything else
            * summary:       dict[str, int] — counts per label

    All four pair_id lists are sorted alphabetically. Only pairs
    present in EVERY run are classified; pairs with gaps are silently
    dropped from the output.

    Raises:
        ValueError if `runs` is not a list or contains fewer than 2 runs.
        ValueError if any run is malformed (propagated from
        Unit 11's _normalise_run).
    """
    if not isinstance(runs, list):
        raise ValueError(
            f"detect_drift expected a list of runs, got {type(runs).__name__}"
        )
    if len(runs) < 2:
        raise ValueError(
            f"detect_drift requires >= 2 runs, got {len(runs)}"
        )

    # Normalise each run to {pair_id: entry} via the same helper Unit
    # 11 uses — keeps pair_id semantics consistent across diff/drift.
    normalised: list = [_normalise_run(r) for r in runs]

    # Classify only pairs present in every run.
    common_ids: set = set(normalised[0].keys())
    for run_map in normalised[1:]:
        common_ids &= set(run_map.keys())

    buckets: dict = {
        _LABEL_STABLE:   [],
        _LABEL_UP:       [],
        _LABEL_DOWN:     [],
        _LABEL_VOLATILE: [],
    }
    for pid in sorted(common_ids):
        sp_scores = [run_map[pid].get(_SP_FIELD) for run_map in normalised]
        ec_scores = [run_map[pid].get(_EC_FIELD) for run_map in normalised]
        label = _classify_pair(sp_scores, ec_scores)
        buckets[label].append(pid)

    return {
        _LABEL_STABLE:   buckets[_LABEL_STABLE],
        _LABEL_UP:       buckets[_LABEL_UP],
        _LABEL_DOWN:     buckets[_LABEL_DOWN],
        _LABEL_VOLATILE: buckets[_LABEL_VOLATILE],
        "summary": {
            _LABEL_STABLE:   len(buckets[_LABEL_STABLE]),
            _LABEL_UP:       len(buckets[_LABEL_UP]),
            _LABEL_DOWN:     len(buckets[_LABEL_DOWN]),
            _LABEL_VOLATILE: len(buckets[_LABEL_VOLATILE]),
        },
    }


def detect_drift_for_run_ids(run_ids: list) -> dict:
    """Load a sequence of stored runs and compute drift classification.

    Args:
        run_ids: ordered list of run identifiers. The runs are loaded
            in this order, so a chronological order produces a
            chronological trajectory.

    Returns:
        Same shape as ``detect_drift``.

    Raises:
        ValueError if `run_ids` is not a list, has fewer than 2 entries,
            or contains a malformed run_id (propagated from
            persistence).
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"detect_drift_for_run_ids expected a list of run_ids, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 2:
        raise ValueError(
            f"drift requires >= 2 runs, got {len(run_ids)}"
        )

    # Validate each id BEFORE loading, so a malformed id at the end
    # doesn't waste effort loading the earlier runs.
    for rid in run_ids:
        _validate_run_id(rid)

    # Unit 23: reorder run_ids by metadata.created_at so multi-run
    # analytics always operate in true chronological order regardless
    # of caller order. Legacy runs sort last; ties broken alphabetically.
    from elins_run_ordering import sort_run_ids_by_timestamp
    run_ids = sort_run_ids_by_timestamp(run_ids)

    # Unit 19: load_comparison_result returns the {metadata, result}
    # envelope; analytics operate on the inner result list.
    runs: list = [load_comparison_result(rid)["result"] for rid in run_ids]
    return detect_drift(runs)
