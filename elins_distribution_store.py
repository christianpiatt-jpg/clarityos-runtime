"""
ELINS distribution store — queued + delivered daily reports.

Per-user state:
  {
    "queued":    list[ {report_id, scenario_text, scheduled_for_ts,
                         deliver_email, deliver_feed, queued_at} ],
    "delivered": list[ {report_id, delivered_at, scenario_id, analysis} ],
  }

Notes
-----
- Scenario text is held only inside `queued` until delivery; on delivery the
  scenario is hashed to a `scenario_id` and the text is dropped from persisted
  state. The `analysis` block contains DEWEY-shaped metadata only.
- Caps prevent unbounded growth: at most 500 queued, 500 delivered per user.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.elins_distribution_store")

_COLL = "elins_distribution"
_MAX_QUEUED = 500
_MAX_DELIVERED = 500


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
    logger.info("elins_distribution_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def _empty_blob() -> dict:
    return {"queued": [], "delivered": []}


def _load(user: str) -> dict:
    if _backend() == "firestore":
        doc = _coll().document(user).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return {
                "queued": list(data.get("queued") or []),
                "delivered": list(data.get("delivered") or []),
            }
        return _empty_blob()
    return dict(_MEMORY.get(user) or _empty_blob())


def _save(user: str, blob: dict) -> None:
    if _backend() == "firestore":
        _coll().document(user).set(blob)
    else:
        _MEMORY[user] = dict(blob)


def new_report_id() -> str:
    return "elinsd_" + secrets.token_urlsafe(12)


def scenario_id_for(text: str) -> str:
    """Stable, content-derived id used in delivered records (hash, not text).
    Allows downstream consumers to deduplicate identical scenarios without
    persisting the text itself."""
    h = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    return f"sc_{h[:16]}"


def queue(
    user: str,
    scenario_text: str,
    scheduled_for_ts: float,
    deliver_email: bool = False,
    deliver_feed: bool = True,
) -> dict:
    blob = _load(user)
    report = {
        "report_id": new_report_id(),
        "scenario_text": scenario_text,             # held only until delivery
        "scheduled_for_ts": float(scheduled_for_ts),
        "deliver_email": bool(deliver_email),
        "deliver_feed": bool(deliver_feed),
        "queued_at": float(scheduled_for_ts),       # caller may override later
    }
    blob["queued"].append(report)
    # Soft cap — drop oldest queued past the limit.
    if len(blob["queued"]) > _MAX_QUEUED:
        blob["queued"] = blob["queued"][-_MAX_QUEUED:]
    _save(user, blob)
    return report


def list_queued(user: str) -> list:
    return list(_load(user)["queued"])


def list_delivered(user: str, limit: int = 50) -> list:
    delivered = list(_load(user)["delivered"])
    delivered.sort(key=lambda r: float(r.get("delivered_at", 0.0)), reverse=True)
    return delivered[: max(1, int(limit))]


def deliver(user: str, report_id: str, delivered_at: float, analysis: dict) -> Optional[dict]:
    """Move a queued report to the delivered list. Returns the delivered
    record, or None if the report_id wasn't queued (caller error)."""
    blob = _load(user)
    queued = blob["queued"]
    idx = next((i for i, r in enumerate(queued) if r.get("report_id") == report_id), -1)
    if idx == -1:
        return None
    report = queued.pop(idx)
    delivered_record = {
        "report_id": report_id,
        "delivered_at": float(delivered_at),
        "scenario_id": scenario_id_for(report.get("scenario_text", "")),  # hashed
        "deliver_email": report.get("deliver_email", False),
        "deliver_feed": report.get("deliver_feed", True),
        "analysis": analysis,
    }
    blob["delivered"].append(delivered_record)
    if len(blob["delivered"]) > _MAX_DELIVERED:
        blob["delivered"] = blob["delivered"][-_MAX_DELIVERED:]
    _save(user, blob)
    return delivered_record


def all_users_with_due_reports(now: float) -> list[str]:
    """Scan store for users with at least one queued report whose
    scheduled_for_ts <= now. Returns the list of usernames; the scheduler
    then iterates them. Memory-backend O(N users); firestore version uses a
    full-collection scan (acceptable for v1; add an index when load grows)."""
    out: list = []
    if _backend() == "firestore":
        for doc in _coll().stream():
            data = doc.to_dict() or {}
            queued = data.get("queued") or []
            if any(float(r.get("scheduled_for_ts", float("inf"))) <= now for r in queued):
                out.append(doc.id)
        return out
    for u, blob in _MEMORY.items():
        queued = blob.get("queued") or []
        if any(float(r.get("scheduled_for_ts", float("inf"))) <= now for r in queued):
            out.append(u)
    return out


def due_reports_for(user: str, now: float) -> list:
    """Subset of queued reports that are due for delivery."""
    return [r for r in _load(user)["queued"] if float(r.get("scheduled_for_ts", float("inf"))) <= now]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
