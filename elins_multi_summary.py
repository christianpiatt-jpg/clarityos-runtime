"""
elins_multi_summary.py — ELINS2 Unit 4.

Per-pair summary tables across a chronological run sequence.
Generalises Unit 14's single-run aggregator to N runs: for every
pair_id that appears in at least one run, surface its score / band
trajectory + stability / volatility metrics + an overall trend
direction.

ROLE
----
Second temporal-intelligence primitive. Where Unit 3 classifies the
sequence as a whole, Unit 4 keeps the per-pair granularity that
dashboards need to drill into "which pair drove the trend".

INPUT CONTRACT
--------------
* ``run_ids`` is treated as already-chronological (caller's
  responsibility — use ``elins_run_ordering.sort_run_ids_by_timestamp``
  if needed).
* Legacy runs (metadata=None, Unit 10 list-only) are SKIPPED.
* After filtering, the sequence must have >= 2 runs. Below that the
  function returns ``{"pair_summaries": {}, "run_ids": [<filtered>]}``.

PAIR-LEVEL OUTPUT
-----------------
For each pair_id present in ANY filtered run, the summary contains::

    {
      "direction_over_time": [<band str per run>],          # length N
      "magnitude_over_time": [<composite score per run>],   # length N
      "severity_over_time":  [<severity label per transition>],  # length N-1
      "stability_score":     <float in [0, 1]>,
      "volatility_score":    <float in [0, 1]>,
      "trend_direction":     "upward" | "downward" | "flat",
    }

Composite per-run values:
    * magnitude = ``(sp_score + ec_score) / 2`` (falls back to 0.0 if
      the pair is missing from a run — spec's "missing pairs handled
      as zeros").
    * direction (band) = the WORSE of ``sp_band`` and ``ec_band`` — the
      bottleneck dimension, which is the operationally interesting one.
      Missing pair → ``"absent"``.
    * severity = bucket of ``|magnitude_delta|`` between consecutive
      runs:
          0        → "none"
          1-2      → "weak"
          3-4      → "moderate"
          >= 5     → "strong"

Aggregate metrics:
    * volatility_score = population stddev of magnitude deltas,
      normalised to [0, 1].
    * stability_score  = 1 - volatility_score.
    * trend_direction = sign of the OLS slope of magnitude_over_time,
      with the same epsilon as Unit 3.

I/O CONTRACT
------------
Loads each requested run once via persistence. No drift / magnitude /
severity re-computation; everything is derived from the raw envelope
payloads. No logging, no network, no randomness.

PUBLIC API
----------
    multi_run_summary(run_ids) -> dict
    pair_stability(run_ids) -> dict[pair_id -> float]
    pair_volatility(run_ids) -> dict[pair_id -> float]
    pair_direction_over_time(run_ids) -> dict[pair_id -> list[str]]
"""
from __future__ import annotations

import math

from elins_persistence import _validate_run_id, load_comparison_result
from elins_trends import (
    _ordinary_least_squares_slope,
    _stddev_of_deltas,
    _EPSILON_SLOPE,
    _MAX_VOLATILITY_NORM,
)


# Locked band → numeric encoding for picking the "worse" of two bands.
# Higher numeric value = stronger; missing/unknown = 0 (worst).
_BAND_NUMERIC: dict = {
    "Strong":           4,
    "Acceptable":       3,
    "Weak":             2,
    "Fails core logic": 1,
    "Fails":            1,
}

# Locked severity-bucket cutoffs over absolute magnitude delta.
_SEVERITY_NONE_MAX:     float = 0.0
_SEVERITY_WEAK_MAX:     float = 2.0
_SEVERITY_MODERATE_MAX: float = 4.0
# Anything > _SEVERITY_MODERATE_MAX → "strong"

# Locked sentinels used in the per-run output sequences.
_ABSENT_BAND:     str = "absent"
_SEVERITY_NONE:     str = "none"
_SEVERITY_WEAK:     str = "weak"
_SEVERITY_MODERATE: str = "moderate"
_SEVERITY_STRONG:   str = "strong"

_TREND_UP:   str = "upward"
_TREND_DOWN: str = "downward"
_TREND_FLAT: str = "flat"

_MIN_RUNS_FOR_SUMMARY: int = 2


def _is_numeric(v) -> bool:
    return (
        v is not None
        and not isinstance(v, bool)
        and isinstance(v, (int, float))
    )


def _worse_band(sp_band, ec_band) -> str:
    """Return the band string for the worse of two band labels. Missing
    / unknown bands map to numeric 0 and lose to any real band."""
    sp_n = _BAND_NUMERIC.get(sp_band, 0) if isinstance(sp_band, str) else 0
    ec_n = _BAND_NUMERIC.get(ec_band, 0) if isinstance(ec_band, str) else 0
    # Pick the lower-numeric (worse) of the two.
    if sp_n <= ec_n and isinstance(sp_band, str):
        return sp_band
    if isinstance(ec_band, str):
        return ec_band
    return _ABSENT_BAND


def _severity_for_delta(delta_abs: float) -> str:
    """Bucket a non-negative absolute magnitude delta into a severity
    label."""
    if delta_abs <= _SEVERITY_NONE_MAX:
        return _SEVERITY_NONE
    if delta_abs <= _SEVERITY_WEAK_MAX:
        return _SEVERITY_WEAK
    if delta_abs <= _SEVERITY_MODERATE_MAX:
        return _SEVERITY_MODERATE
    return _SEVERITY_STRONG


def _pair_index_for_run(run_payload) -> dict:
    """Build ``{pair_id: entry_dict}`` for a single run's payload."""
    out: dict = {}
    if not isinstance(run_payload, list):
        return out
    for entry in run_payload:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("pair_id")
        if isinstance(pid, str):
            out[pid] = entry
    return out


def _magnitude_for_entry(entry) -> float:
    """Composite magnitude = mean of sp+ec scores (each may be missing).
    Returns 0.0 if both are missing."""
    if not isinstance(entry, dict):
        return 0.0
    sp = entry.get("single_party_score")
    ec = entry.get("economic_coercion_score")
    nums = [float(v) for v in (sp, ec) if _is_numeric(v)]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def _trend_direction_from_slope(slope: float) -> str:
    if slope >= _EPSILON_SLOPE:
        return _TREND_UP
    if slope <= -_EPSILON_SLOPE:
        return _TREND_DOWN
    return _TREND_FLAT


def _filter_non_legacy(run_ids: list) -> list:
    """Drop legacy envelopes (metadata=None). Returns
    ``[(run_id, envelope), ...]`` in input order."""
    out: list = []
    for rid in run_ids:
        env = load_comparison_result(rid)
        meta = env.get("metadata") if isinstance(env, dict) else None
        if isinstance(meta, dict):
            out.append((rid, env))
    return out


def _build_pair_summaries(non_legacy: list) -> dict:
    """Core orchestration: build the per-pair summary dict over the
    filtered (rid, envelope) pair list."""
    per_run_indexes = [
        _pair_index_for_run(env.get("result")) for _, env in non_legacy
    ]
    all_pair_ids: set = set()
    for idx in per_run_indexes:
        all_pair_ids.update(idx.keys())

    summaries: dict = {}
    for pid in sorted(all_pair_ids):
        magnitudes: list = []
        directions: list = []
        for idx in per_run_indexes:
            entry = idx.get(pid)
            magnitudes.append(_magnitude_for_entry(entry))
            if isinstance(entry, dict):
                directions.append(_worse_band(
                    entry.get("single_party_band"),
                    entry.get("economic_coercion_band"),
                ))
            else:
                directions.append(_ABSENT_BAND)

        severities: list = []
        for i in range(len(magnitudes) - 1):
            severities.append(
                _severity_for_delta(abs(magnitudes[i + 1] - magnitudes[i]))
            )

        vol_raw = _stddev_of_deltas(magnitudes)
        vol_norm = min(vol_raw / _MAX_VOLATILITY_NORM, 1.0)
        stability = max(0.0, 1.0 - vol_norm)
        slope = _ordinary_least_squares_slope(magnitudes)
        trend_direction = _trend_direction_from_slope(slope)

        summaries[pid] = {
            "direction_over_time": directions,
            "magnitude_over_time": magnitudes,
            "severity_over_time":  severities,
            "stability_score":     stability,
            "volatility_score":    vol_norm,
            "trend_direction":     trend_direction,
        }
    return summaries


def multi_run_summary(run_ids) -> dict:
    """Build the per-pair summary table across `run_ids`.

    Args:
        run_ids: chronologically-ordered list of run identifiers.
            Caller is responsible for ordering. Legacy runs are
            silently dropped.

    Returns:
        ``{"pair_summaries": {pair_id: {...}}, "run_ids": [<filtered>]}``.
        For < 2 non-legacy runs, ``pair_summaries`` is an empty dict
        and the response is still well-formed.

    Raises:
        ValueError if `run_ids` is not a list or contains a malformed id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"multi_run_summary expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    non_legacy = _filter_non_legacy(run_ids)
    filtered_ids = [rid for rid, _ in non_legacy]
    if len(non_legacy) < _MIN_RUNS_FOR_SUMMARY:
        return {"pair_summaries": {}, "run_ids": filtered_ids}

    summaries = _build_pair_summaries(non_legacy)
    return {"pair_summaries": summaries, "run_ids": filtered_ids}


def pair_stability(run_ids) -> dict:
    """Return ``{pair_id: stability_score}`` across the run sequence."""
    summary = multi_run_summary(run_ids)
    return {
        pid: data["stability_score"]
        for pid, data in summary["pair_summaries"].items()
    }


def pair_volatility(run_ids) -> dict:
    """Return ``{pair_id: volatility_score}`` across the run sequence."""
    summary = multi_run_summary(run_ids)
    return {
        pid: data["volatility_score"]
        for pid, data in summary["pair_summaries"].items()
    }


def pair_direction_over_time(run_ids) -> dict:
    """Return ``{pair_id: [band_str, ...]}`` across the run sequence.

    Each list has one entry per filtered (non-legacy) run; pairs
    missing from a given run get the sentinel ``"absent"``.
    """
    summary = multi_run_summary(run_ids)
    return {
        pid: list(data["direction_over_time"])
        for pid, data in summary["pair_summaries"].items()
    }
