"""
v47 — Threads vault: persistent threaded conversations on top of
:mod:`memory_vault`.

Each user owns a set of threads stored entirely inside the vault. The
module never bypasses the vault API; it is a thin layer that builds
the namespaced keys, manages the per-thread sequence counter, and
keeps the per-thread meta in sync with appended messages.

Vault layout
------------

* ``threads.meta.{thread_id}`` — :class:`ThreadMeta`
* ``threads.messages.{thread_id}.{ts_ms}_{seq}`` — :class:`Message`
* ``threads.embeddings.{thread_id}.…`` — *reserved* for v47+, no logic yet

``thread_id`` is a random ``uuid4()`` string. ``ts_ms`` is the integer
millisecond timestamp at the moment of append; ``seq`` is a per-thread
monotonic counter starting at 0. Sorting message keys lexically keeps
them in chronological order (the seq suffix breaks ties when several
messages land in the same millisecond).

Public API
----------

    create_thread(user_id, title)                      -> ThreadMeta
    list_threads(user_id)                              -> list[ThreadMeta]
    get_thread(user_id, thread_id)                     -> (meta, [Message])
    append_message(user_id, thread_id, message)        -> (meta, message)
    rename_thread(user_id, thread_id, title)           -> ThreadMeta
    delete_thread(user_id, thread_id)                  -> None

    THREADS_VAULT_VERSION                              # version string

Errors are raised as :class:`KeyError` for ``thread not found`` so the
app layer can map cleanly to HTTP 404. Argument-shape failures use
:class:`ValueError` (mirrors ``memory_vault``).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional, TypedDict

import memory_vault

logger = logging.getLogger("clarityos.threads_vault")

THREADS_VAULT_VERSION: str = "threads_vault.v51.1"

# Vault key prefixes. Anything before the first '.' is the namespace
# (``threads`` — added in memory_vault v47); the rest is structured
# under these helper prefixes.
_META_PREFIX:    str = "threads.meta."
_MESSAGES_PREFIX: str = "threads.messages."
_EMBEDDINGS_PREFIX: str = "threads.embeddings."

VALID_ROLES: tuple = ("user", "assistant", "system")


# ---------------------------------------------------------------------------
# TypedDicts (documentation aid; the wire schema is enforced by Pydantic
# in app.py).
# ---------------------------------------------------------------------------
class ThreadMeta(TypedDict):
    thread_id: str
    title: Optional[str]
    created_at: int
    updated_at: int
    message_count: int
    archived: bool
    # v50 — per-thread summary. Kernel-generated; metadata-only,
    # never carries raw message text. ``summary_ts_ms`` is the
    # timestamp at which the summary was last computed.
    summary: Optional[str]
    summary_ts_ms: Optional[int]
    # v51 — project membership. None for threads that aren't part of
    # any project (existing v47-v50 threads stay valid). When set,
    # ``GET /me/threads?project_id=X`` filters on this field.
    project_id: Optional[str]


class Message(TypedDict, total=False):
    role: str
    content: str
    ts_ms: int
    model: Optional[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


def _validate_user(user_id: Any) -> str:
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    return user_id


def _validate_thread_id(thread_id: Any) -> str:
    """Thread ids are urlsafe so the app layer can put them in URL paths
    without escaping. We accept any non-empty string but reject ``.``
    so the message-key parsing isn't ambiguous."""
    if not thread_id or not isinstance(thread_id, str):
        raise ValueError("thread_id must be a non-empty string")
    if "." in thread_id or "/" in thread_id or "\\" in thread_id:
        raise ValueError("thread_id may not contain '.', '/' or '\\\\'")
    return thread_id


def _meta_key(thread_id: str) -> str:
    return f"{_META_PREFIX}{thread_id}"


def _message_key(thread_id: str, ts_ms: int, seq: int) -> str:
    # Zero-pad the seq so lex-sort matches numeric order. 6 digits gives
    # us a million messages per thread before the suffix wraps (we cap
    # threads long before that).
    return f"{_MESSAGES_PREFIX}{thread_id}.{int(ts_ms)}_{int(seq):06d}"


def _coerce_meta(raw: Any, *, thread_id: str) -> ThreadMeta:
    """Normalise a meta dict loaded from the vault into ThreadMeta shape.
    v50: also surfaces ``summary`` + ``summary_ts_ms``. Anything legacy
    that doesn't carry those fields gets ``None`` (i.e., reads as
    "no summary yet")."""
    if not isinstance(raw, dict):
        raise KeyError(f"thread {thread_id!r} has no usable meta")
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
    raw_project_id = raw.get("project_id")
    project_id_val: Optional[str] = (
        raw_project_id if isinstance(raw_project_id, str) and raw_project_id.strip()
        else None
    )

    out: ThreadMeta = {
        "thread_id":     str(raw.get("thread_id") or thread_id),
        "title":         raw.get("title") if isinstance(raw.get("title"), str) else None,
        "created_at":    int(raw.get("created_at") or 0),
        "updated_at":    int(raw.get("updated_at") or 0),
        "message_count": int(raw.get("message_count") or 0),
        "archived":      bool(raw.get("archived")),
        "summary":       summary,
        "summary_ts_ms": summary_ts_ms,
        "project_id":    project_id_val,
    }
    return out


def _coerce_message(raw: Any) -> Message:
    if not isinstance(raw, dict):
        return {"role": "system", "content": "", "ts_ms": 0, "model": None}
    role = str(raw.get("role") or "system")
    if role not in VALID_ROLES:
        role = "system"
    return {
        "role":    role,
        "content": str(raw.get("content") or ""),
        "ts_ms":   int(raw.get("ts_ms") or 0),
        "model":   raw.get("model") if isinstance(raw.get("model"), str) else None,
    }


def _list_message_keys(user_id: str, thread_id: str) -> list[str]:
    """All ``threads.messages.{thread_id}.*`` keys, sorted lexically."""
    prefix = f"{_MESSAGES_PREFIX}{thread_id}."
    keys = [
        k for k in memory_vault.vault_keys_for_user(user_id)
        if k.startswith(prefix)
    ]
    return sorted(keys)


def _list_meta_keys(user_id: str) -> list[str]:
    return [
        k for k in memory_vault.vault_keys_for_user(user_id)
        if k.startswith(_META_PREFIX)
    ]


# ---------------------------------------------------------------------------
# Public — create / list / get / append / rename / delete
# ---------------------------------------------------------------------------
def create_thread(
    user_id: str,
    title: Optional[str],
    *,
    project_id: Optional[str] = None,
) -> ThreadMeta:
    """Create a new thread for ``user_id``. ``title`` is optional and
    can be edited later via :func:`rename_thread`. ``project_id`` is
    optional (v51); when omitted the thread isn't tied to any project
    and the v47/v50 endpoints behave as before.

    Returns the freshly-created :class:`ThreadMeta`."""
    user_id = _validate_user(user_id)
    if title is not None and not isinstance(title, str):
        raise ValueError("title must be a string or None")
    if project_id is not None:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("project_id must be a non-empty string or None")
        project_id = project_id.strip()
    memory_vault.vault_init(user_id)

    thread_id = uuid.uuid4().hex
    now = _now_ms()
    meta: ThreadMeta = {
        "thread_id":     thread_id,
        "title":         title.strip() if isinstance(title, str) else None,
        "created_at":    now,
        "updated_at":    now,
        "message_count": 0,
        "archived":      False,
        "summary":       None,
        "summary_ts_ms": None,
        "project_id":    project_id,
    }
    memory_vault.vault_put(user_id, _meta_key(thread_id), meta)
    return meta


def list_threads(user_id: str) -> list[ThreadMeta]:
    """Return every thread for ``user_id``, newest-first by
    ``updated_at``. Threads with corrupted meta are skipped (logged)."""
    user_id = _validate_user(user_id)
    memory_vault.vault_init(user_id)

    out: list[ThreadMeta] = []
    for key in _list_meta_keys(user_id):
        thread_id = key[len(_META_PREFIX):]
        try:
            raw = memory_vault.vault_get(user_id, key)
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning("threads_vault meta load failed key=%s err=%s", key, e)
            continue
        if raw is None:
            continue
        try:
            out.append(_coerce_meta(raw, thread_id=thread_id))
        except KeyError:
            continue
    out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
    return out


def get_thread(
    user_id: str, thread_id: str,
) -> tuple[ThreadMeta, list[Message]]:
    """Return ``(meta, messages)`` for ``thread_id``.

    Raises :class:`KeyError` when the thread doesn't exist."""
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)

    raw = memory_vault.vault_get(user_id, _meta_key(thread_id))
    if raw is None:
        raise KeyError(f"thread {thread_id!r} not found")
    meta = _coerce_meta(raw, thread_id=thread_id)

    msgs: list[Message] = []
    for key in _list_message_keys(user_id, thread_id):
        try:
            raw_msg = memory_vault.vault_get(user_id, key)
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning("threads_vault message load failed key=%s err=%s", key, e)
            continue
        if raw_msg is None:
            continue
        msgs.append(_coerce_message(raw_msg))
    return meta, msgs


def append_message(
    user_id: str, thread_id: str, message: Message,
) -> tuple[ThreadMeta, Message]:
    """Append ``message`` to ``thread_id``. Returns the updated
    ``(meta, message)`` pair (the message is normalised + the
    ``ts_ms`` field is filled in if absent).

    Raises :class:`KeyError` when the thread doesn't exist.
    """
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)
    if not isinstance(message, dict):
        raise ValueError("message must be a dict")

    raw_meta = memory_vault.vault_get(user_id, _meta_key(thread_id))
    if raw_meta is None:
        raise KeyError(f"thread {thread_id!r} not found")
    meta = _coerce_meta(raw_meta, thread_id=thread_id)

    role = str(message.get("role") or "user")
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES!r}")

    ts_ms = message.get("ts_ms")
    try:
        ts_ms = int(ts_ms) if ts_ms is not None else _now_ms()
    except (TypeError, ValueError):
        ts_ms = _now_ms()

    # Per-thread seq is the existing message count. With the message
    # key embedding both ts_ms + seq, two writes in the same ms still
    # produce distinct vault keys.
    seq = int(meta.get("message_count") or 0)

    saved: Message = {
        "role":    role,
        "content": str(message.get("content") or ""),
        "ts_ms":   ts_ms,
        "model":   message["model"] if isinstance(message.get("model"), str) else None,
    }
    memory_vault.vault_put(
        user_id, _message_key(thread_id, ts_ms, seq), saved,
    )

    meta["updated_at"]    = ts_ms
    meta["message_count"] = seq + 1
    memory_vault.vault_put(user_id, _meta_key(thread_id), meta)
    return meta, saved


def rename_thread(
    user_id: str, thread_id: str, title: str,
) -> ThreadMeta:
    """Update ``title`` on ``thread_id``. Raises :class:`KeyError` when
    the thread doesn't exist; :class:`ValueError` on bad title shape."""
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)
    if not isinstance(title, str):
        raise ValueError("title must be a string")

    raw = memory_vault.vault_get(user_id, _meta_key(thread_id))
    if raw is None:
        raise KeyError(f"thread {thread_id!r} not found")
    meta = _coerce_meta(raw, thread_id=thread_id)
    meta["title"] = title.strip() or None
    meta["updated_at"] = _now_ms()
    memory_vault.vault_put(user_id, _meta_key(thread_id), meta)
    return meta


def delete_thread(user_id: str, thread_id: str) -> None:
    """Drop ``thread_id`` and every message + reserved-embedding key
    that belongs to it. Idempotent: deleting a missing thread is a
    no-op (mirrors ``vault_delete`` semantics)."""
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)

    # Meta first, then messages, then reserved embeddings — order
    # doesn't matter functionally; meta-first means a concurrent
    # ``list_threads`` won't return the now-emptying thread.
    memory_vault.vault_delete(user_id, _meta_key(thread_id))

    for key in _list_message_keys(user_id, thread_id):
        memory_vault.vault_delete(user_id, key)

    embedding_prefix = f"{_EMBEDDINGS_PREFIX}{thread_id}."
    for key in memory_vault.vault_keys_for_user(user_id):
        if key.startswith(embedding_prefix):
            memory_vault.vault_delete(user_id, key)


# ---------------------------------------------------------------------------
# v50 — summary helpers
# ---------------------------------------------------------------------------
def get_thread_meta(user_id: str, thread_id: str) -> ThreadMeta:
    """Load just the meta document for a thread. Cheaper than
    ``get_thread`` when the caller doesn't need the message list.

    Raises :class:`KeyError` when the thread doesn't exist."""
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)
    raw = memory_vault.vault_get(user_id, _meta_key(thread_id))
    if raw is None:
        raise KeyError(f"thread {thread_id!r} not found")
    return _coerce_meta(raw, thread_id=thread_id)


def update_thread_summary(
    user_id: str,
    thread_id: str,
    summary: Optional[str],
    ts_ms: int,
) -> ThreadMeta:
    """Persist a freshly-computed summary onto the thread's meta.

    Passing ``summary=None`` (or an empty string) clears the summary —
    used by :func:`intelligence_kernel.summarize_thread` when the
    thread has no messages so the UI can show "no summary yet".

    Raises :class:`KeyError` when the thread doesn't exist."""
    user_id = _validate_user(user_id)
    thread_id = _validate_thread_id(thread_id)
    try:
        ts_ms_int = int(ts_ms) if ts_ms is not None else _now_ms()
    except (TypeError, ValueError):
        ts_ms_int = _now_ms()

    raw = memory_vault.vault_get(user_id, _meta_key(thread_id))
    if raw is None:
        raise KeyError(f"thread {thread_id!r} not found")
    meta = _coerce_meta(raw, thread_id=thread_id)

    if isinstance(summary, str) and summary.strip():
        meta["summary"] = summary.strip()
        meta["summary_ts_ms"] = ts_ms_int
    else:
        meta["summary"] = None
        meta["summary_ts_ms"] = None

    memory_vault.vault_put(user_id, _meta_key(thread_id), meta)
    return meta
