"""
elins_run_composite.py — ELINS Unit 22.

One-shot composite analytics endpoint backing
``POST /elins/regression/run/composite``. Returns metadata + the entire
analytic surface for a run (or run sequence) in a single response.

WHY
---
Dashboards previously had to fan out across:
    * GET  /elins/regression/run/{rid}/metadata        (Unit 19)
    * GET  /elins/regression/run/{rid}/summary         (Unit 14)
    * POST /elins/regression/runs/summary              (Unit 18)
    * POST /elins/regression/drift                     (Unit 13)
    * POST /elins/regression/drift/magnitude           (Unit 15)
    * POST /elins/regression/drift/severity            (Unit 16)
    * POST /elins/regression/drift/series              (Unit 17)

Unit 22 collapses all of the above into one round-trip with a
consistent shape, sharing a single load pass per run.

RESPONSE SHAPE
--------------
Single run (len(run_ids) == 1)::

    {
      "run_ids":  ["r"],
      "metadata": [<dict or None>],
      "summary":  {<Unit 14 single-run summary table>}
    }

Multi run (len(run_ids) >= 2)::

    {
      "run_ids":   [r1, r2, ...],
      "metadata":  [<dict or None>, ...],
      "summary":   {<Unit 18 cross-run summary>},
      "direction": {<Unit 13 drift buckets>},
      "magnitude": {<Unit 15 per-pair magnitude>},
      "severity":  {<Unit 16 per-pair severity>},
      "series":    {<Unit 17 per-pair time series>}
    }

The four pair-keyed sections (direction / magnitude / severity / series)
respect Unit 21 filtering when called via ``composite_endpoint_wrapper``.
``summary`` is intentionally never filtered.

I/O CONTRACT
------------
``composite_for_run_ids`` reads each requested run exactly once via
``elins_persistence.load_comparison_result``. Analytics are then
computed from those in-memory result lists by the existing pure
analytics primitives (no re-loads).

The internal ``_compose`` helper is fully pure — it operates on
already-loaded data and is used by both the public functions and the
tests for byte-equal verification.

PUBLIC API
----------
    composite_for_run_ids(run_ids) -> dict
    composite_endpoint_wrapper(run_ids, prefix, limit, offset) -> dict
"""
from __future__ import annotations

from elins_pair_filtering import (
    apply_pair_filters,
    apply_pair_filters_to_drift,
    validate_pair_filters,
)
from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_drift import detect_drift
from elins_run_drift_magnitude import drift_magnitude
from elins_run_drift_series import drift_series
from elins_run_drift_severity import classify_drift_severity
from elins_run_summary import summary_table
from elins_run_summary_multi import summary_across_runs


# Locked top-level keys (multi-run mode includes all six; single-run
# mode includes only the first three).
_KEY_RUN_IDS:   str = "run_ids"
_KEY_METADATA:  str = "metadata"
_KEY_SUMMARY:   str = "summary"
_KEY_DIRECTION: str = "direction"
_KEY_MAGNITUDE: str = "magnitude"
_KEY_SEVERITY:  str = "severity"
_KEY_SERIES:    str = "series"


def _compose(run_ids: list, metadata_list: list, results: list) -> dict:
    """Pure composer. Builds the composite dict from already-loaded
    data — no I/O, no re-loads, no validation of run_ids (caller has
    already done that).

    For len(run_ids) == 1 returns the single-run shape (summary only);
    for len(run_ids) >= 2 returns the multi-run shape.
    """
    out: dict = {
        _KEY_RUN_IDS:  list(run_ids),
        _KEY_METADATA: list(metadata_list),
    }
    if len(run_ids) == 1:
        out[_KEY_SUMMARY] = summary_table(results[0])
        return out

    # Multi-run mode.
    out[_KEY_SUMMARY] = summary_across_runs(
        [(rid, res) for rid, res in zip(run_ids, results)]
    )
    direction = detect_drift(results)
    magnitude = drift_magnitude(results)
    severity  = classify_drift_severity(direction, magnitude)
    series    = drift_series(results)
    out[_KEY_DIRECTION] = direction
    out[_KEY_MAGNITUDE] = magnitude
    out[_KEY_SEVERITY]  = severity
    out[_KEY_SERIES]    = series
    return out


def composite_for_run_ids(run_ids) -> dict:
    """Load each run once and return the composite analytics dict.

    Args:
        run_ids: list of validated run identifiers. Must contain at
            least 1 entry.

    Returns:
        Composite dict (see module docstring for shape). Pair-keyed
        sections are unfiltered — wrap in ``composite_endpoint_wrapper``
        to apply Unit 21 filtering.

    Raises:
        ValueError if `run_ids` is not a list, is empty, or contains a
            malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"composite_for_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 1:
        raise ValueError(
            "composite_for_run_ids requires >= 1 run_id, got 0"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    # Unit 23: reorder run_ids by metadata.created_at so the composite
    # operates on a true chronological sequence. The returned ``run_ids``
    # and ``metadata`` fields reflect the sorted order so dashboards
    # render index-aligned data. Legacy runs sort last; ties broken
    # alphabetically.
    from elins_run_ordering import sort_run_ids_by_timestamp
    run_ids = sort_run_ids_by_timestamp(run_ids)

    envelopes = [load_comparison_result(rid) for rid in run_ids]
    metadata_list = [env.get("metadata") for env in envelopes]
    results       = [env.get("result")   for env in envelopes]
    return _compose(run_ids, metadata_list, results)


def composite_endpoint_wrapper(
    run_ids,
    pair_id_prefix=None,
    limit=None,
    offset=None,
) -> dict:
    """Compute the composite for `run_ids` and apply Unit 21 filtering
    to the four pair-keyed sections.

    ``summary`` is intentionally never filtered — it's an aggregate
    across the whole run, and dashboards rely on it for true counts.

    Args:
        run_ids: ordered list of run identifiers.
        pair_id_prefix, limit, offset: see
            ``elins_pair_filtering.validate_pair_filters``.

    Returns:
        Composite dict with the four pair-keyed sections sliced per the
        filter parameters. Single-run composites pass through unchanged
        (no pair-keyed sections to filter).

    Raises:
        ValueError on a malformed filter input or run_id.
        FileNotFoundError if any run does not exist.
    """
    # Validate filter inputs cheaply, BEFORE we pay for the load.
    validate_pair_filters(pair_id_prefix, limit, offset)

    composite = composite_for_run_ids(run_ids)

    if _KEY_DIRECTION in composite:
        composite[_KEY_DIRECTION] = apply_pair_filters_to_drift(
            composite[_KEY_DIRECTION], pair_id_prefix, limit, offset,
        )
    if _KEY_MAGNITUDE in composite:
        composite[_KEY_MAGNITUDE] = apply_pair_filters(
            composite[_KEY_MAGNITUDE], pair_id_prefix, limit, offset,
        )
    if _KEY_SEVERITY in composite:
        composite[_KEY_SEVERITY] = apply_pair_filters(
            composite[_KEY_SEVERITY], pair_id_prefix, limit, offset,
        )
    if _KEY_SERIES in composite:
        composite[_KEY_SERIES] = apply_pair_filters(
            composite[_KEY_SERIES], pair_id_prefix, limit, offset,
        )
    return composite
