"""
Mesh metadata store — Dewey-only metadata sync across the user's devices.

Per-user state:
  {
    "devices": {
      <device_id>: {
        "metadata": dict,           # caller-provided; counts + last_updated_ts only
        "last_seen_ts": float,
      },
      ...
    }
  }

Caps: at most 8 devices per user (LRU eviction by last_seen_ts), at most 16 KB
per device metadata blob (excess is dropped, not stored).

NEVER stored: text, vectors, event content, scenario text. Caller is responsible
for sanitizing the payload before pushing; the store enforces a serialized-byte
ceiling but does not deeply inspect the structure.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.mesh_metadata_store")

_COLL = "mesh_metadata"
_MAX_DEVICES = 8
_MAX_DEVICE_BLOB_BYTES = 16 * 1024  # 16 KB


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


_MEMORY: dict[str, dict] = {}
_firestore_client = None


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "CLARITYOS_BACKEND=firestore but google-cloud-firestore is not installed."
        ) from e
    _firestore_client = firestore.Client()
    logger.info("mesh_metadata_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def _empty_blob() -> dict:
    return {"devices": {}}


def _load(user: str) -> dict:
    if _backend() == "firestore":
        doc = _coll().document(user).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return {"devices": dict(data.get("devices") or {})}
        return _empty_blob()
    return dict(_MEMORY.get(user) or _empty_blob())


def _save(user: str, blob: dict) -> None:
    if _backend() == "firestore":
        _coll().document(user).set(blob)
    else:
        _MEMORY[user] = dict(blob)


def upsert_device(user: str, device_id: str, metadata: dict, now_ts: float) -> dict:
    """Push a metadata blob for one device. Enforces 16 KB ceiling and
    8-device LRU cap. Returns the resulting device entry."""
    if not device_id:
        raise ValueError("device_id is required")
    # Reject oversize payloads (don't truncate — let the caller know).
    serialized = json.dumps(metadata or {}, separators=(",", ":"), default=str)
    if len(serialized.encode("utf-8")) > _MAX_DEVICE_BLOB_BYTES:
        raise ValueError(f"metadata exceeds {_MAX_DEVICE_BLOB_BYTES}-byte cap")

    blob = _load(user)
    devices = blob["devices"]
    devices[device_id] = {
        "metadata": dict(metadata or {}),
        "last_seen_ts": float(now_ts),
    }

    # LRU eviction past _MAX_DEVICES.
    if len(devices) > _MAX_DEVICES:
        ranked = sorted(
            devices.items(),
            key=lambda kv: float((kv[1] or {}).get("last_seen_ts", 0.0)),
            reverse=True,
        )
        devices = dict(ranked[:_MAX_DEVICES])
        blob["devices"] = devices

    _save(user, blob)
    return devices[device_id]


def state_for(user: str) -> dict:
    """Return the full mesh state for a user (devices map only — no
    aggregation done server-side; clients render as they wish)."""
    return _load(user)


def remove_device(user: str, device_id: str) -> bool:
    blob = _load(user)
    if device_id in blob["devices"]:
        del blob["devices"][device_id]
        _save(user, blob)
        return True
    return False


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
