"""
SOS Runtime — FastAPI app.

Five endpoints per the V1 spec:
    GET  /health     — public, liveness probe.
    POST /engage     — call Claude with operator message + context.
    POST /elins      — deterministic stub (v34+ kernel wire is its own pass).
    POST /continuity — record continuity markers into sessions + states.
    POST /state      — read or write the per-operator state.

All POST endpoints require ``require_caller`` (Cloud Run IAM JWT)
unless ``SOS_AUTH_MODE=insecure``. WordPress is the operator trust
boundary; this service trusts the ``user_id`` in the body.

Persistence: Firestore (or in-memory backend for tests / dev).
LLM: Anthropic SDK (or fake-mode echo for tests / no-key paths).

Run locally:
    SOS_BACKEND=memory uvicorn sos_runtime.main:app --reload
"""
from __future__ import annotations

import logging
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import SERVICE_NAME, VERSION
from .auth import Principal, auth_status, require_caller
from .firestore_store import _now_ms, get_store
from .llm import call_claude, llm_status
from .schemas import (
    ContinuityRequest,
    ContinuityResponse,
    ElinsRequest,
    ElinsResponse,
    EngageRequest,
    EngageResponse,
    HealthResponse,
    StateRequest,
    StateResponse,
)


logger = logging.getLogger("sos_runtime")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SOS Runtime",
    version=VERSION,
    description=(
        "Operator-facing reasoning service. Sits behind the "
        "WordPress SOS Connector plugin; talks to Claude; persists "
        "to Firestore. Independent of the V47–V82 ClarityOS "
        "infrastructure."
    ),
)

# WordPress origin allow-list. ``SOS_CORS_ORIGINS`` overrides; the
# default matches the spec's pro-mediations.com host.
import os as _os
_default_origins = "https://pro-mediations.com,https://www.pro-mediations.com"
_origins = [
    o.strip() for o in (
        _os.environ.get("SOS_CORS_ORIGINS") or _default_origins
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,   # bearer-token auth, no cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _shape_continuity(state_doc: dict | None) -> dict:
    """Project a state doc into the continuity envelope returned by
    /engage and /continuity."""
    if not state_doc:
        return {}
    return dict(state_doc.get("continuity") or {})


def _shape_state(state_doc: dict | None, user_id: str) -> dict:
    """Project a state doc into the public state shape — never leaks
    Firestore-internal fields."""
    if not state_doc:
        return {
            "user_id":         user_id,
            "current_state":   None,
            "continuity":      {},
            "last_transition": None,
            "updated_at":      None,
        }
    return {
        "user_id":         user_id,
        "current_state":   state_doc.get("current_state"),
        "continuity":      dict(state_doc.get("continuity") or {}),
        "last_transition": state_doc.get("last_transition"),
        "updated_at":      state_doc.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=VERSION,
    )


@app.get("/status")
def status(caller: Principal = Depends(require_caller)) -> dict:
    """Authenticated introspection: confirms the auth + LLM mode the
    pod is running in. Used by the WordPress connector's "test
    connection" admin action."""
    return {
        "ok":       True,
        "service":  SERVICE_NAME,
        "version":  VERSION,
        "caller":   {
            "email": caller.email,
            "mode":  caller.mode,
        },
        "auth":     auth_status(),
        "llm":      llm_status(),
    }


# ---------------------------------------------------------------------------
# /engage
# ---------------------------------------------------------------------------
@app.post("/engage", response_model=EngageResponse)
def engage(
    req: EngageRequest,
    caller: Principal = Depends(require_caller),
) -> EngageResponse:
    store = get_store()
    # 1. Upsert session.
    store.upsert_session(
        req.session_id, req.user_id,
        metadata={"last_endpoint": "engage"},
    )
    # 2. Append engage event (no model_response yet).
    event = store.append_event(
        session_id=req.session_id,
        user_id=req.user_id,
        type="engage",
        payload={"message": req.message, "context": req.context},
    )
    # 3. LLM dispatch.
    model_result = call_claude(req.message, req.context)
    # 4. Mutate the just-stored event with the model response. The
    #    memory backend mutates in-place; the firestore backend
    #    creates a sibling event so we keep an append-only audit.
    if hasattr(store, "_events"):   # memory backend optimisation
        for e in store._events:    # type: ignore[attr-defined]
            if e["id"] == event["id"]:
                e["model_response"] = {
                    "reply":    model_result["reply"],
                    "model_id": model_result["model_id"],
                    "mock":     model_result["mock"],
                }
                break
    else:                            # pragma: no cover (live Firestore)
        store.append_event(
            session_id=req.session_id,
            user_id=req.user_id,
            type="engage",
            payload={"_kind": "model_response", "for_event": event["id"]},
            model_response={
                "reply":    model_result["reply"],
                "model_id": model_result["model_id"],
                "mock":     model_result["mock"],
            },
        )
    # 5. Touch state (bump updated_at; no current_state transition).
    state_doc = store.set_state(
        req.user_id,
        continuity={"last_engage_ts_ms": _now_ms()},
        transition=False,
    )
    return EngageResponse(
        reply=model_result["reply"],
        elins={},  # populated by /elins (or v2 wire)
        state=_shape_state(state_doc, req.user_id),
        continuity=_shape_continuity(state_doc),
    )


# ---------------------------------------------------------------------------
# /elins  (v1 stub — wires to V34+ ELINS kernel in a follow-up unit)
# ---------------------------------------------------------------------------
ELINS_TODO_NOTE = (
    "wire to V34+ ELINS kernel (ELINS.standard_elins / regional_elins / "
    "forecast_engine) — own follow-up unit per the SOS_V1 sizing call."
)


@app.post("/elins", response_model=ElinsResponse)
def elins(
    req: ElinsRequest,
    caller: Principal = Depends(require_caller),
) -> ElinsResponse:
    store = get_store()
    store.upsert_session(
        req.session_id, req.user_id,
        metadata={"last_endpoint": "elins"},
    )
    # Deterministic normalisation: pass through signal + stamp a
    # received_at_ms so downstream consumers can sequence requests.
    normalized = {
        "user_id":       req.user_id,
        "session_id":    req.session_id,
        "signal":        dict(req.signal),
        "received_at_ms": _now_ms(),
    }
    store.append_event(
        session_id=req.session_id,
        user_id=req.user_id,
        type="elins",
        payload={"signal": req.signal},
    )
    return ElinsResponse(
        ok=True,
        normalized=normalized,
        todo=ELINS_TODO_NOTE,
    )


# ---------------------------------------------------------------------------
# /continuity
# ---------------------------------------------------------------------------
@app.post("/continuity", response_model=ContinuityResponse)
def continuity(
    req: ContinuityRequest,
    caller: Principal = Depends(require_caller),
) -> ContinuityResponse:
    store = get_store()
    store.upsert_session(
        req.session_id, req.user_id,
        metadata={"last_endpoint": "continuity"},
    )
    store.append_event(
        session_id=req.session_id,
        user_id=req.user_id,
        type="continuity",
        payload={"markers": req.markers},
    )
    state_doc = store.set_state(
        req.user_id,
        continuity=dict(req.markers),
        transition=False,
    )
    return ContinuityResponse(
        ack=True,
        continuity=_shape_continuity(state_doc),
    )


# ---------------------------------------------------------------------------
# /state
# ---------------------------------------------------------------------------
@app.post("/state", response_model=StateResponse)
def state(
    req: StateRequest,
    caller: Principal = Depends(require_caller),
) -> StateResponse:
    store = get_store()
    store.upsert_session(
        req.session_id, req.user_id,
        metadata={"last_endpoint": "state"},
    )
    if req.current_state is not None:
        # Write path. Triggers last_transition bump.
        state_doc = store.set_state(
            req.user_id,
            current_state=req.current_state,
            transition=True,
        )
        store.append_event(
            session_id=req.session_id,
            user_id=req.user_id,
            type="state",
            payload={"current_state": req.current_state, "mode": "write"},
        )
    else:
        # Read path. Don't append an event for pure reads — they're
        # cheap and the timeline shouldn't bloat with idle polls.
        state_doc = store.get_state(req.user_id)
    shaped = _shape_state(state_doc, req.user_id)
    return StateResponse(**shaped)
