"""
elins_pair_filtering.py — ELINS Unit 21.

Server-side filtering and pagination helpers for the per-pair analytics
endpoints (Units 11/13/15/16/17). All public functions are pure.

WHY
---
Endpoints like ``/elins/regression/drift/series`` can return one entry
per pair across N runs. With a few hundred evidence files that is too
much for a dashboard sparkline grid. Unit 21 introduces optional
``pair_id_prefix`` / ``limit`` / ``offset`` query parameters so callers
can request just the slice they need.

PIPELINE
--------
For every per-pair endpoint:

    1. Compute the full analytic result.
    2. Apply ``pair_id_prefix`` (case-sensitive ``startswith``).
    3. Sort alphabetically by ``pair_id``.
    4. Apply ``offset``.
    5. Apply ``limit``.

VALIDATION
----------
``validate_pair_filters`` enforces the input contract at one place:

    * ``pair_id_prefix`` — string or ``None`` (empty string == None,
      i.e. no filtering).
    * ``limit`` — int >= 1 or ``None``. Bool rejected (Python's
      ``bool`` is a subclass of ``int`` but operationally the wrong
      type here).
    * ``offset`` — int >= 0 or ``None`` (None defaults to 0). Bool
      rejected.

I/O CONTRACT
------------
No I/O. No logging. No randomness. Pure transformations on the
analytic dicts produced upstream.

PUBLIC API
----------
    validate_pair_filters(pair_id_prefix, limit, offset) -> tuple
    select_pair_ids(pair_ids, prefix, limit, offset) -> list[str]
    apply_pair_filters(data, prefix, limit, offset) -> dict
    apply_pair_filters_to_drift(buckets, prefix, limit, offset) -> dict
    apply_pair_filters_to_diff(diff_result, prefix, limit, offset) -> dict
"""
from __future__ import annotations


# Locked drift bucket names (mirrors Unit 13 / Unit 16).
_DRIFT_BUCKET_KEYS: tuple = (
    "stable", "trending_up", "trending_down", "volatile",
)

# Locked diff list-key names (mirrors Unit 11).
_DIFF_PAIR_LIST_KEYS: tuple = ("added", "removed", "unchanged")
_DIFF_CHANGED_KEY: str = "changed"


def validate_pair_filters(pair_id_prefix, limit, offset) -> tuple:
    """Validate the optional filter inputs and return a normalised triple.

    Args:
        pair_id_prefix: ``None`` or a string. Empty string is treated as
            "no prefix".
        limit: ``None`` or a positive int (>= 1). Bool is rejected.
        offset: ``None`` or a non-negative int (>= 0). Bool is rejected.

    Returns:
        ``(normalised_prefix, normalised_limit, normalised_offset)``
        where:
            * normalised_prefix: the original string (or "" if None /
              empty); a falsy value means "no filter".
            * normalised_limit: int or None
            * normalised_offset: int (defaults to 0)

    Raises:
        ValueError on a malformed input.
    """
    if pair_id_prefix is not None and not isinstance(pair_id_prefix, str):
        raise ValueError(
            f"pair_id_prefix must be a string, "
            f"got {type(pair_id_prefix).__name__}"
        )
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError(
                f"limit must be a positive int, got {type(limit).__name__}"
            )
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError(
                f"offset must be a non-negative int, "
                f"got {type(offset).__name__}"
            )
        if offset < 0:
            raise ValueError(f"offset must be >= 0, got {offset}")

    norm_prefix = pair_id_prefix or ""  # None or "" => ""
    norm_limit  = limit
    norm_offset = offset if offset is not None else 0
    return norm_prefix, norm_limit, norm_offset


def select_pair_ids(pair_ids, prefix, limit, offset) -> list:
    """Filter, sort, offset, and limit a flat collection of pair_ids.

    Inputs are not validated here — callers should pre-validate via
    ``validate_pair_filters``. Non-string entries in ``pair_ids`` are
    silently dropped (defensive).

    Returns:
        list[str] of selected pair_ids in alphabetical order.
    """
    selected = [p for p in pair_ids if isinstance(p, str)]
    if prefix:
        selected = [p for p in selected if p.startswith(prefix)]
    selected = sorted(set(selected))
    if offset:
        selected = selected[offset:]
    if limit is not None:
        selected = selected[:limit]
    return selected


def apply_pair_filters(data: dict, pair_id_prefix, limit, offset) -> dict:
    """Filter a ``{pair_id: <opaque value>}`` dict.

    Used by ``magnitude``, ``severity``, and ``series`` endpoints.
    Values are returned unchanged; only the key set is filtered.

    Args:
        data: dict keyed by pair_id (string).
        pair_id_prefix, limit, offset: see ``validate_pair_filters``.

    Returns:
        New dict with the filtered/sorted/paginated key subset. Output
        keys are alphabetically ordered. Original dict is not mutated.

    Raises:
        ValueError on a malformed filter input or non-dict ``data``.
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"apply_pair_filters expected a dict, got {type(data).__name__}"
        )
    norm_prefix, norm_limit, norm_offset = validate_pair_filters(
        pair_id_prefix, limit, offset,
    )
    allowed = select_pair_ids(
        list(data.keys()), norm_prefix, norm_limit, norm_offset,
    )
    return {pid: data[pid] for pid in allowed}


def apply_pair_filters_to_drift(
    buckets: dict, pair_id_prefix, limit, offset,
) -> dict:
    """Filter Unit 13's bucket-keyed drift output.

    Each bucket list (``stable`` / ``trending_up`` / ``trending_down`` /
    ``volatile``) is intersected with the allowed pair_id set. The
    ``summary`` counts are recomputed from the filtered buckets so
    callers always see counts that match what was returned. Unknown
    keys (forward-compatibility) are passed through unchanged.

    Raises:
        ValueError on a malformed filter input or non-dict ``buckets``.
    """
    if not isinstance(buckets, dict):
        raise ValueError(
            f"apply_pair_filters_to_drift expected a dict, "
            f"got {type(buckets).__name__}"
        )
    norm_prefix, norm_limit, norm_offset = validate_pair_filters(
        pair_id_prefix, limit, offset,
    )

    union: list = []
    for key in _DRIFT_BUCKET_KEYS:
        bucket = buckets.get(key, [])
        if isinstance(bucket, list):
            union.extend(bucket)

    allowed = set(select_pair_ids(
        union, norm_prefix, norm_limit, norm_offset,
    ))

    out: dict = {}
    for key in _DRIFT_BUCKET_KEYS:
        bucket = buckets.get(key, [])
        if isinstance(bucket, list):
            out[key] = sorted(
                p for p in bucket
                if isinstance(p, str) and p in allowed
            )
        else:
            out[key] = bucket

    out["summary"] = {key: len(out[key]) for key in _DRIFT_BUCKET_KEYS}
    return out


def apply_pair_filters_to_diff(
    diff_result: dict, pair_id_prefix, limit, offset,
) -> dict:
    """Filter Unit 11's ``compare_runs`` output shape.

    The diff dict has:
        * ``added`` / ``removed`` / ``unchanged``: lists of pair_id
          strings.
        * ``changed``: list of dicts, each with a ``pair_id`` field.
        * ``summary``: counts dict (recomputed from filtered lists).

    Filtering uses the union of all four pair_id sources to determine
    the allowed set, then intersects each list against it. The
    ``summary`` counts are refreshed from the filtered output.

    Raises:
        ValueError on a malformed filter input or non-dict
        ``diff_result``.
    """
    if not isinstance(diff_result, dict):
        raise ValueError(
            f"apply_pair_filters_to_diff expected a dict, "
            f"got {type(diff_result).__name__}"
        )
    norm_prefix, norm_limit, norm_offset = validate_pair_filters(
        pair_id_prefix, limit, offset,
    )

    union: list = []
    for key in _DIFF_PAIR_LIST_KEYS:
        bucket = diff_result.get(key, [])
        if isinstance(bucket, list):
            union.extend(bucket)
    changed = diff_result.get(_DIFF_CHANGED_KEY, [])
    if isinstance(changed, list):
        for entry in changed:
            if isinstance(entry, dict):
                pid = entry.get("pair_id")
                if isinstance(pid, str):
                    union.append(pid)

    allowed = set(select_pair_ids(
        union, norm_prefix, norm_limit, norm_offset,
    ))

    out: dict = {}
    for key in _DIFF_PAIR_LIST_KEYS:
        bucket = diff_result.get(key, [])
        if isinstance(bucket, list):
            out[key] = sorted(
                p for p in bucket
                if isinstance(p, str) and p in allowed
            )
        else:
            out[key] = bucket

    if isinstance(changed, list):
        out[_DIFF_CHANGED_KEY] = sorted(
            (e for e in changed
             if isinstance(e, dict) and e.get("pair_id") in allowed),
            key=lambda e: e.get("pair_id", ""),
        )
    else:
        out[_DIFF_CHANGED_KEY] = changed

    out["summary"] = {
        "added":     len(out["added"])     if isinstance(out["added"], list)     else 0,
        "removed":   len(out["removed"])   if isinstance(out["removed"], list)   else 0,
        "changed":   len(out[_DIFF_CHANGED_KEY])
                       if isinstance(out[_DIFF_CHANGED_KEY], list) else 0,
        "unchanged": len(out["unchanged"]) if isinstance(out["unchanged"], list) else 0,
    }
    return out
