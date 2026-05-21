"""
elins_run_summary_multi.py — ELINS Unit 18.

Cross-run aggregate summary: per-run summary tables side-by-side in a
single response, so dashboards do not have to fan out across multiple
endpoints.

Complements:
    * Unit 14 ``summary_table`` — single-run aggregate (delegated to)
    * Units 13/15/16 — multi-run drift / magnitude / severity
    * Unit 17       — multi-run per-pair time series

ROLE
----
Pure aggregator. For each ``(run_id, run)`` pair it delegates to
Unit 14's ``summary_table`` and indexes the result by ``run_id``.
Output keys are sorted alphabetically by ``run_id``.

I/O CONTRACT
------------
``summary_across_runs`` is pure (no I/O). ``summary_across_run_ids``
reads via the persistence layer; that's the only I/O. No logging, no
network, no LLM, no randomness.

PUBLIC API
----------
    summary_across_runs(runs) -> dict   (pure)
    summary_across_run_ids(run_ids) -> dict
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_summary import summary_table


def summary_across_runs(runs: list) -> dict:
    """Pure cross-run summary aggregator.

    Args:
        runs: list of ``(run_id, run_payload)`` pairs. Each pair must be
            a 2-element tuple or list. ``run_id`` must be a non-empty
            string; ``run_payload`` must be a list of dicts (the same
            shape Unit 14's ``summary_table`` accepts).

            An empty ``runs`` list is allowed and returns
            ``{"runs": {}}``.

    Returns:
        ``{"runs": {run_id: <summary_table output>, ...}}`` with the
        inner ``"runs"`` dict keyed alphabetically by ``run_id``.

    Raises:
        ValueError if ``runs`` is not a list, or if any element is not
        a 2-pair of (str, list), or if any inner ``summary_table`` call
        raises (e.g. malformed run payload).
    """
    if not isinstance(runs, list):
        raise ValueError(
            f"summary_across_runs expected a list of (run_id, run) pairs, "
            f"got {type(runs).__name__}"
        )

    # Validate each pair shape up-front so we fail fast on a bad input
    # without producing a partial output.
    cleaned: list = []
    for i, item in enumerate(runs):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(
                f"summary_across_runs: runs[{i}] must be a (run_id, run) "
                f"pair, got {type(item).__name__}"
            )
        rid, payload = item[0], item[1]
        if not isinstance(rid, str) or not rid:
            raise ValueError(
                f"summary_across_runs: runs[{i}][0] must be a non-empty "
                f"string run_id, got {type(rid).__name__}"
            )
        if not isinstance(payload, list):
            raise ValueError(
                f"summary_across_runs: runs[{i}][1] must be a list "
                f"(run payload), got {type(payload).__name__}"
            )
        cleaned.append((rid, payload))

    # Delegate per-run summarisation to Unit 14. Sort alphabetically by
    # run_id so output ordering is deterministic regardless of input
    # order. Duplicate run_ids overwrite (last one wins) — defensive,
    # not a spec'd error.
    by_id: dict = {}
    for rid, payload in cleaned:
        by_id[rid] = summary_table(payload)

    return {"runs": {rid: by_id[rid] for rid in sorted(by_id.keys())}}


def summary_across_run_ids(run_ids: list) -> dict:
    """Load a sequence of stored runs and return per-run summary tables.

    Args:
        run_ids: list of run identifiers. Must contain at least one
            entry; each id must satisfy the canonical run_id regex.

    Returns:
        Same shape as ``summary_across_runs``.

    Raises:
        ValueError if ``run_ids`` is not a list, is empty, or contains a
            malformed run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"summary_across_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 1:
        raise ValueError(
            "summary_across_run_ids requires >= 1 run_id, got 0"
        )

    # Validate all ids BEFORE loading (defense against partial work).
    for rid in run_ids:
        _validate_run_id(rid)

    # Unit 23: reorder run_ids by metadata.created_at so the loaded
    # (rid, payload) sequence is chronological. Legacy runs sort last;
    # ties broken alphabetically. (summary_across_runs sorts its OUTPUT
    # alphabetically by rid per the Unit 18 spec, so the visible "runs"
    # key order is unaffected — only the internal iteration changes.)
    from elins_run_ordering import sort_run_ids_by_timestamp
    run_ids = sort_run_ids_by_timestamp(run_ids)

    # Unit 19: load_comparison_result returns the {metadata, result}
    # envelope; analytics operate on the inner result list.
    pairs: list = [
        (rid, load_comparison_result(rid)["result"]) for rid in run_ids
    ]
    return summary_across_runs(pairs)
