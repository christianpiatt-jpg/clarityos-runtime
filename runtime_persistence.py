"""
runtime_persistence.py — Unit 42.

Minimal persistence layer for the runtime loop: vault_state keyed by
operator_id and session_state keyed by session_id. In-memory by
default; opt-in JSON-file backing via an env var. Designed to be wired
under Unit 40 (``session_loop``) and Unit 41 (``runtime_http``) in a
later unit — this module intentionally ships **only** the
load/save surface and leaves the integration call to whoever needs it.

Naming note: ``runtime_persistence`` (not ``persistence`` or
``vault_store``) because the existing repo already has a
``vault_store`` module (file-backed operator-vault storage) and a
``sessions_store`` module (auth session tokens) with different
semantics. The "runtime" prefix scopes this layer to the runtime
loop established by Units 35-41.

ROLE
----
Read/write the two state objects that the runtime loop produces:

    * ``vault_state``   — Unit 35's merged vault output, keyed by operator_id
    * ``session_state`` — Unit 40's façade state,        keyed by session_id

Both objects are JSON-safe by construction; every save is validated
via ``json.dumps`` before commit so non-serializable values fail fast
at the boundary rather than corrupting state in memory.

BACKENDS (LOCKED)
-----------------
Two backends, selected by ``CLARITYOS_RUNTIME_STORE_DIR``:

    unset / empty   → in-memory backend
                      (process-local dicts, lost on restart)
    set to a path   → file backend
                      ({dir}/vault/{operator_id}.json
                       {dir}/session/{session_id}.json)

Switching at runtime is supported (caller can change the env var and
call ``reload_backend()``); the in-memory dict is preserved across
backend switches but lookups in file-mode hit disk first then fall
back to the in-memory dict. This lets tests use file-mode without
losing test fixtures and lets the production process boot file-mode
without re-priming.

CONCURRENCY
-----------
Single-process safe. Multi-process concurrency is out of scope —
later units will add file locking or move to sqlite if needed.

PUBLIC API
----------
    load_vault(operator_id:  str) -> dict | None
    save_vault(operator_id:  str, vault_state: dict) -> None
    load_session(session_id: str) -> dict | None
    save_session(session_state: dict) -> None

    reload_backend() -> None     # re-read CLARITYOS_RUNTIME_STORE_DIR
    _reset_for_tests() -> None   # wipe in-memory dicts + clear backend
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_ENV_DIR = "CLARITYOS_RUNTIME_STORE_DIR"

# Strict ID validation — both keys are filenames in the file backend,
# so we reject anything that could path-traverse or hit reserved
# Windows names. Letters, digits, dash, underscore, dot. 1-128 chars.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _validate_id(value, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    if not _ID_RE.match(value):
        raise ValueError(
            f"{field_name} must match {_ID_RE.pattern!r}, got {value!r}"
        )
    return value


def _validate_jsonable(payload, field_name: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError(
            f"{field_name} must be a dict, got {type(payload).__name__}"
        )
    # Round-trip through JSON so non-serializable values fail at the
    # boundary, not at read time on some other machine.
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"{field_name} must be JSON-serializable: {e}"
        )
    return payload


# ---------------------------------------------------------------------------
# Backend state — module-level so swaps work across imports
# ---------------------------------------------------------------------------
_VAULTS:   dict[str, dict] = {}
_SESSIONS: dict[str, dict] = {}
_STORE_DIR: Optional[Path] = None

# ---------------------------------------------------------------------------
# v62 / Unit 46 — Per-operator write lock
#
# Prevents two threads writing to the same operator's vault from
# racing on the file-mode atomic-replace (where both writers share a
# single ``{path}.tmp`` filename, leading to "thread A's replace
# commits thread B's content" interleaving). In in-memory mode the
# GIL already serializes single-key dict assignment, so the lock is
# belt-and-suspenders there.
#
# IMPORTANT — what this DOES NOT solve:
#   The documented v43 "vault hydrated only at start" race is a
#   lost-update problem, not a partial-write one. Two sessions A and
#   B for the same operator each hold their own session_state with
#   different vault snapshots; whoever calls save_vault last
#   silently overwrites the other's contribution. The lock here
#   serializes the writes but each writer still doesn't see the
#   other's update. Fixing lost-updates would require a
#   read-modify-write transaction inside save_vault OR per-step
#   re-hydration in session_loop.step_session — both are larger
#   changes and belong to a later unit.
#
# Scope:
#   * save_vault    is wrapped (per-operator lock).
#   * save_session  is NOT wrapped — sessions are keyed by session_id,
#     and per-session locks would never contend on the same key. A
#     future unit can add per-session locks if multiple writers to
#     the same session_id ever appear.
#
# Lock identity:
#   * Per-operator threading.Lock, stored in _OPERATOR_LOCKS.
#   * _LOCK_REGISTRY_LOCK guards the registry itself so two threads
#     can't create duplicate locks for the same operator on first
#     access.
# ---------------------------------------------------------------------------
_OPERATOR_LOCKS: dict[str, threading.Lock] = {}
_LOCK_REGISTRY_LOCK = threading.Lock()

# v63 / Unit 48 — per-operator wallclock timestamp of the most recent
# save_vault call. In-memory only; restarts wipe the map. (The vault
# itself survives via the file backend; only the "last touched at"
# metadata is volatile.) File persistence for this is a future unit
# — for the MVP inspector, in-memory is enough.
_VAULT_TIMESTAMPS: dict[str, str] = {}


def _vault_clock_now() -> str:
    """ISO-8601 UTC timestamp. Module-level so tests can monkey-patch."""
    return datetime.now(timezone.utc).isoformat()


def _operator_lock(operator_id: str) -> threading.Lock:
    """Return the threading.Lock for ``operator_id``, creating one
    on first access. Double-checked locking on the registry — the
    fast path doesn't hold the registry lock."""
    lock = _OPERATOR_LOCKS.get(operator_id)
    if lock is not None:
        return lock
    with _LOCK_REGISTRY_LOCK:
        lock = _OPERATOR_LOCKS.get(operator_id)
        if lock is None:
            lock = threading.Lock()
            _OPERATOR_LOCKS[operator_id] = lock
        return lock


def _resolve_store_dir() -> Optional[Path]:
    raw = (os.environ.get(_ENV_DIR) or "").strip()
    if not raw:
        return None
    return Path(raw)


def reload_backend() -> None:
    """Re-read ``CLARITYOS_RUNTIME_STORE_DIR`` and create the directory
    structure when file-mode is active. Safe to call repeatedly."""
    global _STORE_DIR
    _STORE_DIR = _resolve_store_dir()
    if _STORE_DIR is not None:
        (_STORE_DIR / "vault").mkdir(parents=True, exist_ok=True)
        (_STORE_DIR / "session").mkdir(parents=True, exist_ok=True)


reload_backend()


# ---------------------------------------------------------------------------
# File I/O helpers (only used when _STORE_DIR is set)
# ---------------------------------------------------------------------------
def _vault_path(operator_id: str) -> Path:
    assert _STORE_DIR is not None
    return _STORE_DIR / "vault" / f"{operator_id}.json"


def _session_path(session_id: str) -> Path:
    assert _STORE_DIR is not None
    return _STORE_DIR / "session" / f"{session_id}.json"


def _read_file(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"could not read {path}: {e}")
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"corrupted JSON in {path}: {e}")
    if not isinstance(loaded, dict):
        raise ValueError(
            f"expected dict in {path}, got {type(loaded).__name__}"
        )
    return loaded


def _write_file(path: Path, payload: dict) -> None:
    # Write to a temp sibling then atomic rename so a partial write
    # never leaves a corrupted file behind. The temp file uses the
    # same parent so the rename is atomic on every supported OS.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Vault — load / save
# ---------------------------------------------------------------------------
def load_vault(operator_id) -> Optional[dict]:
    """Return the vault_state for ``operator_id``, or None if absent.

    File-mode reads disk first then falls back to the in-memory dict
    so callers see the most-recent committed state regardless of which
    process last wrote.

    Raises:
        ValueError: malformed operator_id, unreadable file, corrupted JSON.
    """
    _validate_id(operator_id, "operator_id")
    if _STORE_DIR is not None:
        on_disk = _read_file(_vault_path(operator_id))
        if on_disk is not None:
            return on_disk
    return _VAULTS.get(operator_id)


def save_vault(operator_id, vault_state) -> None:
    """Overwrite the stored vault_state for ``operator_id``.

    v62 / Unit 46: wrapped in a per-operator threading.Lock so two
    threads writing the same operator's vault don't race on the
    file-mode ``{path}.tmp → replace`` sequence. See module docstring
    above the lock registry for the scope of this protection.

    Raises:
        ValueError: malformed operator_id or non-JSON-safe vault_state.
    """
    _validate_id(operator_id, "operator_id")
    _validate_jsonable(vault_state, "vault_state")
    with _operator_lock(operator_id):
        _VAULTS[operator_id] = vault_state
        # v63 / Unit 48: stamp the wallclock so /operator/vault/{id}
        # can surface a meaningful last_updated to the inspector UI.
        _VAULT_TIMESTAMPS[operator_id] = _vault_clock_now()
        if _STORE_DIR is not None:
            _write_file(_vault_path(operator_id), vault_state)


# ---------------------------------------------------------------------------
# Session — load / save
# ---------------------------------------------------------------------------
def load_session(session_id) -> Optional[dict]:
    """Return the session_state for ``session_id``, or None if absent.

    Same disk-then-memory precedence as ``load_vault``.

    Raises:
        ValueError: malformed session_id, unreadable file, corrupted JSON.
    """
    _validate_id(session_id, "session_id")
    if _STORE_DIR is not None:
        on_disk = _read_file(_session_path(session_id))
        if on_disk is not None:
            return on_disk
    return _SESSIONS.get(session_id)


def save_session(session_state) -> None:
    """Upsert ``session_state`` keyed by ``session_state['session_id']``.

    Raises:
        ValueError: missing/malformed session_id or non-JSON-safe state.
    """
    if not isinstance(session_state, dict):
        raise ValueError(
            f"session_state must be a dict, "
            f"got {type(session_state).__name__}"
        )
    if "session_id" not in session_state:
        raise ValueError("session_state missing required key 'session_id'")
    session_id = _validate_id(session_state["session_id"], "session_id")
    _validate_jsonable(session_state, "session_state")
    _SESSIONS[session_id] = session_state
    if _STORE_DIR is not None:
        _write_file(_session_path(session_id), session_state)


def list_sessions_for_operator(operator_id) -> list:
    """v63 / Unit 47: return summary entries for every session whose
    ``operator_id`` matches.

    Each entry is::

        {
          "session_id":  str,
          "operator_id": str,
          "history_len": int,     # number of step entries
          "timestamp":   str,     # most-recent step timestamp, or ""
        }

    The summary excludes ``vault_state`` and ``history`` so listing is
    cheap even when the operator has many long-running sessions. Use
    ``load_session`` to fetch a single session's full state.

    Sort: newest first by ``timestamp`` (empty timestamps sort to the
    end). Stable on tie.

    File-mode caveat: iterating disk + in-memory means reading every
    session file. O(N) per call where N is total sessions on disk.
    Acceptable at MVP scale; a future unit can add an index if needed.

    Raises:
        ValueError: malformed operator_id, unreadable file, or
            corrupted JSON in any session file on disk.
    """
    _validate_id(operator_id, "operator_id")

    # Gather candidates from both backends. Disk takes precedence for
    # the per-session content (same disk-first rule as load_session).
    seen: dict[str, dict] = {}
    if _STORE_DIR is not None:
        session_dir = _STORE_DIR / "session"
        if session_dir.is_dir():
            for path in session_dir.glob("*.json"):
                if path.suffix.lower() != ".json":
                    continue
                if path.name.endswith(".tmp.json"):
                    continue
                stored = _read_file(path)
                if not isinstance(stored, dict):
                    continue
                sid = stored.get("session_id")
                if isinstance(sid, str) and sid:
                    seen[sid] = stored
    for sid, stored in _SESSIONS.items():
        if sid not in seen:
            seen[sid] = stored

    summaries: list[dict] = []
    for sid, stored in seen.items():
        if not isinstance(stored, dict):
            continue
        if stored.get("operator_id") != operator_id:
            continue
        history = stored.get("history")
        history_len = len(history) if isinstance(history, list) else 0
        timestamp = ""
        if isinstance(history, list) and history:
            last = history[-1]
            if isinstance(last, dict):
                ts = last.get("timestamp")
                if isinstance(ts, str):
                    timestamp = ts
        summaries.append({
            "session_id":  sid,
            "operator_id": operator_id,
            "history_len": history_len,
            "timestamp":   timestamp,
        })

    # Newest first; empty timestamps go to the end. Tuple-key sort
    # keeps the comparison total-ordered.
    summaries.sort(
        key=lambda s: (s["timestamp"] == "", s["timestamp"]),
        reverse=False,
    )
    # The first key gives empty-last; the second gives ascending
    # within the non-empty group. Reverse the non-empty group so
    # newest-first.
    non_empty = [s for s in summaries if s["timestamp"] != ""]
    empty = [s for s in summaries if s["timestamp"] == ""]
    non_empty.sort(key=lambda s: s["timestamp"], reverse=True)
    return non_empty + empty


def get_vault_last_updated(operator_id) -> str:
    """v63 / Unit 48: return the most-recent save_vault wallclock for
    ``operator_id``, or "" if the operator has no vault on record.

    The actual ELINS payload (last_fusion / last_long_arc) doesn't
    carry timestamps in the current v33/v34 runtime output, so
    deriving from the payload is unreliable. Instead save_vault
    stamps ``_VAULT_TIMESTAMPS`` server-side on every commit.

    Raises:
        ValueError: malformed operator_id (same regex as load_vault).
    """
    _validate_id(operator_id, "operator_id")
    return _VAULT_TIMESTAMPS.get(operator_id, "")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    """Wipe the in-memory maps. Does NOT delete files on disk —
    tests that exercise the file backend should use a ``tmp_path``
    so cleanup happens automatically when pytest tears down the
    fixture.

    v62 / Unit 46: also wipes the per-operator lock registry. Locks
    held by a still-running thread would block forever if recycled,
    but tests that need the lock during torture cases acquire fresh
    locks after this reset — safe because Python's GC won't collect
    a Lock with active holders.
    """
    _VAULTS.clear()
    _SESSIONS.clear()
    _VAULT_TIMESTAMPS.clear()
    with _LOCK_REGISTRY_LOCK:
        _OPERATOR_LOCKS.clear()
