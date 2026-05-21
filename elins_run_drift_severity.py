"""
elins_run_drift_severity.py — ELINS Unit 16.

Composite drift classifier: fuses Unit 13's directional label with
Unit 15's magnitude metrics into a single per-pair severity record.

ROLE
----
Pure analytic on top of two earlier analytics. Produces operator-
friendly composite labels like ``"trending_up_strong"`` plus the raw
direction / severity / max_swing / range fields needed by dashboards.

LABEL CONSTRUCTION
------------------
Severity is derived from the larger of the two dimensions' max_swing:

    max_swing == 0         → "none"
    1 <= max_swing <= 2    → "weak"
    3 <= max_swing <= 4    → "moderate"
    max_swing >= 5         → "strong"

Label is then composed:

    direction == "stable"  → label = "stable", severity = "none"
                              (severity is forced to "none" regardless
                               of computed value — defensive)
    otherwise              → label = f"{direction}_{severity}"

So ``volatile`` with a swing of 6 yields ``"volatile_strong"``;
``trending_down`` with a swing of 3 yields ``"trending_down_moderate"``;
etc. Locked naming convention.

PAIR PRESENCE
-------------
Only pairs present in BOTH the direction input and the magnitude input
are classified. Mismatched pairs (in one but not the other) are
silently dropped from output.

I/O CONTRACT
------------
``classify_drift_severity`` is pure (no I/O). The wrapper
``classify_drift_severity_for_run_ids`` reads via the persistence
layer; that's the only I/O. No logging, no network, no LLM, no
randomness.

PUBLIC API
----------
    classify_drift_severity(direction, magnitude) -> dict   (pure)
    classify_drift_severity_for_run_ids(run_ids) -> dict
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_drift import detect_drift
from elins_run_drift_magnitude import drift_magnitude


# Locked direction bucket names (mirrors Unit 13).
_DIRECTION_BUCKETS: tuple = (
    "stable", "trending_up", "trending_down", "volatile",
)

# Locked severity bands (max_swing thresholds).
_SEVERITY_NONE: str = "none"
_SEVERITY_WEAK: str = "weak"
_SEVERITY_MODERATE: str = "moderate"
_SEVERITY_STRONG: str = "strong"

# Locked threshold boundaries (inclusive upper bounds for weak/moderate).
_WEAK_MAX_SWING: int = 2
_MODERATE_MAX_SWING: int = 4
# Anything above _MODERATE_MAX_SWING falls into "strong".


def _direction_per_pair(direction: dict) -> dict:
    """Invert Unit 13's bucket-keyed output into ``{pair_id: direction}``.

    Defensively handles missing buckets (returns whatever's present).
    """
    out: dict = {}
    for label in _DIRECTION_BUCKETS:
        bucket = direction.get(label, [])
        if not isinstance(bucket, list):
            continue
        for pid in bucket:
            if isinstance(pid, str):
                out[pid] = label
    return out


def _severity_for_max_swing(max_swing: int) -> str:
    """Map a non-negative integer max_swing to a severity band per
    locked thresholds."""
    if max_swing <= 0:
        return _SEVERITY_NONE
    if max_swing <= _WEAK_MAX_SWING:
        return _SEVERITY_WEAK
    if max_swing <= _MODERATE_MAX_SWING:
        return _SEVERITY_MODERATE
    return _SEVERITY_STRONG


def classify_drift_severity(direction: dict, magnitude: dict) -> dict:
    """Pure composite classifier.

    Args:
        direction: exact output of Unit 13's ``detect_drift``. Must be
            a dict with bucket-keyed lists of pair_ids.
        magnitude: exact output of Unit 15's ``drift_magnitude``. Must
            be a dict keyed by pair_id with single_party + economic_
            coercion sub-dicts.

    Returns:
        dict keyed alphabetically by pair_id. Each value is:

            {
              "label":       str,    # e.g. "trending_up_strong"
              "direction":   str,    # one of _DIRECTION_BUCKETS
              "severity":    str,    # "none"/"weak"/"moderate"/"strong"
              "max_swing":   {"single_party": int, "economic_coercion": int},
              "range":       {"single_party": int, "economic_coercion": int}
            }

        Pairs missing from either input are silently dropped.

    Raises:
        ValueError if `direction` or `magnitude` is not a dict.
    """
    if not isinstance(direction, dict):
        raise ValueError(
            f"classify_drift_severity expected dict for direction, "
            f"got {type(direction).__name__}"
        )
    if not isinstance(magnitude, dict):
        raise ValueError(
            f"classify_drift_severity expected dict for magnitude, "
            f"got {type(magnitude).__name__}"
        )

    dir_per_pair = _direction_per_pair(direction)
    common = sorted(set(dir_per_pair.keys()) & set(magnitude.keys()))

    out: dict = {}
    for pid in common:
        d = dir_per_pair[pid]
        m = magnitude[pid]

        # Defensive — if magnitude entry lacks the expected sub-dicts,
        # skip the pair rather than crash.
        sp = m.get("single_party") if isinstance(m, dict) else None
        ec = m.get("economic_coercion") if isinstance(m, dict) else None
        if not isinstance(sp, dict) or not isinstance(ec, dict):
            continue

        sp_swing = sp.get("max_swing", 0)
        ec_swing = ec.get("max_swing", 0)
        sp_range = sp.get("range", 0)
        ec_range = ec.get("range", 0)
        if not all(isinstance(v, int) and not isinstance(v, bool)
                   for v in (sp_swing, ec_swing, sp_range, ec_range)):
            continue

        max_swing_overall = max(sp_swing, ec_swing)
        severity = _severity_for_max_swing(max_swing_overall)

        if d == "stable":
            label = "stable"
            severity = _SEVERITY_NONE  # locked override per spec
        else:
            label = f"{d}_{severity}"

        out[pid] = {
            "label":     label,
            "direction": d,
            "severity":  severity,
            "max_swing": {
                "single_party":      sp_swing,
                "economic_coercion": ec_swing,
            },
            "range": {
                "single_party":      sp_range,
                "economic_coercion": ec_range,
            },
        }
    return out


def classify_drift_severity_for_run_ids(run_ids: list) -> dict:
    """Load a sequence of stored runs, compute Unit 13 direction and
    Unit 15 magnitude, and combine into severity classification.

    Args:
        run_ids: ordered list of run identifiers. Must contain at
            least 2 entries.

    Returns:
        Same shape as ``classify_drift_severity``.

    Raises:
        ValueError if `run_ids` is not a list, has fewer than 2
            entries, or contains a malformed run_id.
        FileNotFoundError if any run does not exist.

    Note:
        Loads each run ONCE and reuses the loaded payloads for both
        analytics — avoids redundant I/O.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"classify_drift_severity_for_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    if len(run_ids) < 2:
        raise ValueError(
            f"drift severity requires >= 2 runs, got {len(run_ids)}"
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
    direction = detect_drift(runs)
    magnitude = drift_magnitude(runs)
    return classify_drift_severity(direction, magnitude)
