"""
v51 — Projects vault: per-user project metadata + thread association.

Mirrors :mod:`threads_vault` in shape. Sits on top of :mod:`memory_vault`
and stores three documents per project:

* ``projects.{project_id}.meta``    — :class:`ProjectMeta`
* ``projects.{project_id}.summary`` — :class:`ProjectSummary`
* ``projects.{project_id}.threads`` — list[str] of thread_ids

Conceptually this maps to a ``vault/projects/{project_id}/`` folder with
``meta.json`` / ``summary.json`` / ``threads.json`` — the on-disk vault
backend just stores them under flat namespaced keys instead.

Public API
----------

    create_project(user_id, project_meta)                 -> ProjectMeta
    list_projects(user_id)                                -> list[ProjectMeta]
    get_project(user_id, project_id)                      -> ProjectMeta
    update_project(user_id, project_id, patch)            -> ProjectMeta
    update_project_summary(user_id, project_id, summary,
                           ts_ms=None)                    -> ProjectMeta
    add_thread_to_project(user_id, project_id, thread_id) -> list[str]
    remove_thread_from_project(user_id, project_id,
                               thread_id)                 -> list[str]
    list_project_threads(user_id, project_id)             -> list[str]
    is_thread_in_project(user_id, project_id, thread_id)  -> bool
    delete_project(user_id, project_id)                   -> None

    PROJECTS_VAULT_VERSION                                # version string

Errors
------
* :class:`KeyError`   — project not found.
* :class:`ValueError` — bad shape (empty user_id, illegal project_id, etc).

The app layer maps ``KeyError`` → 404 and ``ValueError`` → 400 (matches
the v47 / v50 contract).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional, TypedDict

import memory_vault

logger = logging.getLogger("clarityos.projects_vault")

PROJECTS_VAULT_VERSION: str = "projects_vault.v51.1"

_META_PREFIX:    str = "projects."
_META_SUFFIX:    str = ".meta"
_SUMMARY_SUFFIX: str = ".summary"
_THREADS_SUFFIX: str = ".threads"

# project_id format: alphanumeric + underscore + hyphen, length 1..64.
# Mirrors the conservative thread_id rules + matches the litigation-style
# ALL_CAPS tags the founder uses (VA_LITIGATION, MSJ_OPPOSITION, etc.).
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

# Soft caps so a single project document can't grow unbounded.
_MAX_NAME_LEN:        int = 200
_MAX_DESCRIPTION_LEN: int = 4000
_MAX_TAGS:            int = 32
_MAX_TAG_LEN:         int = 64
_MAX_THREADS:         int = 5000   # threads tracked per project index


# ---------------------------------------------------------------------------
# TypedDicts (documentation aid; wire schema enforced by Pydantic in app.py)
# ---------------------------------------------------------------------------
class ProjectMeta(TypedDict, total=False):
    project_id:     str
    name:           str
    description:    str
    default_model:  Optional[str]
    allowed_models: Optional[list[str]]
    tags:           list[str]
    created_at:     int
    updated_at:     int
    summary:        Optional[str]
    summary_ts_ms:  Optional[int]
    thread_count:   int


class ProjectSummary(TypedDict, total=False):
    summary: Optional[str]
    ts_ms:   Optional[int]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


def _validate_user(user_id: Any) -> str:
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    return user_id


def _validate_project_id(project_id: Any) -> str:
    if not project_id or not isinstance(project_id, str):
        raise ValueError("project_id must be a non-empty string")
    if not _PROJECT_ID_RE.match(project_id):
        raise ValueError(
            "project_id must be 1-64 chars of [A-Za-z0-9_-] only "
            f"(got {project_id!r})",
        )
    return project_id


def _meta_key(project_id: str) -> str:
    return f"{_META_PREFIX}{project_id}{_META_SUFFIX}"


def _summary_key(project_id: str) -> str:
    return f"{_META_PREFIX}{project_id}{_SUMMARY_SUFFIX}"


def _threads_key(project_id: str) -> str:
    return f"{_META_PREFIX}{project_id}{_THREADS_SUFFIX}"


def _coerce_meta(raw: Any, *, project_id: str) -> ProjectMeta:
    """Normalise a meta dict loaded from the vault into ProjectMeta shape."""
    if not isinstance(raw, dict):
        raise KeyError(f"project {project_id!r} has no usable meta")

    name = raw.get("name") if isinstance(raw.get("name"), str) else project_id
    description = raw.get("description") if isinstance(raw.get("description"), str) else ""

    default_model = raw.get("default_model")
    if not isinstance(default_model, str) or not default_model:
        default_model = None

    raw_allowed = raw.get("allowed_models")
    allowed_models: Optional[list[str]] = None
    if isinstance(raw_allowed, list):
        cleaned = [m for m in raw_allowed if isinstance(m, str) and m.strip()]
        allowed_models = cleaned or None

    raw_tags = raw.get("tags")
    tags: list[str] = []
    if isinstance(raw_tags, list):
        for t in raw_tags[:_MAX_TAGS]:
            if isinstance(t, str) and t.strip():
                tags.append(t.strip()[:_MAX_TAG_LEN])

    raw_summary = raw.get("summary")
    summary: Optional[str] = (
        raw_summary if isinstance(raw_summary, str) and raw_summary.strip()
        else None
    )
    raw_summary_ts = raw.get("summary_ts_ms")
    try:
        summary_ts_ms: Optional[int] = (
            int(raw_summary_ts) if raw_summary_ts is not None else None
        )
    except (TypeError, ValueError):
        summary_ts_ms = None

    out: ProjectMeta = {
        "project_id":     str(raw.get("project_id") or project_id),
        "name":           name[:_MAX_NAME_LEN],
        "description":    description[:_MAX_DESCRIPTION_LEN],
        "default_model":  default_model,
        "allowed_models": allowed_models,
        "tags":           tags,
        "created_at":     int(raw.get("created_at") or 0),
        "updated_at":     int(raw.get("updated_at") or 0),
        "summary":        summary,
        "summary_ts_ms":  summary_ts_ms,
        "thread_count":   int(raw.get("thread_count") or 0),
    }
    return out


def _list_meta_keys(user_id: str) -> list[str]:
    return [
        k for k in memory_vault.vault_keys_for_user(user_id)
        if k.startswith(_META_PREFIX) and k.endswith(_META_SUFFIX)
    ]


def _project_id_from_meta_key(key: str) -> str:
    # key shape: ``projects.{project_id}.meta``
    return key[len(_META_PREFIX):-len(_META_SUFFIX)]


def _load_threads_index(user_id: str, project_id: str) -> list[str]:
    raw = memory_vault.vault_get(user_id, _threads_key(project_id))
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for tid in raw:
        if isinstance(tid, str) and tid:
            out.append(tid)
    return out


def _save_threads_index(user_id: str, project_id: str, ids: list[str]) -> None:
    # Cap so the index doesn't grow unbounded if a caller forgets to prune.
    if len(ids) > _MAX_THREADS:
        ids = ids[-_MAX_THREADS:]
    memory_vault.vault_put(user_id, _threads_key(project_id), ids)


# ---------------------------------------------------------------------------
# Public — create / list / get / update
# ---------------------------------------------------------------------------
def create_project(user_id: str, project_meta: dict) -> ProjectMeta:
    """Create a new project for ``user_id``.

    ``project_meta`` is expected to carry at minimum ``project_id`` and
    ``name``. Optional fields: ``description``, ``default_model``,
    ``allowed_models`` (list of model_ids or aliases), ``tags`` (list).

    Raises :class:`ValueError` on bad shape or if the project already
    exists. Returns the freshly-created :class:`ProjectMeta`.
    """
    user_id = _validate_user(user_id)
    if not isinstance(project_meta, dict):
        raise ValueError("project_meta must be a dict")

    project_id = _validate_project_id(project_meta.get("project_id"))
    memory_vault.vault_init(user_id)

    # Reject duplicate.
    existing = memory_vault.vault_get(user_id, _meta_key(project_id))
    if existing is not None:
        raise ValueError(f"project {project_id!r} already exists")

    name = project_meta.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("project name must be a non-empty string")

    now = _now_ms()
    meta_input = {
        "project_id":     project_id,
        "name":           name.strip(),
        "description":    project_meta.get("description") or "",
        "default_model":  project_meta.get("default_model"),
        "allowed_models": project_meta.get("allowed_models"),
        "tags":           project_meta.get("tags") or [],
        "created_at":     now,
        "updated_at":     now,
        "summary":        None,
        "summary_ts_ms":  None,
        "thread_count":   0,
    }
    meta = _coerce_meta(meta_input, project_id=project_id)

    memory_vault.vault_put(user_id, _meta_key(project_id), meta)
    memory_vault.vault_put(
        user_id, _summary_key(project_id),
        {"summary": None, "ts_ms": None},
    )
    memory_vault.vault_put(user_id, _threads_key(project_id), [])
    return meta


def list_projects(user_id: str) -> list[ProjectMeta]:
    """Return every project for ``user_id``, newest-first by
    ``updated_at``."""
    user_id = _validate_user(user_id)
    memory_vault.vault_init(user_id)

    out: list[ProjectMeta] = []
    for key in _list_meta_keys(user_id):
        project_id = _project_id_from_meta_key(key)
        try:
            raw = memory_vault.vault_get(user_id, key)
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "projects_vault meta load failed key=%s err=%s", key, e,
            )
            continue
        if raw is None:
            continue
        try:
            out.append(_coerce_meta(raw, project_id=project_id))
        except KeyError:
            continue
    out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
    return out


def get_project(user_id: str, project_id: str) -> ProjectMeta:
    """Load a project's meta. Raises :class:`KeyError` when missing."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    raw = memory_vault.vault_get(user_id, _meta_key(project_id))
    if raw is None:
        raise KeyError(f"project {project_id!r} not found")
    return _coerce_meta(raw, project_id=project_id)


def update_project(
    user_id: str, project_id: str, patch: dict,
) -> ProjectMeta:
    """Merge ``patch`` into the project's meta. Only known fields are
    applied (name / description / default_model / allowed_models /
    tags). Raises :class:`KeyError` when the project doesn't exist."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    if not isinstance(patch, dict):
        raise ValueError("patch must be a dict")

    raw = memory_vault.vault_get(user_id, _meta_key(project_id))
    if raw is None:
        raise KeyError(f"project {project_id!r} not found")
    meta = _coerce_meta(raw, project_id=project_id)

    if "name" in patch and isinstance(patch["name"], str) and patch["name"].strip():
        meta["name"] = patch["name"].strip()[:_MAX_NAME_LEN]
    if "description" in patch and isinstance(patch["description"], str):
        meta["description"] = patch["description"][:_MAX_DESCRIPTION_LEN]
    if "default_model" in patch:
        dm = patch["default_model"]
        meta["default_model"] = dm if (isinstance(dm, str) and dm) else None
    if "allowed_models" in patch:
        am = patch["allowed_models"]
        if isinstance(am, list):
            cleaned = [m for m in am if isinstance(m, str) and m.strip()]
            meta["allowed_models"] = cleaned or None
        elif am is None:
            meta["allowed_models"] = None
    if "tags" in patch and isinstance(patch["tags"], list):
        cleaned_tags = []
        for t in patch["tags"][:_MAX_TAGS]:
            if isinstance(t, str) and t.strip():
                cleaned_tags.append(t.strip()[:_MAX_TAG_LEN])
        meta["tags"] = cleaned_tags

    meta["updated_at"] = _now_ms()
    memory_vault.vault_put(user_id, _meta_key(project_id), meta)
    return meta


def update_project_summary(
    user_id: str,
    project_id: str,
    summary: Optional[str],
    ts_ms: Optional[int] = None,
) -> ProjectMeta:
    """Persist (or clear, by passing None / whitespace) a summary onto
    the project. Updates both the dedicated summary doc and the meta
    fields so callers don't have to read both."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)

    try:
        ts_ms_int = int(ts_ms) if ts_ms is not None else _now_ms()
    except (TypeError, ValueError):
        ts_ms_int = _now_ms()

    raw = memory_vault.vault_get(user_id, _meta_key(project_id))
    if raw is None:
        raise KeyError(f"project {project_id!r} not found")
    meta = _coerce_meta(raw, project_id=project_id)

    if isinstance(summary, str) and summary.strip():
        meta["summary"] = summary.strip()
        meta["summary_ts_ms"] = ts_ms_int
    else:
        meta["summary"] = None
        meta["summary_ts_ms"] = None

    meta["updated_at"] = _now_ms()
    memory_vault.vault_put(user_id, _meta_key(project_id), meta)
    memory_vault.vault_put(
        user_id, _summary_key(project_id),
        {"summary": meta["summary"], "ts_ms": meta["summary_ts_ms"]},
    )
    return meta


# ---------------------------------------------------------------------------
# Public — thread index
# ---------------------------------------------------------------------------
def add_thread_to_project(
    user_id: str, project_id: str, thread_id: str,
) -> list[str]:
    """Append ``thread_id`` to the project's threads index. Idempotent —
    a second call with the same thread_id is a no-op. Updates the
    meta's ``thread_count``. Raises :class:`KeyError` when the project
    doesn't exist."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("thread_id must be a non-empty string")

    raw = memory_vault.vault_get(user_id, _meta_key(project_id))
    if raw is None:
        raise KeyError(f"project {project_id!r} not found")
    meta = _coerce_meta(raw, project_id=project_id)

    ids = _load_threads_index(user_id, project_id)
    if thread_id not in ids:
        ids.append(thread_id)
        _save_threads_index(user_id, project_id, ids)
    meta["thread_count"] = len(ids)
    meta["updated_at"] = _now_ms()
    memory_vault.vault_put(user_id, _meta_key(project_id), meta)
    return ids


def remove_thread_from_project(
    user_id: str, project_id: str, thread_id: str,
) -> list[str]:
    """Drop ``thread_id`` from the index. Idempotent. Raises
    :class:`KeyError` when the project doesn't exist."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("thread_id must be a non-empty string")

    raw = memory_vault.vault_get(user_id, _meta_key(project_id))
    if raw is None:
        raise KeyError(f"project {project_id!r} not found")
    meta = _coerce_meta(raw, project_id=project_id)

    ids = [t for t in _load_threads_index(user_id, project_id) if t != thread_id]
    _save_threads_index(user_id, project_id, ids)
    meta["thread_count"] = len(ids)
    meta["updated_at"] = _now_ms()
    memory_vault.vault_put(user_id, _meta_key(project_id), meta)
    return ids


def list_project_threads(user_id: str, project_id: str) -> list[str]:
    """Return the project's thread_ids in insertion order. Raises
    :class:`KeyError` when the project doesn't exist."""
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    if memory_vault.vault_get(user_id, _meta_key(project_id)) is None:
        raise KeyError(f"project {project_id!r} not found")
    return _load_threads_index(user_id, project_id)


def is_thread_in_project(
    user_id: str, project_id: str, thread_id: str,
) -> bool:
    """Cheap check used by the message-post endpoint to validate the
    ``project_id`` payload field. Returns False (rather than raising)
    when the project doesn't exist."""
    try:
        return thread_id in list_project_threads(user_id, project_id)
    except (KeyError, ValueError):
        return False


def delete_project(user_id: str, project_id: str) -> None:
    """Drop the project's meta + summary + threads index. Idempotent.

    Does NOT delete the threads themselves — those keep their
    project_id field but become orphans (the UI will hide them when
    filtering by this project_id, but they're still readable by id).
    """
    user_id = _validate_user(user_id)
    project_id = _validate_project_id(project_id)
    memory_vault.vault_delete(user_id, _meta_key(project_id))
    memory_vault.vault_delete(user_id, _summary_key(project_id))
    memory_vault.vault_delete(user_id, _threads_key(project_id))
