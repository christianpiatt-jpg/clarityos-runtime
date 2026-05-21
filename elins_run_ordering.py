"""
elins_run_ordering.py — ELINS Unit 23.

Time-aware ordering helper for multi-run analytics. Replaces caller
order with the true chronological order taken from each run's
``metadata.created_at`` timestamp (Unit 19).

WHY
---
Up through Unit 22, every multi-run wrapper trusted the caller-supplied
``run_ids`` order as chronological. This assumption breaks the moment
a dashboard renders runs in a non-chronological way (alphabetical,
pinned-first, paginated, etc.). Unit 23 makes ordering deterministic
and backed by metadata: drift / magnitude / severity / series / summary
always operate in true ascending-timestamp order regardless of how the
caller listed the ids.

ORDERING RULES
--------------
    * Primary key: ``metadata.created_at`` (ISO8601 string, ascending).
    * Legacy runs (``metadata is None`` — Unit 10 list-only files)
      sort LAST so timestamped runs aren't mixed into a chronologically
      undefined region.
    * Ties broken alphabetically by ``run_id``.

I/O CONTRACT
------------
``sort_run_ids_by_timestamp`` reads each requested run via
``elins_persistence.load_comparison_result`` to inspect its metadata.
That's the only I/O. The function does not log, network, or randomise.

PUBLIC API
----------
    sort_run_ids_by_timestamp(run_ids) -> list[str]
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result


# Sort-key first-element flags. Smaller sorts first, so timestamped
# runs (0) precede legacy runs (1).
_SORT_BUCKET_TIMESTAMPED: int = 0
_SORT_BUCKET_LEGACY:      int = 1


def sort_run_ids_by_timestamp(run_ids) -> list:
    """Return ``run_ids`` reordered ascending by ``metadata.created_at``.

    Args:
        run_ids: list of run identifiers. Each id is validated against
            the canonical run_id regex before any load happens. Empty
            list returns an empty list.

    Returns:
        list[str] of the same ids, reordered. Legacy runs (no
        metadata, or no ``created_at`` field) sort to the end. Ties
        within a sort bucket are broken alphabetically by run_id.

    Raises:
        ValueError if `run_ids` is not a list, or contains a malformed
            run_id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"sort_run_ids_by_timestamp expected a list, "
            f"got {type(run_ids).__name__}"
        )

    # Validate up front so a bad id at the end doesn't waste loads.
    for rid in run_ids:
        _validate_run_id(rid)

    items: list = []
    for rid in run_ids:
        envelope = load_comparison_result(rid)
        meta = envelope.get("metadata") if isinstance(envelope, dict) else None
        ts = meta.get("created_at") if isinstance(meta, dict) else None
        items.append((rid, ts))

    def _key(item):
        rid, ts = item
        if not isinstance(ts, str):
            # Legacy / missing-timestamp runs sort to the end, then
            # alphabetically among themselves.
            return (_SORT_BUCKET_LEGACY, "", rid)
        return (_SORT_BUCKET_TIMESTAMPED, ts, rid)

    items.sort(key=_key)
    return [rid for rid, _ in items]
