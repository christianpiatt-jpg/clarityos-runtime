"""
Markov v2 — per-user, per-session state history.

Document shape (collection: `markov_states`, keyed by random id `ms_<token>`):
    {
        "id":           str,
        "user":         str,
        "session_id":   str,
        "state_index":  int,           # 0-based, monotonically increasing per (user, session)
        "state_vector": list[float],   # 768-dim, L2-normalized (validated at the route layer)
        "qc_envelope":  dict,          # { qc_stability, qc_drift, qc_predictive, qc_pressure }
        "timestamp":    float,         # POSIX seconds
    }

`latest_for(user, session_id)` and `next_index_for(user, session_id)` both
require a composite Firestore index on (user ASC, session_id ASC,
state_index DESC). Created via gcloud at deploy time.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.markov_states_store")

_COLL = "markov_states"


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
    logger.info("markov_states_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def new_id() -> str:
    return "ms_" + secrets.token_urlsafe(12)


def create(state_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(state_id).set(payload)
    else:
        _MEMORY[state_id] = dict(payload)


def latest_for(user: str, session_id: str) -> Optional[dict]:
    """Return the highest-state_index doc for (user, session_id), or None."""
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .where(filter=FieldFilter("session_id", "==", session_id))
            .order_by("state_index", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(q.stream())
        return docs[0].to_dict() if docs else None
    candidates = [
        d for d in _MEMORY.values()
        if d.get("user") == user and d.get("session_id") == session_id
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.get("state_index", -1))


def next_index_for(user: str, session_id: str) -> int:
    """Returns the next available state_index for (user, session_id).
    0 if no states exist yet, else `latest.state_index + 1`."""
    latest = latest_for(user, session_id)
    if latest is None:
        return 0
    return int(latest.get("state_index", -1)) + 1


def recent_for(user: str, session_id: str, limit: int = 3) -> list[dict]:
    """Last `limit` states for (user, session_id), newest first. Same
    composite index as `latest_for`."""
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .where(filter=FieldFilter("session_id", "==", session_id))
            .order_by("state_index", direction=firestore.Query.DESCENDING)
            .limit(max(1, int(limit)))
        )
        return [doc.to_dict() for doc in q.stream()]
    candidates = [
        d for d in _MEMORY.values()
        if d.get("user") == user and d.get("session_id") == session_id
    ]
    candidates.sort(key=lambda d: d.get("state_index", -1), reverse=True)
    return candidates[: max(1, int(limit))]


def list_sessions_for_user(user: str, limit: int = 50) -> list[dict]:
    """v28 — return summary metadata for all sessions a user has touched.
    For each `session_id`, returns `{session_id, state_count, latest_state_index,
    latest_ts}`. Newest-first by `latest_ts`. No state vectors are returned —
    metadata only, suitable for the cockpit Session List panel."""
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        # Group by session_id in Python; firestore doesn't have GROUP BY.
        # Caps the scan via `limit*20` to avoid pulling unbounded docs.
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .limit(int(limit) * 20)
        )
        docs = [doc.to_dict() for doc in q.stream()]
    else:
        docs = [d for d in _MEMORY.values() if d.get("user") == user]

    by_session: dict[str, dict] = {}
    for d in docs:
        sid = d.get("session_id")
        if not sid:
            continue
        try:
            idx = int(d.get("state_index", -1))
            ts = float(d.get("timestamp", 0.0))
        except (TypeError, ValueError):
            continue
        cur = by_session.get(sid)
        if cur is None:
            by_session[sid] = {
                "session_id": sid,
                "state_count": 1,
                "latest_state_index": idx,
                "latest_ts": ts,
            }
        else:
            cur["state_count"] += 1
            if idx > cur["latest_state_index"]:
                cur["latest_state_index"] = idx
                cur["latest_ts"] = ts
    out = list(by_session.values())
    out.sort(key=lambda r: r["latest_ts"], reverse=True)
    return out[: max(1, int(limit))]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
