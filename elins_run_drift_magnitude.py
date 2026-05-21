"""
elins_run_drift_magnitude.py — ELINS Unit 15.

Quantitative temporal drift: per-pair magnitude metrics across a
sequence of stored runs. Complements Unit 13's directional classifier
with the "how much" layer.

ROLE
----
Pure higher-order temporal analytic. For each pair_id present in
EVERY run, computes three numeric metrics per dimension (single_party,
economic_coercion):

    range     = max(scores) - min(scores)            (int)
    max_swing = max(|scores[i+1] - scores[i]|)        (int)
    mean_step = mean(|scores[i+1] - scores[i]|)       (float, rounded
                to 1 decimal place)

Pairs with missing or None scores in any run are skipped entirely.
Pairs with gaps (not in every run) are silently dropped — same
trajectory-completeness rule as Unit 13.

I/O CONTRACT
------------
``drift_magnitude`` is pure (no I/O). ``drift_magnitude_for_run_ids``
reads via the persistence layer; that's the only I/O. No logging, no
network, no LLM, no randomness.

PUBLIC API
----------
    drift_magnitude(runs) -> dict   (pure)
    drift_magnitude_for_run_ids(run_ids) -> dict  (loads via persistence)
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_diff import _normalise_run


# Locked field names (same constants as Unit 13).
_SP_FIELD: str = "single_party_score"
_EC_FIELD: str = "economic_coercion_score"

# Locked rounding precision for mean_step.
_MEAN_STEP_ROUND_DIGITS: int = 1


def _all_numeric(seq: list) -> bool:
    """True iff every value in `seq` is int/float (not bool, not None)."""
    for v in seq:
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
            return False
    return True


def _step_diffs(seq: list) -> list:
    """Return absolute differences between adjacent elements. For
    sequences of length < 2, returns []."""
    return [abs(seq[i + 1] - seq[i]) for i in range(len(seq) - 1)]


def _dimension_metrics(scores: list) -> dict:
    """Compute {range, max_swing, mean_step} for a single-dimension score
    series. Caller guarantees all values are numeric (`_all_numeric`)
    and at least 2 values are present.
    """
    rng = max(scores) - min(scores)
    diffs = _step_diffs(scores)
    if not diffs:
        # Defensive: caller ensures len(scores) >= 2, so diffs is
        # always non-empty. Keep this branch for safety.
        return {"range": 0, "max_swing": 0, "mean_step": 0.0}
    return {
        "range":     rng,
        "max_swing": max(diffs),
        "mean_step": round(sum(diffs) / len(diffs), _MEAN_STEP_ROUND_DIGITS),
    }


def drift_magnitude(runs: list) -> dict:
    """Pure quantitative drift analyser.

    Args:
        runs: list of stored-run payloads (Unit 5/8 dashboard shape).
            Must contain at least 2 runs.

    Returns:
        dict keyed alphabetically by pair_id. Each value is:

            {
              "single_party":      {"range": int, "max_swing": int,
                                    "mean_step": float},
              "economic_coercion": {"range": int, "max_swing": int,
                                    "mean_step": float}
            }

        Only pairs present in EVERY run with all-numeric scores in
        BOTH dimensions are included. Pairs with gaps or with any
        None / non-numeric / bool score are silently dropped.

    Raises:
        ValueError if `runs` is not a list, or contains fewer than 2
        runs (drift requires ≥ 2 points).
        ValueError if any run is malformed (propagated from
        Unit 11's _normalise_run).
    """
    if not isinstance(runs, list):
        raise ValueError(
            f"drift_magnitude expected a list of runs, got {type(runs).__name__}"
        )
    if len(runs) < 2:
        raise ValueError(
            f"drift_magnitude requires >= 2 runs, got {len(runs)}"
        )

    normalised: list = [_normalise_run(r) for r in runs]

    common_ids: set = set(normalised[0].keys())
    for run_map in normalised[1:]:
        common_ids &= set(run_map.keys())

    out: dict = {}
    for pid in sorted(common_ids):
        sp_scores = [run_map[pid].get(_SP_FIELD) for run_map in normalised]
        ec_scores = [run_map[pid].get(_EC_FIELD) for run_map in normalised]

        # Skip pair if any score in either dimension is missing/None/bool.
        if not _all_numeric(sp_scores) or not _all_numeric(ec_scores):
            continue

        out[pid] = {
            "single_party":      _dimension_metrics(sp_scores),
            "economic_coercion": _dimension_metrics(ec_scores),
        }

    return out


def drift_magnitude_for_run_ids(run_ids: list) -> dict:
    """Load a sequence of stored runs and compute drift magnitude.

    Args:
        run_ids: ordered list of run identifiers. Must contain at
            least 2 entries.

    Returns:
        Same shape as ``drift_magnitude``.

    Raises:
        ValueError if `run_ids` is not a list, has fewer than 2
            entries, or contains a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"drift_magnitude_for_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 2:
        raise ValueError(
            f"drift magnitude requires >= 2 runs, got {len(run_ids)}"
        )

    # Validate all ids BEFORE loading (defense against partial work).
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
    return drift_magnitude(runs)
