"""
incident_store.py — P0/P1 incident store for the acceptance harness.

Located at repo root alongside users_store.py and memory_vault.py
(matching the existing flat-backend layout; the user instruction said
backend/incident_store.py but the repo's actual layout has FastAPI
modules at the repo root, so this lives there).

Persistence: append-only JSONL file, configurable via
CLARITYOS_INCIDENT_STORE env var. Default path: data/incidents.jsonl.
No third-party telemetry SDK per polish-plan §8 non-negotiable.

# SPEC AMBIGUITY D3 — accepted default:
#   P0 = data loss / vault corruption / security boundary failure /
#        total surface outage.
#   P1 = visible write-path quota or auth error / artifact-presence
#        failure on at least one surface for any operator / onboarding
#        completion failure on a previously-passing surface.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

Severity = Literal["P0", "P1", "P2", "P3"]
Surface = Literal["web", "phone", "desktop", "backend"]


class Incident(BaseModel):
    id: str
    severity: Severity
    surface: Surface
    os: Optional[str] = None
    title: str
    detail: Optional[str] = None
    operator_id: Optional[str] = None
    created_at: int          # epoch ms
    resolved_at: Optional[int] = None


# ---------------------------------------------------------------------------
# Storage path resolution
# ---------------------------------------------------------------------------
_DEFAULT_PATH = "data/incidents.jsonl"


def _store_path() -> Path:
    return Path(os.environ.get("CLARITYOS_INCIDENT_STORE", _DEFAULT_PATH))


def _ensure_dir() -> None:
    _store_path().parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_incident(
    severity: Severity,
    surface: Surface,
    title: str,
    *,
    os_name: Optional[str] = None,
    detail: Optional[str] = None,
    operator_id: Optional[str] = None,
) -> Incident:
    """Create a new incident record. severity must be P0/P1/P2/P3."""
    inc = Incident(
        id=f"inc-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}",
        severity=severity,
        surface=surface,
        os=os_name,
        title=title,
        detail=detail,
        operator_id=operator_id,
        created_at=int(time.time() * 1000),
        resolved_at=None,
    )
    _ensure_dir()
    with _store_path().open("a", encoding="utf-8") as f:
        f.write(inc.model_dump_json() + "\n")
    return inc


def list_incidents(*, open_only: bool = False) -> list[Incident]:
    path = _store_path()
    if not path.exists():
        return []
    out: list[Incident] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                inc = Incident(**json.loads(line))
            except Exception:
                continue
            if open_only and inc.resolved_at is not None:
                continue
            out.append(inc)
    return out


def resolve_incident(incident_id: str) -> bool:
    """Mark an incident resolved. Rewrites the JSONL file in place.
    Returns True if the incident was found and resolved, False otherwise."""
    path = _store_path()
    if not path.exists():
        return False
    rows: list[Incident] = []
    found = False
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                inc = Incident(**json.loads(line))
            except Exception:
                continue
            if inc.id == incident_id and inc.resolved_at is None:
                inc.resolved_at = int(time.time() * 1000)
                found = True
            rows.append(inc)
    if found:
        with path.open("w", encoding="utf-8") as f:
            for inc in rows:
                f.write(inc.model_dump_json() + "\n")
    return found


def list_since(since_ms: int) -> list[Incident]:
    """List incidents created at or after since_ms. Used by the 72h
    stability window check in scenario 05."""
    return [inc for inc in list_incidents() if inc.created_at >= since_ms]
