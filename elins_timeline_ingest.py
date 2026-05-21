"""
elins_timeline_ingest.py — ELINS Unit 6.

CSV and JSON ingestors that construct Unit 1 ``Timeline`` and Unit 4
``TimelineEconomic`` dataclass instances from external file or in-memory
payloads.

ROLE
----
Adapter layer between external data sources (CSV files, JSON dicts) and
the regression validators. Constructs ready-to-validate dataclass
instances; never invokes the validators itself.

Pure (modulo file reads in the two CSV loaders), deterministic,
side-effect-free.

I/O CONTRACT
------------
Only the two CSV loaders open files. The JSON loaders take an in-memory
dict and never touch the filesystem. No logging, no network, no LLM,
no randomness.

CSV FORMAT
----------
First row: header. Header MUST contain exactly the required field names
for the target dataclass — extras are rejected, missing fields are
rejected. Data rows follow.

For Timeline (single-party fear), the required header is:
    t, regime_competition, autocratization, repression_index,
    digital_repression, perceived_threat, fear_signal, dissent_capacity,
    normative_constraint, support_buffer, trigger_event

For TimelineEconomic, the required header is:
    t, economic_pressure, material_insecurity, state_coercion,
    compliance_signal, resistance_capacity, support_buffer,
    trigger_event

Empty `trigger_event` cells are treated as None.
Empty file (header only) → empty `points` (Unit 3 N=0 convention).
`timeline_id` is derived from the filename without extension.

JSON FORMAT
-----------
{
    "timeline_id": "...",          # non-empty string, required
    "points": [
        {
            "t": "...",            # string, required
            "<numeric_field>": float / int (not bool),
            ...
            "trigger_event": str or null    # optional; defaults to None
        },
        ...
    ]
}

PUBLIC API
----------
    load_timeline_from_csv(path)         -> Timeline
    load_timeline_from_json(obj)         -> Timeline
    load_economic_timeline_from_csv(path) -> TimelineEconomic
    load_economic_timeline_from_json(obj) -> TimelineEconomic
"""
from __future__ import annotations

import csv
import os

from elins_regression_economic_coercion import (
    TimelineEconomic, TimePointEconomic,
)
from elins_regression_single_party import Timeline, TimePoint


# ===========================================================================
# Locked required-field tuples (single source of truth for each loader)
# ===========================================================================

# Single-party fear timeline — numeric fields, in canonical order.
_SP_NUMERIC_FIELDS: tuple = (
    "regime_competition",
    "autocratization",
    "repression_index",
    "digital_repression",
    "perceived_threat",
    "fear_signal",
    "dissent_capacity",
    "normative_constraint",
    "support_buffer",
)

# Economic-coercion timeline — numeric fields, in canonical order.
_EC_NUMERIC_FIELDS: tuple = (
    "economic_pressure",
    "material_insecurity",
    "state_coercion",
    "compliance_signal",
    "resistance_capacity",
    "support_buffer",
)

# Required CSV header sets (numeric fields + t + trigger_event).
_SP_CSV_HEADER: frozenset = frozenset(("t",) + _SP_NUMERIC_FIELDS + ("trigger_event",))
_EC_CSV_HEADER: frozenset = frozenset(("t",) + _EC_NUMERIC_FIELDS + ("trigger_event",))


# ===========================================================================
# Shared validation helpers
# ===========================================================================
def _filename_stem(path: str) -> str:
    """Filename without directory or extension."""
    return os.path.splitext(os.path.basename(path))[0]


def _validate_csv_header(actual: list, required: frozenset, label: str) -> None:
    """Raise ValueError if the CSV header doesn't match the required set
    EXACTLY (no missing, no extras)."""
    if actual is None:
        raise ValueError(f"{label}: CSV is missing a header row")
    actual_set = set(actual)
    missing = required - actual_set
    extra = actual_set - required
    if missing:
        raise ValueError(
            f"{label}: CSV header missing required fields: {sorted(missing)}"
        )
    if extra:
        raise ValueError(
            f"{label}: CSV header has unexpected fields: {sorted(extra)}"
        )


def _parse_csv_numeric(
    raw_value, field_name: str, idx: int, label: str,
) -> float:
    """Parse a CSV cell value into a float. Empty cells and non-numeric
    text raise ValueError."""
    if raw_value is None or raw_value == "":
        raise ValueError(
            f"{label}: row {idx} field '{field_name}' is empty; "
            f"a numeric value is required"
        )
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{label}: row {idx} field '{field_name}' is not a number "
            f"(got {raw_value!r})"
        )


def _parse_trigger_event(raw_value) -> object:
    """CSV trigger_event: empty string → None. Otherwise pass through
    as a string (raises if a CSV row somehow yielded a non-str)."""
    if raw_value is None or raw_value == "":
        return None
    if not isinstance(raw_value, str):
        # Defensive — csv.DictReader always returns strings.
        raise ValueError(
            f"trigger_event must be a string (got {type(raw_value).__name__})"
        )
    return raw_value


def _validate_json_numeric(
    value, field_name: str, idx: int, label: str,
) -> float:
    """Validate a JSON numeric value. Bool is rejected (bool is a
    subclass of int but semantically wrong here)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(
            f"{label}: points[{idx}].{field_name} must be a number "
            f"(got {type(value).__name__})"
        )
    return float(value)


def _validate_json_trigger(value, idx: int, label: str) -> object:
    """JSON trigger_event: must be a string or null/None. May be omitted
    entirely (caller passes the default None)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(
        f"{label}: points[{idx}].trigger_event must be a string or null "
        f"(got {type(value).__name__})"
    )


# ===========================================================================
# Single-party fear Timeline loaders
# ===========================================================================
def load_timeline_from_csv(path: str) -> Timeline:
    """Construct a Timeline from a CSV file at `path`.

    The `timeline_id` is derived from the filename stem.

    Raises:
        ValueError on header mismatch, missing fields, non-numeric
            numeric values, or unreadable file.
        OSError on I/O failure (passthrough from open).
    """
    label = "single_party_fear_csv"
    timeline_id = _filename_stem(path)
    if not timeline_id:
        raise ValueError(f"{label}: cannot derive timeline_id from path {path!r}")

    points: list = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_header(reader.fieldnames, _SP_CSV_HEADER, label)
        for idx, row in enumerate(reader):
            t = row.get("t")
            if not isinstance(t, str) or t == "":
                raise ValueError(
                    f"{label}: row {idx} field 't' is empty or missing"
                )
            kw: dict = {"t": t}
            for fname in _SP_NUMERIC_FIELDS:
                kw[fname] = _parse_csv_numeric(row.get(fname), fname, idx, label)
            kw["trigger_event"] = _parse_trigger_event(row.get("trigger_event"))
            points.append(TimePoint(**kw))

    return Timeline(timeline_id=timeline_id, points=tuple(points))


def load_timeline_from_json(obj: dict) -> Timeline:
    """Construct a Timeline from an in-memory JSON dict. No file I/O.

    Raises:
        ValueError on missing/empty `timeline_id`, non-list `points`,
        missing fields, or non-numeric numeric values.
    """
    label = "single_party_fear_json"
    if not isinstance(obj, dict):
        raise ValueError(f"{label}: expected dict, got {type(obj).__name__}")

    timeline_id = obj.get("timeline_id")
    points_raw = obj.get("points")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise ValueError(f"{label}: timeline_id must be a non-empty string")
    if not isinstance(points_raw, list):
        raise ValueError(f"{label}: points must be a list")

    points: list = []
    for idx, p in enumerate(points_raw):
        if not isinstance(p, dict):
            raise ValueError(
                f"{label}: points[{idx}] must be a JSON object"
            )
        t = p.get("t")
        if not isinstance(t, str) or t == "":
            raise ValueError(
                f"{label}: points[{idx}].t must be a non-empty string"
            )
        kw: dict = {"t": t}
        for fname in _SP_NUMERIC_FIELDS:
            if fname not in p:
                raise ValueError(
                    f"{label}: points[{idx}] missing required field '{fname}'"
                )
            kw[fname] = _validate_json_numeric(p[fname], fname, idx, label)
        kw["trigger_event"] = _validate_json_trigger(
            p.get("trigger_event"), idx, label,
        )
        points.append(TimePoint(**kw))

    return Timeline(timeline_id=timeline_id, points=tuple(points))


# ===========================================================================
# Economic-coercion TimelineEconomic loaders
# ===========================================================================
def load_economic_timeline_from_csv(path: str) -> TimelineEconomic:
    """Construct a TimelineEconomic from a CSV file at `path`.

    The `timeline_id` is derived from the filename stem.

    Raises:
        ValueError on header mismatch, missing fields, non-numeric
            numeric values, or unreadable file.
        OSError on I/O failure (passthrough from open).
    """
    label = "economic_coercion_csv"
    timeline_id = _filename_stem(path)
    if not timeline_id:
        raise ValueError(f"{label}: cannot derive timeline_id from path {path!r}")

    points: list = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _validate_csv_header(reader.fieldnames, _EC_CSV_HEADER, label)
        for idx, row in enumerate(reader):
            t = row.get("t")
            if not isinstance(t, str) or t == "":
                raise ValueError(
                    f"{label}: row {idx} field 't' is empty or missing"
                )
            kw: dict = {"t": t}
            for fname in _EC_NUMERIC_FIELDS:
                kw[fname] = _parse_csv_numeric(row.get(fname), fname, idx, label)
            kw["trigger_event"] = _parse_trigger_event(row.get("trigger_event"))
            points.append(TimePointEconomic(**kw))

    return TimelineEconomic(timeline_id=timeline_id, points=tuple(points))


def load_economic_timeline_from_json(obj: dict) -> TimelineEconomic:
    """Construct a TimelineEconomic from an in-memory JSON dict. No
    file I/O.

    Raises:
        ValueError on missing/empty `timeline_id`, non-list `points`,
        missing fields, or non-numeric numeric values.
    """
    label = "economic_coercion_json"
    if not isinstance(obj, dict):
        raise ValueError(f"{label}: expected dict, got {type(obj).__name__}")

    timeline_id = obj.get("timeline_id")
    points_raw = obj.get("points")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise ValueError(f"{label}: timeline_id must be a non-empty string")
    if not isinstance(points_raw, list):
        raise ValueError(f"{label}: points must be a list")

    points: list = []
    for idx, p in enumerate(points_raw):
        if not isinstance(p, dict):
            raise ValueError(
                f"{label}: points[{idx}] must be a JSON object"
            )
        t = p.get("t")
        if not isinstance(t, str) or t == "":
            raise ValueError(
                f"{label}: points[{idx}].t must be a non-empty string"
            )
        kw: dict = {"t": t}
        for fname in _EC_NUMERIC_FIELDS:
            if fname not in p:
                raise ValueError(
                    f"{label}: points[{idx}] missing required field '{fname}'"
                )
            kw[fname] = _validate_json_numeric(p[fname], fname, idx, label)
        kw["trigger_event"] = _validate_json_trigger(
            p.get("trigger_event"), idx, label,
        )
        points.append(TimePointEconomic(**kw))

    return TimelineEconomic(timeline_id=timeline_id, points=tuple(points))
