"""
Request and response shapes for SOS Runtime endpoints.

Stays Pydantic v2-compatible (the existing ClarityOS app already
runs on Pydantic v2 via FastAPI; we match). All shapes use
``model_config = ConfigDict(extra="ignore")`` so unknown fields the
WordPress connector adds don't reject the request — the OS controls
the contract via the typed surface.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Common envelope — every authenticated endpoint takes user_id + session_id
# ---------------------------------------------------------------------------
class _Envelope(BaseModel):
    """Shared base for authenticated payloads."""
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    service: str
    version: str


# ---------------------------------------------------------------------------
# /engage
# ---------------------------------------------------------------------------
class EngageRequest(_Envelope):
    message: str = Field(..., min_length=1, max_length=32_000)
    context: dict[str, Any] = Field(default_factory=dict)


class EngageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str
    elins: dict[str, Any]
    state: dict[str, Any]
    continuity: dict[str, Any]


# ---------------------------------------------------------------------------
# /elins  (v1 deterministic stub; wires to V34+ kernel in a follow-up unit)
# ---------------------------------------------------------------------------
class ElinsRequest(_Envelope):
    signal: dict[str, Any] = Field(default_factory=dict)


class ElinsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    normalized: dict[str, Any]
    todo: str


# ---------------------------------------------------------------------------
# /continuity
# ---------------------------------------------------------------------------
class ContinuityRequest(_Envelope):
    markers: dict[str, Any] = Field(default_factory=dict)


class ContinuityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ack: bool
    continuity: dict[str, Any]


# ---------------------------------------------------------------------------
# /state
# ---------------------------------------------------------------------------
class StateRequest(_Envelope):
    """Optional state override. When ``current_state`` is None, the
    endpoint is a read; when it's a string or a dict, it writes."""
    current_state: Optional[Any] = None


class StateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    current_state: Any
    continuity: dict[str, Any]
    last_transition: Optional[int] = None   # ms epoch
    updated_at: Optional[int] = None         # ms epoch


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------
class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: str
    message: str
