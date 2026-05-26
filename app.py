"""
ClarityOS Cloud — single FastAPI app.

v2.3 — adds browser-safe CORS via CORSMiddleware. Configurable
via CLARITYOS_CORS_ORIGINS (comma-separated). No route or envelope
changes; this is strictly an additive middleware so the WordPress
front-end at pro-mediations.com (and any future origins) can call
the API from a browser.

v2.2 — adds Firestore-backed user/session persistence behind a
backend switch (CLARITYOS_BACKEND=memory|firestore). All routes,
envelopes, status codes, and signatures are unchanged from v2.1.

v2.1 — adds GCS-backed library access, structured logging, and a
protected /config endpoint, while preserving all v2.0 behavior:
auth, session middleware, engine adapters, mobile-safe JSON envelope,
custom exception handler.

Routes
------
  POST /login                 username/password -> session_id
  POST /register              create user; returns session_id (auto-login)
  GET  /me            [auth]  current session info
  GET  /config        [auth]  runtime configuration (bucket, prefix, TTL)
  POST /markov        [auth]  Markov / Markoff engine
  POST /galileo       [auth]  Galileo clarity cycle
  POST /library       [auth]  Library lookup (GCS-backed)
  POST /tizzy         [auth]  Tizzy engine
  GET  /health                health check (public)
  GET  /                      index of available routes (public)

Mobile-safe envelope
--------------------
  success:  {"ok": true,  "engine": "...", "data": {...}, ...}
  error  :  {"ok": false, "error": "code", "message": "human text"}

Environment variables
---------------------
  CLARITYOS_BACKEND            "memory" (default) or "firestore"
  CLARITYOS_CORS_ORIGINS       comma-separated allowed origins; default
                               "https://pro-mediations.com,
                                https://www.pro-mediations.com,
                                https://clarity.pro-mediations.com"
  CLARITYOS_ADMIN_USER         default "admin"
  CLARITYOS_ADMIN_PASSWORD     if unset, a random one is generated and
                               printed once on startup (bootstrap only)
  CLARITYOS_SESSION_TTL        seconds; default 86400 (24h)
  CLARITYOS_LIBRARY_BUCKET     default "clarityos-library"
  CLARITYOS_LIBRARY_PREFIX     default "" (no prefix)
"""

import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

import bcrypt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

import users_store
import sessions_store
import invites_store
import tokens as invite_tokens
import billing
import vault_store
import library_store
import timeline_store
import usage_store
import dewey_neighborhoods_store
import dewey_memberships_store
import dewey_worker
import dewey_pipeline
import markov_states_store
import envelopes_store
import trajectories_store
import elins_distribution_store    # v28 — surface/distribution layer
import mesh_metadata_store         # v28 — Dewey-only metadata mesh
import v29_hardening               # v29 — validation / rate-limit / flags
import membership_store            # v30 — cohort cap, waitlist, transactions
import membership_billing          # v30 — charge / record_transaction
import billing_intents             # v31 — PaymentIntent + webhook handler
import billing_renewal             # v31 — daily renewal scheduler
import waitlist_store              # v32 — public waitlist pipeline
import comment_generator           # v33 — MRCG v1.0 (#cmt)
import dm_store                    # v33 — manual DM tracking
from ELINS import standard_elins   # v33 — canonical 10-layer ELINS pipeline
from ELINS import elins_project    # v33 — ELINS persistence layer
from ELINS import forecast_engine  # v34 — multi-primitive envelope forecast
from ELINS import regional_elins   # v35 — region-aware ELINS
from ELINS import ingestion_bus    # v54 — RSS/Atom + manual ingestion bus
import perplexity_oracle           # v35 — ESO fetcher (deterministic mock)
import elins_scheduler             # v36 — macro-ELINS scheduler
import elins_scheduler_config      # v36 — scheduler config store
import elins_entity_graph          # v37 — cross-cluster entity graph
import elins_dashboard              # v38 — interactive dashboard aggregator
import operator_state              # v39 — operator state memory + continuity
import intelligence_kernel        # v40 — unified #c/#G/ELINS/ESO/macro kernel
import billing_config              # v42 — Stripe mode/keys + recent events
import founder_analytics           # v43 — founder analytics aggregator
import model_router                 # v44 — multi-model router
import local_model_runtime          # v45 — on-device inference runtime
import memory_vault                 # v46 — local encrypted KV store
import threads_vault                # v47 — threaded interactions
import projects_vault               # v51 — project layer
import problem_solver               # v76 — ProblemSolver.REGRESSION_FIRST
import entitlement_view             # v83 — entitlement projection over v30/v31/v42 stores
from el_ins import timeline as el_ins_timeline   # v78 — Regression-First timeline events

# google-cloud-storage is imported lazily-tolerant: if the package is
# missing the rest of the app still boots; only /library calls fail.
try:
    from google.cloud import storage as gcs_storage
    from google.api_core import exceptions as gcs_exceptions
except Exception:  # pragma: no cover
    gcs_storage = None
    gcs_exceptions = None


# ===========================================================================
# Logging
# ===========================================================================
logging.basicConfig(
    level=os.environ.get("CLARITYOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("clarityos")


# PASS-4 FIX-P5 — Local helpers ``_session_ref`` / ``_user_ref`` are
# thin aliases over ``runtime_privacy``. Existing call sites in this
# module keep their familiar names; the centralised helpers are the
# single source of truth for redaction shape across the runtime.
import runtime_privacy as _privacy

_session_ref = _privacy.session_ref
_user_ref = _privacy.user_ref


# ===========================================================================
# App + config
# ===========================================================================
app = FastAPI(title="ClarityOS Cloud", version="2.4")

# ----- ACCEPTANCE: harness dashboard router (additive, no existing routes touched) -----
# Mounts /founder/acceptance/* endpoints used by the acceptance harness
# and the FounderAcceptance web route. Defined in acceptance_dashboard.py
# at repo root.
try:
    from acceptance_dashboard import acceptance_router  # noqa: E402
    app.include_router(acceptance_router)
except ImportError:
    # Acceptance dashboard is optional at boot — the rest of app.py
    # continues without it if the module is absent.
    pass
# Phase 6B / 7C — also mount /founder/analytics/* and /founder/telemetry
# from the same module. Each in its own try/except so a missing module
# does not block the others.
try:
    from acceptance_dashboard import analytics_router  # noqa: E402
    app.include_router(analytics_router)
except ImportError:
    pass
try:
    from acceptance_dashboard import telemetry_router  # noqa: E402
    app.include_router(telemetry_router)
except ImportError:
    pass
# Phase 8B / 9C — additional routers from the same module: identity
# and console. Each in its own try/except so a missing router does
# not block the others.
try:
    from acceptance_dashboard import identity_router  # noqa: E402
    app.include_router(identity_router)
except ImportError:
    pass
try:
    from acceptance_dashboard import console_router  # noqa: E402
    app.include_router(console_router)
except ImportError:
    pass
try:
    from acceptance_dashboard import surfaces_router  # noqa: E402
    app.include_router(surfaces_router)
except ImportError:
    pass
try:
    from acceptance_dashboard import operator_router  # noqa: E402
    app.include_router(operator_router)
except ImportError:
    pass
try:
    from acceptance_dashboard import launch_router  # noqa: E402
    app.include_router(launch_router)
except ImportError:
    pass
# ----- /ACCEPTANCE -----

# ----- v60 / Unit 41 — HTTP runtime surface -----
# Exposes POST /operator/session/start and /step, wrapping the Unit 40
# session_loop façade. No persistence — clients own session_state. Same
# try/except pattern as the acceptance routers so a missing module does
# not block boot.
try:
    from runtime_http import runtime_router  # noqa: E402
    app.include_router(runtime_router)
except ImportError:
    pass
# ----- /v60 -----

# ----- v63 / Units 47 + 48 — Session history + vault inspector -----
# Read-only endpoints under /operator/* (sessions list + vault).
# Session-detail endpoint lives on runtime_router via /operator/session/{id}.
try:
    from runtime_http import operator_router  # noqa: E402
    app.include_router(operator_router)
except ImportError:
    pass
# ----- /v63 -----

# ----- v65 / Unit 69 — Provider health dashboard -----
# Mounts /runtime/providers/health under its own router. Auth-gated
# (require_operator). Same try/except pattern as the others.
try:
    from runtime_http import providers_router  # noqa: E402
    app.include_router(providers_router)
except ImportError:
    pass
# ----- /v65 -----

# ----- v69 / Unit 74 — EL/INS reasoning-stability operator -----
# Mounts POST /el_ins/analyze + GET /el_ins/{recent, thread/{tid}, macro}
# under their own router. Auth-gated via require_operator.
try:
    from runtime_http import el_ins_router  # noqa: E402
    app.include_router(el_ins_router)
except ImportError:
    pass
# ----- /v69 -----

# ----- v73 / Units 82+83 — Operator + Org timelines -----
# Operator timeline: auth-gated, top-level /timeline/*.
# Org timeline: founder-cohort gated, /org/timeline/*.
try:
    from runtime_http import timeline_router, org_timeline_router  # noqa: E402
    app.include_router(timeline_router)
    app.include_router(org_timeline_router)
except ImportError:
    pass
# ----- /v73 -----

SESSION_TTL_SECONDS = int(os.environ.get("CLARITYOS_SESSION_TTL", "86400"))
LIBRARY_BUCKET = os.environ.get("CLARITYOS_LIBRARY_BUCKET", "clarityos-library")
LIBRARY_PREFIX = os.environ.get("CLARITYOS_LIBRARY_PREFIX", "")
BACKEND = os.environ.get("CLARITYOS_BACKEND", "memory").lower()

# Terrace + invite config
TERRACE_1_CAP = int(os.environ.get("CLARITYOS_TERRACE_1_CAP", "500"))
INVITE_BASE_URL = os.environ.get(
    "CLARITYOS_INVITE_BASE_URL",
    "https://clarityos.app",  # frontend host; abstracted so we can swap later
)
INVITE_DEFAULT_TTL_DAYS = int(os.environ.get("CLARITYOS_INVITE_TTL_DAYS", "7"))
INVITE_ONLY = os.environ.get("CLARITYOS_INVITE_ONLY", "false").lower() == "true"
ADMIN_USER = os.environ.get("CLARITYOS_ADMIN_USER", "admin")
COHORT_FOUNDER = "founder"
COHORT_FOUNDER_EXCEPTION = "founder_exception"
COHORT_TERRACE_1 = "terrace_1"
VALID_COHORTS = {COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION, COHORT_TERRACE_1}

# Storage Layer v1 — per-object envelope sizes (bytes)
VAULT_ENVELOPE_BYTES = 256 * 1024
LIBRARY_ENVELOPE_BYTES = 128 * 1024
TIMELINE_ENVELOPE_BYTES = 32 * 1024

# Vault accepts these `type` values. "elins_raw" is added so /elins/ingest/raw
# can write through the same code path as user-direct vault writes.
ALLOWED_VAULT_TYPES = ("note", "session", "elins_raw")

# Storage Layer v1 — per-user quota ceilings (bytes). Founders/operators get
# the higher cap; everyone else (terrace_1, free, registered-no-cohort) gets
# the lower one. Generous on purpose — this revision is "high ceilings, no
# tight limits" per spec; tighter tiers can ride on top later.
QUOTA_FOUNDER_BYTES = 1_000_000_000   # 1 GB
QUOTA_DEFAULT_BYTES = 500_000_000     # 500 MB
FOUNDER_LIKE_COHORTS = {COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION}
THIRTY_DAYS_SECONDS = 30 * 24 * 60 * 60

# CORS — comma-separated list of allowed origins. Browsers will refuse to
# call the API from any origin not on this list. Empty entries are dropped
# so a stray comma in the env var doesn't accidentally permit "" (== same-
# origin), and trailing whitespace is stripped.
_CORS_DEFAULT = "https://pro-mediations.com,https://www.pro-mediations.com,https://clarity.pro-mediations.com"
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CLARITYOS_CORS_ORIGINS", _CORS_DEFAULT).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-ID", "Authorization"],
)


# ===========================================================================
# User / session helpers (delegate to users_store + sessions_store)
# ===========================================================================
def _create_user(
    username: str,
    password: str,
    tier: str = "free",
    cohort: Optional[str] = None,
    operator_id: Optional[str] = None,
    billing_expires_at: Optional[float] = None,
    billing_subscription_id: Optional[str] = None,
) -> None:
    """Hash with bcrypt and persist to whichever backend is configured.

    Cohort + operator envelope fields are written via update_user after
    create_user so the existing memory/Firestore schema in users_store
    stays untouched (Firestore happily takes new fields; memory does too).
    """
    pwd_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    users_store.create_user(
        username=username,
        password_hash=pwd_hash,
        salt="",  # bcrypt embeds salt in the hash; field reserved for future schemes
        tier=tier,
        created_at=time.time(),
    )
    extras: dict = {}
    if cohort is not None:
        extras["cohort"] = cohort
    if operator_id is not None:
        extras["operator_id"] = operator_id
    if billing_expires_at is not None:
        extras["billing_expires_at"] = billing_expires_at
    if billing_subscription_id is not None:
        extras["billing_subscription_id"] = billing_subscription_id
    if extras:
        users_store.update_user(username, extras)


def _new_operator_id() -> str:
    return "op_" + secrets.token_urlsafe(12)


def _bootstrap_admin() -> str:
    """
    Seed admin user. Returns one of:
        'env'        — created with password from env var
        'generated'  — created with a random password printed once to stdout
                       (LEGACY — only when CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED is not "true")
        'existing'   — admin already present in the store (firestore re-deploy case)

    FIX-C1: when CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED is "true", refuse to boot
    without CLARITYOS_ADMIN_PASSWORD. This closes the bootstrap-password-to-Cloud-
    Logging privacy gap (PASS-3D G-P6 / PASS-4 FIX-C1). The legacy random-
    generation + print path is preserved behind the flag for transition.
    """
    user = os.environ.get("CLARITYOS_ADMIN_USER", "admin")

    # If admin already exists (typical on Firestore restart), don't re-create —
    # but make sure the cohort tag is set on every boot, so an admin that
    # predates the invite system gets upgraded to "founder".
    if users_store.user_exists(user):
        existing = users_store.get_user(user) or {}
        if existing.get("cohort") != COHORT_FOUNDER:
            users_store.update_user(user, {
                "cohort": COHORT_FOUNDER,
                "operator_id": existing.get("operator_id") or _new_operator_id(),
            })
        return "existing"

    required = (
        os.environ.get("CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED") or ""
    ).strip().lower() == "true"
    pwd = os.environ.get("CLARITYOS_ADMIN_PASSWORD")

    if required:
        # FIX-C1: mandatory password. Refuse to generate or print anything.
        if not pwd:
            raise RuntimeError(
                "CLARITYOS_ADMIN_PASSWORD is required for admin bootstrap; "
                "refusing to generate or print a bootstrap password."
            )
        source = "env"
    elif pwd:
        source = "env"
    else:
        # LEGACY path — preserved until CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED
        # is flipped to "true" globally. Generates a random password and prints
        # it once to stdout. Captured by Cloud Run stdout → Cloud Logging in
        # production; deployments that care about that must set the required
        # flag and provide CLARITYOS_ADMIN_PASSWORD.
        pwd = secrets.token_urlsafe(12)
        source = "generated"
        bar = "=" * 64
        print(bar, flush=True)
        print(" ClarityOS bootstrap admin (lost on restart unless Firestore enabled)", flush=True)
        print(f"   username: {user}", flush=True)
        print(f"   password: {pwd}", flush=True)
        print(" Set CLARITYOS_ADMIN_USER / CLARITYOS_ADMIN_PASSWORD to override.", flush=True)
        print(bar, flush=True)
    _create_user(user, pwd, cohort=COHORT_FOUNDER, operator_id=_new_operator_id())
    return source


_admin_pwd_source = _bootstrap_admin()

# v29 — Cohort 1 default flag overrides. Founders + Terrace 1 see v28
# surfaces by default; everyone else stays default-off until a server-side
# operator toggles them on per-user. Idempotent on every process boot.
for _coh in (COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION, COHORT_TERRACE_1):
    v29_hardening.set_flag("v28_surfaces", True, cohort=_coh)
    v29_hardening.set_flag("onboarding_v1", True, cohort=_coh)
    v29_hardening.set_flag("whats_new_v28", True, cohort=_coh)

# v30 — register flags + cohort-default enables. The Founders cohort gets
# the founding tier offer + g-credits + the membership UI; Terrace 1 gets
# the membership UI but the founding-tier offer is conditional on cap.
v29_hardening._DEFAULT_FLAGS.setdefault("founder_tier_enabled", False)
v29_hardening._DEFAULT_FLAGS.setdefault("g_credits_enabled", False)
v29_hardening._DEFAULT_FLAGS.setdefault("membership_ui_enabled", False)
for _coh in (COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION):
    v29_hardening.set_flag("founder_tier_enabled", True, cohort=_coh)
    v29_hardening.set_flag("g_credits_enabled", True, cohort=_coh)
    v29_hardening.set_flag("membership_ui_enabled", True, cohort=_coh)
v29_hardening.set_flag("g_credits_enabled", True, cohort=COHORT_TERRACE_1)
v29_hardening.set_flag("membership_ui_enabled", True, cohort=COHORT_TERRACE_1)

# Startup configuration log line (no secrets).
logger.info(
    "startup config backend=%s admin_user=%s admin_pwd_source=%s "
    "library_bucket=%s library_prefix=%r session_ttl=%ds gcs_available=%s "
    "cors_origins=%s",
    BACKEND,
    _user_ref(os.environ.get("CLARITYOS_ADMIN_USER", "admin")),
    _admin_pwd_source,
    LIBRARY_BUCKET,
    LIBRARY_PREFIX,
    SESSION_TTL_SECONDS,
    gcs_storage is not None,
    CORS_ORIGINS,
)

# v36 — Macro-ELINS scheduler boot. The scheduler is opt-in via the
# config store; if a previous founder turned it on, we relight the
# daemon thread. Tests force CLARITYOS_DISABLE_MACRO_SCHEDULER=1 to
# keep boot quiet.
if os.environ.get("CLARITYOS_DISABLE_MACRO_SCHEDULER", "0") != "1":
    try:
        _macro_cfg = elins_scheduler_config.get_config()
        if _macro_cfg.get("enabled"):
            elins_scheduler.start_elins_scheduler()
            logger.info(
                "macro elins scheduler boot enabled cadence=%s mode=%s",
                _macro_cfg.get("cadence"), _macro_cfg.get("external_signal_mode"),
            )
    except Exception as _e:  # pragma: no cover (defensive)
        logger.warning("macro scheduler boot skipped err=%s", _e)


# ===========================================================================
# Mobile-safe response envelope
# ===========================================================================
def ok_response(engine: str, data: dict, **extra) -> dict:
    payload = {"ok": True, "engine": engine, "data": data}
    payload.update(extra)
    return payload


def error_response(error: str, message: str) -> dict:
    return {"ok": False, "error": error, "message": message}


@app.exception_handler(HTTPException)
async def _envelope_http_exception_handler(_request: Request, exc: HTTPException):
    """Unwrap detail=envelope so mobile clients see {ok:false,...} at top level."""
    if isinstance(exc.detail, dict) and "ok" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response("http_error", str(exc.detail)),
    )


# ===========================================================================
# Session middleware (FastAPI dependency)
# ===========================================================================
def require_session(x_session_id: Optional[str] = Header(default=None)) -> dict:
    """Validate X-Session-ID header. Raises 401 on missing/invalid/expired."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("missing_session", "X-Session-ID header required"),
        )
    session = sessions_store.get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("invalid_session", "Unknown session id"),
        )
    if session["expires_at"] < time.time():
        sessions_store.delete_session(x_session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("expired_session", "Session expired; log in again"),
        )
    # v29 — surface cohort to consumers (feature flags, audit logs).
    cohort: Optional[str] = None
    try:
        u = users_store.get_user(session["user"]) or {}
        cohort = u.get("cohort")
    except Exception:  # pragma: no cover — defensive against backend hiccups
        cohort = None
    return {"session_id": x_session_id, "user": session["user"], "cohort": cohort}


# ===========================================================================
# GCS library access
# ===========================================================================
_gcs_client: Optional["gcs_storage.Client"] = None


def _get_gcs_client():
    """Lazy-init the GCS client with default credentials (Cloud Run service account or local ADC)."""
    global _gcs_client
    if _gcs_client is not None:
        return _gcs_client
    if gcs_storage is None:
        raise HTTPException(
            status_code=500,
            detail=error_response(
                "gcs_unavailable",
                "google-cloud-storage is not installed; pip install -r requirements.txt",
            ),
        )
    try:
        _gcs_client = gcs_storage.Client()
    except Exception as e:
        logger.exception("gcs client init failed")
        raise HTTPException(
            status_code=500,
            detail=error_response(
                "gcs_init_error",
                f"Could not initialise GCS client: {e}. "
                "On Cloud Run, attach a service account with Storage Object Viewer. "
                "Locally, run `gcloud auth application-default login`.",
            ),
        )
    return _gcs_client


def load_library_object(path: str) -> str:
    """
    Fetch a single object from gs://CLARITYOS_LIBRARY_BUCKET/CLARITYOS_LIBRARY_PREFIX/path
    and return its decoded text contents. Raises 404 if missing, 502 on other errors.
    """
    if not path or path.strip() == "":
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_path", "Library path is required"),
        )
    # Build full object key; normalise slashes so prefix and path join cleanly.
    key = f"{LIBRARY_PREFIX.strip('/')}/{path.lstrip('/')}".lstrip("/")
    logger.info("library fetch bucket=%s key=%s", LIBRARY_BUCKET, key)
    client = _get_gcs_client()
    try:
        bucket = client.bucket(LIBRARY_BUCKET)
        blob = bucket.blob(key)
        if not blob.exists(client):
            raise HTTPException(
                status_code=404,
                detail=error_response("not_found", "Library entry not found"),
            )
        data = blob.download_as_bytes()
    except HTTPException:
        raise
    except Exception as e:
        if gcs_exceptions and isinstance(e, gcs_exceptions.NotFound):
            raise HTTPException(
                status_code=404,
                detail=error_response("not_found", "Library entry not found"),
            )
        logger.exception("library fetch failed key=%s", key)
        raise HTTPException(
            status_code=502,
            detail=error_response("gcs_error", f"GCS read failed: {e}"),
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        # Binary blob — return base64 so it's still mobile-safe JSON.
        import base64
        return "base64:" + base64.b64encode(data).decode("ascii")


# ===========================================================================
# Engine adapters  (replace bodies with real engines; keep signatures)
# Each adapter takes (text, meta, user) where user is the username string,
# logs adapter timing, and wraps unexpected errors in the envelope.
# ===========================================================================

def _timed(adapter_name: str, fn, *args, **kwargs):
    """Run adapter fn, log execution time, convert unexpected errors to envelope."""
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("adapter %s failed", adapter_name)
        raise HTTPException(
            status_code=500,
            detail=error_response("engine_error", str(e)),
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    logger.info("adapter %s ok elapsed_ms=%.1f", adapter_name, elapsed_ms)
    return result


def markov_adapter(text: str, meta: dict | None, user: str) -> dict:
    length = len(text.strip())
    tags: list[str] = []
    if "?" in text:
        tags.append("question")
    if "!" in text:
        tags.append("emphasis")
    if length > 120:
        tags.append("long")
    return {
        "score": min(1.0, length / 200.0),
        "tags": tags,
        "interpretation": f"(markov-stub) {text[:200]}",
        "user": user,
    }


def galileo_adapter(text: str, meta: dict | None, user: str) -> dict:
    length = len(text.strip())
    if length > 200:
        clarity_level = 3
    elif length > 80:
        clarity_level = 2
    else:
        clarity_level = 1
    return {
        "clarity_level": clarity_level,
        "summary": f"(galileo-stub) {text[:200]}",
        "mode": (meta or {}).get("mode", "conversational"),
        "user": user,
    }


def library_adapter(text: str, meta: dict | None, user: str) -> dict:
    """
    `text` is the library path within CLARITYOS_LIBRARY_PREFIX.
    `meta.path` overrides `text` if both are provided.
    """
    path = (meta or {}).get("path") or text
    content = load_library_object(path)
    return {
        "path": path,
        "bucket": LIBRARY_BUCKET,
        "prefix": LIBRARY_PREFIX,
        "size": len(content),
        "content": content,
        "user": user,
    }


def tizzy_adapter(text: str, meta: dict | None, user: str) -> dict:
    return {
        "input": text,
        "result": f"tizzy-stub: {text}",
        "user": user,
        "note": "stub — define Tizzy engine logic and replace this body",
    }


# ===========================================================================
# Request models
# ===========================================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class EngineRequest(BaseModel):
    text: str
    meta: Optional[dict] = None


# ===========================================================================
# Auth routes
# ===========================================================================
@app.post("/login")
def login(req: LoginRequest):
    user = users_store.get_user(req.username)
    if not user or not bcrypt.checkpw(
        req.password.encode("utf-8"), user["password_hash"]
    ):
        logger.warning("login failed username=%s", req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("bad_credentials", "Username or password is incorrect"),
        )
    session_id = secrets.token_urlsafe(32)
    sessions_store.create_session(
        session_id=session_id,
        username=req.username,
        expires_at=time.time() + SESSION_TTL_SECONDS,
    )
    logger.info(
        "login ok user=%s session=%s",
        _user_ref(req.username), _session_ref(session_id),
    )
    return {
        "ok": True,
        "session_id": session_id,
        "expires_in": SESSION_TTL_SECONDS,
        "user": req.username,
    }


@app.post("/register")
def register(req: RegisterRequest):
    """
    Create a new user and auto-login.

    Returns the same envelope as /login so a freshly-registered client can
    immediately call protected routes with the returned session_id.

    When CLARITYOS_INVITE_ONLY=true, this endpoint is locked — clients must
    use /invite/{token}/redeem (founder_exception) or
    /invite/{token}/finalize (terrace_1) instead.
    """
    if INVITE_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(
                "invite_required",
                "Open registration is disabled. An invite token is required.",
            ),
        )
    username = req.username
    password = req.password

    # Validate username
    if not username or len(username) < 3 or len(username) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_username", "Username must be 3-64 characters"),
        )
    if any(c.isspace() for c in username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_username", "Username cannot contain whitespace"),
        )
    # Validate password
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_password", "Password must be at least 8 characters"),
        )

    # Duplicate-username protection
    if users_store.user_exists(username):
        logger.warning("register duplicate username=%s", username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response("user_exists", "Username is already taken"),
        )

    # Create user (reuses the same bcrypt path as the admin bootstrap)
    _create_user(username, password)

    # Auto-login: create a session using the same pattern as /login
    session_id = secrets.token_urlsafe(32)
    sessions_store.create_session(
        session_id=session_id,
        username=username,
        expires_at=time.time() + SESSION_TTL_SECONDS,
    )
    logger.info(
        "register ok user=%s session=%s",
        _user_ref(username), _session_ref(session_id),
    )
    return {
        "ok": True,
        "session_id": session_id,
        "expires_in": SESSION_TTL_SECONDS,
        "user": username,
    }


# ===========================================================================
# Invite + billing — Terrace-1 onboarding
# ===========================================================================
def _validate_credentials(username: str, password: str) -> None:
    if not username or len(username) < 3 or len(username) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_username", "Username must be 3-64 characters"),
        )
    if any(c.isspace() for c in username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_username", "Username cannot contain whitespace"),
        )
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_password", "Password must be at least 8 characters"),
        )


def _require_admin(session: dict = Depends(require_session)) -> dict:
    if session["user"] != ADMIN_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response("forbidden", "Admin only"),
        )
    return session


def _require_founder(session: dict = Depends(require_session)) -> dict:
    """Cohort-based gate. Distinct from _require_admin (which checks the
    bootstrap admin username). Used by the ELINS ingest routes."""
    user_doc = users_store.get_user(session["user"]) or {}
    if user_doc.get("cohort") not in FOUNDER_LIKE_COHORTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response("forbidden", "Founder cohort required"),
        )
    return session


def _verify_invite_token(token: str) -> dict:
    payload = invite_tokens.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("invalid_token", "Invite token is invalid or expired"),
        )
    invite_id = payload.get("sub")
    if not invite_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("malformed_token", "Token missing invite id"),
        )
    invite = invites_store.get_invite(invite_id)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("invite_not_found", "Invite does not exist"),
        )
    if invite.get("status") == "used":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response("already_used", "Invite has already been redeemed"),
        )
    if invite.get("expires_at", 0) < time.time():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=error_response("expired", "Invite has expired"),
        )
    return invite


def _create_session_for(username: str) -> dict:
    session_id = secrets.token_urlsafe(32)
    sessions_store.create_session(
        session_id=session_id,
        username=username,
        expires_at=time.time() + SESSION_TTL_SECONDS,
    )
    return {
        "ok": True,
        "session_id": session_id,
        "expires_in": SESSION_TTL_SECONDS,
        "user": username,
    }


class CreateInviteRequest(BaseModel):
    cohort: str  # "founder_exception" | "terrace_1"
    expires_in_days: Optional[int] = None


class RedeemFreeRequest(BaseModel):
    username: str
    password: str


class CheckoutRequest(BaseModel):
    username: str
    password: str
    plan: str  # "onetime" | "recurring"


class FinalizeRequest(BaseModel):
    session_id: str  # Stripe Checkout Session ID
    username: str
    password: str


@app.post("/invite/create")
def invite_create(req: CreateInviteRequest, session: dict = Depends(_require_admin)):
    """Admin-only. Creates a single-use invite token + Firestore record."""
    cohort = req.cohort
    if cohort not in (COHORT_FOUNDER_EXCEPTION, COHORT_TERRACE_1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_cohort", f"cohort must be one of: founder_exception, terrace_1"),
        )

    # Enforce Terrace-1 cap (counts redeemed only — unused invites don't count
    # against the cap until they're used, so the admin can pre-mint).
    if cohort == COHORT_TERRACE_1:
        redeemed = invites_store.count_redeemed(COHORT_TERRACE_1)
        if redeemed >= TERRACE_1_CAP:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_response(
                    "terrace_full",
                    f"Terrace-1 is full ({redeemed}/{TERRACE_1_CAP} seats redeemed)",
                ),
            )
        price = 50
        billing_required = True
    else:
        price = 0
        billing_required = False

    ttl_days = req.expires_in_days or INVITE_DEFAULT_TTL_DAYS
    expires_at = time.time() + ttl_days * 24 * 60 * 60
    invite_id = invites_store.new_invite_id()
    invites_store.create_invite(
        invite_id=invite_id,
        cohort=cohort,
        price=price,
        billing_required=billing_required,
        inviter=session["user"],
        expires_at=expires_at,
    )
    token = invite_tokens.sign_token({
        "sub": invite_id,
        "inviter_id": session["user"],
        "cohort": cohort,
        "price": price,
        "billing_required": billing_required,
        "max_uses": 1,
        "exp": int(expires_at),
    })
    url = f"{INVITE_BASE_URL.rstrip('/')}/invite/{token}"
    logger.info("invite created cohort=%s inviter=%s id=%s", cohort, session["user"], invite_id)
    return {
        "ok": True,
        "invite_id": invite_id,
        "token": token,
        "url": url,
        "cohort": cohort,
        "price": price,
        "billing_required": billing_required,
        "expires_at": expires_at,
    }


class AdminResetPasswordRequest(BaseModel):
    username: str
    new_password: str


@app.post("/admin/reset_password")
def admin_reset_password(
    req: AdminResetPasswordRequest,
    session: dict = Depends(_require_admin),
):
    """Admin-only. Replace a user's password hash with a fresh bcrypt hash
    of `new_password`. Returns 404 if the user does not exist. Existing
    sessions for the target user are NOT revoked by this call."""
    _validate_credentials(req.username, req.new_password)
    if not users_store.user_exists(req.username):
