"""
elins_directory_scanner.py — ELINS Unit 9.

Bridge between filesystem evidence sets and the batch comparison engine.

Given a directory containing files named with the convention
``<stem>_sp.{csv,json}`` and ``<stem>_ec.{csv,json}``, builds a list of
``(Timeline, TimelineEconomic)`` pairs for the matching stems. Loaders
from Unit 6 do the actual parsing.

ROLE
----
Pure adapter (modulo file I/O). Does not run any regressions itself —
just produces typed pairs that downstream batch comparison consumes.

I/O CONTRACT
------------
The only allowed I/O is file reads:
    * `os.listdir(path)` to enumerate the directory
    * `open()` for JSON files (CSV files are opened by the Unit 6
      CSV loaders themselves)

No logging, no network, no LLM, no randomness, no mutation.

PAIRING RULES
-------------
1. A "pair" is two files in the directory sharing a stem and the
   ``_sp`` / ``_ec`` role suffix.
2. Files that don't match the regex are ignored (e.g., README.md,
   notes.txt, foo.tmp).
3. Stems with only one role present (sp without ec, or vice versa)
   are silently dropped — they don't form a pair.
4. **Ambiguity is rejected**: if both ``case01_sp.csv`` and
   ``case01_sp.json`` exist for the same stem, ``ValueError`` is
   raised. This forces the operator to clean up evidence inputs
   rather than silently picking one format over the other.
5. Output is sorted by stem ascending for deterministic ordering.
6. Subdirectories are ignored (only top-level files are scanned).

PUBLIC API
----------
    scan_directory_for_timeline_pairs(path) -> list[tuple[Timeline, TimelineEconomic]]
"""
from __future__ import annotations

import json
import os
import re

from elins_regression_economic_coercion import TimelineEconomic
from elins_regression_single_party import Timeline
from elins_timeline_ingest import (
    load_economic_timeline_from_csv,
    load_economic_timeline_from_json,
    load_timeline_from_csv,
    load_timeline_from_json,
)


# Locked file-name regex. Match on the full filename. Groups:
#   1 = stem (anything non-empty up to the role suffix)
#   2 = role: "sp" or "ec"
#   3 = extension: "csv" or "json"
_PAIR_FILE_RE = re.compile(r"^(.+)_(sp|ec)\.(csv|json)$")


def _load_sp(path: str, ext: str) -> Timeline:
    """Dispatch SP load by extension."""
    if ext == "csv":
        return load_timeline_from_csv(path)
    # ext == "json"
    with open(path, "r", encoding="utf-8") as fh:
        obj = json.load(fh)
    return load_timeline_from_json(obj)


def _load_ec(path: str, ext: str) -> TimelineEconomic:
    """Dispatch EC load by extension."""
    if ext == "csv":
        return load_economic_timeline_from_csv(path)
    # ext == "json"
    with open(path, "r", encoding="utf-8") as fh:
        obj = json.load(fh)
    return load_economic_timeline_from_json(obj)


def scan_directory_for_timeline_pairs(path: str) -> list:
    """Scan a directory for matching SP/EC file pairs and load each
    into typed timelines.

    Args:
        path: directory path (absolute or relative). Subdirectories
            are not traversed.

    Returns:
        list of 2-tuples ``(Timeline, TimelineEconomic)`` in stem-
        ascending order. Empty list if the directory has no matching
        complete pairs.

    Raises:
        ValueError if `path` is not a non-empty string.
        FileNotFoundError if the path does not exist.
        NotADirectoryError if the path exists but is not a directory.
        ValueError if a stem has duplicate role files (e.g., both
            case01_sp.csv and case01_sp.json).
        ValueError (propagated from Unit 6 ingestors) if a matched
            file is malformed.
    """
    if not isinstance(path, str) or not path:
        raise ValueError(
            f"scan_directory_for_timeline_pairs expected non-empty str, "
            f"got {type(path).__name__}"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(f"directory not found: {path!r}")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"path is not a directory: {path!r}")

    # Bucket: pairs[stem] = {"sp": (full_path, ext), "ec": (full_path, ext)}
    pairs: dict = {}
    for entry in os.listdir(path):
        full = os.path.join(path, entry)
        if not os.path.isfile(full):
            continue   # skip subdirectories
        m = _PAIR_FILE_RE.match(entry)
        if not m:
            continue   # skip unrelated files
        stem, role, ext = m.group(1), m.group(2), m.group(3)
        bucket = pairs.setdefault(stem, {})
        if role in bucket:
            other_path = bucket[role][0]
            raise ValueError(
                f"ambiguous role for stem {stem!r}: "
                f"both {os.path.basename(other_path)!r} and {entry!r} "
                f"present; remove one to disambiguate"
            )
        bucket[role] = (full, ext)

    out: list = []
    for stem in sorted(pairs.keys()):
        bucket = pairs[stem]
        if "sp" not in bucket or "ec" not in bucket:
            continue   # silently drop incomplete pairs
        sp_path, sp_ext = bucket["sp"]
        ec_path, ec_ext = bucket["ec"]
        sp_tl = _load_sp(sp_path, sp_ext)
        ec_tl = _load_ec(ec_path, ec_ext)
        out.append((sp_tl, ec_tl))

    return out
