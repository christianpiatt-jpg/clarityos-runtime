"""
elins_persistence_sqlite.py — ELINS Unit 25.

SQLite-backed replacement for the Unit 10 / Unit 19 / Unit 20 file-based
persistence layer. Public API and envelope semantics are identical;
storage is now a single-table SQLite database with WAL mode for
concurrent readers + writers.

ENVELOPE
--------
Same as Unit 19::

    {
      "metadata": {
        "created_at":     "<ISO8601 UTC timestamp>",
        "source":         "single" | "batch" | "directory",
        "evidence_dir":   "<string or null>",
        "engine_version": "elins-19"
      },
      "result": <original payload>
    }

Legacy list-only files (from Unit 10) are read transparently and
returned as ``{"metadata": None, "result": <list>}`` — the same
behaviour the JSON loader had, preserved verbatim.

SCHEMA
------
::

    CREATE TABLE runs (
        run_id       TEXT PRIMARY KEY,
        envelope_json TEXT NOT NULL
    )

WAL mode is enabled at DB creation time (a persistent property of the
file). Foreign keys are enabled per connection for future-proofing.

DB PATH RESOLUTION
------------------
1. ``CLARITYOS_ELINS_RUNS_DB`` env var (explicit path) — highest precedence
2. ``CLARITYOS_ELINS_RUNS_DIR`` env var (legacy runs-dir) → DB stored at
   ``<that_dir>/elins_runs.db``
3. ``./elins_runs/elins_runs.db`` (default)

The legacy env var continues to work so existing test fixtures that
set ``CLARITYOS_ELINS_RUNS_DIR=<tmp_path>/elins_runs`` get a fresh
DB at ``<tmp_path>/elins_runs/elins_runs.db`` without modification.

MIGRATION
---------
On first access for a given DB path:
    * If the DB file does not exist:
        - Create it with the schema above + WAL mode.
        - Scan the legacy runs directory for ``*.json`` files.
        - Import each valid one (run_id stem matches the regex) into
          the DB, normalising legacy shapes through the same logic
          that the old loader applied.
        - Leave the JSON files in place (rollback-friendly).
    * If the DB file already exists:
        - Open it, set per-connection pragmas, return.

Migration is per-DB-path and one-shot; subsequent calls for the same
path bypass the scan.

I/O CONTRACT
------------
SQLite file I/O + (one-time) JSON file reads during migration. No
logging, no network, no LLM, no randomness (UUID generation lives in
the dashboard wrapper).

PUBLIC API
----------
    save_comparison_result(run_id, payload, *, source, evidence_dir) -> None
    load_comparison_result(run_id) -> dict
    delete_comparison_result(run_id) -> None         # spec name (Unit 25)
    delete_run(run_id) -> None                       # legacy alias
    delete_runs_older_than(days) -> list[str]
    list_runs() -> list[str]
    list_runs_with_metadata() -> list[dict]
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import datetime as _dt_module
from datetime import timedelta, timezone

# Module-level public binding for the ``datetime.datetime`` class. The
# ``_build_metadata`` and ``delete_runs_older_than`` paths read this
# binding so tests can monkeypatch it to inject canned clock values.
# Helpers that PARSE timestamps (``_parse_iso_filter_value``) reach into
# ``_dt_module.datetime`` directly so the injection doesn't break
# ``fromisoformat`` calls.
datetime = _dt_module.datetime


# ---- Locked module constants (mirror the Unit 10 / Unit 19 module) --------
_DEFAULT_RUNS_DIR: str = "./elins_runs"
_RUNS_DIR_ENV_VAR: str = "CLARITYOS_ELINS_RUNS_DIR"
_DB_PATH_ENV_VAR:  str = "CLARITYOS_ELINS_RUNS_DB"
_DB_FILENAME:      str = "elins_runs.db"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Unit 19 metadata constants.
_ENGINE_VERSION: str = "elins-19"
_ALLOWED_SOURCES: tuple = ("single", "batch", "directory")

_META_CREATED_AT_FIELD:     str = "created_at"
_META_SOURCE_FIELD:         str = "source"
_META_EVIDENCE_DIR_FIELD:   str = "evidence_dir"
_META_ENGINE_VERSION_FIELD: str = "engine_version"

_ENVELOPE_METADATA_KEY: str = "metadata"
_ENVELOPE_RESULT_KEY:   str = "result"

# Unit 20 + Unit 27/28 listing field order.
_LISTING_FIELDS: tuple = (
    "run_id",
    _META_CREATED_AT_FIELD,
    _META_SOURCE_FIELD,
    _META_EVIDENCE_DIR_FIELD,
    _META_ENGINE_VERSION_FIELD,
    "notes",      # Unit 28
    "tags",       # Unit 28
    "archived",   # Unit 28
)


# ---- One-shot init state, per DB path -------------------------------------
_INIT_LOCK = threading.Lock()
_INITIALIZED_PATHS: set = set()


def _reset_init_cache_for_tests() -> None:
    """Clear the per-path init cache. Used by test fixtures that wipe
    the runs directory mid-suite (uncommon)."""
    with _INIT_LOCK:
        _INITIALIZED_PATHS.clear()


# ---- Validation helpers (same contract as Unit 10/19) ---------------------
def _validate_run_id(run_id) -> None:
    if not isinstance(run_id, str):
        raise ValueError(
            f"run_id must be a string, got {type(run_id).__name__}"
        )
    if not run_id:
        raise ValueError("run_id must be non-empty")
    if not _RUN_ID_RE.match(run_id):
        raise ValueError(
            f"run_id {run_id!r} contains invalid characters; "
            f"only letters, digits, underscore, and hyphen are allowed"
        )


def _validate_source(source) -> None:
    if source not in _ALLOWED_SOURCES:
        raise ValueError(
            f"source must be one of {_ALLOWED_SOURCES}, got {source!r}"
        )


def _build_metadata(source: str, evidence_dir) -> dict:
    return {
        _META_CREATED_AT_FIELD:     datetime.now(timezone.utc).isoformat(),
        _META_SOURCE_FIELD:         source,
        _META_EVIDENCE_DIR_FIELD:   evidence_dir,
        _META_ENGINE_VERSION_FIELD: _ENGINE_VERSION,
    }


# ---- Path resolution + init ------------------------------------------------
def _runs_dir() -> str:
    return os.environ.get(_RUNS_DIR_ENV_VAR, _DEFAULT_RUNS_DIR)


def _resolve_db_path() -> str:
    """Resolve the SQLite DB path from env vars or defaults."""
    explicit = os.environ.get(_DB_PATH_ENV_VAR, "").strip()
    if explicit:
        return explicit
    return os.path.join(_runs_dir(), _DB_FILENAME)


def _legacy_json_dir() -> str:
    """Directory to scan for legacy *.json files during migration."""
    return _runs_dir()


def _normalise_legacy_load(loaded):
    """Match the pre-Unit-25 ``load_comparison_result`` envelope
    normalisation exactly. Used both at migration time and by any code
    path that needs to handle an arbitrary stored payload uniformly."""
    if isinstance(loaded, list):
        return {_ENVELOPE_METADATA_KEY: None, _ENVELOPE_RESULT_KEY: loaded}
    if isinstance(loaded, dict) and (
        _ENVELOPE_METADATA_KEY in loaded
        and _ENVELOPE_RESULT_KEY in loaded
    ):
        return loaded
    return {_ENVELOPE_METADATA_KEY: None, _ENVELOPE_RESULT_KEY: loaded}


def _migrate_json_dir_into(conn: sqlite3.Connection, json_dir: str) -> None:
    """Scan `json_dir` for legacy *.json files and import each into the
    open SQLite connection. Skips non-files, non-JSON extensions, and
    filenames that don't match the canonical run_id regex. Corrupt
    files are silently skipped (defensive — we don't want a malformed
    file to abort the migration of everything else)."""
    if not os.path.isdir(json_dir):
        return
    for entry in sorted(os.listdir(json_dir)):
        if not entry.endswith(".json"):
            continue
        # Skip the DB file itself if (somehow) it ended up named .json.
        if entry == _DB_FILENAME:
            continue
        stem = entry[: -len(".json")]
        if not _RUN_ID_RE.match(stem):
            continue
        full_path = os.path.join(json_dir, entry)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        envelope = _normalise_legacy_load(loaded)
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, envelope_json) VALUES (?, ?)",
            (stem, json.dumps(envelope, sort_keys=True, ensure_ascii=False)),
        )
    conn.commit()


def _ensure_init(db_path: str) -> None:
    """One-shot init for the DB at `db_path`. Creates the file +
    schema if missing, enables WAL, and runs the legacy JSON migration
    on first creation."""
    if db_path in _INITIALIZED_PATHS:
        return
    with _INIT_LOCK:
        if db_path in _INITIALIZED_PATHS:
            return
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        db_existed = os.path.exists(db_path)
        conn = sqlite3.connect(db_path)
        try:
            # WAL is a persistent property of the file, but setting it
            # repeatedly is harmless and gives us a stable contract.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                "run_id TEXT PRIMARY KEY, "
                "envelope_json TEXT NOT NULL)"
            )
            # Unit 27/28: extend the runs table with operator-utility
            # columns (notes / tags / archived). Each ALTER is wrapped
            # because re-running against a DB that already has the
            # column raises sqlite3.OperationalError. Idempotent by
            # design — running the init multiple times converges.
            for col_sql in (
                "ALTER TABLE runs ADD COLUMN notes TEXT DEFAULT NULL",
                "ALTER TABLE runs ADD COLUMN tags TEXT DEFAULT '[]'",
                "ALTER TABLE runs ADD COLUMN archived INTEGER DEFAULT 0",
            ):
                try:
                    conn.execute(col_sql)
                except sqlite3.OperationalError:
                    pass  # column already exists
            # ELINS2 Unit 11: cache table for full intelligence payloads.
            # Keyed by SHA-256 of the JSON-encoded ordered run_ids, so
            # order-sensitive — `[a, b]` and `[b, a]` cache to distinct
            # rows on purpose (sequence intelligence depends on order).
            conn.execute(
                "CREATE TABLE IF NOT EXISTS intelligence_cache ("
                "run_set_hash TEXT PRIMARY KEY, "
                "run_ids TEXT NOT NULL, "
                "payload TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "ttl_seconds INTEGER NOT NULL)"
            )
            conn.commit()
            if not db_existed:
                _migrate_json_dir_into(conn, _legacy_json_dir())
        finally:
            conn.close()
        _INITIALIZED_PATHS.add(db_path)


def _open() -> sqlite3.Connection:
    """Return a new connection to the active DB, with per-connection
    pragmas applied. Caller is responsible for closing."""
    db_path = _resolve_db_path()
    _ensure_init(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---- Public API -----------------------------------------------------------
def save_comparison_result(
    run_id: str,
    payload,
    *,
    source: str = "single",
    evidence_dir=None,
) -> None:
    """Persist `payload` under `run_id`, wrapped in a Unit 19 envelope.

    See module docstring for the envelope shape. Overwrites any
    existing row with the same ``run_id``; the new envelope reflects
    the current ``created_at`` timestamp.
    """
    _validate_run_id(run_id)
    _validate_source(source)
    envelope = {
        _ENVELOPE_METADATA_KEY: _build_metadata(source, evidence_dir),
        _ENVELOPE_RESULT_KEY:   payload,
    }
    body = json.dumps(envelope, sort_keys=True, ensure_ascii=False)
    conn = _open()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, envelope_json) VALUES (?, ?)",
            (run_id, body),
        )
        conn.commit()
    finally:
        conn.close()


def load_comparison_result(run_id: str) -> dict:
    """Return the envelope dict for the stored run, or raise
    ``FileNotFoundError`` if no such run exists."""
    _validate_run_id(run_id)
    conn = _open()
    try:
        row = conn.execute(
            "SELECT envelope_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")
    return json.loads(row[0])


def delete_comparison_result(run_id: str) -> None:
    """Remove a stored run by id.

    Raises ``FileNotFoundError`` if no such run exists (matching the
    pre-Unit-25 ``delete_run`` contract)."""
    _validate_run_id(run_id)
    conn = _open()
    try:
        cur = conn.execute(
            "DELETE FROM runs WHERE run_id = ?", (run_id,),
        )
        affected = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if affected == 0:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")


# Locked legacy alias — many call sites still use the Unit 10 name.
delete_run = delete_comparison_result


def delete_runs_older_than(days) -> list:
    """Delete every stored run whose ``metadata.created_at`` is more
    than `days` days in the past. Returns the deleted run_ids in
    alphabetical order.

    ``days == 0`` is special-cased as a no-op (matches the pre-Unit-25
    contract — protects against accidental "delete everything"
    requests via a zero arg).

    Legacy runs (``metadata is None`` or missing ``created_at``) are
    NEVER deleted by age — they have no timestamp to compare against.
    """
    if isinstance(days, bool) or not isinstance(days, int):
        raise ValueError(
            f"days must be a non-negative int, got {type(days).__name__}"
        )
    if days < 0:
        raise ValueError(f"days must be >= 0, got {days}")
    if days == 0:
        return []

    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()

    deleted: list = []
    conn = _open()
    try:
        rows = conn.execute(
            "SELECT run_id, envelope_json FROM runs"
        ).fetchall()
        for run_id, env_json in rows:
            try:
                envelope = json.loads(env_json)
            except json.JSONDecodeError:
                continue
            meta = envelope.get(_ENVELOPE_METADATA_KEY) \
                if isinstance(envelope, dict) else None
            if not isinstance(meta, dict):
                continue  # legacy → no age signal
            ts = meta.get(_META_CREATED_AT_FIELD)
            if not isinstance(ts, str) or not ts:
                continue
            if ts < cutoff_iso:
                conn.execute(
                    "DELETE FROM runs WHERE run_id = ?", (run_id,),
                )
                deleted.append(run_id)
        conn.commit()
    finally:
        conn.close()
    return sorted(deleted)


def list_runs() -> list:
    """List all stored run_ids in alphabetical order."""
    conn = _open()
    try:
        rows = conn.execute(
            "SELECT run_id FROM runs ORDER BY run_id ASC"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def _parse_tags_field(raw) -> list:
    """Decode the ``tags`` column. Defensive — returns ``[]`` for any
    malformed value so callers never see a stray non-list type."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [t for t in parsed if isinstance(t, str)]


def _flatten_listing_row(
    run_id, env_json, notes, tags_raw, archived_raw,
) -> dict:
    """Build a Unit 20 + Unit 27/28 flat listing row from the raw SQL
    column values. Single source of truth for the listing shape."""
    try:
        envelope = json.loads(env_json)
    except (json.JSONDecodeError, TypeError):
        envelope = {}
    meta = envelope.get(_ENVELOPE_METADATA_KEY) \
        if isinstance(envelope, dict) else None
    if isinstance(meta, dict):
        created_at     = meta.get(_META_CREATED_AT_FIELD)
        source         = meta.get(_META_SOURCE_FIELD)
        evidence_dir   = meta.get(_META_EVIDENCE_DIR_FIELD)
        engine_version = meta.get(_META_ENGINE_VERSION_FIELD)
    else:
        created_at     = None
        source         = None
        evidence_dir   = None
        engine_version = None
    return {
        "run_id":                   run_id,
        _META_CREATED_AT_FIELD:     created_at,
        _META_SOURCE_FIELD:         source,
        _META_EVIDENCE_DIR_FIELD:   evidence_dir,
        _META_ENGINE_VERSION_FIELD: engine_version,
        "notes":                    notes,
        "tags":                     _parse_tags_field(tags_raw),
        "archived":                 bool(archived_raw),
    }


def list_runs_with_metadata() -> list:
    """List all stored runs as flat metadata dicts, alphabetical by
    ``run_id``. Each entry has eight keys (Unit 20: ``run_id``,
    ``created_at``, ``source``, ``evidence_dir``, ``engine_version``;
    Unit 27/28: ``notes``, ``tags``, ``archived``). Legacy runs report
    ``None`` for every metadata field; ``notes`` defaults to ``None``,
    ``tags`` to ``[]``, ``archived`` to ``False``."""
    conn = _open()
    try:
        rows = conn.execute(
            "SELECT run_id, envelope_json, notes, tags, archived "
            "FROM runs ORDER BY run_id ASC"
        ).fetchall()
    finally:
        conn.close()
    return [_flatten_listing_row(*r) for r in rows]


def _parse_iso_filter_value(value, *, field: str):
    """Parse an ISO8601 timestamp string for the Unit 26 since/until
    filter. Naive timestamps are interpreted as UTC.

    Uses ``_dt_module.datetime`` directly so that tests which monkeypatch
    the module-level ``datetime`` binding for clock injection don't
    accidentally break parsing."""
    try:
        dt = _dt_module.datetime.fromisoformat(value)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"{field} must be a valid ISO8601 timestamp, got {value!r}"
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# Locked sort / order vocabularies for Unit 26.
_QUERY_SORT_FIELDS:  tuple = ("run_id", _META_CREATED_AT_FIELD)
_QUERY_ORDER_VALUES: tuple = ("asc", "desc")


def _validate_query_filters(
    source, since, until, sort, order, limit, offset,
) -> tuple:
    """Validate Unit 26 query params and return parsed since/until
    datetimes (or None) plus the normalised sort/order/limit/offset."""
    if source is not None and source not in _ALLOWED_SOURCES:
        raise ValueError(
            f"source must be one of {_ALLOWED_SOURCES}, got {source!r}"
        )
    since_dt = (
        _parse_iso_filter_value(since, field="since")
        if since is not None and since != "" else None
    )
    until_dt = (
        _parse_iso_filter_value(until, field="until")
        if until is not None and until != "" else None
    )
    if sort not in _QUERY_SORT_FIELDS:
        raise ValueError(
            f"sort must be one of {_QUERY_SORT_FIELDS}, got {sort!r}"
        )
    if order not in _QUERY_ORDER_VALUES:
        raise ValueError(
            f"order must be one of {_QUERY_ORDER_VALUES}, got {order!r}"
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
    return since_dt, until_dt, sort, order, limit, (offset or 0)


def query_runs(
    source=None,
    since=None,
    until=None,
    sort: str = "run_id",
    order: str = "asc",
    limit=None,
    offset=None,
    include_archived: bool = False,
) -> list:
    """Unit 26 + Unit 27/28: server-side filter + sort + paginate over
    the runs table.

    All parameters are optional; with everything default this returns
    the same shape and ordering as ``list_runs_with_metadata`` minus
    archived rows.

    Args:
        source: ``"single"`` / ``"batch"`` / ``"directory"`` filter.
            Legacy runs (source=None) are excluded when this is set.
        since: ISO8601 lower bound on ``metadata.created_at`` (inclusive).
            Naive timestamps interpreted as UTC. Legacy runs (no
            timestamp) are excluded when this is set.
        until: ISO8601 upper bound on ``metadata.created_at``
            (exclusive — half-open interval ``[since, until)``).
        sort: ``"run_id"`` or ``"created_at"``. Default ``"run_id"``.
        order: ``"asc"`` or ``"desc"``. Default ``"asc"``.
        limit: max number of rows to return (>= 1).
        offset: skip first N rows after sort + filter (>= 0).
        include_archived: when False (default), archived runs are
            excluded from the result. When True, all runs are
            considered regardless of archived flag.

    Returns:
        list[dict] with the Unit 20 + Unit 27/28 flat-metadata row
        shape (8 keys).

    Raises:
        ValueError on any malformed argument.
    """
    since_dt, until_dt, sort, order, limit, offset = (
        _validate_query_filters(
            source, since, until, sort, order, limit, offset,
        )
    )

    # Pull every row in one go — the metadata lives inside the
    # envelope JSON, so SQL-side filtering would require the json1
    # extension. In-Python filtering on the result set keeps the
    # backend portable across SQLite builds.
    conn = _open()
    try:
        rows = conn.execute(
            "SELECT run_id, envelope_json, notes, tags, archived "
            "FROM runs"
        ).fetchall()
    finally:
        conn.close()

    flat_rows: list = [_flatten_listing_row(*r) for r in rows]

    # Unit 27/28: hide archived runs unless explicitly opted in.
    if not include_archived:
        flat_rows = [r for r in flat_rows if not r["archived"]]

    # Apply filters.
    if source is not None:
        flat_rows = [
            r for r in flat_rows if r[_META_SOURCE_FIELD] == source
        ]
    if since_dt is not None or until_dt is not None:
        kept: list = []
        for r in flat_rows:
            ts = r[_META_CREATED_AT_FIELD]
            if not isinstance(ts, str):
                continue  # legacy → cannot satisfy time-range filter
            try:
                row_dt = _parse_iso_filter_value(ts, field="created_at")
            except ValueError:
                continue
            if since_dt is not None and row_dt < since_dt:
                continue
            if until_dt is not None and row_dt >= until_dt:
                continue
            kept.append(r)
        flat_rows = kept

    # Sort.
    reverse = (order == "desc")
    if sort == "run_id":
        flat_rows.sort(key=lambda r: r["run_id"], reverse=reverse)
    else:  # sort == "created_at"
        # Legacy runs (no timestamp) always go to the END regardless of
        # direction — they have no comparable signal. Within the
        # timestamped bucket, sort by (ts, run_id) so ties are broken
        # alphabetically by run_id.
        timestamped = [
            r for r in flat_rows if isinstance(r[_META_CREATED_AT_FIELD], str)
        ]
        legacy = [
            r for r in flat_rows
            if not isinstance(r[_META_CREATED_AT_FIELD], str)
        ]
        timestamped.sort(
            key=lambda r: (r[_META_CREATED_AT_FIELD], r["run_id"]),
            reverse=reverse,
        )
        legacy.sort(key=lambda r: r["run_id"])
        flat_rows = timestamped + legacy

    # Paginate.
    if offset:
        flat_rows = flat_rows[offset:]
    if limit is not None:
        flat_rows = flat_rows[:limit]

    return flat_rows


# ---- Unit 27/28 — operator utility accessors ------------------------------
def _run_exists_or_raise(conn, run_id: str) -> None:
    """Raise FileNotFoundError if `run_id` is not present in the runs
    table. Caller owns the connection."""
    row = conn.execute(
        "SELECT 1 FROM runs WHERE run_id = ?", (run_id,),
    ).fetchone()
    if row is None:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")


def get_notes(run_id: str):
    """Return the stored notes string for a run, or ``None`` if unset.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    conn = _open()
    try:
        row = conn.execute(
            "SELECT notes FROM runs WHERE run_id = ?", (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")
    return row[0]


def set_notes(run_id: str, notes) -> None:
    """Replace the stored notes for a run.

    Args:
        run_id: validated identifier.
        notes: a string or ``None`` (clears the field).

    Raises:
        ValueError on a malformed run_id or non-string non-None notes.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    if notes is not None and not isinstance(notes, str):
        raise ValueError(
            f"notes must be a string or None, got {type(notes).__name__}"
        )
    conn = _open()
    try:
        _run_exists_or_raise(conn, run_id)
        conn.execute(
            "UPDATE runs SET notes = ? WHERE run_id = ?",
            (notes, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_tags(run_id: str) -> list:
    """Return the stored tags list for a run.

    Empty list if no tags have been set; never returns ``None``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    conn = _open()
    try:
        row = conn.execute(
            "SELECT tags FROM runs WHERE run_id = ?", (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")
    return _parse_tags_field(row[0])


def set_tags(run_id: str, tags) -> None:
    """Replace the stored tags list for a run.

    Args:
        run_id: validated identifier.
        tags: list of strings. ``[]`` clears the field; ``None`` is
            rejected (use ``[]`` instead).

    Raises:
        ValueError on a malformed run_id or non-list/non-string-element
            tags.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    if not isinstance(tags, list):
        raise ValueError(
            f"tags must be a list, got {type(tags).__name__}"
        )
    for i, t in enumerate(tags):
        if not isinstance(t, str):
            raise ValueError(
                f"tags[{i}] must be a string, got {type(t).__name__}"
            )
    body = json.dumps(tags, ensure_ascii=False)
    conn = _open()
    try:
        _run_exists_or_raise(conn, run_id)
        conn.execute(
            "UPDATE runs SET tags = ? WHERE run_id = ?",
            (body, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_archived(run_id: str) -> bool:
    """Return ``True`` if the run is archived, else ``False``.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    conn = _open()
    try:
        row = conn.execute(
            "SELECT archived FROM runs WHERE run_id = ?", (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError(f"run_id not found: {run_id!r}")
    return bool(row[0])


def set_archived(run_id: str, flag) -> None:
    """Mark a run as archived (``flag=True``) or active (``flag=False``).

    Archived runs are hidden from the default listing endpoint; pass
    ``?include_archived=true`` to surface them.

    Raises:
        ValueError on a malformed run_id or non-bool flag.
        FileNotFoundError if the run does not exist.
    """
    _validate_run_id(run_id)
    if not isinstance(flag, bool):
        raise ValueError(
            f"flag must be a bool, got {type(flag).__name__}"
        )
    conn = _open()
    try:
        _run_exists_or_raise(conn, run_id)
        conn.execute(
            "UPDATE runs SET archived = ? WHERE run_id = ?",
            (1 if flag else 0, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def rename_run(old_run_id: str, new_run_id: str) -> None:
    """Rename a stored run by updating its primary-key column. All
    operator-utility metadata (notes / tags / archived) and the
    envelope payload are carried over to the new id atomically.

    No-op if ``old_run_id == new_run_id`` (consistent with
    ``save_comparison_result`` overwrite behaviour).

    Raises:
        ValueError on malformed ids or if ``new_run_id`` already exists.
        FileNotFoundError if ``old_run_id`` does not exist.
    """
    _validate_run_id(old_run_id)
    _validate_run_id(new_run_id)
    if old_run_id == new_run_id:
        return
    conn = _open()
    try:
        _run_exists_or_raise(conn, old_run_id)
        collision = conn.execute(
            "SELECT 1 FROM runs WHERE run_id = ?", (new_run_id,),
        ).fetchone()
        if collision is not None:
            raise ValueError(
                f"new_run_id already exists: {new_run_id!r}"
            )
        conn.execute(
            "UPDATE runs SET run_id = ? WHERE run_id = ?",
            (new_run_id, old_run_id),
        )
        conn.commit()
    finally:
        conn.close()


def _set_run_created_at(run_id: str, iso_timestamp: str) -> None:
    """Test helper: directly overwrite a stored run's
    ``metadata.created_at`` field. Used by the retention test fixture
    in place of the pre-Unit-25 file-mtime backdating trick.

    Raises FileNotFoundError if `run_id` is not stored."""
    _validate_run_id(run_id)
    if not isinstance(iso_timestamp, str) or not iso_timestamp:
        raise ValueError("iso_timestamp must be a non-empty string")
    conn = _open()
    try:
        row = conn.execute(
            "SELECT envelope_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"run_id not found: {run_id!r}")
        envelope = json.loads(row[0])
        if not isinstance(envelope.get(_ENVELOPE_METADATA_KEY), dict):
            envelope[_ENVELOPE_METADATA_KEY] = {}
        envelope[_ENVELOPE_METADATA_KEY][_META_CREATED_AT_FIELD] = (
            iso_timestamp
        )
        conn.execute(
            "UPDATE runs SET envelope_json = ? WHERE run_id = ?",
            (json.dumps(envelope, sort_keys=True, ensure_ascii=False),
             run_id),
        )
        conn.commit()
    finally:
        conn.close()
