"""
elins_persistence.py — ELINS Unit 10 / 19 / 20 / 25 façade.

Drop-in re-export of the SQLite-backed persistence layer introduced in
Unit 25. Public API, envelope semantics, validation, listing, and
metadata are identical to the pre-Unit-25 file-based implementation;
storage moved from one JSON file per run to a single SQLite database
file (default: ``./elins_runs/elins_runs.db``).

Every public name that callers, analytics modules, and tests imported
from this module continues to be exported from here. Internal helpers
(``_validate_run_id``, the metadata-field name constants, the run-id
regex, etc.) are also re-exported because tests and sibling modules
reference them directly.

See ``elins_persistence_sqlite`` for the backing implementation and
the migration logic that lifts pre-Unit-25 ``*.json`` files into the
new database on first access.
"""
from __future__ import annotations

# Public API — exactly the surface the pre-Unit-25 module exposed.
from elins_persistence_sqlite import (  # noqa: F401
    save_comparison_result,
    load_comparison_result,
    delete_comparison_result,
    delete_run,
    delete_runs_older_than,
    list_runs,
    list_runs_with_metadata,
    query_runs,
    # Unit 27/28 — operator utilities
    get_notes,
    set_notes,
    get_tags,
    set_tags,
    get_archived,
    set_archived,
    rename_run,
)

# Internal helpers + module constants that other ELINS modules and the
# test suite reach in to. Kept stable across Unit 25 so nothing else
# needs to change.
from elins_persistence_sqlite import (  # noqa: F401
    _DEFAULT_RUNS_DIR,
    _RUNS_DIR_ENV_VAR,
    _DB_PATH_ENV_VAR,
    _DB_FILENAME,
    _RUN_ID_RE,
    _ENGINE_VERSION,
    _ALLOWED_SOURCES,
    _LISTING_FIELDS,
    _META_CREATED_AT_FIELD,
    _META_SOURCE_FIELD,
    _META_EVIDENCE_DIR_FIELD,
    _META_ENGINE_VERSION_FIELD,
    _ENVELOPE_METADATA_KEY,
    _ENVELOPE_RESULT_KEY,
    _validate_run_id,
    _validate_source,
    _build_metadata,
    _set_run_created_at,
    _reset_init_cache_for_tests,
)

# Re-export the underlying ``datetime`` symbol so tests that previously
# monkeypatched ``elins_persistence.datetime`` (Unit 19 timestamp
# injection pattern) keep working transparently against the new module.
from elins_persistence_sqlite import datetime  # noqa: F401
