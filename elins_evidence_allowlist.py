"""
elins_evidence_allowlist.py — ELINS Unit 24.

Security hardening for the directory-scan path. Caller-supplied evidence
directories must lie inside one of a small set of operator-allowlisted
roots; symlinks that escape a root, ``..`` traversal, and relative
paths are all rejected.

WHY
---
Unit 9 introduced the directory scanner and Unit 19 captured
``evidence_dir`` in run metadata. Both happily accepted any path the
caller passed. Without an allowlist, a hostile / careless client could
point the scanner at ``/etc`` or ``C:\\Windows\\System32`` and have its
contents (or path leaks via metadata) exposed via the listing endpoint.

Unit 24 closes that gap: the validator runs at the start of
``analyze_and_store`` for the directory branch, and a malformed path
short-circuits to a ``ValueError`` (translated to HTTP 400 at the
endpoint layer).

ALLOWLIST CONFIGURATION
-----------------------
``ALLOWED_EVIDENCE_DIRS`` is a module-level tuple of absolute paths.
The default is ``("/evidence", "/var/evidence")`` — operators extend
or replace it for their deployment. Tests monkeypatch the constant
(see ``tests/conftest.py`` for the autouse fixture that allows
``tempfile.gettempdir()`` so pytest ``tmp_path`` paths pass).

VALIDATION RULES
----------------
``validate_evidence_dir(path)`` rejects with
``ValueError("evidence_dir_not_allowed: ...")`` when the path:

    * is not a non-empty string
    * is not absolute
    * contains a ``..`` segment (defense in depth — even though
      ``os.path.normpath`` would resolve it)
    * is not an existing directory
    * after symlink resolution falls outside every allowlisted root

On success, returns the symlink-resolved, normalised absolute path so
the caller can use it for both the scan and the metadata field.

I/O CONTRACT
------------
Stat-style filesystem reads only (``os.path.isabs/isdir/realpath/
normpath/commonpath``). No file content reads, no logging, no network,
no randomness.

PUBLIC API
----------
    ALLOWED_EVIDENCE_DIRS: tuple[str, ...]
    validate_evidence_dir(path: str) -> str
"""
from __future__ import annotations

import os


# Locked default allowlist. Operators override per deployment by setting
# this attribute on the module (or by editing the source for a fresh
# install). Tests monkeypatch it via the autouse fixture in conftest.py.
ALLOWED_EVIDENCE_DIRS: tuple = (
    "/evidence",
    "/var/evidence",
)


# Locked error prefix — tests grep on this string.
_ERROR_PREFIX: str = "evidence_dir_not_allowed"


def _split_segments(path: str) -> list:
    """Split a path into segments using both ``/`` and ``\\`` so a
    Windows-style path like ``C:\\foo\\..\\bar`` and a POSIX-style
    ``/foo/../bar`` both expose ``..`` to the traversal check."""
    return path.replace("\\", "/").split("/")


def validate_evidence_dir(path) -> str:
    """Validate `path` against the active allowlist + safety rules.

    Args:
        path: caller-supplied evidence directory.

    Returns:
        The symlink-resolved, normalised absolute path. Use this value
        for both the scan and any metadata persistence so the stored
        ``evidence_dir`` matches what was actually scanned.

    Raises:
        ValueError prefixed with ``evidence_dir_not_allowed:`` for any
        of the rejection reasons documented in the module docstring.
    """
    if not isinstance(path, str) or not path:
        raise ValueError(
            f"{_ERROR_PREFIX}: path must be a non-empty string"
        )
    if not os.path.isabs(path):
        raise ValueError(
            f"{_ERROR_PREFIX}: path must be absolute, got {path!r}"
        )

    # Defense in depth: reject any path whose textual form contains a
    # ``..`` segment, even though ``normpath`` would otherwise resolve
    # it. This makes the allowlist contract auditable from the raw
    # string alone.
    if ".." in _split_segments(path):
        raise ValueError(
            f"{_ERROR_PREFIX}: parent-directory traversal not allowed "
            f"in {path!r}"
        )

    normalized = os.path.normpath(path)
    if not os.path.isdir(normalized):
        raise ValueError(
            f"{_ERROR_PREFIX}: path is not an existing directory: "
            f"{normalized!r}"
        )

    # Resolve symlinks BEFORE the containment check — a symlink inside
    # an allowlisted root that points outside it must be rejected.
    real_path = os.path.realpath(normalized)

    for root in ALLOWED_EVIDENCE_DIRS:
        if not isinstance(root, str) or not root:
            continue
        real_root = os.path.realpath(os.path.normpath(root))
        try:
            common = os.path.commonpath([real_root, real_path])
        except ValueError:
            # Different drive on Windows — try the next root.
            continue
        if common == real_root:
            return real_path

    raise ValueError(
        f"{_ERROR_PREFIX}: path is not inside any allowlisted root: "
        f"{real_path!r}"
    )
