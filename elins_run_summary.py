"""
elins_run_summary.py — ELINS Unit 14.

Single-run aggregation: produces a compact summary table over one
stored run — counts per band, min/max/mean of scores per dimension,
total pairs.

Complements:
    * Unit 11 diff   — point-to-point change detection
    * Unit 13 drift  — multi-run trajectory classification
    * Unit 14 (this) — at-a-glance snapshot of a single run

ROLE
----
Pure aggregator over the dashboard payload shape (Units 5/8/10).
Reuses the Unit 11 normalisation helper so legacy entries (no
``pair_id``) still summarise correctly.

BAND KEY MAPPING
----------------
Stored payloads use the full band label string ``"Fails core logic"``.
This module's output keys use the work-set's shortened ``"Fails"`` for
brevity. The mapping is locked:

    "Strong"          → "Strong"
    "Acceptable"      → "Acceptable"
    "Weak"            → "Weak"
    "Fails core logic"→ "Fails"

Unknown band strings are silently skipped from the per-band counts
(defensive — they don't appear in canonical Unit 5/8 output).
``total_pairs`` always reflects the full run length, regardless of
band coverage.

I/O CONTRACT
------------
``summary_table`` is pure (no I/O). ``summary_table_for_run_id`` reads
via the persistence layer; that's the only I/O. No logging, no network,
no LLM, no randomness.

PUBLIC API
----------
    summary_table(run) -> dict   (pure)
    summary_table_for_run_id(run_id) -> dict  (loads via persistence)
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_diff import _normalise_run


# Locked field names extracted from each entry.
_SP_SCORE_FIELD: str = "single_party_score"
_EC_SCORE_FIELD: str = "economic_coercion_score"
_SP_BAND_FIELD: str = "single_party_band"
_EC_BAND_FIELD: str = "economic_coercion_band"

# Locked band-key mapping. Stored payloads use the full label
# ``"Fails core logic"``; output keys use the shorter ``"Fails"``.
_BAND_KEY_MAP: dict = {
    "Strong":           "Strong",
    "Acceptable":       "Acceptable",
    "Weak":             "Weak",
    "Fails core logic": "Fails",
}

# Locked output key list (alphabetical-friendly + matches work-set example).
_BAND_OUTPUT_KEYS: tuple = ("Strong", "Acceptable", "Weak", "Fails")

# Locked rounding precision for mean score.
_MEAN_ROUND_DIGITS: int = 1


def _empty_band_counts() -> dict:
    """Return a fresh dict of all 4 band-output keys, each mapped to 0."""
    return {key: 0 for key in _BAND_OUTPUT_KEYS}


def _empty_score_stats() -> dict:
    """Return the score-stats shape for an empty run."""
    return {"min": None, "max": None, "mean": None}


def _bucket_band(label, counts: dict) -> None:
    """Increment the count for the given band label, mapping the stored
    label to the output key. Unknown labels are silently skipped."""
    if not isinstance(label, str):
        return
    output_key = _BAND_KEY_MAP.get(label)
    if output_key is None:
        return
    counts[output_key] += 1


def _score_stats(values: list) -> dict:
    """Compute {"min": ..., "max": ..., "mean": ...} for a list of
    numeric values. Empty list → all None. Mean is rounded to
    _MEAN_ROUND_DIGITS decimal places."""
    # Filter out None and non-numeric defensively.
    numeric = [
        v for v in values
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not numeric:
        return _empty_score_stats()
    raw_mean = sum(numeric) / len(numeric)
    return {
        "min":  min(numeric),
        "max":  max(numeric),
        "mean": round(raw_mean, _MEAN_ROUND_DIGITS),
    }


def summary_table(run) -> dict:
    """Pure single-run aggregator.

    Args:
        run: list[dict] — a stored-run payload (the shape produced by
            Unit 5/8 dashboard wrappers and persisted by Unit 10).

    Returns:
        dict with:
            * total_pairs:                int
            * single_party_bands:         {"Strong","Acceptable","Weak","Fails"}
            * economic_coercion_bands:    same 4-key shape
            * single_party_scores:        {"min","max","mean"}
            * economic_coercion_scores:   same 3-key shape

    Empty run → counts all 0, score stats all None.

    Raises:
        ValueError if `run` is not a list, or if any list element is
        not a dict (propagated from Unit 11 normalisation).
    """
    # Reuse Unit 11 normalisation so legacy entries (no pair_id) get
    # synthesised pos_<i> ids and the entries themselves come back as
    # dicts. We don't actually need the pair_id keys here, but the
    # validation behavior is what matters.
    normalised = _normalise_run(run)
    entries = list(normalised.values())

    sp_band_counts = _empty_band_counts()
    ec_band_counts = _empty_band_counts()
    sp_scores: list = []
    ec_scores: list = []

    for entry in entries:
        _bucket_band(entry.get(_SP_BAND_FIELD), sp_band_counts)
        _bucket_band(entry.get(_EC_BAND_FIELD), ec_band_counts)
        sp_scores.append(entry.get(_SP_SCORE_FIELD))
        ec_scores.append(entry.get(_EC_SCORE_FIELD))

    return {
        "total_pairs":              len(entries),
        "single_party_bands":       sp_band_counts,
        "economic_coercion_bands":  ec_band_counts,
        "single_party_scores":      _score_stats(sp_scores),
        "economic_coercion_scores": _score_stats(ec_scores),
    }


def summary_table_for_run_id(run_id: str) -> dict:
    """Load a stored run by id and return its summary table.

    Args:
        run_id: validated identifier (same regex as save/load).

    Returns:
        Same shape as ``summary_table``.

    Raises:
        ValueError on a malformed run_id (propagated from persistence).
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    # Unit 19: load_comparison_result returns the {metadata, result}
    # envelope; analytics operate on the inner result list.
    run = load_comparison_result(run_id)["result"]
    return summary_table(run)
