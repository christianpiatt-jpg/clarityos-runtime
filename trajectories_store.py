"""
DEWEY v5 trajectory storage.

Document shape (collection: `trajectories`, keyed by random id `traj_<token>`):
    {
        "id":                       str,    # same as trajectory_id
        "user":                     str,
        "session_id":               str,
        "trajectory_id":            str,
        "created_at":               float,
        "horizon_steps":            int,
        "start_state_vector":       list[float],
        "start_predictive_vector":  list[float],
        "steps":                    list[dict],   # each: step_index, state_vector,
                                                  # qc_envelope, dominant_neighborhoods, branch_label
        "summary":                  dict,         # stability/drift/pressure/branching/anchored_elins_brief_id
    }

`list_for_user(user)` queries by `user` ordered by `created_at` DESC and
requires a composite index on (user ASC, created_at DESC).
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.trajectories_store")

_COLL = "trajectories"


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
    try:
        _firestore_client = firestore.Client()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Could not initialise Firestore client: {e}") from e
    logger.info("trajectories_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def new_id() -> str:
    return "traj_" + secrets.token_urlsafe(12)


def create(traj_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(traj_id).set(payload)
    else:
        _MEMORY[traj_id] = dict(payload)


def get(traj_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(traj_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(traj_id)


def list_for_user(user: str, limit: int = 20) -> list[dict]:
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(max(1, int(limit)))
        )
        return [doc.to_dict() for doc in q.stream()]
    candidates = [d for d in _MEMORY.values() if d.get("user") == user]
    candidates.sort(key=lambda d: d.get("created_at", 0), reverse=True)
    return candidates[: max(1, int(limit))]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
