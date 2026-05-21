"""
elins_run_diff.py — ELINS Unit 11.

Run-to-run diff engine: compares two stored regression-run payloads and
reports added / removed / changed / unchanged pairs.

ROLE
----
Pure analytic primitive. Does not store, fetch, or transform; just
diffs two list-of-dict payloads (the shape produced by the Unit 5/8
dashboard wrappers and persisted by Unit 10).

KEY: ``pair_id``
----------------
Each entry must carry a stable ``pair_id`` (added in Unit 11). For
legacy stored runs that pre-date Unit 11 and lack the field, the diff
engine falls back to a synthesized positional id of the form
``"pos_<index>"``. This means a fresh-run vs legacy-run diff will
treat *every* fresh entry as "added" and every legacy entry as
"removed" unless the operator manually re-runs the legacy data with
the new wrapper.

CHANGE DETECTION
----------------
Two entries with the same ``pair_id`` are flagged "changed" if any of
these six fields differ:
    * single_party_score
    * economic_coercion_score
    * single_party_band
    * economic_coercion_band
    * score_delta
    * band_delta
``assertions_failed_*`` and ``scenario_results_*`` are intentionally
not part of the change-detection set — they are downstream details,
not the headline state being tracked.

I/O CONTRACT
------------
``compare_runs`` is pure (no I/O). ``diff_runs`` reads via the
persistence layer; that's the only I/O in this module. No logging,
no network, no LLM, no randomness.

PUBLIC API
----------
    compare_runs(run_a, run_b) -> dict   (pure)
    diff_runs(run_id_a, run_id_b) -> dict (loads via persistence)
"""
from __future__ import annotations

from elins_persistence import load_comparison_result


# Locked field set used for change detection. Any addition is a
# deliberate spec change.
_CHANGE_FIELDS: tuple = (
    "single_party_score",
    "economic_coercion_score",
    "single_party_band",
    "economic_coercion_band",
    "score_delta",
    "band_delta",
)


def _normalise_run(run) -> dict:
    """Build ``{pair_id: entry}`` from a stored run, synthesising
    ``pos_<i>`` ids for any legacy entry missing ``pair_id``.

    Raises:
        ValueError if `run` is not a list, or if a list element is not
        a dict.
    """
    if not isinstance(run, list):
        raise ValueError(
            f"compare_runs expected a list payload, got {type(run).__name__}"
        )
    out: dict = {}
    for i, entry in enumerate(run):
        if not isinstance(entry, dict):
            raise ValueError(
                f"compare_runs: run[{i}] is not a dict (got {type(entry).__name__})"
            )
        pid = entry.get("pair_id")
        if not isinstance(pid, str) or not pid:
            pid = f"pos_{i}"
        # If two entries collide on the same pair_id within one run,
        # keep the first occurrence — duplicates are out-of-contract
        # but we don't crash on them.
        out.setdefault(pid, entry)
    return out


def _entries_changed(a_entry: dict, b_entry: dict) -> bool:
    """True iff any of the six change-detection fields differ between
    the two entries. Missing fields compare as None on both sides."""
    for fname in _CHANGE_FIELDS:
        if a_entry.get(fname) != b_entry.get(fname):
            return True
    return False


def compare_runs(run_a, run_b) -> dict:
    """Pure run-to-run diff over two stored payloads.

    Args:
        run_a: list[dict] — earlier run payload.
        run_b: list[dict] — later run payload.

    Returns:
        dict with:
            * added:     list[str]  — pair_ids in B not in A
            * removed:   list[str]  — pair_ids in A not in B
            * changed:   list[dict] — per-pair before/after entries
            * unchanged: list[str]  — pair_ids identical in both
            * summary:   dict[str, int] — counts for each above

    Ordering: alphabetical by pair_id throughout (added, removed,
    unchanged are sorted lists; changed entries are sorted by pair_id).

    Raises:
        ValueError if either run is not a list, or if any list element
        is not a dict.
    """
    a_map = _normalise_run(run_a)
    b_map = _normalise_run(run_b)

    a_ids = set(a_map.keys())
    b_ids = set(b_map.keys())

    added = sorted(b_ids - a_ids)
    removed = sorted(a_ids - b_ids)
    common = sorted(a_ids & b_ids)

    changed: list = []
    unchanged: list = []
    for pid in common:
        a_entry = a_map[pid]
        b_entry = b_map[pid]
        if _entries_changed(a_entry, b_entry):
            change_dict: dict = {"pair_id": pid}
            for fname in _CHANGE_FIELDS:
                change_dict[f"{fname}_a"] = a_entry.get(fname)
                change_dict[f"{fname}_b"] = b_entry.get(fname)
            changed.append(change_dict)
        else:
            unchanged.append(pid)

    return {
        "added":     added,
        "removed":   removed,
        "changed":   changed,
        "unchanged": unchanged,
        "summary": {
            "added":     len(added),
            "removed":   len(removed),
            "changed":   len(changed),
            "unchanged": len(unchanged),
        },
    }


def diff_runs(run_id_a: str, run_id_b: str) -> dict:
    """Load two stored runs by id and compute their diff.

    Args:
        run_id_a, run_id_b: validated run ids (the persistence layer
            checks the regex; this function passes them through).

    Returns:
        dict — same shape as ``compare_runs``.

    Raises:
        ValueError if either run_id is malformed (propagated from
        persistence).
        FileNotFoundError if either run does not exist.
    """
    # Unit 19: load_comparison_result returns the {metadata, result}
    # envelope; analytics operate on the inner result list.
    run_a = load_comparison_result(run_id_a)["result"]
    run_b = load_comparison_result(run_id_b)["result"]
    return compare_runs(run_a, run_b)
