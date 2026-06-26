"""
runtime_http.py — Unit 41.

HTTP runtime surface. Wraps Unit 40 (``session_loop.start_session`` +
``session_loop.step_session``) behind a tiny FastAPI router with two
endpoints so the web / phone / desktop clients can drive the runtime
loop over the wire. No new logic — every behaviour comes from Unit 40
and below.

ROLE
----
First HTTP-level operator surface. Exposes:

    POST /operator/session/start
    POST /operator/session/step

Both endpoints are stateless: the client owns ``session_state`` and
sends it back on every step. Persistence belongs to a later unit
(Unit 42 ``runtime_persistence.py``); this module deliberately
contains no read/write to disk or DB.

NO SIDE EFFECTS AT IMPORT
-------------------------
The module exposes a ``runtime_router`` (``fastapi.APIRouter``). It
neither creates a ``FastAPI`` app nor opens connections at import
time — tests can ``from runtime_http import runtime_router`` and
mount it on a private ``FastAPI`` instance without booting the full
``app.py`` tree.

IMPORTS (LOCKED)
----------------
Only ``fastapi``, ``pydantic``, and ``session_loop``. No direct
imports of ``runtime_kernel``, ``runtime_dispatcher``, ``model_router``,
or any ELINS module — everything flows through Unit 40. Verified by
test ``test_imports_only_session_loop_and_fastapi``.

PUBLIC SURFACE
--------------
    runtime_router: fastapi.APIRouter

    POST /operator/session/start
        body  : { "operator_id": str }
        reply : { "session_state": <Unit 40 session_state> }

    POST /operator/session/step
        body  : {
            "session_state": <Unit 40 session_state>,
            "text":          str,
            "intent_type":   "query | action | plan | diagnostic" (default "query")
        }
        reply : {
            "session_state": <updated Unit 40 session_state>,
            "step_result":   <full Unit 39 output>
        }

Errors:
    422 — Pydantic body validation failure (missing field, wrong type)
    400 — Unit 40 / Unit 39 validation failure (empty operator_id,
          unknown intent_type, malformed session_state, downstream
          ELINS / kernel validation error). The error message text
          is the ValueError raised by the underlying unit.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

import runtime_persistence
import runtime_providers
import session_loop


# ---------------------------------------------------------------------------
# v64 / Unit 66 — Auth dependency for operator-scoped reads.
#
# Mirrors the require_session pattern in app.py but lives here to avoid
# the circular import that would happen if runtime_http imported app
# (app already imports runtime_http for include_router). The
# implementation is small enough that duplicating beats the import
# gymnastics.
#
# Resolves the authed user from X-Session-ID. Returns the user string
# (treated as the operator_id — v66 establishes 1:1 mapping; if a
# separate operator_id ever lands, a future unit upgrades this).
#
# Applied as ``Depends(require_operator)`` on the 3 v63 GET endpoints
# Christian's spec called out:
#   GET /operator/session/{session_id}
#   GET /operator/sessions
#   GET /operator/vault/{operator_id}
#
# Scope intentionally narrow — /operator/session/start + /step remain
# open per existing v60/v61 contract. The /start privacy hole (anyone
# can start a session under any operator_id and inherit that
# operator's vault) is a separate concern flagged in v64 memory.
# ---------------------------------------------------------------------------
def require_operator(
    x_session_id: Optional[str] = Header(default=None),
) -> str:
    """Resolve the authed operator_id from X-Session-ID.

    Returns the user string from sessions_store. Raises 401 on
    missing / invalid / expired session — same error contract as
    app.py's ``require_session``.
    """
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Session-ID header required",
        )
    # Lazy import — sessions_store doesn't trigger any heavy module
    # initialisation, but lazy keeps runtime_http's top-level imports
    # tidy.
    import sessions_store as _sessions
    session = _sessions.get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session",
        )
    if session["expires_at"] < time.time():
        _sessions.delete_session(x_session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session expired",
        )
    return session["user"]


runtime_router = APIRouter(
    prefix="/operator/session",
    tags=["operator", "session"],
)

# v63 / Units 47 + 48 — separate router for the operator-scoped reads
# whose paths don't sit under /operator/session (the list endpoint
# uses /operator/sessions and the vault inspector uses /operator/vault).
# Mounting two routers keeps each path declaration short and avoids
# the path-doubling that comes from a single shared prefix.
operator_router = APIRouter(
    prefix="/operator",
    tags=["operator"],
)

# v65 / Unit 69 — Third router for runtime-level (non-operator-scoped)
# read endpoints. Currently hosts the provider health dashboard.
# Separate from runtime_router (which is /operator/session) and
# operator_router (/operator/*) because /runtime/* sits under a
# distinct namespace.
providers_router = APIRouter(
    prefix="/runtime/providers",
    tags=["runtime", "providers"],
)

# v69 / Unit 74 — EL/INS reasoning-stability operator surface.
# Lives under /el_ins so it sits parallel to /operator/* and
# /runtime/* — it's per-operator (auth-gated) but the data is a
# diagnostic, not session state.
el_ins_router = APIRouter(
    prefix="/el_ins",
    tags=["el_ins"],
)

# v73 / Unit 82 — Operator timeline. Top-level path (NOT under /el_ins)
# per spec — it's a cross-cutting event log, not an EL/INS sub-surface.
timeline_router = APIRouter(
    prefix="/timeline",
    tags=["timeline"],
)

# v73 / Unit 83 — Org-level timeline. Founder-gated.
org_timeline_router = APIRouter(
    prefix="/org/timeline",
    tags=["org", "timeline"],
)


# v73 / Unit 83 — Founder-cohort gate. Mirrors the app.py
# _require_founder pattern but lives here so /org/timeline/* doesn't
# need to import app.py back (avoids the circular import that bit
# v64). Cohort literals match app.py's COHORT_FOUNDER /
# COHORT_FOUNDER_EXCEPTION constants.
_FOUNDER_COHORTS: frozenset[str] = frozenset({"founder", "founder_exception"})


def require_founder(
    operator_id: str = Depends(require_operator),
) -> str:
    """Cohort-based gate. Returns the authed operator_id when the user
    is in the ``founder`` or ``founder_exception`` cohort; otherwise
    raises 403 — same status code as app.py's ``_require_founder``.
    """
    import users_store as _users  # lazy — matches the require_operator pattern
    user_doc = _users.get_user(operator_id) or {}
    if user_doc.get("cohort") not in _FOUNDER_COHORTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Founder cohort required",
        )
    return operator_id


# ---------------------------------------------------------------------------
# Request models
#
# Response shapes are plain dicts returned by Unit 40 — FastAPI emits them
# as JSON without us declaring a response model. Declaring response
# models would mean re-asserting the locked shape here and risk
# diverging from Unit 40 silently.
# ---------------------------------------------------------------------------
class StartSessionRequest(BaseModel):
    operator_id: str = Field(
        ...,
        description="Non-empty operator identifier. Echoed into the "
                    "returned session_state.",
    )
    resume: bool = Field(
        default=False,
        description="v61 / Unit 43: when True and session_id is "
                    "supplied, try to resume that session from "
                    "persistence (operator_id must match the stored "
                    "session's operator_id). Falls back to a fresh "
                    "start_session on miss or mismatch.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="v61 / Unit 43: required when resume=True. Ignored "
                    "otherwise.",
    )


class StepSessionRequest(BaseModel):
    session_state: dict = Field(
        ...,
        description="Full session_state dict — typically the one "
                    "returned by /start or the previous /step.",
    )
    text: str = Field(
        ...,
        description="Operator's input text for this step. May be empty.",
    )
    intent_type: Optional[str] = Field(
        default="query",
        description="One of query | action | plan | diagnostic.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@runtime_router.post("/start")
def start(
    body: StartSessionRequest,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Begin or resume a session.

    Wraps ``session_loop.start_session``. Returns the new session_state
    inside a single ``{"session_state": ...}`` envelope.

    v65 / Unit 68 — auth-gated. ``body.operator_id`` is preserved in
    the request shape for v62-v67 client compatibility but **server
    ignores it** — the authed identity from ``require_operator`` is
    the sole source of truth for who owns the session. Resume
    ownership now compares against the authed identity, not against
    a client-claimed operator_id.

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    if body.resume and body.session_id:
        try:
            stored = runtime_persistence.load_session(body.session_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if (
            isinstance(stored, dict)
            and stored.get("operator_id") == operator_id
        ):
            return {"session_state": stored}
        # Miss or operator mismatch → fall through to fresh start.
        # Same "don't leak existence" posture as v61.
    try:
        state = session_loop.start_session(operator_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"session_state": state}


@runtime_router.post("/step")
def step(
    body: StepSessionRequest,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Advance the session by one operator step.

    Wraps ``session_loop.step_session``. Returns the new session_state
    plus the full Unit 39 step_result.

    v65 / Unit 68 — auth-gated + ownership-checked.

    Behaviour:
      * ``body.session_state`` is preserved in the request shape for
        v62-v67 client compatibility, but the server enforces that
        the session belongs to the authed operator by checking
        ``runtime_persistence.load_session(session_id).operator_id``.
      * Mismatch → 404 (don't leak existence of other operators'
        sessions).
      * On match, the handler rewrites
        ``session_state.operator_id`` to the authed value before
        passing to ``step_session`` so the v64 reload-before-apply
        path doesn't get a stale-or-spoofed identity.

    ``intent_type`` defaults to ``"query"`` when the client omits it.
    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    intent_type = body.intent_type or "query"

    # Ownership check via persistence. session_state must have a
    # session_id (Pydantic accepts arbitrary dict but session_loop
    # validates the required keys downstream; we duplicate the
    # session_id read here for the ownership check).
    session_state = body.session_state
    session_id = session_state.get("session_id") if isinstance(session_state, dict) else None
    if isinstance(session_id, str) and session_id:
        try:
            stored = runtime_persistence.load_session(session_id)
        except ValueError:
            stored = None
        if isinstance(stored, dict) and stored.get("operator_id") != operator_id:
            # Belongs to someone else — 404 not 403, no leak.
            raise HTTPException(status_code=404, detail="session not found")
    # session_id missing or not loadable → let session_loop validate
    # and surface the error normally (400). No auth-related decision
    # to make on that path.

    # Rewrite operator_id in the inbound session_state to the authed
    # value. v64's step_session reloads anyway, but this prevents a
    # client-spoofed operator_id from being persisted on the first
    # call before any prior save exists.
    if isinstance(session_state, dict):
        rewritten = dict(session_state)
        rewritten["operator_id"] = operator_id
        session_state = rewritten

    try:
        out = session_loop.step_session(
            session_state,
            body.text,
            intent_type=intent_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out


# ---------------------------------------------------------------------------
# v63 / Unit 47 — Session history viewer
#
# Two read-only endpoints over the v60 persistence layer:
#   * GET /operator/session/{session_id}            — detail
#   * GET /operator/sessions?operator_id=...         — list per operator
#
# Both return v59-locked session_state shapes verbatim — clients map
# field names if their UI wants different labels (the spec's
# {input, intent, runtime_response, model_response} terminology doesn't
# match v59's {text, intent_type, runtime_decision, engine}; we don't
# break the lock).
#
# No mutation. No auth (matches /start + /step which are also open —
# pre-existing privacy posture, fix is a future auth-wiring unit).
# ---------------------------------------------------------------------------
# NOTE on route ordering: the list endpoint uses a different path
# (/sessions, plural) than the detail endpoint (/session/{id}, singular).
# That avoids any chance of "list" being interpreted as a session_id.
# ---------------------------------------------------------------------------

@runtime_router.get("/{session_id}")
def get_session_detail(
    session_id: str,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Fetch the full session_state for ``session_id``.

    v64 / Unit 66 — auth-gated + ownership-checked.

    Returns ``{"session_state": <v59 shape>}`` on hit when
    ``stored["operator_id"] == operator_id`` (the authed user).

    Returns 404 when:
        * no session exists for that id, OR
        * the session exists but belongs to a different operator
          (we deliberately don't leak the distinction — 404 either
          way to avoid confirming session-id existence).

    Returns 400 on a malformed id (regex reject from persistence).
    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    try:
        stored = runtime_persistence.load_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not isinstance(stored, dict):
        raise HTTPException(status_code=404, detail="session not found")
    if stored.get("operator_id") != operator_id:
        # Don't leak existence — 404 not 403.
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_state": stored}


@operator_router.get("/sessions")
def list_sessions(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """List session summaries for the authed operator.

    v64 / Unit 66 — auth-gated. The v63 query-string
    ``?operator_id=...`` is removed; the authed identity is the
    only operator the endpoint will list. (v63 clients that
    passed the query param will see it silently ignored because
    FastAPI binds the dependency-injected ``operator_id`` first.)

    Returns ``{"operator_id": str, "sessions": list[<summary>]}``
    where each summary carries session_id, operator_id, history_len,
    and timestamp. Sort: newest-first by last-step timestamp.

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    try:
        summaries = runtime_persistence.list_sessions_for_operator(operator_id)
    except ValueError as e:
        # Shouldn't happen for an authed user (the session_store
        # only stores valid user strings), but defensive.
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "sessions": summaries}


# ---------------------------------------------------------------------------
# v63 / Unit 48 — Operator-scoped vault inspector
#
# One read-only endpoint:
#   * GET /operator/vault/{operator_id}              — vault snapshot
#
# Naming: ``/operator/vault/...`` deliberately matches the existing
# ``/operator/session/...`` prefix so all runtime-loop endpoints live
# under a single router. (Web's client routes use /operator-vault to
# avoid colliding with the legacy /vault from the v1 storage layer —
# the server prefix is unrelated.)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# v64 / Unit 67 — Operator model preferences API.
#
# Two endpoints, both auth-gated:
#   GET  /operator/model_preferences  → current {provider, model}
#                                       resolved via get_operator_model
#   POST /operator/model_preferences  → set {provider, model} in vault
#
# Both honour the same require_operator dependency. Allowlist for
# {provider, model} reuses runtime_providers.PROVIDERS_ORDER and the
# v44 SUPPORTED_MODELS catalogue.
# ---------------------------------------------------------------------------

class ModelPreferencesRequest(BaseModel):
    provider: str = Field(
        ...,
        description="One of anthropic | openai | gemini | xai | local.",
    )
    model: str = Field(
        ...,
        description="Non-empty model name. Must form a valid model_id "
                    "when combined with the provider prefix.",
    )


@operator_router.get("/model_preferences")
def get_model_preferences(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Return the resolved ``(provider, model)`` for the authed
    operator.

    Walks ``runtime_providers.get_operator_model`` against the
    operator's current vault. If the vault has no explicit
    preference, the response carries the resolution-chain default
    (first available real provider, or anthropic/claude-3.7 mock
    fallback when no keys are set).

    Returns ``{operator_id, provider, model, source}`` where
    ``source`` is ``"vault"`` when the preference is explicitly
    set, ``"default"`` otherwise.
    """
    try:
        vault = runtime_persistence.load_vault(operator_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    provider, model = runtime_providers.get_operator_model(vault)
    # Distinguish vault-set from default-chain — useful for the UI
    # to render "(default)" vs the explicit pick.
    source = "default"
    if isinstance(vault, dict):
        runtime = vault.get("runtime")
        if isinstance(runtime, dict) and isinstance(
            runtime.get("model_preferences"), dict,
        ):
            source = "vault"
    return {
        "operator_id": operator_id,
        "provider":    provider,
        "model":       model,
        "source":      source,
    }


@operator_router.post("/model_preferences")
def set_model_preferences(
    body: ModelPreferencesRequest,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Update ``vault["runtime"]["model_preferences"]`` for the authed
    operator.

    Validation:
        * ``provider`` must be one of
          ``runtime_providers.PROVIDERS_ORDER``.
        * ``(provider, model)`` must map to an id present in
          ``model_router.SUPPORTED_MODELS`` (via
          ``runtime_providers.model_id_for``).

    Returns the updated ``{operator_id, provider, model, source:"vault"}``.
    """
    # Provider check via runtime_providers (raises ValueError on bad input).
    try:
        new_model_id = runtime_providers.model_id_for(body.provider, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Allowlist against SUPPORTED_MODELS.
    import model_router as _mr
    if not _mr.is_valid_model(new_model_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"({body.provider!r}, {body.model!r}) maps to unsupported "
                f"model_id {new_model_id!r}"
            ),
        )

    try:
        prior_vault = runtime_persistence.load_vault(operator_id) or {}
        new_vault = runtime_providers.set_operator_model_preference_in_vault(
            prior_vault, body.provider, body.model,
        )
        runtime_persistence.save_vault(operator_id, new_vault)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "operator_id": operator_id,
        "provider":    body.provider,
        "model":       body.model,
        "source":      "vault",
    }


@operator_router.get("/vault/{operator_id}")
def get_vault(
    operator_id: str,
    authed_operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Fetch the vault snapshot for the authed operator.

    v64 / Unit 66 — auth-gated. The path-form ``operator_id`` is
    retained for URL-shape compatibility with v63 clients but the
    server **ignores** it and always uses the authed identity. This
    closes the v63 IDOR vector (anyone could read any vault by
    guessing the id).

    Returns::

        {
          "operator_id":  str,        # the AUTHED id, not the path value
          "vault":        dict | None,
          "last_updated": str
        }

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    # ``operator_id`` from the path is deliberately ignored — kept in
    # the signature so the path param remains documented in OpenAPI
    # but server-side always uses ``authed_operator_id``.
    _ = operator_id
    try:
        stored = runtime_persistence.load_vault(authed_operator_id)
        last_updated = runtime_persistence.get_vault_last_updated(authed_operator_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "operator_id":  authed_operator_id,
        "vault":        stored,
        "last_updated": last_updated,
    }


# ---------------------------------------------------------------------------
# v65 / Unit 69 — Provider health dashboard
#
# Lightweight health-check endpoint per provider. For every provider
# with an env key configured, issue a 1-token trivial completion call
# via the v65 _http_post_json chokepoint. Timeout 3s. Any exception →
# available=false with the exception string.
#
# The synthetic "mock" provider is always available=true — the
# fallback path through model_router._mock_result is guaranteed to
# work (deterministic, no I/O).
#
# Returned per provider:
#     {"available": bool, "error": str | None}
#
# Auth-gated even though the data is system-level — consistent with
# the rest of /operator/* and /runtime/* under v66 / v68 and prevents
# unauthenticated probes from learning which keys are configured.
# ---------------------------------------------------------------------------

# v66 / Unit 71 — the legacy ``_PROVIDER_HEALTH_TIMEOUT = 3.0`` module
# constant is gone; the per-provider value now comes from
# ``runtime_http_config.get_health_timeout(provider)``. Production
# behaviour is unchanged (3s across the board) but the value is
# addressable and tunable.
import runtime_http_config


def _check_provider_health(provider: str) -> dict[str, Any]:
    """Issue a trivial 1-token completion to ``provider`` and return
    ``{"available": bool, "error": str | None}``.

    Returns ``available: False, error: "no api key configured"`` when
    the env key is unset. Any other failure carries the exception
    text.
    """
    import model_router as _mr

    if not _mr._provider_configured(provider):
        return {"available": False, "error": "no api key configured"}

    # Per-Unit-71: pull the health timeout from the runtime_http_config
    # registry. Override the call-path timeout transactionally via the
    # `_request_timeout` context manager that model_router exports.
    health_timeout = runtime_http_config.get_health_timeout(provider)
    try:
        with _mr._request_timeout(health_timeout):
            if provider == "anthropic":
                wire_model = "claude-3.7-sonnet-20250101"  # placeholder; provider validates
                key = (os.environ.get("CLARITYOS_ANTHROPIC_KEY") or "").strip()
                _mr._http_post_json(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    body={
                        "model": wire_model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "?"}],
                    },
                )
            elif provider == "openai":
                key = (os.environ.get("CLARITYOS_OPENAI_KEY") or "").strip()
                _mr._http_post_json(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    body={
                        "model": "gpt-5.4-mini",
                        "messages": [{"role": "user", "content": "?"}],
                        "max_completion_tokens": 1,
                    },
                )
            elif provider == "gemini":
                key = (os.environ.get("CLARITYOS_GEMINI_KEY") or "").strip()
                _mr._http_post_json(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                    headers={"Content-Type": "application/json"},
                    body={
                        "contents": [{"parts": [{"text": "?"}]}],
                        "generationConfig": {"maxOutputTokens": 1},
                    },
                )
            else:
                return {"available": False, "error": f"unknown provider {provider!r}"}
        return {"available": True, "error": None}
    except Exception as e:  # pragma: no cover (real-network path)
        return {"available": False, "error": str(e)}


# Need os in this scope. Already imported at module top via app.py
# auth pattern, but re-import here defensively.
import os  # noqa: E402


@providers_router.get("/health")
def get_provider_health(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Per-provider availability snapshot.

    Returns a dict keyed by provider name with ``{available, error}``.
    The synthetic ``mock`` entry is always ``{available: True, error: null}``.

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    # Match Christian's example shape: anthropic / openai / gemini / mock.
    _ = operator_id  # auth-only; result is system-level
    return {
        "anthropic": _check_provider_health("anthropic"),
        "openai":    _check_provider_health("openai"),
        "gemini":    _check_provider_health("gemini"),
        "mock":      {"available": True, "error": None},
    }


# ---------------------------------------------------------------------------
# v66 / Unit 71 — Server-side model registry endpoint.
#
# Returns the structured ``MODEL_REGISTRY`` (provider → models) plus
# the flat allowlist ``SUPPORTED_MODELS`` used by validation. Useful
# for clients that want to render a model picker without hardcoding
# the list, and for ops to confirm which models a deployment accepts.
#
# Auth-gated, same pattern as /runtime/providers/health. Reads-only;
# the registry itself is configured at import time in model_router.
# ---------------------------------------------------------------------------
@providers_router.get("/models")
def get_provider_models(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Return the server-side model registry.

    Shape::

        {
          "registry":  { <provider>: [<model_id>, ...], ... },
          "supported": [<model_id>, ..., "auto"]
        }

    Where ``registry`` is ``model_router.MODEL_REGISTRY`` and
    ``supported`` is the derived flat tuple ``SUPPORTED_MODELS``.
    The ``"auto"`` routing sentinel appears in ``supported`` but
    never under a provider in ``registry`` (it isn't a wire model).

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    _ = operator_id  # auth-only; payload is system-level
    import model_router as _mr
    return {
        "registry":  {
            provider: list(models)
            for provider, models in _mr.MODEL_REGISTRY.items()
        },
        "supported": list(_mr.SUPPORTED_MODELS),
    }


# ---------------------------------------------------------------------------
# v68 / Unit 73 — Provider HTTP config surface.
#
# Returns the per-provider call + health timeouts and retry budget that
# ``runtime_http_config`` exposes. Pairs with /health (state) and
# /models (catalogue) to render the full Provider Dashboard surface.
#
# Auth-gated; same pattern as the rest of /runtime/providers/*.
# ---------------------------------------------------------------------------
@providers_router.get("/config")
def get_provider_config(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Return the per-provider HTTP behaviour config.

    Shape::

        {
          "timeouts": { <provider>: {"call": <float>, "health": <float>}, ... },
          "retries":  { <provider>: <int>, ... },
          "defaults": {
            "call_timeout":   <float>,
            "health_timeout": <float>,
            "retries":        <int>
          }
        }

    The provider key set in ``timeouts`` / ``retries`` is whatever
    ``runtime_http_config`` declares; defaults apply to anything
    outside the registry (e.g. the synthetic ``mock`` provider has
    no HTTP path so it doesn't appear in these maps).

    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    _ = operator_id  # auth-only; payload is system-level
    providers = sorted(set(runtime_http_config.PROVIDER_CALL_TIMEOUTS.keys()))
    return {
        "timeouts": {
            p: {
                "call":   runtime_http_config.get_call_timeout(p),
                "health": runtime_http_config.get_health_timeout(p),
            }
            for p in providers
        },
        "retries": {
            p: runtime_http_config.get_retry_count(p)
            for p in providers
        },
        "defaults": {
            "call_timeout":   runtime_http_config.DEFAULT_CALL_TIMEOUT,
            "health_timeout": runtime_http_config.DEFAULT_HEALTH_TIMEOUT,
            "retries":        runtime_http_config.DEFAULT_RETRIES,
        },
    }


# ---------------------------------------------------------------------------
# v69 / Unit 74 — EL/INS endpoints
#
# Four endpoints exposing the el_ins kernel module:
#   POST /el_ins/analyze              — analyze text, optionally store
#   GET  /el_ins/recent               — latest N records for authed operator
#   GET  /el_ins/thread/{thread_id}   — thread-scoped history
#   GET  /el_ins/macro                — macro-batch view (since=...)
#
# All four auth-gated via require_operator. The /analyze endpoint
# accepts ``provider_mode`` (llm|deterministic|auto) and an optional
# ``thread_id`` — when present, the record is stored in el_ins_store.
# ---------------------------------------------------------------------------

class ElInsAnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        description="Non-empty text to analyze. Whitespace-only input is "
                    "accepted but returns a deterministic balanced result "
                    "with zero scores.",
    )
    provider_mode: Optional[str] = Field(
        default="auto",
        description="One of llm | deterministic | auto. Defaults to auto.",
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="When set, the result is stored in el_ins_store under "
                    "this thread_id for later retrieval.",
    )


@el_ins_router.post("/analyze")
def el_ins_analyze(
    body: ElInsAnalyzeRequest,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Analyze ``text`` and (optionally) store the result.

    Returns ``{result, stored, thread_id, timestamp}``. ``stored`` is
    True iff ``thread_id`` was provided and the store accepted the
    record.

    Returns 400 on bad ``provider_mode``.
    Returns 401 on missing / invalid / expired X-Session-ID.
    """
    import el_ins  # lazy
    import time as _time
    mode = body.provider_mode or "auto"
    if mode not in el_ins.PROVIDER_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"provider_mode must be one of {el_ins.PROVIDER_MODES}, got {mode!r}",
        )
    try:
        result = el_ins.analyze_text(body.text, provider_mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    timestamp = _time.time()
    stored = False
    if body.thread_id:
        try:
            el_ins.store_el_ins_record({
                "operator_id": operator_id,
                "thread_id":   body.thread_id,
                "timestamp":   timestamp,
                "source":      "on_demand",
                "result":      dict(result),
            })
            stored = True
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {
        "result":    result,
        "stored":    stored,
        "thread_id": body.thread_id,
        "timestamp": timestamp,
    }


@el_ins_router.get("/recent")
def el_ins_recent(
    limit: int = 100,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Most-recent ``limit`` records for the authed operator across all
    threads. Newest-first. ``limit`` clamped to [1, 1000]."""
    import el_ins  # lazy
    try:
        rows = el_ins.get_recent_el_ins(operator_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "records": rows}


@el_ins_router.get("/thread/{thread_id}")
def el_ins_thread(
    thread_id: str,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """All records for ``(authed operator, thread_id)``, newest-first."""
    import el_ins  # lazy
    try:
        rows = el_ins.get_thread_el_ins(operator_id, thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "thread_id": thread_id, "records": rows}


@el_ins_router.get("/macro")
def el_ins_macro(
    since: Optional[float] = None,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Macro-batch view for the authed operator. When ``since`` (unix
    seconds, float) is supplied, restricts to records with
    ``timestamp >= since``. Otherwise returns all records, newest-first."""
    import el_ins  # lazy
    try:
        rows = el_ins.get_macro_el_ins(operator_id, since=since)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "since": since, "records": rows}


# ---------------------------------------------------------------------------
# v70 / Unit 76 — Thread stability + TSI
# ---------------------------------------------------------------------------
@el_ins_router.get("/thread/{thread_id}/stability")
def el_ins_thread_stability(
    thread_id: str,
    window: int = 10,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Return ``{thread_id, stability, tsi, window}`` for the
    most-recent ``window`` records on the authed operator's
    ``thread_id``. Empty thread returns ``stability="stable"``,
    ``tsi=100``, ``window=0``.
    """
    import el_ins  # lazy
    try:
        return el_ins.compute_thread_stability(
            operator_id, thread_id, window=window,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# v70 / Unit 77 — Operator-level EL/INS summary (macro dashboard data)
# ---------------------------------------------------------------------------
@el_ins_router.get("/operator/summary")
def el_ins_operator_summary(
    sample_size: int = 20,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Aggregate macro summary for the authed operator over the most
    recent ``sample_size`` records across all threads.

    Shape::

        {
          "recent_classification_distribution": {"high_el": N, "high_ins": N, "balanced": N},
          "avg_tsi":     int (0..100),
          "trend":       "improving" | "declining" | "stable",
          "sample_size": int     # actual sample size used
        }
    """
    import el_ins  # lazy
    try:
        return el_ins.compute_operator_summary(
            operator_id, sample_size=sample_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# v71 / Unit 78 — EL/INS export (JSON + PDF)
#
# Two endpoints emit portable per-operator exports for onboarding /
# coaching / institutional review. Both auth-gated; both clamp to a
# sane upper bound on ``limit`` to keep PDF generation tractable.
# ---------------------------------------------------------------------------
def _clamp_export_limit(limit: int) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 200
    return max(1, min(1000, n))


def _health_version() -> str:
    """Inspect the FastAPI ``/health`` route's literal return so the
    PDF footer stays in sync with the running app without ``app.py``
    importing this module back. Falls back to ``unknown`` on any
    introspection failure."""
    try:
        import app as _app  # lazy
        # Probe the bare in-process function — bypasses HTTP.
        resp = _app.health()
        return str(resp.get("version") or "unknown")
    except Exception:  # pragma: no cover (defensive)
        return "unknown"


def _build_version() -> str:
    try:
        from pathlib import Path as _Path
        return _Path("BUILD_VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except Exception:  # pragma: no cover (defensive)
        return "unknown"


@el_ins_router.get("/export/json")
def el_ins_export_json(
    limit: int = 200,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Portable JSON export of the authed operator's EL/INS records.

    Returns ``{operator_id, generated_at, records}``. ``limit`` clamps
    to ``[1, 1000]``; default 200.
    """
    import el_ins  # lazy
    n = _clamp_export_limit(limit)
    rows = el_ins.get_recent_el_ins(operator_id, limit=n)
    return el_ins.build_json_export(operator_id, rows)


@el_ins_router.get("/export/pdf")
async def el_ins_export_pdf(
    limit: int = 200,
    operator_id: str = Depends(require_operator),
) -> Response:
    """Portable PDF export of the authed operator's EL/INS records.

    PDF generation is CPU-bound but tiny (~5ms / 200 records on a
    2024 laptop). We still hop it onto a worker thread via
    ``asyncio.to_thread`` so larger payloads (limit=1000) don't
    stall the event loop.

    Returns the raw PDF bytes with ``application/pdf`` content type
    and a ``Content-Disposition: attachment`` header so browsers
    trigger a download.
    """
    import asyncio
    import el_ins  # lazy
    n = _clamp_export_limit(limit)
    rows = el_ins.get_recent_el_ins(operator_id, limit=n)
    summary = el_ins.compute_operator_summary(operator_id, sample_size=n)
    version = _health_version()
    build = _build_version()
    pdf_bytes = await asyncio.to_thread(
        el_ins.build_pdf_export,
        operator_id, rows, summary,
        version=version, build=build,
    )
    filename = f"el_ins_export_{operator_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# v71 / Unit 79 — Reasoning-mode endpoint
#
# Surfaces ``select_reasoning_mode(el, ins, tsi)`` against the
# operator's latest EL/INS record. Used by the cockpit indicator
# label across web/desktop/phone.
#
# Returns "normal" + a null record when the operator has no records
# yet, so the UI can render a safe placeholder without 404 handling.
# ---------------------------------------------------------------------------
@el_ins_router.get("/operator/reasoning_mode")
def el_ins_operator_reasoning_mode(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Return the reasoning-mode currently implied by the operator's
    most-recent EL/INS record.

    Shape::

        {
          "operator_id":    str,
          "reasoning_mode": str,    # grounding | analysis | structured_reflection
                                    # | stabilization | normal
          "el":             float | None,
          "ins":            float | None,
          "tsi":            int | None,
          "timestamp":      float | None
        }

    Empty-history operators get
    ``reasoning_mode="normal"`` with every other field None.
    """
    import el_ins  # lazy
    import intelligence_kernel as _ik

    rows = el_ins.get_recent_el_ins(operator_id, limit=1)
    if not rows:
        return {
            "operator_id":    operator_id,
            "reasoning_mode": "normal",
            "el":             None,
            "ins":            None,
            "tsi":            None,
            "timestamp":      None,
        }
    rec = rows[0]
    analysis = (rec.get("result") or {}).get("analysis", {})
    el_score = float(analysis.get("el_score") or 0.0)
    ins_score = float(analysis.get("ins_score") or 0.0)
    tsi = rec.get("tsi") if isinstance(rec.get("tsi"), int) else None
    mode = _ik.select_reasoning_mode(el_score, ins_score, tsi)
    return {
        "operator_id":    operator_id,
        "reasoning_mode": mode,
        "el":             el_score,
        "ins":            ins_score,
        "tsi":            tsi,
        "timestamp":      float(rec.get("timestamp") or 0.0),
    }


# ---------------------------------------------------------------------------
# v72 / Unit 80 — Anomaly endpoints
# ---------------------------------------------------------------------------
@el_ins_router.get("/anomalies")
def el_ins_list_anomalies(
    limit: int = 100,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Newest-first list of the authed operator's anomalies.

    ``limit`` clamps to ``[1, 1000]``. Default 100.
    """
    import el_ins  # lazy
    try:
        rows = el_ins.list_anomalies(operator_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "anomalies": rows}


@el_ins_router.get("/anomalies/{anomaly_id}")
def el_ins_get_anomaly(
    anomaly_id: str,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Single-anomaly fetch for the authed operator. Returns 404 when
    the id doesn't match a stored row owned by this operator (no
    cross-operator leak).
    """
    import el_ins  # lazy
    try:
        anom = el_ins.get_anomaly(operator_id, anomaly_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if anom is None:
        raise HTTPException(status_code=404, detail="anomaly not found")
    return anom


# ---------------------------------------------------------------------------
# v72 / Unit 81 — Roll-up endpoints
# ---------------------------------------------------------------------------
def _rollup_for(operator_id: str, window_name: str) -> dict[str, Any]:
    import el_ins  # lazy
    try:
        out = el_ins.compute_rollup(operator_id, window_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # v73 / Unit 82 — emit a ``rollup`` timeline event for the
    # requesting operator. Side effect on a GET endpoint, but matches
    # the spec ("audit-trail of when operators reviewed"). Failures
    # swallow — timeline is a diagnostic, never allowed to break the
    # endpoint response.
    try:
        ev = el_ins.build_rollup_event(
            operator_id,
            window=window_name,
            avg_el=out.get("avg_el", 0.0),
            avg_ins=out.get("avg_ins", 0.0),
            avg_tsi=out.get("avg_tsi", 0),
            record_count=out.get("record_count", 0),
        )
        el_ins.store_event(ev)
    except Exception:  # pragma: no cover (defensive)
        pass
    return out


@el_ins_router.get("/rollup/24h")
def el_ins_rollup_24h(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Operator-level aggregate over the last 24 hours."""
    return _rollup_for(operator_id, "24h")


@el_ins_router.get("/rollup/7d")
def el_ins_rollup_7d(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Operator-level aggregate over the last 7 days."""
    return _rollup_for(operator_id, "7d")


@el_ins_router.get("/rollup/30d")
def el_ins_rollup_30d(
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Operator-level aggregate over the last 30 days."""
    return _rollup_for(operator_id, "30d")


# ---------------------------------------------------------------------------
# v73 / Unit 82 — Operator timeline endpoints
#
# Write-only-from-system event log. No POST surface: events land via
# the kernel hook (``run_thread_message``) and the rollup endpoints.
# All three reads auth-gated by ``require_operator``; cross-operator
# access on the single-event endpoint returns 404 (no existence leak).
# ---------------------------------------------------------------------------
@timeline_router.get("")
def timeline_list(
    limit: int = 200,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Newest-first list of timeline events for the authed operator.
    ``limit`` clamps to ``[1, 1000]`` (DEFAULT_TIMELINE_LIMIT = 200).
    """
    import el_ins  # lazy
    try:
        rows = el_ins.list_events(operator_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"operator_id": operator_id, "events": rows}


@timeline_router.get("/since/{timestamp_ms}")
def timeline_since(
    timestamp_ms: int,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Events newer than ``timestamp_ms`` (inclusive) for the authed
    operator. Newest-first. Used by clients polling for "new since
    last seen" without server-side seen-state."""
    import el_ins  # lazy
    try:
        rows = el_ins.list_events_since(operator_id, timestamp_ms)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "operator_id":  operator_id,
        "since_ms":     int(timestamp_ms),
        "events":       rows,
    }


@timeline_router.get("/{event_id}")
def timeline_get(
    event_id: str,
    operator_id: str = Depends(require_operator),
) -> dict[str, Any]:
    """Single-event lookup. Returns 404 when the id doesn't match an
    event owned by the authed operator (no cross-operator existence
    leak)."""
    import el_ins  # lazy
    try:
        ev = el_ins.get_event(operator_id, event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if ev is None:
        raise HTTPException(status_code=404, detail="timeline event not found")
    return ev


# ---------------------------------------------------------------------------
# v73 / Unit 83 — Org-level timeline endpoints
#
# Founder-cohort gated. Returns sanitised, masked entries — never
# raw payloads, never thread_ids, never unmasked operator_ids.
# Cross-operator masking is one-way (last 6 chars only).
# ---------------------------------------------------------------------------
def _org_timeline_for(window_name: str) -> dict[str, Any]:
    import el_ins  # lazy
    try:
        rows = el_ins.compute_org_timeline(window_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"window": window_name, "entries": rows}


@org_timeline_router.get("/24h")
def org_timeline_24h(
    _founder_id: str = Depends(require_founder),
) -> dict[str, Any]:
    """Org-level aggregated timeline over the last 24 hours.
    Founder-cohort gated."""
    return _org_timeline_for("24h")


@org_timeline_router.get("/7d")
def org_timeline_7d(
    _founder_id: str = Depends(require_founder),
) -> dict[str, Any]:
    """Org-level aggregated timeline over the last 7 days.
    Founder-cohort gated."""
    return _org_timeline_for("7d")


@org_timeline_router.get("/30d")
def org_timeline_30d(
    _founder_id: str = Depends(require_founder),
) -> dict[str, Any]:
    """Org-level aggregated timeline over the last 30 days.
    Founder-cohort gated."""
    return _org_timeline_for("30d")
