"""
elins_run_drift_series.py — ELINS Unit 17.

Per-pair time-series export across a sequence of runs. Surfaces the
raw underlying data that Units 13/15/16 derive their classifications
from, enabling sparkline / trend-line visualisation in dashboards.

ROLE
----
Pure data exporter. No classification, no aggregation — just the raw
SP/EC score and band series across the run sequence in caller-supplied
chronological order.

PER-PAIR OUTPUT
---------------
For each pair_id present in EVERY run with all-numeric scores AND
present bands in BOTH dimensions:

    {
      "single_party_scores":      [int, ...],   # length == len(runs)
      "economic_coercion_scores": [int, ...],
      "single_party_bands":       [str, ...],
      "economic_coercion_bands":  [str, ...]
    }

Pairs with gaps (missing from some runs) are silently dropped — same
trajectory-completeness rule as Units 13/15/16. Pairs with any
None/non-numeric/bool score in any run, or any missing/non-string
band in any run, are also dropped (defensive).

I/O CONTRACT
------------
``drift_series`` is pure (no I/O). ``drift_series_for_run_ids`` reads
via the persistence layer; that's the only I/O. No logging, no
network, no LLM, no randomness.

PUBLIC API
----------
    drift_series(runs) -> dict   (pure)
    drift_series_for_run_ids(run_ids) -> dict
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_diff import _normalise_run


# Locked field names extracted from each entry.
_SP_SCORE_FIELD: str = "single_party_score"
_EC_SCORE_FIELD: str = "economic_coercion_score"
_SP_BAND_FIELD: str = "single_party_band"
_EC_BAND_FIELD: str = "economic_coercion_band"


def _is_clean_numeric(v) -> bool:
    """True iff `v` is int/float (not bool, not None, not string)."""
    return (
        v is not None
        and not isinstance(v, bool)
        and isinstance(v, (int, float))
    )


def _is_clean_band(v) -> bool:
    """True iff `v` is a non-empty string."""
    return isinstance(v, str) and bool(v)


def drift_series(runs: list) -> dict:
    """Pure per-pair time-series exporter.

    Args:
        runs: list of stored-run payloads (Unit 5/8 dashboard shape),
            in chronological order. Must contain at least 2 runs.

    Returns:
        dict keyed alphabetically by pair_id. Each value is:

            {
              "single_party_scores":      [int, ...],
              "economic_coercion_scores": [int, ...],
              "single_party_bands":       [str, ...],
              "economic_coercion_bands":  [str, ...]
            }

        Each series has length == len(runs), in run order.

        Only pairs present in EVERY run with clean scores AND clean
        bands in BOTH dimensions are included. Pairs with any gap,
        any None/non-numeric/bool score, or any missing/non-string
        band are silently dropped.

    Raises:
        ValueError if `runs` is not a list, or contains fewer than 2
        runs.
        ValueError if any run is malformed (propagated from
        Unit 11's _normalise_run).
    """
    if not isinstance(runs, list):
        raise ValueError(
            f"drift_series expected a list of runs, got {type(runs).__name__}"
        )
    if len(runs) < 2:
        raise ValueError(
            f"drift_series requires >= 2 runs, got {len(runs)}"
        )

    normalised: list = [_normalise_run(r) for r in runs]

    common_ids: set = set(normalised[0].keys())
    for run_map in normalised[1:]:
        common_ids &= set(run_map.keys())

    out: dict = {}
    for pid in sorted(common_ids):
        sp_scores = [run_map[pid].get(_SP_SCORE_FIELD) for run_map in normalised]
        ec_scores = [run_map[pid].get(_EC_SCORE_FIELD) for run_map in normalised]
        sp_bands  = [run_map[pid].get(_SP_BAND_FIELD)  for run_map in normalised]
        ec_bands  = [run_map[pid].get(_EC_BAND_FIELD)  for run_map in normalised]

        if not all(_is_clean_numeric(v) for v in sp_scores):
            continue
        if not all(_is_clean_numeric(v) for v in ec_scores):
            continue
        if not all(_is_clean_band(v) for v in sp_bands):
            continue
        if not all(_is_clean_band(v) for v in ec_bands):
            continue

        out[pid] = {
            "single_party_scores":      list(sp_scores),
            "economic_coercion_scores": list(ec_scores),
            "single_party_bands":       list(sp_bands),
            "economic_coercion_bands":  list(ec_bands),
        }

    return out


def drift_series_for_run_ids(run_ids: list) -> dict:
    """Load a sequence of stored runs and return per-pair time series.

    Args:
        run_ids: ordered list of run identifiers (chronological).
            Must contain at least 2 entries.

    Returns:
        Same shape as ``drift_series``.

    Raises:
        ValueError if `run_ids` is not a list, has fewer than 2
            entries, or contains a malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"drift_series_for_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 2:
        raise ValueError(
            f"drift series requires >= 2 runs, got {len(run_ids)}"
        )

    # Validate all ids BEFORE loading (defense against partial work).
    for rid in run_ids:
        _validate_run_id(rid)

    # Unit 23: reorder run_ids by metadata.created_at so series elements
    # always come back in true chronological order regardless of caller
    # order. Legacy runs sort last; ties broken alphabetically.
    from elins_run_ordering import sort_run_ids_by_timestamp
    run_ids = sort_run_ids_by_timestamp(run_ids)

    # Unit 19: load_comparison_result returns the {metadata, result}
    # envelope; analytics operate on the inner result list.
    runs: list = [load_comparison_result(rid)["result"] for rid in run_ids]
    return drift_series(runs)
