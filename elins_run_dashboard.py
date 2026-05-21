"""
elins_run_dashboard.py — ELINS Unit 27.

Unified dashboard composite for a single run or a run sequence.
Combines the Unit 22 analytic composite with the Unit 27/28 operator-
utility columns (notes / tags / archived) into one response shape.

WHY
---
The Unit 22 ``/elins/regression/run/composite`` endpoint returns
metadata + summary + drift sections at the top level of the response.
Dashboards usually want one extra hop: the operator-facing flags
(notes / tags / archived) per run. Unit 27 introduces a dedicated
``/elins/regression/run/dashboard`` endpoint with a SHAPE LOCKED to
include all seven payload sections every call:

    {
      "run_ids":  [...],
      "metadata": [...],
      "summary":  {...},
      "drift": {
        "direction": {...},
        "magnitude": {...},
        "severity":  {...},
        "series":    {...}
      },
      "notes":    [...],
      "tags":     [...],
      "archived": [...]
    }

For single-run mode the four ``drift`` sub-keys are present but empty
dicts (drift requires >= 2 runs); for multi-run mode all four are
populated. Operator-utility arrays (``notes`` / ``tags`` /
``archived``) are always present with one element per run_id, aligned
to the timestamp-sorted ``run_ids`` order.

I/O CONTRACT
------------
Single-pass orchestration on top of:
    * ``elins_run_composite.composite_for_run_ids`` for the analytic
      sections (timestamp ordering, metadata, summary, drift).
    * ``elins_persistence`` operator-utility accessors for the
      notes / tags / archived arrays.

No direct file or DB I/O. No logging.

PUBLIC API
----------
    dashboard_for_run_ids(run_ids) -> dict
"""
from __future__ import annotations

from elins_persistence import get_archived, get_notes, get_tags
from elins_run_composite import composite_for_run_ids


# Locked nested-key names for the dashboard drift section.
_DRIFT_KEY:    str = "drift"
_NOTES_KEY:    str = "notes"
_TAGS_KEY:     str = "tags"
_ARCHIVED_KEY: str = "archived"

_DRIFT_SUBKEYS: tuple = ("direction", "magnitude", "severity", "series")


def _empty_drift() -> dict:
    """Return the single-run shape for the drift section — all four
    sub-keys present but empty dicts so the response shape is locked
    across run-count variations."""
    return {k: {} for k in _DRIFT_SUBKEYS}


def dashboard_for_run_ids(run_ids) -> dict:
    """Return the Unit 27 dashboard composite for the given run_ids.

    Delegates to ``composite_for_run_ids`` for the analytic sections
    (which validates input, loads runs once, sorts by timestamp, and
    computes drift when there are >= 2 runs). Then attaches the
    operator-utility arrays in the same sorted order.

    Args:
        run_ids: list of run identifiers. Must contain at least 1
            entry; each id must satisfy the canonical regex.

    Returns:
        Dashboard composite dict (see module docstring for the locked
        shape). Single-run responses include empty drift sub-sections
        rather than omitting them.

    Raises:
        ValueError if ``run_ids`` is malformed (propagated from
            ``composite_for_run_ids``).
        FileNotFoundError if any run does not exist.
    """
    composite = composite_for_run_ids(run_ids)
    sorted_run_ids = composite["run_ids"]
    metadata       = composite["metadata"]

    if len(sorted_run_ids) == 1:
        drift_section = _empty_drift()
    else:
        drift_section = {
            "direction": composite["direction"],
            "magnitude": composite["magnitude"],
            "severity":  composite["severity"],
            "series":    composite["series"],
        }

    return {
        "run_ids":     list(sorted_run_ids),
        "metadata":    list(metadata),
        "summary":     composite["summary"],
        _DRIFT_KEY:    drift_section,
        _NOTES_KEY:    [get_notes(rid)    for rid in sorted_run_ids],
        _TAGS_KEY:     [get_tags(rid)     for rid in sorted_run_ids],
        _ARCHIVED_KEY: [get_archived(rid) for rid in sorted_run_ids],
    }
