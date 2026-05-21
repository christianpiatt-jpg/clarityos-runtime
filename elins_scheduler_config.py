"""
v36 — Macro-ELINS scheduler config store.

Tiny key/value store for the macro-ELINS scheduler. One row per
process; founder-toggleable via /founder/elins/scheduler/config.

Defaults:
    enabled                 False
    cadence                 "3x_week"   (Mon/Wed/Fri pattern via interval)
    external_signal_mode    "cloud_only"
    system_user             "scheduler"
    last_run_ts             0.0

Backends mirror the rest of the project (memory + Firestore).
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("clarityos.elins_scheduler_config")

VALID_CADENCES: tuple = ("off", "daily", "3x_week", "weekly")
VALID_SIGNAL_MODES: tuple = ("cloud_only", "cloud_perplexity")

_DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "cadence": "3x_week",
    "external_signal_mode": "cloud_only",
    "system_user": "scheduler",
    "last_run_ts": 0.0,
}

_CONFIG_DOC_ID = "macro_scheduler"
_CONFIG_COLL = "elins_scheduler_config"

# In-memory state. Tests reset via ``_reset_memory_for_tests``.
_MEM_CONFIG: dict[str, Any] = dict(_DEFAULT_CONFIG)


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


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
    return _firestore_client


def _coerce_cfg(cfg: dict) -> dict:
    """Clamp + type-coerce arbitrary input into the canonical shape."""
    out = dict(_DEFAULT_CONFIG)
    out.update({k: v for k, v in (cfg or {}).items() if k in _DEFAULT_CONFIG})
    out["enabled"] = bool(out.get("enabled"))
    cad = out.get("cadence") or "3x_week"
    if cad not in VALID_CADENCES:
        cad = "3x_week"
    out["cadence"] = cad
    mode = out.get("external_signal_mode") or "cloud_only"
    if mode not in VALID_SIGNAL_MODES:
        mode = "cloud_only"
    out["external_signal_mode"] = mode
    out["system_user"] = str(out.get("system_user") or "scheduler")
    try:
        out["last_run_ts"] = float(out.get("last_run_ts") or 0.0)
    except (TypeError, ValueError):
        out["last_run_ts"] = 0.0
    return out


def get_config() -> dict:
    if _backend() == "firestore":
        doc = _get_firestore().collection(_CONFIG_COLL).document(_CONFIG_DOC_ID).get()
        if not doc.exists:
            return dict(_DEFAULT_CONFIG)
        return _coerce_cfg(doc.to_dict() or {})
    return dict(_MEM_CONFIG)


def set_config(updates: dict) -> dict:
    """Merge ``updates`` into the stored config. Returns the new full
    config dict. Unknown keys are silently dropped; invalid enum values
    fall back to defaults."""
    cur = get_config()
    cur.update({k: v for k, v in (updates or {}).items() if k in _DEFAULT_CONFIG})
    coerced = _coerce_cfg(cur)
    if _backend() == "firestore":
        _get_firestore().collection(_CONFIG_COLL).document(_CONFIG_DOC_ID).set(coerced)
    else:
        _MEM_CONFIG.clear()
        _MEM_CONFIG.update(coerced)
    return dict(coerced)


def reset_to_defaults() -> dict:
    return set_config(dict(_DEFAULT_CONFIG))


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    _MEM_CONFIG.clear()
    _MEM_CONFIG.update(_DEFAULT_CONFIG)
