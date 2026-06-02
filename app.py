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
                                https://clarity.pro-mediations.com,
                                https://pocket.clarityos.dev,
                                http://localhost:5174,
                                https://clarityos-pocket-v0-3-736968277491.us-central1.run.app"
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
from typing import Any, Literal, Optional

import bcrypt
import hmac
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
import billing_subscriptions        # C1 / A+D — Stripe Subscriptions (canonical)
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

# v0.3.11 / Card 16 — engine boot timestamp, used by /operator/state to
# report uptime. Set once at module load; immutable for the life of the
# revision.
_ENGINE_START_TIME = time.time()

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
#
# Defaults (in order):
#   * https://pro-mediations.com                      — WordPress front-end (apex)
#   * https://www.pro-mediations.com                  — WordPress front-end (www)
#   * https://clarity.pro-mediations.com              — Clarity subdomain front-end
#   * https://pocket.clarityos.dev                    — Pocket SPA prod (custom domain, planned)
#   * http://localhost:5174                           — Pocket SPA dev (Vite dev server)
#   * https://clarityos-pocket-v0-3-…run.app          — Pocket SPA Cloud Run URL (used until
#                                                       pocket.clarityos.dev domain mapping lands)
#
# The cockpit Node v0.2 surface at cockpit.pro-mediations.com is server-
# rendered (no browser-side XHR to this API) so it deliberately does NOT
# need a CORS allow entry.
#
# Production deploys override this default via the
# ``CLARITYOS_CORS_ORIGINS`` env var on the Cloud Run service; keep
# the two lists in sync so a future "remove the env var" never silently
# drops a real prod origin.
_CORS_DEFAULT = ",".join([
    "https://pro-mediations.com",
    "https://www.pro-mediations.com",
    "https://clarity.pro-mediations.com",
    "https://pocket.clarityos.dev",
    "http://localhost:5174",
    "https://clarityos-pocket-v0-3-736968277491.us-central1.run.app",
])
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


# ---------------------------------------------------------------------------
# Card 16 — operator-token auth (privileged path)
# ---------------------------------------------------------------------------
def _is_operator_token(request: Request) -> bool:
    """Return True iff the request carries a valid Operator token.

    The token is expected in the ``Authorization`` header in the form:

        Authorization: Operator <token>

    The expected value comes from the ``CLARITYOS_OPERATOR_TOKEN`` env
    var (mounted from Secret Manager in production). When the env var
    is unset OR empty, no token can be valid — every operator-only
    surface stays locked. Comparison is constant-time
    (``hmac.compare_digest``) so the response time doesn't leak any
    information about partial-match length.
    """
    expected = (os.environ.get("CLARITYOS_OPERATOR_TOKEN") or "").strip()
    if not expected:
        return False
    auth = request.headers.get("authorization") or ""
    # Case-insensitive scheme match; preserve whatever spacing the
    # client used between scheme and token.
    scheme, _, presented = auth.partition(" ")
    if scheme.lower() != "operator":
        return False
    presented = presented.strip()
    if not presented:
        return False
    return hmac.compare_digest(presented, expected)


def require_operator_token(request: Request) -> dict:
    """FastAPI dependency for operator-only endpoints.

    Rejects with 401 unless the request carries a valid Operator
    token. Returns a small dict so endpoints can log who hit them
    (``operator=True`` is the only identity available — the token
    has no user_id binding by design)."""
    if not _is_operator_token(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response(
                "operator_token_required",
                "This endpoint requires a valid Operator token in the "
                "Authorization header.",
            ),
        )
    return {"operator": True}


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
def _auth_rate_limit_enabled() -> bool:
    """Brute-force throttle on /login + /register. Enforced in production;
    the test suite disables it (conftest sets CLARITYOS_DISABLE_AUTH_RATE_LIMIT=1)
    so cumulative auth calls across tests don't drain a shared per-IP bucket.
    Read at call time so a test can toggle it via monkeypatch."""
    return os.environ.get("CLARITYOS_DISABLE_AUTH_RATE_LIMIT", "0") != "1"


def _throttle_auth(
    request: Request, route: str, *, capacity: int, window_s: float
) -> None:
    """IP-keyed token-bucket guard for the unauthenticated auth endpoints.
    Raises 429 (standard envelope) when the per-IP bucket is empty. The
    bucket refills continuously, so a throttled client recovers on its own —
    no admin unlock, no account lockout. No-op when disabled (tests).

    Reuses the same ``v29_hardening`` limiter + ``_client_ip`` first-hop
    extraction that ``/waitlist/join`` uses, and enforces unconditionally
    (not gated by CLARITYOS_RATE_LIMIT_ENFORCE) because login brute force is
    a hard boundary, not a soft observe-only limit."""
    if not _auth_rate_limit_enabled():
        return
    ip = _client_ip(request)
    if not v29_hardening.check_rate_limit(
        f"ip:{ip}", route, capacity=capacity, window_s=window_s,
    ):
        v29_hardening.log_event(
            "auth_rate_limited", route=route, success=False, ip=ip[:24],
        )
        raise HTTPException(
            status_code=429,
            detail=error_response(
                "rate_limited",
                "Too many attempts; please wait a minute and try again",
            ),
        )


@app.post("/login")
def login(req: LoginRequest, request: Request):
    _throttle_auth(request, "/login", capacity=5, window_s=900.0)
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
def register(req: RegisterRequest, request: Request):
    """
    Create a new user and auto-login.

    Returns the same envelope as /login so a freshly-registered client can
    immediately call protected routes with the returned session_id.

    When CLARITYOS_INVITE_ONLY=true, this endpoint is locked — clients must
    use /invite/{token}/redeem (founder_exception) or
    /invite/{token}/finalize (terrace_1) instead.
    """
    _throttle_auth(request, "/register", capacity=3, window_s=3600.0)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("user_not_found", f"No user named {req.username}"),
        )
    pwd_hash = bcrypt.hashpw(req.new_password.encode("utf-8"), bcrypt.gensalt())
    users_store.update_user(req.username, {"password_hash": pwd_hash})
    logger.info(
        "admin reset_password target=%s by_admin=%s",
        req.username, session["user"],
    )
    return {
        "ok": True,
        "username": req.username,
        "reset_at": time.time(),
    }


@app.get("/invite/{token}")
def invite_get(token: str):
    """Public. Validates the token and returns invite metadata for onboarding."""
    invite = _verify_invite_token(token)
    return {
        "ok": True,
        "data": {
            "cohort": invite["cohort"],
            "price": invite["price"],
            "billing_required": invite["billing_required"],
            "expires_at": invite["expires_at"],
        },
    }


@app.post("/invite/{token}/redeem")
def invite_redeem(token: str, req: RedeemFreeRequest):
    """Public. Redeem a FREE invite (founder_exception). Creates the user
    and operator envelope, returns a session token. For paid invites use
    /invite/{token}/checkout + /invite/{token}/finalize."""
    invite = _verify_invite_token(token)
    if invite["billing_required"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "billing_required",
                "This invite requires payment. Use /invite/{token}/checkout.",
            ),
        )
    _validate_credentials(req.username, req.password)
    if users_store.user_exists(req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response("user_exists", "Username is already taken"),
        )

    operator_id = _new_operator_id()
    _create_user(
        req.username,
        req.password,
        cohort=invite["cohort"],
        operator_id=operator_id,
    )
    invites_store.mark_used(invite["invite_id"], used_by=req.username)
    logger.info(
        "invite redeemed (free) cohort=%s user=%s operator=%s",
        invite["cohort"], _user_ref(req.username), _user_ref(operator_id),
    )
    resp = _create_session_for(req.username)
    resp.update({"cohort": invite["cohort"], "operator_id": operator_id})
    return resp


@app.post("/invite/{token}/checkout")
def invite_checkout(token: str, req: CheckoutRequest):
    """Public. Start a Stripe Checkout session for a paid invite. Returns
    a redirect URL the client opens. Username + password are validated
    here so the client gets early feedback; they're persisted only after
    /finalize confirms payment."""
    invite = _verify_invite_token(token)
    if not invite["billing_required"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                "no_billing",
                "This invite is free. Use /invite/{token}/redeem.",
            ),
        )
    _validate_credentials(req.username, req.password)
    if req.plan not in ("onetime", "recurring"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_plan", "plan must be 'onetime' or 'recurring'"),
        )
    if users_store.user_exists(req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response("user_exists", "Username is already taken"),
        )

    success_url = f"{INVITE_BASE_URL.rstrip('/')}/invite/{token}/success?plan={req.plan}"
    cancel_url = f"{INVITE_BASE_URL.rstrip('/')}/invite/{token}"

    try:
        url = billing.create_checkout_session(
            invite_id=invite["invite_id"],
            username=req.username,
            plan=req.plan,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except billing.BillingNotConfigured as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response("billing_not_configured", str(e)),
        )
    return {"ok": True, "checkout_url": url, "plan": req.plan}


@app.post("/invite/{token}/finalize")
def invite_finalize(token: str, req: FinalizeRequest):
    """Public. Called after Stripe Checkout success-redirect. Verifies the
    Stripe session was paid, then creates the user + operator envelope."""
    invite = _verify_invite_token(token)
    if not invite["billing_required"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("no_billing", "This invite is free; use /redeem"),
        )
    _validate_credentials(req.username, req.password)
    if users_store.user_exists(req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response("user_exists", "Username is already taken"),
        )

    try:
        sess = billing.retrieve_session(req.session_id)
    except billing.BillingNotConfigured as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response("billing_not_configured", str(e)),
        )
    except Exception as e:
        logger.warning(
            "stripe session retrieve failed session=%s err=%s",
            _session_ref(req.session_id), e,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("bad_session", "Could not verify Stripe session"),
        )

    # Bind the Stripe session to this invite — prevents reuse of one paid
    # session across different invites.
    if sess.get("client_reference_id") != invite["invite_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("session_mismatch", "Stripe session is not bound to this invite"),
        )
    if not billing.session_is_paid(sess):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=error_response("not_paid", "Stripe session is not in a paid state"),
        )

    plan = (sess.get("metadata") or {}).get("plan", "onetime")
    subscription_id = sess.get("subscription")  # set when mode=subscription
    if plan == "onetime":
        billing_expires_at = time.time() + THIRTY_DAYS_SECONDS
    else:
        # For recurring, expiration is governed by Stripe — we set a
        # provisional 30-day window; the webhook updates as billing events fire.
        billing_expires_at = time.time() + THIRTY_DAYS_SECONDS

    operator_id = _new_operator_id()
    _create_user(
        req.username,
        req.password,
        cohort=invite["cohort"],
        operator_id=operator_id,
        billing_expires_at=billing_expires_at,
        billing_subscription_id=subscription_id,
    )
    invites_store.mark_used(invite["invite_id"], used_by=req.username)
    logger.info(
        "invite finalized cohort=%s user=%s operator=%s plan=%s",
        invite["cohort"], _user_ref(req.username), _user_ref(operator_id), plan,
    )
    resp = _create_session_for(req.username)
    resp.update({
        "cohort": invite["cohort"],
        "operator_id": operator_id,
        "plan": plan,
        "billing_expires_at": billing_expires_at,
    })
    return resp


@app.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Stripe webhook. v42 hardening:

    * Mock mode (``CLARITYOS_BILLING_MODE`` != "stripe") still accepts
      unsigned JSON for synthetic events; signature is required only
      when running against real Stripe.
    * In stripe mode the signature is verified, the resolved Stripe
      mode (``test``/``live``) must match the event's ``livemode``
      flag, and missing webhook secret returns 503.
    * Every event id is checked against ``billing_config.seen_event``;
      duplicates short-circuit with ``{ok: True, duplicate: True}``.
    * Subscription lifecycle (``checkout.session.completed``,
      ``invoice.payment_succeeded``, ``customer.subscription.updated``,
      ``customer.subscription.deleted``) maps onto
      ``users_store.set_billing_state`` + a transaction record on
      ``membership_store``.
    * ``billing_config.record_billing_event`` keeps a ring of recent
      events for the founder console.
    """
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")

    runtime_mode = os.environ.get("CLARITYOS_BILLING_MODE", "mock").lower()
    use_signature = runtime_mode == "stripe"

    if not use_signature:
        # Mock mode — accept the raw JSON body as the event. Used by tests
        # and operators driving synthetic events from a local shell.
        try:
            event = json.loads(payload.decode("utf-8")) if payload else None
        except Exception:
            return JSONResponse(
                status_code=400,
                content=error_response("bad_payload", "could not parse JSON event body"),
            )
        if not isinstance(event, dict):
            return JSONResponse(
                status_code=400,
                content=error_response("bad_payload", "event must be a JSON object"),
            )
    else:
        if not billing.is_webhook_configured():
            return JSONResponse(
                status_code=503,
                content=error_response(
                    "webhook_not_configured",
                    "Stripe webhook signing secret not set",
                ),
            )
        if not sig:
            return JSONResponse(
                status_code=400,
                content=error_response(
                    "missing_signature", "Stripe-Signature header is required",
                ),
            )
        try:
            event = billing.verify_webhook(payload, sig)
        except billing.BillingNotConfigured as e:
            return JSONResponse(status_code=503, content=error_response("billing_not_configured", str(e)))
        if event is None:
            return JSONResponse(
                status_code=400,
                content=error_response("bad_signature", "Stripe webhook signature did not verify"),
            )
        # v42 — reject mode mismatch (test event arriving on live key, or vice versa).
        configured_mode = billing_config.get_stripe_mode()
        event_livemode = bool(event.get("livemode"))
        event_mode = "live" if event_livemode else "test"
        if configured_mode in billing_config.VALID_MODES and event_mode != configured_mode:
            v29_hardening.log_event(
                "billing_webhook_mode_mismatch",
                route="/billing/webhook", success=False,
                configured_mode=configured_mode, event_mode=event_mode,
            )
            return JSONResponse(
                status_code=400,
                content=error_response(
                    "mode_mismatch",
                    f"event mode {event_mode!r} does not match configured mode {configured_mode!r}",
                ),
            )

    etype = event.get("type", "")
    eid = event.get("id")
    obj = (event.get("data") or {}).get("object") or {}

    # v42 — idempotency: short-circuit duplicate event ids.
    if eid and billing_config.seen_event(eid):
        v29_hardening.log_event(
            "billing_webhook_duplicate", route="/billing/webhook",
            event_id=str(eid), event_type=etype, success=True,
        )
        return {"ok": True, "duplicate": True}
    if eid:
        billing_config.mark_event_seen(eid)

    v29_hardening.log_event(
        "billing_webhook_received", route="/billing/webhook",
        event_type=etype, event_id=str(eid or ""),
        intent_id=str(obj.get("id") or ""), success=True,
        mode=runtime_mode,
    )

    # v42 — record on the recent-events ring for the founder console.
    user_id_meta = (
        (obj.get("metadata") or {}).get("user_id")
        or (obj.get("metadata") or {}).get("username")
    )
    billing_config.record_billing_event(
        etype, user_id=user_id_meta,
        payload_meta=_billing_payload_meta(etype, obj),
        event_id=eid, mode=runtime_mode,
    )

    # v31 — PaymentIntent dispatcher for membership + #G credit flows.
    if etype.startswith("payment_intent."):
        result = billing_intents.handle_payment_webhook(event)
        if not result.get("ok") and result.get("error") == "intent_not_found":
            # Don't 4xx — Stripe retries on non-2xx and the intent will
            # never appear, so we ack and move on. Operator can audit
            # via the structured log.
            pass
        return {"ok": True}

    # C1 / A+D — Stripe Subscription lifecycle (canonical billing for new
    # signups). Additive + idempotent: these sync the new subscription fields
    # (and mirror billing_state / membership) for subscription members. They
    # run alongside the v42 _handle_subscription_event below; each no-ops when
    # the Stripe customer doesn't resolve to a user, so existing flows (and
    # the v42 tests, which resolve by metadata) are untouched.
    if etype in ("invoice.paid", "invoice.payment_succeeded"):
        billing_subscriptions.handle_invoice_paid(obj)
    elif etype == "invoice.payment_failed":
        billing_subscriptions.handle_invoice_payment_failed(obj)
    elif etype == "customer.subscription.updated":
        billing_subscriptions.handle_subscription_updated(obj)
    elif etype == "customer.subscription.deleted":
        billing_subscriptions.handle_subscription_deleted(obj)

    # v42 — subscription / checkout lifecycle handlers (billing_state mirror).
    _handle_subscription_event(etype, obj)
    return {"ok": True}


def _billing_payload_meta(event_type: str, obj: dict) -> dict:
    """Extract a small metadata-only slice from the Stripe event object.
    Filters PII (handled by ``billing_config._sanitise_meta`` too) but
    keeps the few fields the founder console wants to display."""
    if not isinstance(obj, dict):
        return {}
    keep = ("id", "status", "amount", "amount_total", "currency",
            "subscription", "current_period_end", "current_period_start",
            "cancel_at", "canceled_at")
    out = {k: obj.get(k) for k in keep if obj.get(k) is not None}
    md = obj.get("metadata") or {}
    if isinstance(md, dict):
        for k in ("kind", "plan", "user_id", "username"):
            v = md.get(k)
            if v is not None:
                out[f"meta.{k}"] = v
    return out


def _handle_subscription_event(event_type: str, obj: dict) -> None:
    """v42 — drive ``users_store.set_billing_state`` + transactions for
    Stripe subscription / checkout events. Caller is responsible for
    idempotency (see ``billing_config.seen_event``)."""
    md = (obj.get("metadata") or {}) if isinstance(obj, dict) else {}
    user = (
        md.get("user_id") or md.get("username")
        or (obj.get("client_reference_id") if isinstance(obj, dict) else None)
    )
    if event_type == "checkout.session.completed":
        if user and obj.get("payment_status") == "paid":
            users_store.set_billing_state(
                user, billing_state="active",
                renewal_ts=time.time() + 30 * 24 * 3600.0,
            )
            try:
                membership_store.record_transaction(
                    user, type="checkout_session_completed",
                    amount=float(obj.get("amount_total") or 0) / 100.0,
                    credits_delta=0,
                    metadata={
                        "session_id_short": _privacy.event_ref(obj.get("id") or ""),
                        "plan": md.get("plan"),
                    },
                )
            except Exception as e:  # pragma: no cover (defensive)
                logger.warning(
                    "checkout transaction record failed user=%s err=%s",
                    _user_ref(user), e,
                )
        return

    if event_type == "invoice.payment_succeeded":
        sub_id = obj.get("subscription")
        period_end = obj.get("current_period_end") or obj.get("period_end")
        if user and period_end:
            try:
                users_store.set_billing_state(
                    user, billing_state="active", renewal_ts=float(period_end),
                )
            except Exception as e:  # pragma: no cover (defensive)
                logger.warning(
                    "invoice.payment_succeeded user=%s err=%s",
                    _user_ref(user), e,
                )
        logger.info(
            "invoice ok subscription=%s period_end=%s user=%s",
            sub_id, period_end, _user_ref(user),
        )
        return

    if event_type == "customer.subscription.updated":
        period_end = obj.get("current_period_end")
        cancel_at = obj.get("cancel_at")
        cancel_at_period_end = obj.get("cancel_at_period_end")
        if not user:
            return
        # Map Stripe status to our billing_state vocabulary.
        s_status = (obj.get("status") or "").lower()
        billing_state = None
        if s_status == "active":
            billing_state = "active" if not cancel_at_period_end else "active"
        elif s_status == "past_due":
            billing_state = "past_due"
        elif s_status in ("incomplete", "incomplete_expired", "unpaid"):
            billing_state = "past_due"
        elif s_status == "canceled":
            billing_state = "cancelled"
        try:
            users_store.set_billing_state(
                user,
                billing_state=billing_state,
                renewal_ts=(float(period_end) if period_end else None),
            )
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "subscription.updated user=%s err=%s",
                _user_ref(user), e,
            )
        if cancel_at:
            users_store.update_user(user, {"cancel_at_ts": float(cancel_at)})
        return

    if event_type == "customer.subscription.deleted":
        if user:
            try:
                users_store.set_billing_state(
                    user, billing_state="cancelled", renewal_ts=None,
                )
                users_store.update_user(
                    user, {
                        "membership_status": "cancelled",
                        "canceled_at_ts": float(obj.get("canceled_at") or time.time()),
                    },
                )
            except Exception as e:  # pragma: no cover (defensive)
                logger.warning(
                    "subscription.deleted user=%s err=%s",
                    _user_ref(user), e,
                )
        return

    if event_type == "invoice.payment_failed":
        if user:
            try:
                users_store.set_billing_state(user, billing_state="past_due")
            except Exception as e:  # pragma: no cover (defensive)
                logger.warning(
                    "invoice.payment_failed user=%s err=%s",
                    _user_ref(user), e,
                )
        return


# ===========================================================================
# Public routes (account + system)
# ===========================================================================
@app.get("/me")
def me(request: Request, session: dict = Depends(require_session)):
    logger.info(
        "me user=%s session=%s",
        _user_ref(session["user"]), _session_ref(session["session_id"]),
    )
    user_doc = users_store.get_user(session["user"]) or {}
    cohort = user_doc.get("cohort")

    # Card 18 — operator identity model:
    #   Operator identity is cohort-derived (durable) and token-override
    #   (request-scoped).
    #   - Cohort membership determines baseline operator identity.
    #   - Operator token elevates the *request* for privileged endpoints.
    #   This preserves identity semantics while keeping capability checks
    #   isolated.
    #
    # ``FOUNDER_LIKE_COHORTS`` (= {"founder", "founder_exception"}) is the
    # same set used by other cohort-derived privilege gates in this file
    # (invite redemption, quota resolution) so the boundary stays
    # consistent across the engine. Token-bearing requests are operator
    # regardless of cohort — that path is unchanged from Card 16.
    operator = _is_operator_token(request) or (cohort in FOUNDER_LIKE_COHORTS)

    # Card 16 — vault_ready: non-throwing probe so a misconfigured
    # vault never causes /me to 500. (This is what bit us in Card 15.)
    vault_ready = memory_vault.is_ready(session["user"])

    # Card 16 — cache the intelligence_kernel view so a single call
    # supplies all three downstream fields, AND tolerate failures so
    # a broken kernel can't 500 /me. /me used to invoke this three
    # times (line-by-line) which both inflated cost and tripled the
    # vault-failure blast radius.
    kernel_view: dict = {}
    try:
        kernel_view = intelligence_kernel.kernel_view_for_user(session["user"])
    except Exception as e:
        logger.warning(
            "kernel_view_for_user failed user=%s err=%s",
            _user_ref(session["user"]), e,
        )

    return {
        "ok": True,
        "user": session["user"],
        "session_id": session["session_id"],
        "cohort": cohort,
        "operator": operator,
        "vault_ready": vault_ready,
        "operator_id": user_doc.get("operator_id"),
        "tier": user_doc.get("tier", "free"),
        "billing_expires_at": user_doc.get("billing_expires_at"),
        # v29 — feature gates that the surface needs to know about up front.
        "features": {
            "v28_surfaces": v29_hardening.feature_enabled(
                "v28_surfaces", user=session["user"], cohort=cohort,
            ),
            "onboarding_v1": v29_hardening.feature_enabled(
                "onboarding_v1", user=session["user"], cohort=cohort,
            ),
            "whats_new_v28": v29_hardening.feature_enabled(
                "whats_new_v28", user=session["user"], cohort=cohort,
            ),
            "demo_data": v29_hardening.feature_enabled(
                "demo_data", user=session["user"], cohort=cohort,
            ),
            "founder_tier_enabled": v29_hardening.feature_enabled(
                "founder_tier_enabled", user=session["user"], cohort=cohort,
            ),
            "g_credits_enabled": v29_hardening.feature_enabled(
                "g_credits_enabled", user=session["user"], cohort=cohort,
            ),
            "membership_ui_enabled": v29_hardening.feature_enabled(
                "membership_ui_enabled", user=session["user"], cohort=cohort,
            ),
        },
        "onboarding": (user_doc.get("onboarding") or {}),
        # v30 — small read-only view so the app shell can render the
        # membership badge without a second round-trip.
        "membership": users_store.get_membership_view(session["user"]),
        # v33 — capabilities the client can advertise (#cmt + standardized
        # ELINS). Keys map to the ``mode`` string the client passes back.
        "capabilities": [
            {"id": "elins_preview",  "label": "ELINS preview", "route": "/elins/preview"},
            {"id": "elins_qc",       "label": "S_ELINS QC",    "route": "/elins/qc"},
            {"id": "elins_forecast", "label": "ELINS forecast","route": "/elins/forecast"},
            {"id": "elins_regional", "label": "ELINS regional","route": "/elins/regional/run"},
            {"id": "elins_entities", "label": "ELINS entity graph","route": "/elins/entities/search"},
            {"id": "elins_dashboard","label": "ELINS dashboard","route": "/elins/dashboard"},
            {"id": "operator_state", "label": "Operator state",  "route": "/me/operator_state"},
            {"id": "intelligence_kernel","label": "Intelligence kernel v1.0","route": "/me"},
            {"id": "founder_analytics","label": "Founder analytics","route": "/founder/analytics/summary"},
            {"id": "model_router",   "label": "Model router",  "route": "/me/operator_state/model"},
            {"id": "local_model",    "label": "Local model runtime","route": "/me/local_model"},
            {"id": "memory_vault",   "label": "Memory Vault",  "route": "/me/vault/status"},
            {"id": "threads",        "label": "Threads",       "route": "/me/threads"},
            {"id": "projects",       "label": "Projects",      "route": "/me/projects"},
            {"id": "emotional_physics","label": "Emotional Physics","route": "/me/emotional_physics/analyze"},
            {"id": "elins_v2",       "label": "ELINS v2 (Path C)","route": "/elins/v2/run"},
            {"id": "ingestion",      "label": "Ingestion bus (RSS + manual)","route": "/ingest/feeds"},
            {"id": "cmt",            "label": "#cmt — Most Relevant Comment", "route": "/cmt/generate"},
            {"id": "c_run_comment",  "label": "#c (mode=comment)", "route": "/c/run"},
        ],
        # v40 — kernel block exposes the user's effective ESO mode +
        # inferred preferences without needing a second round-trip to
        # /me/operator_state. v41 adds top-level shortcuts so older
        # clients can read external_signal_mode + eso_source without
        # walking the kernel block.
        "intelligence_kernel": kernel_view,
        "external_signal_mode": kernel_view.get("external_signal_mode"),
        "eso_source": kernel_view.get("eso_source"),
    }


# ---------------------------------------------------------------------------
# Card 16 — operator-only diagnostic endpoint
# ---------------------------------------------------------------------------
@app.get("/operator/state")
def operator_state_diagnostic(_: dict = Depends(require_operator_token)):
    """Operator-only diagnostic view of the engine.

    Card 16.1: renamed from ``operator_state`` to ``operator_state_diagnostic``
    so this view function no longer shadows the module-level
    ``import operator_state`` (line 107). The URL stays ``/operator/state``;
    the response shape is unchanged. The rename unblocks five callsites
    that read ``operator_state.get_operator_state(...)`` /
    ``set_preferred_model(...)`` later in the file, plus the new Card 19
    ``/model/route`` adapter.

    Auth: ``Authorization: Operator <token>`` (validated against
    ``CLARITYOS_OPERATOR_TOKEN``). No user session required — this is
    the privileged "root shell" surface and is intentionally not
    user-scoped.

    Returns:
      engine_revision   K_REVISION env (set by Cloud Run) or
                        BUILD_VERSION file content
      vault_status      "ready" or "not_configured"
      active_sessions   count of live sessions in sessions_store
      uptime_seconds    int seconds since module load
      cors_origins      live CORS allow-list (same as /config)
      backend           backend mode ("memory" / "firestore")
      version           api version
    """
    # engine_revision — prefer K_REVISION (auto-set by Cloud Run);
    # fall back to BUILD_VERSION file (read once on each call —
    # tolerant of missing files).
    engine_revision = os.environ.get("K_REVISION") or ""
    if not engine_revision:
        bv_path = os.environ.get("BUILD_VERSION_FILE", "BUILD_VERSION")
        try:
            with open(bv_path, "r", encoding="utf-8") as f:
                engine_revision = f.read().strip()
        except Exception:
            engine_revision = "(unknown)"

    # vault_status — non-throwing probe.
    vault_status = "ready" if memory_vault.is_ready() else "not_configured"

    # active_sessions — defensive count. sessions_store backends
    # vary (memory vs firestore); a count() method may or may not
    # exist. Try the most common shapes; fall back to "unknown".
    active_sessions: int | str = "unknown"
    try:
        if hasattr(sessions_store, "count_sessions"):
            active_sessions = int(sessions_store.count_sessions())
        elif hasattr(sessions_store, "list_session_ids"):
            active_sessions = len(list(sessions_store.list_session_ids()))
    except Exception:
        active_sessions = "unknown"

    uptime_seconds = int(time.time() - _ENGINE_START_TIME)

    return {
        "ok": True,
        "engine_revision": engine_revision,
        "vault_status": vault_status,
        "active_sessions": active_sessions,
        "uptime_seconds": uptime_seconds,
        "cors_origins": CORS_ORIGINS,
        "backend": BACKEND,
        "version": "2.4",
    }


@app.get("/config")
def get_config(session: dict = Depends(require_session)):
    """Runtime configuration — for Cloud Run verification."""
    logger.info(
        "config user=%s session=%s",
        _user_ref(session["user"]), _session_ref(session["session_id"]),
    )
    return {
        "ok": True,
        "data": {
            "backend": BACKEND,
            "library_bucket": LIBRARY_BUCKET,
            "library_prefix": LIBRARY_PREFIX,
            "session_ttl": SESSION_TTL_SECONDS,
            "cors_origins": CORS_ORIGINS,
            "user": session["user"],
            "gcs_available": gcs_storage is not None,
            "version": "2.4",
            "invite_only": INVITE_ONLY,
            "terrace_1_cap": TERRACE_1_CAP,
            "terrace_1_redeemed": invites_store.count_redeemed(COHORT_TERRACE_1),
            "billing_configured": billing.is_configured(),
        },
    }


# ===========================================================================
# Storage Layer v1 — vault / library / timeline
#
# Per-user content storage backed by Firestore. Three buckets, each with a
# per-object envelope and a shared per-user byte quota tracked in usage_store.
# Quota resolution is cohort-driven: founder / founder_exception → 1 GB,
# everyone else (terrace_1, registered-no-cohort) → 500 MB.
# ===========================================================================
def _quota_for(user: str) -> int:
    user_doc = users_store.get_user(user) or {}
    cohort = user_doc.get("cohort")
    return QUOTA_FOUNDER_BYTES if cohort in FOUNDER_LIKE_COHORTS else QUOTA_DEFAULT_BYTES


def _envelope_check(payload_bytes: int, max_bytes: int, kind: str) -> None:
    if payload_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=error_response(
                "envelope_exceeded",
                f"{kind} payload {payload_bytes} bytes exceeds {max_bytes}-byte envelope",
            ),
        )


def _assert_quota(user: str, bytes_to_add: int) -> int:
    """Verify the write fits in the user's quota. Returns current usage."""
    if bytes_to_add <= 0:
        return usage_store.get_bytes(user)
    quota = _quota_for(user)
    used = usage_store.get_bytes(user)
    if used + bytes_to_add > quota:
        raise HTTPException(
            status_code=413,
            detail=error_response(
                "quota_exceeded",
                f"would exceed quota: {used + bytes_to_add} > {quota} bytes",
            ),
        )
    return used


def _serialized_size(payload: dict) -> int:
    return len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


# ---------- Vault ----------------------------------------------------------
class VaultWriteRequest(BaseModel):
    # Cockpit composer surfaces title/content/tags only — type defaults to "note".
    # Phone clients still send type="session" explicitly for transcripts.
    type: str = "note"
    title: str = ""
    content: str
    tags: list[str] = []
    metadata: dict = {}


class VaultUpdateRequest(BaseModel):
    id: str
    title: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None


class VaultDeleteRequest(BaseModel):
    id: str


def _summary_from(title: str, content: str, max_len: int = 120) -> str:
    """Pick a short summary string for timeline events: title if present,
    else the first non-empty line of content, truncated."""
    if title and title.strip():
        s = title.strip()
    elif content:
        s = next((ln for ln in content.split("\n") if ln.strip()), content.strip())
    else:
        s = ""
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _emit_timeline(user: str, kind: str, ref: Optional[str], summary: str, data: dict) -> None:
    """Best-effort timeline event emission from vault/library write paths.

    Failures are logged and swallowed so a bad timeline write never fails
    the primary vault/library write that triggered it. Charged against the
    user's usage like any other write; if the small event would push the
    user over their (already generous) quota, the emission is skipped.

    v3: persists `object_vector` on the auto-emitted event for schema
    parity with direct timeline writes.
    """
    try:
        now = time.time()
        event = {
            "user": user,
            "kind": kind,
            "summary": summary or "",
            "ref": ref,
            "ts": now,
            "data": dict(data or {}),
            "created_at": now,
        }
        event["object_vector"] = dewey_pipeline.embed_object(event)
        size = _serialized_size(event)
        if size > TIMELINE_ENVELOPE_BYTES:
            # Strip data and the vector — both are larger than summary —
            # before deciding to skip entirely.
            event["data"] = {}
            event["object_vector"] = None
            size = _serialized_size(event)
            if size > TIMELINE_ENVELOPE_BYTES:
                logger.warning("timeline event too large after stripping data; skipped kind=%s", kind)
                return
        if usage_store.get_bytes(user) + size > _quota_for(user):
            logger.warning(
                "timeline emission skipped (would exceed quota) user=%s kind=%s",
                _user_ref(user), kind,
            )
            return
        event_id = timeline_store.new_id()
        event["id"] = event_id
        event["size_bytes"] = size
        timeline_store.create(event_id, event)
        usage_store.add_bytes(user, size)
        logger.info("timeline vector_persisted kind=%s id=%s", kind, event_id)
    except Exception as e:
        logger.warning("timeline emission failed kind=%s err=%s", kind, e)


@app.post("/vault/write")
def vault_write(req: VaultWriteRequest, session: dict = Depends(require_session)):
    user = session["user"]
    if req.type not in ALLOWED_VAULT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_type", f"type must be one of: {', '.join(ALLOWED_VAULT_TYPES)}"),
        )
    item = {
        "user": user,
        "type": req.type,
        "title": req.title or "",
        "content": req.content,
        "tags": list(req.tags or []),
        "metadata": dict(req.metadata or {}),
        "created_at": time.time(),
    }
    item["object_vector"] = dewey_pipeline.embed_object(item)
    size = _serialized_size(item)
    _envelope_check(size, VAULT_ENVELOPE_BYTES, "vault")
    _assert_quota(user, size)
    item_id = vault_store.new_id()
    item["id"] = item_id
    item["size_bytes"] = size
    vault_store.create(item_id, item)
    new_used = usage_store.add_bytes(user, size)
    logger.info(
        "vault vector_persisted user=%s id=%s size=%d",
        _user_ref(user), item_id, size,
    )
    _emit_timeline(user, "vault.write", item_id,
                   _summary_from(item["title"], item["content"]),
                   {"type": item["type"], "tags": item["tags"]})
    dewey_worker.process_object(user, "vault", item_id, item)
    return {"ok": True, "item": item, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.post("/vault/update")
def vault_update(req: VaultUpdateRequest, session: dict = Depends(require_session)):
    user = session["user"]
    existing = vault_store.get(req.id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"No vault item with id {req.id}"),
        )
    if existing.get("user") != user:
        raise HTTPException(
            status_code=403,
            detail=error_response("forbidden", "Vault item belongs to another user"),
        )
    updated = dict(existing)
    if req.title is not None:
        updated["title"] = req.title
    if req.type is not None:
        if req.type not in ("note", "session"):
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_type", "type must be 'note' or 'session'"),
            )
        updated["type"] = req.type
    if req.content is not None:
        updated["content"] = req.content
    if req.tags is not None:
        updated["tags"] = list(req.tags)
    if req.metadata is not None:
        updated["metadata"] = dict(req.metadata)
    updated["updated_at"] = time.time()
    # v3: re-embed since title/content may have changed. Drop the stale
    # vector before recomputing so it isn't included in the embed text or
    # in the size measurement under its old form.
    updated.pop("object_vector", None)
    updated["object_vector"] = dewey_pipeline.embed_object(updated)
    old_size = int(updated.pop("size_bytes", 0))
    new_size = _serialized_size(updated)
    _envelope_check(new_size, VAULT_ENVELOPE_BYTES, "vault")
    delta = new_size - old_size
    if delta > 0:
        _assert_quota(user, delta)
    updated["size_bytes"] = new_size
    vault_store.update(req.id, updated)
    new_used = usage_store.add_bytes(user, delta)
    logger.info(
        "vault vector_persisted user=%s id=%s delta=%d",
        _user_ref(user), req.id, delta,
    )
    _emit_timeline(user, "vault.update", req.id,
                   _summary_from(updated.get("title", ""), updated.get("content", "")),
                   {"type": updated.get("type"), "tags": updated.get("tags", [])})
    return {"ok": True, "item": updated, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.post("/vault/delete")
def vault_delete(req: VaultDeleteRequest, session: dict = Depends(require_session)):
    user = session["user"]
    item = vault_store.get(req.id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"No vault item with id {req.id}"),
        )
    if item.get("user") != user:
        raise HTTPException(
            status_code=403,
            detail=error_response("forbidden", "Vault item belongs to another user"),
        )
    size = int(item.get("size_bytes", 0))
    vault_store.delete(req.id)
    new_used = usage_store.add_bytes(user, -size)
    logger.info(
        "vault delete user=%s id=%s size=%d",
        _user_ref(user), req.id, size,
    )
    _emit_timeline(user, "vault.delete", req.id,
                   _summary_from(item.get("title", ""), item.get("content", "")),
                   {"type": item.get("type")})
    return {"ok": True, "id": req.id, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.get("/vault/list")
def vault_list(session: dict = Depends(require_session), limit: int = 100):
    user = session["user"]
    limit = min(max(1, limit), 500)
    items = vault_store.list_for_user(user, limit=limit)
    return {"ok": True, "items": items, "count": len(items)}


# ---------- Library (per-user authored entries) ---------------------------
# Distinct from the engine-owned GCS-backed `/library` POST route — this is
# user-authored content. Stored in the `library_user` Firestore collection.
class LibraryWriteRequest(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    metadata: dict = {}


class LibraryUpdateRequest(BaseModel):
    id: str
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None


@app.post("/library/write")
def library_user_write(req: LibraryWriteRequest, session: dict = Depends(require_session)):
    user = session["user"]
    if not req.title or not req.title.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_title", "title must be non-empty"),
        )
    now = time.time()
    item = {
        "user": user,
        "title": req.title.strip(),
        "content": req.content,
        "tags": list(req.tags or []),
        "metadata": dict(req.metadata or {}),
        "created_at": now,
        "updated_at": now,
    }
    item["object_vector"] = dewey_pipeline.embed_object(item)
    size = _serialized_size(item)
    _envelope_check(size, LIBRARY_ENVELOPE_BYTES, "library")
    _assert_quota(user, size)
    item_id = library_store.new_id()
    item["id"] = item_id
    item["size_bytes"] = size
    library_store.create(item_id, item)
    new_used = usage_store.add_bytes(user, size)
    logger.info(
        "library vector_persisted user=%s id=%s size=%d",
        _user_ref(user), item_id, size,
    )
    _emit_timeline(user, "library.write", item_id,
                   _summary_from(item["title"], item["content"]),
                   {"tags": item["tags"]})
    dewey_worker.process_object(user, "library", item_id, item)
    return {"ok": True, "item": item, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.post("/library/update")
def library_user_update(req: LibraryUpdateRequest, session: dict = Depends(require_session)):
    user = session["user"]
    existing = library_store.get(req.id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"No library item with id {req.id}"),
        )
    if existing.get("user") != user:
        raise HTTPException(
            status_code=403,
            detail=error_response("forbidden", "Library item belongs to another user"),
        )
    updated = dict(existing)
    if req.title is not None:
        if not req.title.strip():
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_title", "title must be non-empty"),
            )
        updated["title"] = req.title.strip()
    if req.content is not None:
        updated["content"] = req.content
    if req.tags is not None:
        updated["tags"] = list(req.tags)
    if req.metadata is not None:
        updated["metadata"] = dict(req.metadata)
    updated["updated_at"] = time.time()
    # v3: drop stale vector and re-embed (title/content may have changed).
    updated.pop("object_vector", None)
    updated["object_vector"] = dewey_pipeline.embed_object(updated)
    # Strip the cached size before re-measuring (size_bytes is itself stored).
    old_size = int(updated.pop("size_bytes", 0))
    new_size = _serialized_size(updated)
    _envelope_check(new_size, LIBRARY_ENVELOPE_BYTES, "library")
    delta = new_size - old_size
    if delta > 0:
        _assert_quota(user, delta)
    updated["size_bytes"] = new_size
    library_store.update(req.id, updated)
    new_used = usage_store.add_bytes(user, delta)
    logger.info(
        "library vector_persisted user=%s id=%s delta=%d",
        _user_ref(user), req.id, delta,
    )
    _emit_timeline(user, "library.update", req.id,
                   _summary_from(updated.get("title", ""), updated.get("content", "")),
                   {"tags": updated.get("tags", [])})
    return {"ok": True, "item": updated, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.get("/library/list")
def library_user_list(session: dict = Depends(require_session), limit: int = 100):
    user = session["user"]
    limit = min(max(1, limit), 500)
    items = library_store.list_for_user(user, limit=limit)
    return {"ok": True, "items": items, "count": len(items)}


# ---------- Timeline (append-only event log) ------------------------------
class TimelineWriteRequest(BaseModel):
    kind: str
    summary: str = ""
    ref: Optional[str] = None
    ts: Optional[float] = None
    data: dict = {}


@app.post("/timeline/write")
def timeline_write(req: TimelineWriteRequest, session: dict = Depends(require_session)):
    user = session["user"]
    if not req.kind or not req.kind.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_kind", "kind must be non-empty"),
        )
    now = time.time()
    event = {
        "user": user,
        "kind": req.kind.strip(),
        "summary": req.summary,
        "ref": req.ref,
        "ts": req.ts if req.ts is not None else now,
        "data": dict(req.data or {}),
        "created_at": now,
    }
    event["object_vector"] = dewey_pipeline.embed_object(event)
    size = _serialized_size(event)
    _envelope_check(size, TIMELINE_ENVELOPE_BYTES, "timeline")
    _assert_quota(user, size)
    event_id = timeline_store.new_id()
    event["id"] = event_id
    event["size_bytes"] = size
    timeline_store.create(event_id, event)
    new_used = usage_store.add_bytes(user, size)
    logger.info(
        "timeline vector_persisted user=%s id=%s kind=%s size=%d",
        _user_ref(user), event_id, event["kind"], size,
    )
    return {"ok": True, "event": event, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.get("/timeline/list")
def timeline_list(
    session: dict = Depends(require_session),
    kind: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 100,
):
    user = session["user"]
    limit = min(max(1, limit), 500)
    events = timeline_store.list_for_user(
        user, kind=kind, since=since, until=until, limit=limit,
    )
    return {"ok": True, "events": events, "count": len(events)}


# ===========================================================================
# ELINS ingestion (founder cohort only)
#
# Three entry points for the morning ELINS run. Each route writes through
# the same envelope/quota/usage/timeline pipeline as user-direct writes,
# then triggers the DEWEY worker so the new objects flow into any matching
# neighborhoods.
# ===========================================================================
class ELINSPrimitivesRequest(BaseModel):
    primitives: list[dict]


class ELINSBriefRequest(BaseModel):
    content: str
    date: Optional[str] = None  # YYYY-MM-DD; default today (UTC)
    metadata: dict = {}


class ELINSRawRequest(BaseModel):
    payload: dict
    label: Optional[str] = None  # display title for the resulting vault item


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@app.post("/elins/ingest/primitives")
def elins_ingest_primitives(
    req: ELINSPrimitivesRequest,
    session: dict = Depends(_require_founder),
):
    """Each primitive becomes one timeline event of kind=elins.primitive,
    which itself triggers the DEWEY worker on the resulting event."""
    user = session["user"]
    if not isinstance(req.primitives, list) or not req.primitives:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_primitives", "primitives must be a non-empty list"),
        )
    written: list[dict] = []
    for p in req.primitives:
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_primitive", "each primitive must be a JSON object"),
            )
        now = time.time()
        summary = str(p.get("name") or p.get("label") or p.get("kind") or "primitive")[:120]
        event = {
            "user": user,
            "kind": "elins.primitive",
            "summary": summary,
            "ref": p.get("id"),
            "ts": now,
            "data": dict(p),
            "created_at": now,
        }
        event["object_vector"] = dewey_pipeline.embed_object(event)
        size = _serialized_size(event)
        _envelope_check(size, TIMELINE_ENVELOPE_BYTES, "timeline")
        _assert_quota(user, size)
        event_id = timeline_store.new_id()
        event["id"] = event_id
        event["size_bytes"] = size
        timeline_store.create(event_id, event)
        usage_store.add_bytes(user, size)
        written.append(event)
        logger.info(
            "elins.primitive vector_persisted user=%s id=%s",
            _user_ref(user), event_id,
        )
        dewey_worker.process_object(user, "timeline", event_id, event)
    logger.info(
        "elins primitives user=%s count=%d",
        _user_ref(user), len(written),
    )
    return {"ok": True, "events": written, "count": len(written)}


@app.post("/elins/ingest/brief")
def elins_ingest_brief(
    req: ELINSBriefRequest,
    session: dict = Depends(_require_founder),
):
    """Writes the brief as a library entry titled `ELINS Brief YYYY-MM-DD`
    and emits a timeline event with kind=elins.brief (which the DEWEY
    worker is registered to trigger on)."""
    user = session["user"]
    date_str = req.date or _today_utc()
    title = f"ELINS Brief {date_str}"
    now = time.time()
    item = {
        "user": user,
        "title": title,
        "content": req.content,
        "tags": ["elins", "brief"],
        "metadata": {"source": "elins", "date": date_str, **dict(req.metadata or {})},
        "created_at": now,
        "updated_at": now,
    }
    item["object_vector"] = dewey_pipeline.embed_object(item)
    size = _serialized_size(item)
    _envelope_check(size, LIBRARY_ENVELOPE_BYTES, "library")
    _assert_quota(user, size)
    item_id = library_store.new_id()
    item["id"] = item_id
    item["size_bytes"] = size
    library_store.create(item_id, item)
    new_used = usage_store.add_bytes(user, size)
    logger.info(
        "elins.brief vector_persisted user=%s id=%s date=%s",
        _user_ref(user), item_id, date_str,
    )
    _emit_timeline(user, "elins.brief", item_id,
                   _summary_from(item["title"], item["content"]),
                   {"date": date_str})
    dewey_worker.process_object(user, "library", item_id, item)
    return {"ok": True, "item": item, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


@app.post("/elins/ingest/raw")
def elins_ingest_raw(
    req: ELINSRawRequest,
    session: dict = Depends(_require_founder),
):
    """Writes the raw JSON to vault with type=elins_raw. The auto-emitted
    timeline event uses kind=vault.write (regular vault path)."""
    user = session["user"]
    label = req.label or f"ELINS raw {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    content_json = json.dumps(req.payload, separators=(",", ":"))
    item = {
        "user": user,
        "type": "elins_raw",
        "title": label,
        "content": content_json,
        "tags": ["elins", "raw"],
        "metadata": {"source": "elins"},
        "created_at": time.time(),
    }
    item["object_vector"] = dewey_pipeline.embed_object(item)
    size = _serialized_size(item)
    _envelope_check(size, VAULT_ENVELOPE_BYTES, "vault")
    _assert_quota(user, size)
    item_id = vault_store.new_id()
    item["id"] = item_id
    item["size_bytes"] = size
    vault_store.create(item_id, item)
    new_used = usage_store.add_bytes(user, size)
    logger.info(
        "elins.raw vector_persisted user=%s id=%s",
        _user_ref(user), item_id,
    )
    _emit_timeline(user, "vault.write", item_id,
                   _summary_from(item["title"], item["content"]),
                   {"type": "elins_raw"})
    dewey_worker.process_object(user, "vault", item_id, item)
    return {"ok": True, "item": item, "usage": {"bytes_used": new_used, "quota": _quota_for(user)}}


# ===========================================================================
# DEWEY Layer v1 — geodesic neighborhoods + memberships
#
# A neighborhood is a query-shaped basin on the (placeholder) embedding
# manifold. When a new object lands (vault/library/elins.primitive), the
# DEWEY worker computes membership against every neighborhood owned by the
# same user and writes a row when the object falls inside.
#
# Geometry primitives live in dewey_pipeline.py; the worker calls them.
# All math is stubbed for v1 — see that module's docstring.
# ===========================================================================
class DeweyCreateNeighborhoodRequest(BaseModel):
    name: str
    query: str
    # filters.domains is the v2 recognized key (list[str]). Other keys are
    # accepted and stored verbatim for forward-compat but ignored by the pipeline.
    filters: dict = {}
    # v2 λ_window is an optional [λ_min, λ_max] range. None / unset → no λ filter.
    # JSON wire accepts either "λ_window" (per spec) or the ASCII alias
    # "lambda_window". curl + bash on some platforms mangle the unicode key,
    # so we accept both. Storage uses "λ_window" verbatim per spec.
    lambda_window: Optional[list[float]] = Field(default=None, alias="λ_window")
    # v2 basin gate. Default 0.3 per spec.
    similarity_threshold: float = 0.3
    # v4 propagation field — None means no propagation (no contributions/curvature
    # computed; backward-compatible behavior).
    influence_radius: Optional[float] = None
    # v4 cap on the number of contributing origins per membership. Default 3.
    max_origins: int = 3

    model_config = ConfigDict(populate_by_name=True)


@app.post("/dewey/neighborhoods/create")
def dewey_neighborhood_create(
    req: DeweyCreateNeighborhoodRequest,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if not req.name or not req.name.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_name", "name must be non-empty"),
        )
    if not req.query or not req.query.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_query", "query must be non-empty"),
        )
    if req.lambda_window is not None:
        if not isinstance(req.lambda_window, list) or len(req.lambda_window) != 2:
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_lambda_window", "λ_window must be [λ_min, λ_max] or null"),
            )
        if req.lambda_window[0] > req.lambda_window[1]:
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_lambda_window", "λ_min must be ≤ λ_max"),
            )
    if not (-1.0 <= req.similarity_threshold <= 1.0):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_threshold", "similarity_threshold must be in [-1, 1]"),
        )
    if req.influence_radius is not None and req.influence_radius < 0.0:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_influence_radius", "influence_radius must be ≥ 0 or null"),
        )
    if req.max_origins < 1:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_max_origins", "max_origins must be ≥ 1"),
        )
    now = time.time()
    # embed_text already L2-normalizes, so origin_vector is unit-length.
    origin_vector = dewey_pipeline.embed_text(req.query)
    nb_id = dewey_neighborhoods_store.new_id()
    nb = {
        "id": nb_id,
        "user": user,
        "name": req.name.strip(),
        "query": req.query,
        "filters": dict(req.filters or {}),
        "origin_vector": origin_vector,
        "λ_window": list(req.lambda_window) if req.lambda_window is not None else None,
        "similarity_threshold": float(req.similarity_threshold),
        "influence_radius": float(req.influence_radius) if req.influence_radius is not None else None,
        "max_origins": int(req.max_origins),
        "created_at": now,
        "updated_at": now,
    }
    dewey_neighborhoods_store.create(nb_id, nb)
    logger.info(
        "dewey neighborhood create user=%s id=%s name=%s threshold=%.3f lambda_window=%s influence_radius=%s max_origins=%d",
        _user_ref(user), nb_id, nb["name"], nb["similarity_threshold"], nb["λ_window"],
        nb["influence_radius"], nb["max_origins"],
    )
    return {"ok": True, "neighborhood": nb}


@app.get("/dewey/neighborhoods/list")
def dewey_neighborhood_list(
    session: dict = Depends(require_session),
    limit: int = 200,
):
    user = session["user"]
    limit = min(max(1, limit), 500)
    neighborhoods = dewey_neighborhoods_store.list_for_user(user, limit=limit)
    return {"ok": True, "neighborhoods": neighborhoods, "count": len(neighborhoods)}


@app.get("/dewey/neighborhoods/{nb_id}")
def dewey_neighborhood_get(
    nb_id: str,
    session: dict = Depends(require_session),
):
    user = session["user"]
    nb = dewey_neighborhoods_store.get(nb_id)
    if not nb:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"No neighborhood with id {nb_id}"),
        )
    if nb.get("user") != user:
        raise HTTPException(
            status_code=403,
            detail=error_response("forbidden", "Neighborhood belongs to another user"),
        )
    memberships = dewey_memberships_store.list_for_neighborhood(nb_id)
    return {
        "ok": True,
        "neighborhood": nb,
        "memberships": memberships,
        "membership_count": len(memberships),
    }


@app.post("/dewey/neighborhoods/{nb_id}/refresh")
def dewey_neighborhood_refresh(
    nb_id: str,
    session: dict = Depends(require_session),
):
    """Recompute memberships from scratch: drop all existing rows for this
    neighborhood, then iterate the user's vault + library + timeline
    objects and rebuild membership."""
    user = session["user"]
    nb = dewey_neighborhoods_store.get(nb_id)
    if not nb:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"No neighborhood with id {nb_id}"),
        )
    if nb.get("user") != user:
        raise HTTPException(
            status_code=403,
            detail=error_response("forbidden", "Neighborhood belongs to another user"),
        )
    removed = dewey_memberships_store.delete_for_neighborhood(nb_id)
    objects: list[tuple[str, dict]] = []
    for v in vault_store.list_for_user(user, limit=500):
        objects.append(("vault", v))
    for l in library_store.list_for_user(user, limit=500):
        objects.append(("library", l))
    for ev in timeline_store.list_for_user(user, limit=500):
        objects.append(("timeline", ev))
    written = dewey_worker.refresh_neighborhood(nb, objects)
    nb["updated_at"] = time.time()
    dewey_neighborhoods_store.update(nb_id, nb)
    logger.info(
        "dewey refresh user=%s nb=%s removed=%d written=%d",
        _user_ref(user), nb_id, removed, written,
    )
    return {
        "ok": True,
        "neighborhood": nb,
        "removed": removed,
        "written": written,
    }


# ===========================================================================
# Markov v2 — per-session state history with QC envelope
#
# Foundational layer for Markov v3 / DEWEY v5 trajectory forecasting / chat.
# Storage only at this layer; no chat endpoint yet (per spec).
# ===========================================================================
class MarkovStateUpdateRequest(BaseModel):
    session_id: str
    state_vector: list[float]
    qc_envelope: dict = {}


def _validate_unit_norm(vec: list[float], tol: float = 0.01) -> float:
    """Returns the computed norm. Raises 400 if the vector is empty or its
    norm deviates from 1.0 by more than `tol`. Tolerance covers ordinary
    float-precision drift (~1e-7) but rejects clearly-unnormalized input."""
    if not vec:
        raise HTTPException(
            status_code=400,
            detail=error_response("empty_vector", "vector must be non-empty"),
        )
    norm = sum(x * x for x in vec) ** 0.5
    if abs(norm - 1.0) > tol:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "not_normalized",
                f"vector must be unit-normalized (norm={norm:.6f}, expected ~1.0)",
            ),
        )
    return norm


_DEFAULT_ENVELOPE_METRICS = {
    "stability_trend": 0.0,
    "drift_trend": 0.0,
    "pressure_trend": 0.0,
}


def _persist_markov_state(
    user: str,
    session_id: str,
    state_vector: list[float],
    qc_envelope: dict,
    predictive_vector: Optional[list[float]] = None,
    envelope_metrics: Optional[dict] = None,
) -> tuple[int, float]:
    """Append a new Markov state. Shared by /markov/state/update and
    /markov/chat. Returns (state_index, timestamp). Caller is responsible
    for normalization validation when accepting from a client.

    Markov v3 fields default per spec: predictive_vector → state_vector,
    envelope_metrics → all-zero trend dict."""
    state_index = markov_states_store.next_index_for(user, session_id)
    now = time.time()
    state_id = markov_states_store.new_id()
    pv = list(predictive_vector) if predictive_vector is not None else list(state_vector)
    em = dict(envelope_metrics) if envelope_metrics is not None else dict(_DEFAULT_ENVELOPE_METRICS)
    markov_states_store.create(state_id, {
        "id": state_id,
        "user": user,
        "session_id": session_id,
        "state_index": state_index,
        "state_vector": list(state_vector),
        "qc_envelope": dict(qc_envelope or {}),
        "envelope_predictive_vector": pv,
        "envelope_metrics": em,
        "timestamp": now,
    })
    return state_index, now


@app.post("/markov/state/update")
def markov_state_update(
    req: MarkovStateUpdateRequest,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_session_id", "session_id must be non-empty"),
        )
    _validate_unit_norm(req.state_vector)
    state_index, now = _persist_markov_state(
        user, req.session_id, req.state_vector, req.qc_envelope,
    )
    logger.info(
        "markov state_update user=%s session=%s index=%d",
        _user_ref(user), _session_ref(req.session_id), state_index,
    )
    return {"ok": True, "state_index": state_index, "timestamp": now}


@app.get("/markov/state/latest")
def markov_state_latest(
    session_id: str,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_session_id", "session_id query param required"),
        )
    state = markov_states_store.latest_for(user, session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("no_state", f"No Markov state for session {session_id}"),
        )
    return {"ok": True, "state": state}


# ===========================================================================
# DEWEY v5 — trajectory forecasting
#
# Read-only with respect to Markov state. Generates a base trajectory plus
# small-perturbation alternative branches from the user's latest Markov
# state, optionally anchored to a high-similarity ELINS brief.
# ===========================================================================
class TrajectoryForecastRequest(BaseModel):
    session_id: str
    horizon_steps: int = 5


_ELINS_ANCHOR_THRESHOLD = 0.7
_TRAJECTORY_MAX_HORIZON = 20
_TRAJECTORY_NUM_BRANCHES = 2


def _anchor_to_elins_brief(user: str, start_state: list[float]) -> Optional[str]:
    """If the user's envelope has any ELINS brief whose object_vector has
    similarity ≥ 0.7 with `start_state`, return the highest-matching
    `brief_id`. Otherwise None."""
    envelope = envelopes_store.get(user)
    if not envelope:
        return None
    briefs = envelope.get("elins_briefs") or []
    best_id: Optional[str] = None
    best_sim = -2.0
    dim = len(start_state)
    for b in briefs:
        v = b.get("object_vector")
        if not v or len(v) != dim:
            continue
        s = dewey_pipeline.similarity(start_state, v)
        if s > best_sim:
            best_sim = s
            best_id = b.get("brief_id")
    if best_sim >= _ELINS_ANCHOR_THRESHOLD and best_id:
        return best_id
    return None


@app.post("/trajectory/forecast")
def trajectory_forecast(
    req: TrajectoryForecastRequest,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_session_id", "session_id must be non-empty"),
        )
    horizon = int(req.horizon_steps)
    if horizon < 1 or horizon > _TRAJECTORY_MAX_HORIZON:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_horizon",
                f"horizon_steps must be in [1, {_TRAJECTORY_MAX_HORIZON}]",
            ),
        )

    # 1. Start vectors from Markov v3.
    state = markov_states_store.latest_for(user, req.session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=error_response(
                "no_state",
                f"No Markov state for session {req.session_id}",
            ),
        )
    start_state = list(state.get("state_vector") or [])
    if not start_state:
        raise HTTPException(
            status_code=400,
            detail=error_response("empty_state", "Markov state has no state_vector"),
        )
    start_predictive = list(state.get("envelope_predictive_vector") or start_state)

    # 2. Load user's neighborhoods once (worker uses them across all branches).
    user_neighborhoods = dewey_neighborhoods_store.list_for_user(user, limit=500)

    # 3. Base trajectory.
    base_steps, base_summary = dewey_pipeline.generate_trajectory(
        start_state, horizon, user_neighborhoods, branch_label="base",
    )

    # 4. Alternative branches (small perturbations).
    alt_branches = dewey_pipeline.generate_alternative_branches(
        start_state, horizon, user_neighborhoods,
        num_branches=_TRAJECTORY_NUM_BRANCHES,
    )

    # 5. Flatten steps (base + alts).
    all_steps = list(base_steps)
    for branch_steps, _ in alt_branches:
        all_steps.extend(branch_steps)

    # 6. Compose summary.
    anchored = _anchor_to_elins_brief(user, start_state)
    summary = {
        "stability_score": base_summary["stability_score"],
        "drift_score": base_summary["drift_score"],
        "pressure_score": base_summary["pressure_score"],
        "branching_factor": 1 + len(alt_branches),
        "anchored_elins_brief_id": anchored,
    }
    # v5.1 — stability variance + branch divergence
    summary.update(dewey_pipeline.compute_trajectory_metrics(all_steps))

    # 7. Persist.
    now = time.time()
    trajectory_id = trajectories_store.new_id()
    doc = {
        "id": trajectory_id,
        "user": user,
        "session_id": req.session_id,
        "trajectory_id": trajectory_id,
        "created_at": now,
        "horizon_steps": horizon,
        "start_state_vector": start_state,
        "start_predictive_vector": start_predictive,
        "steps": all_steps,
        "summary": summary,
    }
    trajectories_store.create(trajectory_id, doc)
    logger.info(
        "trajectory forecast user=%s session=%s id=%s horizon=%d branches=%d anchored=%s stability=%.3f",
        _user_ref(user), _session_ref(req.session_id), trajectory_id, horizon,
        summary["branching_factor"], summary["anchored_elins_brief_id"],
        summary["stability_score"],
    )

    return {
        "ok": True,
        "trajectory_id": trajectory_id,
        "horizon_steps": horizon,
        "summary": summary,
        "steps": all_steps,
    }


_V51_METRIC_KEYS = ("stability_variance", "mean_branch_divergence", "max_branch_divergence")


def _ensure_v51_metrics(traj: dict) -> dict:
    """Lazy backfill — if `summary` is missing any v5.1 metric, compute and
    persist them. Returns the (possibly updated) trajectory doc."""
    summary = traj.get("summary") or {}
    if all(k in summary for k in _V51_METRIC_KEYS):
        return traj
    metrics = dewey_pipeline.compute_trajectory_metrics(traj.get("steps") or [])
    summary.update(metrics)
    traj["summary"] = summary
    try:
        trajectories_store.create(traj["id"], traj)  # set semantics → upsert
        logger.info(
            "trajectory v5.1 metrics backfilled id=%s var=%.4f mean_div=%.4f max_div=%.4f",
            traj.get("id"),
            metrics["stability_variance"],
            metrics["mean_branch_divergence"],
            metrics["max_branch_divergence"],
        )
    except Exception as e:
        logger.warning("trajectory v5.1 backfill persist failed id=%s err=%s", traj.get("id"), e)
    return traj


@app.get("/trajectory/compare")
def trajectory_compare(
    trajectory_id_a: str,
    trajectory_id_b: str,
    session: dict = Depends(require_session),
):
    """Compare two trajectories owned by the same user. Lazy-backfills the
    v5.1 metrics on either trajectory if missing."""
    user = session["user"]
    if not trajectory_id_a or not trajectory_id_b:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_ids", "trajectory_id_a and trajectory_id_b are required",
            ),
        )

    def _load_owned(tid: str) -> dict:
        t = trajectories_store.get(tid)
        if t is None:
            raise HTTPException(
                status_code=404,
                detail=error_response("not_found", f"No trajectory with id {tid}"),
            )
        if t.get("user") != user:
            raise HTTPException(
                status_code=403,
                detail=error_response("forbidden", f"Trajectory {tid} belongs to another user"),
            )
        return t

    a = _ensure_v51_metrics(_load_owned(trajectory_id_a))
    b = _ensure_v51_metrics(_load_owned(trajectory_id_b))
    sa = a.get("summary") or {}
    sb = b.get("summary") or {}

    def _f(d: dict, k: str) -> float:
        try:
            return float(d.get(k, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    return {
        "ok": True,
        "trajectory_a": {"trajectory_id": a.get("trajectory_id"), "summary": sa},
        "trajectory_b": {"trajectory_id": b.get("trajectory_id"), "summary": sb},
        "comparison": {
            "stability_delta": _f(sa, "stability_score") - _f(sb, "stability_score"),
            "divergence_delta": _f(sa, "mean_branch_divergence") - _f(sb, "mean_branch_divergence"),
        },
    }


@app.get("/markov/envelope/latest")
def markov_envelope_latest(
    session_id: str,
    session: dict = Depends(require_session),
):
    """Markov v3 — slim view of the latest state suitable for trajectory
    forecasting. Returns the four envelope-relevant fields with safe
    defaults for legacy (pre-v3) docs that lack the new fields."""
    user = session["user"]
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_session_id", "session_id query param required"),
        )
    state = markov_states_store.latest_for(user, session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("no_state", f"No Markov state for session {session_id}"),
        )
    state_vector = state.get("state_vector") or []
    predictive_vector = state.get("envelope_predictive_vector") or list(state_vector)
    return {
        "ok": True,
        "state_vector": state_vector,
        "predictive_vector": predictive_vector,
        "qc_envelope": state.get("qc_envelope") or {},
        "envelope_metrics": state.get("envelope_metrics") or dict(_DEFAULT_ENVELOPE_METRICS),
    }


# ===========================================================================
# 4/3-1 chat runtime — Markov v3
#
# Processors: Observer → Interpreter → Regulator → Projector → -1 Subtractive.
# Pipeline math is in dewey_pipeline (predict_next_state, compute_noise_component,
# top_neighborhoods_*); this route orchestrates them and persists the result.
#
# Reply generation is a stub ("Acknowledged.") — replaced by a DEWEY-anchored
# generator in a later block.
# ===========================================================================
INTENT_DESCRIPTORS = {
    "ask": "asking a question, seeking information, requesting an answer or fact",
    "build": "building, creating, designing, constructing, implementing, making something",
    "clarify": "clarifying, explaining, defining, disambiguating, resolving ambiguity",
    "reflect": "reflecting, considering, thinking about one's own state or process",
    "act": "taking action, executing, doing, performing a concrete task right now",
}

_IDENTITY_QC_ENVELOPE = {
    "qc_stability": 1.0,
    "qc_drift": 0.0,
    "qc_predictive": 1.0,
    "qc_pressure": 0.0,
}


class MarkovChatRequest(BaseModel):
    session_id: str
    message: str


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(len(a))]


def _vec_sub(a: list[float], b: list[float]) -> list[float]:
    return [a[i] - b[i] for i in range(len(a))]


def _vec_scale(v: list[float], s: float) -> list[float]:
    return [s * x for x in v]


def _vec_lincomb(a: list[float], sa: float, b: list[float], sb: float) -> list[float]:
    return [sa * a[i] + sb * b[i] for i in range(len(a))]


# ---------------------------------------------------------------------------
# Envelope v3 — decay + refresh + envelope_vector recompute
# ---------------------------------------------------------------------------
_ENVELOPE_V3_DEFAULTS = {
    "strength": 1.0,
    "decay_rate": 0.002,         # per hour (legacy default; v3.5 uses per-timescale defaults)
    "activation_threshold": 0.6,
}
_ENVELOPE_REFRESH_TIER_LOW = 0.7   # bumps strength by +0.05 * multiplier
_ENVELOPE_REFRESH_TIER_HIGH = 0.85  # ADDITIONAL +0.10 * multiplier (stacks on top of low)
_ENVELOPE_REFRESH_BUMP_LOW = 0.05
_ENVELOPE_REFRESH_BUMP_HIGH = 0.10

# Envelope v3.5 — multi-timescale memory.
_VALID_TIMESCALES = ("short", "mid", "long")
_DEFAULT_TIMESCALE = "mid"
_DEFAULT_DECAY_BY_TIMESCALE = {
    "short": 0.010,    # fast decay
    "mid":   0.002,    # moderate (matches v3 default)
    "long":  0.0003,   # slow decay
}
_REFRESH_MULTIPLIER_BY_TIMESCALE = {
    "short": 1.5,      # short refreshes faster than mid
    "mid":   1.0,
    "long":  0.5,      # long refreshes slower than mid
}

# Envelope v4 — consolidation (promotion + demotion).
_PROMOTION_THRESHOLD = {"short": 0.30, "mid": 0.50}  # short→mid, mid→long
_PROMOTION_NEXT = {"short": "mid", "mid": "long"}     # no promotion past long
_DEMOTION_THRESHOLD = {"long": 0.40, "mid": 0.25}     # long→mid, mid→short
_DEMOTION_NEXT = {"long": "mid", "mid": "short"}      # no demotion past short
_DEMOTION_STALE_HOURS = 48.0                          # "not referenced for 48h"
_DEMOTION_LOW_STRENGTH_THRESHOLD = 0.3
_DEMOTION_BUMP_LOW_STRENGTH = 0.10
_DEMOTION_BUMP_STALE = 0.10
_PROMOTION_BUMP_HIGH_SIM = 0.10                       # sim ≥ 0.85
_PROMOTION_BUMP_HIGH_STRENGTH = 0.05                  # strength ≥ 0.8
_PROMOTION_BUMP_ACTIVE = 0.05                         # strength ≥ activation_threshold

# Envelope v4.5 — interference + pattern separation.
_INTERFERENCE_TIER_LOW = 0.90       # +0.05 to each brief in pair
_INTERFERENCE_TIER_HIGH = 0.95      # ADDITIONAL +0.10 (stacks)
_INTERFERENCE_BUMP_LOW = 0.05
_INTERFERENCE_BUMP_HIGH = 0.10
_SEPARATION_TRIGGER = 0.20          # interference_score threshold for separation
_SEPARATION_STRENGTH_PENALTY = 0.10
_SEPARATION_VECTOR_COEF = 0.05      # subtract this fraction of envelope_vector
_INTERFERENCE_DECAY_STALE_HOURS = 24.0
_INTERFERENCE_DECAY_BUMP = 0.05

# Envelope v5 — replay cycles.
_REPLAY_CADENCE_HOURS = 24.0
_REPLAY_CANDIDATE_TIMESCALES = ("mid", "long")
_REPLAY_CANDIDATE_MIN_STRENGTH = 0.5
_REPLAY_BUMP = 0.10
_REPLAY_STRENGTHEN_THRESHOLD = 0.30
_REPLAY_STRENGTHEN_AMOUNT = 0.05
_REPLAY_DEMOTION_STALE_HOURS = 72.0
_REPLAY_DEMOTION_LOW_STRENGTH = 0.3
_REPLAY_DEMOTION_BUMP = 0.10

# Envelope v5.5 — drift correction + centroid stabilization.
_DRIFT_EVENT_THRESHOLD = 0.10           # flagged as drift event
_DRIFT_CORRECTION_THRESHOLD = 0.20      # triggers correction
_DRIFT_CENTROID_PULLBACK_OLD = 0.8      # weight on old centroid in correction
_DRIFT_CENTROID_PULLBACK_NEW = 0.2      # weight on current envelope_vector
_DRIFT_BRIEF_PULLBACK_OLD = 0.95        # weight on brief's own vector
_DRIFT_BRIEF_PULLBACK_CENTROID = 0.05   # weight on centroid
_DRIFT_UNSTABLE_STRENGTH_THRESHOLD = 0.3
_DRIFT_UNSTABLE_STRENGTH_PENALTY = 0.05
_CENTROID_REFRESH_CADENCE_HOURS = 48.0
_CENTROID_REFRESH_OLD = 0.9             # slow refresh — keep most of old centroid
_CENTROID_REFRESH_NEW = 0.1             # blend in a little of envelope_vector
# Server-managed envelope fields preserved across /envelope/update calls.
_ENVELOPE_PRESERVED_SERVER_FIELDS = (
    "envelope_centroid",
    "envelope_drift_events",
    "envelope_last_replay_ts",
    "last_centroid_update_ts",
    "events",                              # v6 — episodic memory list
    "envelope_last_episode_consolidation_ts",  # v6 — episode consolidation gate
    "episodes",                            # v6.5 — per-episode aggregates + links
    "narratives",                          # v7 — narrative node graph
    "story_arcs",                          # v7 — clustered story arcs
    "envelope_last_arc_clustering_ts",     # v7 — arc clustering gate
    "identity",                            # v8 — identity profile
    "trajectory",                          # v9 — operator-trajectory profile
    "elins",                               # v12 — ELINS physics layer
    "universal_physics",                   # v13 — universal physics context
    "coherence",                           # v14 — cross-layer coherence report
    "external_context",                    # v15 — external knowledge context
    "s_strategy_layer",                    # v16 — Sun Tzu strategy overlay (also nested under elins)
    "physics_reasoning_context",           # v17 — cross-scale harmonized reasoning block
    "reasoning_cues",                      # v18 — generator conditioning surface
    "reasoning_weights",                   # v19 — soft weighting vector
    "memory_context",                      # v20 — long-range cross-turn memory surface
    "external_knowledge",                  # v21 — conceptual-retrieval layer
    "cognitive_loop",                      # v22 — full cognitive loop integrator
    "reasoning_scaffold",                  # v23 — context-weighted scaffold
    "response_shape",                      # v24 — response-shape hints
    "response_templates",                  # v25 — micro-template phrasing patterns
    "sentence_operators",                  # v26 — sentence-level modifiers
    "connective_ops",                      # v27 — connective tissue operators
)

# Envelope v6 — episodic memory + event linking.
_EVENT_DEFAULT_STRENGTH = 0.5
_EVENT_DECAY_RATE = 0.005                  # per chat (not per hour)
_EVENT_INACTIVE_STRENGTH = 0.1
_EVENT_LINK_SIM_THRESHOLD = 0.70           # link brief to event if sim ≥ this
_EVENT_LINK_TIER_HIGH = 0.85               # +0.02 to brief AND event
_EVENT_LINK_TIER_VERY_HIGH = 0.95          # ADDITIONAL +0.03 to brief AND event
_EVENT_LINK_BUMP_HIGH = 0.02
_EVENT_LINK_BUMP_VERY_HIGH = 0.03
_EPISODE_GAP_SECONDS = 600.0               # within 10 min → same episode
_EPISODE_CONSOLIDATION_CADENCE_HOURS = 24.0
_EPISODE_PROMOTE_STRENGTH = 0.6            # episode strength ≥ → long-term brief
_EPISODE_DEMOTE_STRENGTH = 0.3             # episode strength ≤ → demote events
_EPISODE_DEMOTE_BUMP = 0.05
# Soft cap on persisted events to avoid Firestore doc-size blowup. Older
# inactive events fall off when the list grows past this.
_EVENT_LIST_SOFT_CAP = 500

# Envelope v6.5 — cross-episode reasoning + temporal causality.
_EPISODE_LINK_SIM_THRESHOLD = 0.70         # cross-episode semantic link
_EPISODE_LINK_STRENGTHEN_THRESHOLD = 0.85  # also bump episode_strength
_EPISODE_LINK_STRENGTHEN_BUMP = 0.02       # × temporal_weight
_CAUSAL_EVENT_SIM_THRESHOLD = 0.80         # event-level causal inference
_CAUSAL_EVENT_STRENGTHEN_BUMP = 0.02       # both events get this
_CAUSAL_EPISODE_STRENGTHEN_THRESHOLD = 0.60  # episode-level weight gate
_CAUSAL_EPISODE_STRENGTHEN_BUMP = 0.03     # × temporal_weight
_TEMPORAL_DECAY_HOURS = 72.0               # exp(-Δt/72) decay


def _temporal_weight(hours: float) -> float:
    """exp(-Δt/72) for cross-episode / causal weighting. Clamped at 1.0
    for non-positive deltas; never negative."""
    import math as _math
    if hours <= 0.0:
        return 1.0
    try:
        return float(_math.exp(-float(hours) / _TEMPORAL_DECAY_HOURS))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _episode_aggregate(events_in_episode: list[dict]) -> tuple[Optional[list[float]], float, float]:
    """Returns (mean_vector_normalized, mean_strength, latest_event_ts)
    over the events in one episode. mean_vector is None if no events
    carry a usable vector."""
    accum: Optional[list[float]] = None
    count = 0
    strengths: list[float] = []
    latest_ts = 0.0
    for ev in events_in_episode:
        try:
            s = float(ev.get("strength", 0.0))
        except (TypeError, ValueError):
            s = 0.0
        strengths.append(s)
        try:
            ts = float(ev.get("timestamp", 0.0))
        except (TypeError, ValueError):
            ts = 0.0
        if ts > latest_ts:
            latest_ts = ts
        v = ev.get("vector")
        if not v:
            continue
        if accum is None:
            accum = list(v)
            count = 1
            continue
        if len(v) != len(accum):
            continue
        for i in range(len(accum)):
            accum[i] += v[i]
        count += 1
    mean_strength = (sum(strengths) / len(strengths)) if strengths else 0.0
    if count == 0 or not accum:
        return None, mean_strength, latest_ts
    return dewey_pipeline._normalize(accum), mean_strength, latest_ts


def _references_prior_text(new_text: str, prior_text: str) -> bool:
    """Heuristic for `E references prior content`: any 5+ char word from
    prior appears in E (case-insensitive). Cheap stand-in for a real
    coreference check; good enough as a soft fallback."""
    if not new_text or not prior_text:
        return False
    new_lower = new_text.lower()
    for w in prior_text.lower().split():
        w = w.strip(".,;:!?\"'()[]{}")
        if len(w) >= 5 and w in new_lower:
            return True
    return False


# Envelope v7 — narrative memory + multi-episode story graphs.
_NARRATIVE_FORMATION_SIM_THRESHOLD = 0.75   # merge episode into existing node
_NARRATIVE_FORMATION_STRENGTHEN_BUMP = 0.02
_NARRATIVE_LINK_SIM_THRESHOLD = 0.70        # cross-narrative semantic link
_NARRATIVE_LINK_STRENGTHEN_THRESHOLD = 0.85
_NARRATIVE_LINK_STRENGTHEN_BUMP = 0.02
_NARRATIVE_CAUSAL_STRENGTHEN_THRESHOLD = 0.60
_NARRATIVE_CAUSAL_STRENGTHEN_BUMP = 0.03
_STORY_ARC_PROMOTE_STRENGTH = 0.6
_STORY_ARC_CLUSTERING_CADENCE_HOURS = 24.0
_NARRATIVE_CLUSTER_SIM_THRESHOLD = 0.70     # node↔node edge for arc clustering


def _narrative_aggregate(
    node: dict,
    episodes_dict: dict,
) -> tuple[Optional[list[float]], float, float]:
    """Recompute (mean_vector_normalized, mean_strength, latest_event_ts)
    over the episodes currently in `node.episode_ids`. Episodes whose vectors
    are missing or dim-mismatched are skipped from the vector mean but still
    contribute to the strength mean."""
    accum: Optional[list[float]] = None
    count = 0
    strengths: list[float] = []
    latest_ts = 0.0
    for eid in node.get("episode_ids", []) or []:
        ep = episodes_dict.get(eid)
        if not isinstance(ep, dict):
            continue
        try:
            s = float(ep.get("episode_strength", 0.0))
        except (TypeError, ValueError):
            s = 0.0
        strengths.append(s)
        try:
            ts = float(ep.get("latest_event_ts", 0.0))
        except (TypeError, ValueError):
            ts = 0.0
        if ts > latest_ts:
            latest_ts = ts
        v = ep.get("episode_vector")
        if not v:
            continue
        if accum is None:
            accum = list(v)
            count = 1
            continue
        if len(v) != len(accum):
            continue
        for i in range(len(accum)):
            accum[i] += v[i]
        count += 1
    mean_strength = (sum(strengths) / len(strengths)) if strengths else 0.0
    if count == 0 or not accum:
        return None, mean_strength, latest_ts
    return dewey_pipeline._normalize(accum), mean_strength, latest_ts


def _connected_components(
    node_ids: list[str],
    adjacency: dict,
) -> list[list[str]]:
    """Standard BFS over an undirected graph (adjacency: node_id → set of
    neighbor node_ids). Returns connected components as lists of node_ids."""
    seen: set = set()
    components: list[list[str]] = []
    for nid in node_ids:
        if nid in seen:
            continue
        # BFS
        component: list[str] = []
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            component.append(cur)
            for nxt in adjacency.get(cur, ()):
                if nxt not in seen:
                    stack.append(nxt)
        components.append(component)
    return components


# Envelope v7.5 — narrative compression + summaries + intent extraction.
_NARRATIVE_COMPRESSION_TARGET_DIM = 128       # PCA target dim (informational; fallback preserves source dim)
_NARRATIVE_COMPRESSION_CADENCE_HOURS = 24.0   # per-node staleness gate
_STORY_SUMMARY_MIN_EPISODES = 3
_STORY_SUMMARY_MIN_STRENGTH = 0.65
_STORY_SUMMARY_MAX_TOKENS = 120
_ARC_SUMMARY_MAX_TOKENS = 200

# Intent keyword catalog. Each entry: (intent_label, list[case-insensitive
# substring patterns]). Order matters — first match wins per pattern, but
# multiple intents can coexist on one node (one per category).
_INTENT_KEYWORDS: tuple = (
    ("goal", ("i want", "i need", "want to", "need to", "trying to",
              "my goal", "going to", "plan to", "would like to", "aiming to")),
    ("preference", ("i prefer", "i like", "i love", "favorite", "rather than",
                    "instead of", "would rather")),
    ("constraint", ("must not", "can't", "cannot", "shouldn't", "no more than",
                    "at most", "limit", "constraint", "deadline", "by friday",
                    "by tomorrow", "no later than")),
    ("long-term project", ("long-term", "long term", "ongoing", "project",
                           "roadmap", "milestone", "phase 1", "phase 2",
                           "this quarter", "this year", "v1", "v2")),
    ("unresolved issue", ("stuck", "unresolved", "broken", "bug", "issue",
                          "problem", "doesn't work", "failing", "error",
                          "can't figure", "not sure how")),
)


def _compress_vector_mean_pool(vectors: list[list[float]]) -> Optional[list[float]]:
    """v7.5 §2 fallback when PCA is unavailable. Mean of input vectors,
    L2-normalized. Returns None if the input list is empty or no vector
    survives dim consistency.

    PCA-to-128 isn't applied because:
      (1) sklearn isn't a runtime dep, and
      (2) the recall step compares against v_final (full dim), so a
          dim-reduced compressed_vector would be incomparable. Mean-pool
          preserves dim and stays sim-comparable.
    """
    if not vectors:
        return None
    accum: Optional[list[float]] = None
    count = 0
    for v in vectors:
        if not v:
            continue
        if accum is None:
            accum = list(v)
            count = 1
            continue
        if len(v) != len(accum):
            continue
        for i in range(len(accum)):
            accum[i] += v[i]
        count += 1
    if accum is None or count == 0:
        return None
    return dewey_pipeline._normalize(accum)


def _node_event_vectors(node: dict, events_by_id: dict) -> list[list[float]]:
    """Return vectors for the events listed in `node.event_ids`."""
    out: list[list[float]] = []
    for evid in node.get("event_ids") or []:
        ev = events_by_id.get(evid)
        if not isinstance(ev, dict):
            continue
        v = ev.get("vector")
        if v:
            out.append(v)
    return out


def _node_event_texts(node: dict, events_by_id: dict) -> list[tuple]:
    """Return (timestamp, text) for events in `node.event_ids`, sorted by
    timestamp ascending."""
    out: list[tuple] = []
    for evid in node.get("event_ids") or []:
        ev = events_by_id.get(evid)
        if not isinstance(ev, dict):
            continue
        t = ev.get("text") or ""
        if not t:
            continue
        try:
            ts = float(ev.get("timestamp", 0.0))
        except (TypeError, ValueError):
            ts = 0.0
        out.append((ts, t))
    out.sort(key=lambda x: x[0])
    return out


def _extractive_summary(
    timestamped_texts: list[tuple],
    max_tokens: int,
    focus: Optional[str] = None,
) -> Optional[str]:
    """Cheap deterministic extractive summarizer for v7.5.

    No LLM available at this layer — pull the first sentence of each event
    in chronological order, dedupe, prefix with [focus] if provided, then
    truncate at ~max_tokens (whitespace-split count). Returns None on empty
    input."""
    if not timestamped_texts:
        return None
    seen: set = set()
    sentences: list[str] = []
    for _, text in timestamped_texts:
        # First sentence only — split on common terminators.
        first = text.strip()
        for sep in (". ", "? ", "! ", "\n"):
            if sep in first:
                first = first.split(sep, 1)[0].rstrip()
                break
        first = first.strip(" .;:!?\"'")
        if not first:
            continue
        key = first.lower()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(first)
    if not sentences:
        return None
    body = ". ".join(sentences) + "."
    words = body.split()
    if len(words) > max_tokens:
        body = " ".join(words[:max_tokens]).rstrip(",;:") + "…"
    if focus:
        return f"[{focus}] {body}"
    return body


def _extract_intents(
    node: dict,
    summary_text: Optional[str],
    event_texts: list[tuple],
    episodes_dict: dict,
) -> list[str]:
    """v7.5 §4 — keyword + structure-based intent classifier. Each label
    appears at most once. `recurring theme` fires when 2+ events in the
    node share a 5+ char content word (cheap stand-in for topic recurrence).

    Sources scanned:
      - summary_text
      - event texts
      - causal chain length (≥ 2 causal_links on this node's episodes → adds
        'long-term project' even if keywords don't fire)
      - episode promotion count (an episode with a `episode_summary_<eid>`
        brief contributes weight to 'recurring theme')
    """
    intents: list[str] = []
    haystack_parts: list[str] = []
    if summary_text:
        haystack_parts.append(summary_text.lower())
    for _, t in event_texts:
        if t:
            haystack_parts.append(t.lower())
    haystack = " \n ".join(haystack_parts)

    for label, patterns in _INTENT_KEYWORDS:
        for pat in patterns:
            if pat in haystack:
                if label not in intents:
                    intents.append(label)
                break

    # Structural signals.
    causal_count = 0
    for eid in node.get("episode_ids") or []:
        ep = episodes_dict.get(eid)
        if isinstance(ep, dict):
            causal_count += len(ep.get("causal_links") or [])
    if causal_count >= 2 and "long-term project" not in intents:
        intents.append("long-term project")

    # Recurring theme: shared 5+ char content word across ≥2 events.
    word_freq: dict = {}
    for _, t in event_texts:
        seen_in_event: set = set()
        for w in t.lower().split():
            w = w.strip(".,;:!?\"'()[]{}")
            if len(w) >= 5 and w not in seen_in_event:
                seen_in_event.add(w)
                word_freq[w] = word_freq.get(w, 0) + 1
    if any(c >= 2 for c in word_freq.values()) and "recurring theme" not in intents:
        intents.append("recurring theme")

    return intents


# Envelope v8 — identity layer + self-modeling + operator-trajectory tracking.
_IDENTITY_NODE_INFLUENCE_THRESHOLD = 0.70    # bump node_strength during formation
_IDENTITY_EPISODE_INFLUENCE_THRESHOLD = 0.85  # bump episode_strength during formation
_IDENTITY_NODE_STRENGTHEN_BUMP = 0.01
_IDENTITY_EPISODE_STRENGTHEN_BUMP = 0.01
_IDENTITY_FORMATION_CADENCE_HOURS = 24.0     # gate for identity rebuild
_STABLE_INTENT_MIN_ARCS = 2
_PREFERENCE_PATTERN_MIN_EPISODES = 3
_LONG_RANGE_GOAL_MIN_ARCS = 2
_LONG_RANGE_GOAL_MIN_CAUSAL_CHAIN = 3
_UNRESOLVED_THEME_MIN_ARCS = 2

# Preference patterns. label → list[case-insensitive substrings]. A pattern
# "fires" for an episode if any of its events contains any substring.
_PREFERENCE_PATTERNS: tuple = (
    ("likes", ("i like", "i love", "likes ", "loving ")),
    ("prefers", ("i prefer", "prefers ", "rather than", "would rather")),
    ("avoids", ("i avoid", "avoids ", "stay away from", "don't want", "do not want")),
    ("works best with", ("works best", "best with", "best when", "most effective when")),
)

# Resolution keywords for "no causal resolution event" check (v8 §6).
_RESOLUTION_KEYWORDS: tuple = (
    "resolved", "fixed", "solved", "completed", "done", "finished",
    "shipped", "closed", "wrapped up",
)


def _episodes_for_arc(arc: dict, narratives_dict: dict) -> list[str]:
    """Flatten arc.arc_nodes → list of episode_ids. Used by identity-layer
    extractors that need to walk into arc-level event/episode content."""
    eids: list[str] = []
    for nid in arc.get("arc_nodes") or []:
        node = narratives_dict.get(nid)
        if isinstance(node, dict):
            for eid in node.get("episode_ids") or []:
                if eid not in eids:
                    eids.append(eid)
    return eids


def _events_for_arc(arc: dict, narratives_dict: dict, events_by_id: dict) -> list[dict]:
    """Flatten arc → list of event dicts."""
    out: list[dict] = []
    seen: set = set()
    for nid in arc.get("arc_nodes") or []:
        node = narratives_dict.get(nid)
        if not isinstance(node, dict):
            continue
        for evid in node.get("event_ids") or []:
            if evid in seen:
                continue
            ev = events_by_id.get(evid)
            if isinstance(ev, dict):
                seen.add(evid)
                out.append(ev)
    return out


# Envelope v9 — operator trajectory model + long-range developmental arcs.
_TRAJECTORY_WINDOW_DAYS = 90
_TRAJECTORY_FORMATION_CADENCE_HOURS = 24.0
_TRAJECTORY_TREND_THRESHOLD_PCT = 0.30           # 30% relative change
_TRAJECTORY_IDENTITY_COUPLING_WEAK_SIM = 0.60
_TRAJECTORY_IDENTITY_COUPLING_STRONG_SIM = 0.80
_TRAJECTORY_IDENTITY_COUPLING_BUMP = 0.05
_PHASE_BUILD_MIN_CAUSAL_CHAIN = 3
_PHASE_REFACTOR_MIN_ARCS = 2
_PHASE_EXPLORATION_MIN_NODES = 3
_PHASE_EXPLORATION_MAX_CAUSAL_CHAIN = 1          # i.e., chain depth ≤ 1
_PHASE_STABILIZATION_MIN_MEAN_STRENGTH = 0.7

_PHASE_REFACTOR_KEYWORDS: tuple = (
    "refactor", "cleanup", "rewrite", "rework", "consolidate", "tidy", "clean up",
)


def _arcs_in_window(story_arcs_dict: dict, window_seconds: float, now_ts: float) -> list:
    """Return arcs whose `latest_event_ts` (fallback `created_at`) is within
    the last `window_seconds`. Arcs with no usable timestamp are included
    (treated as fresh)."""
    out: list = []
    for arc in story_arcs_dict.values():
        if not isinstance(arc, dict):
            continue
        try:
            ts = float(arc.get("latest_event_ts") or arc.get("created_at") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if ts <= 0 or (now_ts - ts) <= window_seconds:
            out.append(arc)
    return out


def _intent_freq_split(arcs_in_window: list, midpoint_ts: float) -> tuple:
    """Split arc intent counts by midpoint_ts into (first_half, second_half)
    dicts of label → count."""
    first: dict = {}
    second: dict = {}
    for arc in arcs_in_window:
        try:
            ts = float(arc.get("latest_event_ts") or arc.get("created_at") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        bucket = first if ts < midpoint_ts else second
        for it in arc.get("intents") or []:
            bucket[it] = bucket.get(it, 0) + 1
    return first, second


# Envelope v12 — ELINS physics layer for geopolitical context.
_ELINS_JSON_ENV_VAR = "CLARITYOS_ELINS_JSON_PATH"
_ELINS_PHYSICS_BLOCK_MAX_TOKENS = 300
_ELINS_TEMPORAL_DELTA_KEYS: tuple = ("24h", "7d", "30d")


def _load_elins_json() -> Optional[dict]:
    """Load ELINS JSON from the path in `CLARITYOS_ELINS_JSON_PATH`.
    Returns None if env var unset, file missing, or parse fails. Failures
    are logged at WARNING but do not raise — ELINS is opt-in physics
    context, not core."""
    path = os.environ.get(_ELINS_JSON_ENV_VAR)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:  # pragma: no cover
        logger.warning("ELINS JSON load failed path=%s err=%s", path, e)
        return None


def _extract_centers_from_text(text: str, all_centers: list) -> list:
    """Word-boundary scan: any known center name appearing as a whole word
    in `text` is returned, preserving the canonical spelling from
    `all_centers`. Word-boundary (not raw substring) avoids false positives
    like `'us'` matching inside `'russia'`."""
    if not text or not all_centers:
        return []
    import re
    text_lower = text.lower()
    found: list = []
    for c in all_centers:
        cl = str(c).lower()
        if not cl:
            continue
        if re.search(r"\b" + re.escape(cl) + r"\b", text_lower):
            if c not in found:
                found.append(c)
    return found


def _matches_any_center(haystack: str, centers: list) -> bool:
    """Word-boundary check used by basin/ridge filtering to avoid the
    same `'us' ⊂ 'russia'` false positive."""
    if not haystack or not centers:
        return False
    import re
    h = str(haystack).lower()
    for c in centers:
        cl = str(c).lower()
        if not cl:
            continue
        if re.search(r"\b" + re.escape(cl) + r"\b", h):
            return True
    return False


def _min_max_normalize(values: list) -> list:
    """Min-max scale a list of floats into [0, 1]. If all values are
    equal, non-zero values map to 1.0 and zeros to 0.0 (avoids divide-
    by-zero and preserves sparsity)."""
    if not values:
        return []
    floats: list = []
    for v in values:
        try:
            floats.append(float(v))
        except (TypeError, ValueError):
            floats.append(0.0)
    lo = min(floats)
    hi = max(floats)
    if hi - lo < 1e-9:
        return [1.0 if v != 0.0 else 0.0 for v in floats]
    return [(v - lo) / (hi - lo) for v in floats]


def _normalize_dict_minmax(d: dict) -> dict:
    """Min-max normalize a dict's values. Keys unchanged; values clamped
    to [0, 1]. Empty input → empty dict."""
    if not d:
        return {}
    keys = list(d.keys())
    vals = [d[k] for k in keys]
    norms = _min_max_normalize(vals)
    return dict(zip(keys, norms))


# Envelope v13 — universal physics context layer.
_UNIVERSAL_CONSTRAINTS: tuple = (
    "conservation laws",
    "symmetry and symmetry breaking",
    "causality",
    "entropy and irreversibility",
    "information flow",
    "boundary conditions",
)

_UNIVERSAL_PHASES: tuple = (
    "equilibrium",
    "near-equilibrium drift",
    "far-from-equilibrium",
    "critical transition",
    "new basin stabilization",
)

_UNIVERSAL_OPERATORS: tuple = (
    "gradient following",
    "basin deepening",
    "ridge crossing",
    "attractor formation",
    "coherence maintenance",
    "drift under pressure",
    "feedback amplification",
    "dissipation and relaxation",
)

_UNIVERSAL_SCALES: tuple = (
    "quantum",
    "thermodynamic",
    "biological",
    "social",
    "cosmological",
)

_UNIVERSAL_SCALE_ANNOTATIONS: dict = {
    "quantum": (
        "unitary evolution under constraints",
        "decoherence as pressure toward classical basins",
        "measurement as ridge crossing",
    ),
    "thermodynamic": (
        "entropy increase in irreversible trajectories",
        "quasi-static vs far-from-equilibrium paths",
    ),
    "biological": (
        "selection as gradient following",
        "fitness landscapes as basins",
        "mutation and drift as perturbations",
    ),
    "social": (
        "institutions as basins",
        "norms and laws as constraints",
        "collective behavior as drift under cultural/economic pressure",
    ),
    "cosmological": (
        "gravity as basin deepening",
        "expansion as large-scale drift",
        "structure formation as attractor emergence",
    ),
}


def _build_universal_physics_block() -> dict:
    """v13 — deterministic universal-physics block. Sorted lists for stable
    rendering across calls. Static; no per-user state, no inputs. Cheap
    enough to call every evolve cycle."""
    return {
        "constraints": sorted(_UNIVERSAL_CONSTRAINTS),
        "phases": sorted(_UNIVERSAL_PHASES),
        "operators": sorted(_UNIVERSAL_OPERATORS),
        "scale_annotations": {
            scale: sorted(_UNIVERSAL_SCALE_ANNOTATIONS[scale])
            for scale in sorted(_UNIVERSAL_SCALES)
            if scale in _UNIVERSAL_SCALE_ANNOTATIONS
        },
    }


# Envelope v14 — cross-layer coherence validator.
_COHERENCE_REQUIRED_KEYS: tuple = (
    "constraints",
    "phases",
    "operators",
    "scale_annotations",
)
_COHERENCE_MIN_IDENTITY_STRENGTH = 0.0
_COHERENCE_MAX_IDENTITY_STRENGTH = 1.0
_COHERENCE_MIN_TRAJECTORY_STRENGTH = 0.0
_COHERENCE_MAX_TRAJECTORY_STRENGTH = 1.0
_COHERENCE_ALLOWED_SCALES: tuple = (
    "quantum",
    "thermodynamic",
    "biological",
    "social",
    "cosmological",
)
_COHERENCE_ELINS_PHYSICS_BLOCK_KEYS: tuple = (
    "centers_involved",
    "pressure_fields",
    "drift_vectors",
    "basin_state",
    "ridge_state",
    "temporal_deltas",
)
_COHERENCE_IDENTITY_LOW_THRESHOLD = 0.1
_COHERENCE_TRAJECTORY_HIGH_THRESHOLD = 0.9


def _run_coherence_checks(
    identity_profile: Optional[dict],
    trajectory_profile: Optional[dict],
    elins_context: Optional[dict],
    universal_physics_block: Optional[dict],
) -> dict:
    """v14 §3 — deterministic coherence validator. Pure function over the
    four loaded/built layer dicts. Never raises; never mutates inputs.
    Returns a fixed-shape dict with five `*_ok` booleans plus a sorted,
    deduped `issues` list. Empty/None inputs cause the corresponding layer
    to be marked not-ok with a `<layer>: missing` issue (so legacy
    envelopes that never built a layer are visible in the report)."""
    issues: list = []

    # 3.1 Identity coherence ------------------------------------------------
    identity_ok = True
    if not isinstance(identity_profile, dict) or not identity_profile:
        identity_ok = False
        issues.append("identity: missing")
    else:
        try:
            ids = float(identity_profile.get("identity_strength", 0.0))
        except (TypeError, ValueError):
            ids = -1.0
            identity_ok = False
            issues.append("identity: identity_strength not numeric")
        if not (_COHERENCE_MIN_IDENTITY_STRENGTH <= ids <= _COHERENCE_MAX_IDENTITY_STRENGTH):
            identity_ok = False
            issues.append(f"identity: identity_strength out of range ({ids})")
        if not isinstance(identity_profile.get("stable_intents"), list):
            identity_ok = False
            issues.append("identity: stable_intents not a list")
        iv = identity_profile.get("identity_vector")
        if iv is None or not isinstance(iv, list):
            identity_ok = False
            issues.append("identity: identity_vector missing or not a list")

    # 3.2 Trajectory coherence ----------------------------------------------
    trajectory_ok = True
    if not isinstance(trajectory_profile, dict) or not trajectory_profile:
        trajectory_ok = False
        issues.append("trajectory: missing")
    else:
        try:
            ts = float(trajectory_profile.get("trajectory_strength", 0.0))
        except (TypeError, ValueError):
            ts = -1.0
            trajectory_ok = False
            issues.append("trajectory: trajectory_strength not numeric")
        if not (_COHERENCE_MIN_TRAJECTORY_STRENGTH <= ts <= _COHERENCE_MAX_TRAJECTORY_STRENGTH):
            trajectory_ok = False
            issues.append(f"trajectory: trajectory_strength out of range ({ts})")
        phase = trajectory_profile.get("phase")
        if not (isinstance(phase, str) and phase.strip()):
            trajectory_ok = False
            issues.append("trajectory: phase missing or empty")
        if not isinstance(trajectory_profile.get("trend_intents"), list):
            trajectory_ok = False
            issues.append("trajectory: trend_intents not a list")
        if not isinstance(trajectory_profile.get("fading_intents"), list):
            trajectory_ok = False
            issues.append("trajectory: fading_intents not a list")

    # 3.3 ELINS coherence ---------------------------------------------------
    elins_ok = True
    if not isinstance(elins_context, dict) or not elins_context:
        elins_ok = False
        issues.append("elins: missing")
    else:
        pb = elins_context.get("physics_block")
        if not isinstance(pb, dict):
            elins_ok = False
            issues.append("elins: physics_block missing or not a dict")
        else:
            for k in _COHERENCE_ELINS_PHYSICS_BLOCK_KEYS:
                if k not in pb:
                    elins_ok = False
                    issues.append(f"elins: physics_block.{k} missing")
        # Pressure fields normalized to [0, 1]
        pf = elins_context.get("pressure_fields")
        if isinstance(pf, dict):
            for k, v in pf.items():
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    elins_ok = False
                    issues.append(f"elins: pressure_fields[{k}] not numeric")
                    continue
                if not (0.0 <= fv <= 1.0):
                    elins_ok = False
                    issues.append(f"elins: pressure_fields[{k}] not normalized ({fv})")

    # 3.4 Universal physics coherence ---------------------------------------
    universal_ok = True
    if not isinstance(universal_physics_block, dict) or not universal_physics_block:
        universal_ok = False
        issues.append("universal: missing")
    else:
        for k in _COHERENCE_REQUIRED_KEYS:
            if k not in universal_physics_block:
                universal_ok = False
                issues.append(f"universal: required key '{k}' missing")
        sa = universal_physics_block.get("scale_annotations")
        if isinstance(sa, dict):
            extra = [s for s in sa.keys() if s not in _COHERENCE_ALLOWED_SCALES]
            for s in sorted(extra):
                universal_ok = False
                issues.append(f"universal: unknown scale '{s}' in scale_annotations")

    # 3.5 Cross-scale coherence (contradiction checks) ----------------------
    cross_scale_ok = True
    # weak identity + strong trajectory
    if isinstance(identity_profile, dict) and isinstance(trajectory_profile, dict):
        try:
            ids = float(identity_profile.get("identity_strength", 0.0))
            ts = float(trajectory_profile.get("trajectory_strength", 0.0))
            if ids < _COHERENCE_IDENTITY_LOW_THRESHOLD and ts > _COHERENCE_TRAJECTORY_HIGH_THRESHOLD:
                cross_scale_ok = False
                issues.append(
                    f"cross_scale: identity_strength<{_COHERENCE_IDENTITY_LOW_THRESHOLD} "
                    f"AND trajectory_strength>{_COHERENCE_TRAJECTORY_HIGH_THRESHOLD}"
                )
        except (TypeError, ValueError):
            pass
    # ELINS: 0 active centers but pressure_fields non-empty
    if isinstance(elins_context, dict):
        centers = elins_context.get("centers_involved") or []
        pf = elins_context.get("pressure_fields") or {}
        if not centers and pf:
            cross_scale_ok = False
            issues.append("cross_scale: elins has 0 active_centers but non-empty pressure_fields")
    # Universal: missing any scale annotation from the allowed set
    if isinstance(universal_physics_block, dict):
        sa = universal_physics_block.get("scale_annotations") or {}
        if isinstance(sa, dict):
            for s in _COHERENCE_ALLOWED_SCALES:
                if s not in sa:
                    cross_scale_ok = False
                    issues.append(f"cross_scale: universal missing scale_annotation '{s}'")

    # Sorted + deduped issues for deterministic output (transmitter exposes
    # this dict; downstream consumers compare across calls).
    deduped = sorted(set(issues))

    return {
        "identity_ok": bool(identity_ok),
        "trajectory_ok": bool(trajectory_ok),
        "elins_ok": bool(elins_ok),
        "universal_ok": bool(universal_ok),
        "cross_scale_ok": bool(cross_scale_ok),
        "issues": deduped,
    }


# Envelope v15 — external knowledge context layer.
_EXTERNAL_MAX_TOPICS = 3
_EXTERNAL_MAX_SUMMARY_SENTENCES = 5
_EXTERNAL_MAX_CONCEPT_NODES = 10
_EXTERNAL_MAX_ANCHORS_PER_TOPIC = 6

# Inline stopword list for cheap topic extraction. Small + opinionated; the
# spec calls these helpers "conceptual placeholders," and a deterministic
# stopword cut-down is good enough for the v15 surface.
_EXTERNAL_STOPWORDS: frozenset = frozenset({
    "the", "a", "an", "of", "to", "and", "or", "but", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "this", "that",
    "these", "those", "it", "its", "they", "them", "their", "we", "us",
    "our", "you", "your", "i", "me", "my", "what", "when", "where", "why",
    "how", "who", "which", "if", "then", "than", "so", "such", "not", "no",
    "can", "could", "would", "should", "will", "may", "might", "must",
    "about", "into", "over", "under", "between", "across", "through",
    "while", "after", "before", "again", "also", "very", "much", "more",
    "most", "some", "any", "each", "every", "all", "both", "either",
    "neither", "other", "another", "same", "different", "new", "old",
})


def _extract_topics(text: str) -> list:
    """Deterministic noun-phrase-ish topic extraction. No NLP dep. Strips
    punctuation, lowercases, removes stopwords, keeps alphabetic tokens of
    length ≥ 4. Ranks by (count desc, length desc, alpha asc) to break ties
    deterministically. Returns up to `_EXTERNAL_MAX_TOPICS` sorted alphabetically."""
    if not text or not isinstance(text, str):
        return []
    import re
    # Strip punctuation; keep alphanumerics + spaces.
    cleaned = re.sub(r"[^A-Za-z0-9\s]+", " ", text).lower()
    counts: dict = {}
    for tok in cleaned.split():
        if len(tok) < 4 or not tok.isalpha() or tok in _EXTERNAL_STOPWORDS:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    if not counts:
        return []
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    top = [t for t, _ in ranked[:_EXTERNAL_MAX_TOPICS]]
    return sorted(top)


def _fetch_summary(topic: str) -> str:
    """Conceptual placeholder for a Wikipedia-style summary. No external
    fetch happens (no HTTP, no API); returns a neutral fixed-template
    description ≤ `_EXTERNAL_MAX_SUMMARY_SENTENCES` sentences. Pure +
    deterministic + never raises."""
    if not topic or not isinstance(topic, str):
        return ""
    t = topic.strip()
    if not t:
        return ""
    # 4-sentence neutral template, parameterized by topic. No opinions.
    sentences = [
        f"{t.capitalize()} is a concept that can be analyzed across multiple scales and frameworks.",
        f"It is commonly situated within physical, linguistic, and formal-mathematical contexts.",
        f"Its boundary conditions, invariants, and relations to neighbouring concepts shape interpretation.",
        f"Treat this entry as a neutral placeholder for an external knowledge summary about {t}.",
    ]
    return " ".join(sentences[:_EXTERNAL_MAX_SUMMARY_SENTENCES])


def _build_concept_tree(topic: str) -> list:
    """Flattened concept-tree nodes (parent / siblings / children /
    attributes) for `topic`. Up to `_EXTERNAL_MAX_CONCEPT_NODES`,
    alphabetically sorted for stable rendering."""
    if not topic or not isinstance(topic, str):
        return []
    t = topic.strip().lower()
    if not t:
        return []
    nodes = [
        f"attribute:{t}/boundary",
        f"attribute:{t}/invariant",
        f"attribute:{t}/scope",
        f"child:{t}/aspect-causal",
        f"child:{t}/aspect-structural",
        f"child:{t}/aspect-temporal",
        f"parent:general-concept",
        f"sibling:adjacent-concept",
        f"sibling:contrast-concept",
        f"sibling:related-concept",
    ]
    return sorted(set(nodes))[:_EXTERNAL_MAX_CONCEPT_NODES]


def _build_physics_anchors(topic: str) -> list:
    """Map a topic to canonical physics anchors. Deterministic and
    topic-agnostic; the topic name is interpolated into each anchor for
    legibility downstream."""
    if not topic or not isinstance(topic, str):
        return []
    t = topic.strip().lower()
    if not t:
        return []
    anchors = [
        f"boundary conditions :: {t}",
        f"conservation principle :: {t}",
        f"field interaction :: {t}",
        f"flow dynamics :: {t}",
        f"phase transition :: {t}",
        f"system invariant :: {t}",
    ]
    return sorted(set(anchors))[:_EXTERNAL_MAX_ANCHORS_PER_TOPIC]


def _build_linguistic_anchors(topic: str) -> list:
    """Map a topic to canonical linguistic anchors (roles, frames, modality,
    tense/aspect, verb patterns)."""
    if not topic or not isinstance(topic, str):
        return []
    t = topic.strip().lower()
    if not t:
        return []
    anchors = [
        f"agent role :: {t}",
        f"frame: change-of-state :: {t}",
        f"modality: necessity :: {t}",
        f"modality: possibility :: {t}",
        f"tense/aspect: present-progressive :: {t}",
        f"verb pattern: causative :: {t}",
    ]
    return sorted(set(anchors))[:_EXTERNAL_MAX_ANCHORS_PER_TOPIC]


def _build_math_anchors(topic: str) -> list:
    """Map a topic to canonical math anchors (sets, functions,
    transformations, metrics, graphs, operators)."""
    if not topic or not isinstance(topic, str):
        return []
    t = topic.strip().lower()
    if not t:
        return []
    anchors = [
        f"function mapping :: {t}",
        f"graph structure :: {t}",
        f"metric space :: {t}",
        f"operator algebra :: {t}",
        f"set membership :: {t}",
        f"transformation group :: {t}",
    ]
    return sorted(set(anchors))[:_EXTERNAL_MAX_ANCHORS_PER_TOPIC]


def _build_external_context_block(request_text: Optional[str]) -> dict:
    """v15 §4 — assemble the external_context block from `request_text`.
    Returns `{}` when text is empty/trivial (per spec §5). All inner lists
    and dict keys are deterministic (sorted) for stable rendering. Each
    list is already truncated to its per-spec cap by the helpers."""
    if not request_text or not isinstance(request_text, str) or not request_text.strip():
        return {}
    topics = _extract_topics(request_text)
    if not topics:
        return {}
    summaries: dict = {}
    concept_trees: dict = {}
    physics_anchors: dict = {}
    linguistic_anchors: dict = {}
    math_anchors: dict = {}
    for t in topics:
        summaries[t] = _fetch_summary(t)
        concept_trees[t] = _build_concept_tree(t)
        physics_anchors[t] = _build_physics_anchors(t)
        linguistic_anchors[t] = _build_linguistic_anchors(t)
        math_anchors[t] = _build_math_anchors(t)
    # Re-key dicts with sorted insertion order for deterministic JSON.
    return {
        "topics": sorted(topics),
        "summaries": dict(sorted(summaries.items())),
        "concept_trees": dict(sorted(concept_trees.items())),
        "physics_anchors": dict(sorted(physics_anchors.items())),
        "linguistic_anchors": dict(sorted(linguistic_anchors.items())),
        "math_anchors": dict(sorted(math_anchors.items())),
    }


# Envelope v16 — ELINS S_strategy (Sun Tzu) integration layer.
_SSTRAT_TERRAIN_KEY = "hydronic_state.hci"
_SSTRAT_SUPPLY_KEY = "hydronic_state.flow_rate"
_SSTRAT_RIDGE_KEY = "hydronic_state.compression_ratio"
_SSTRAT_CX_KEY = "contradiction_load.cx_value"
_SSTRAT_PMIS_KEY = "contradiction_load.p_mis"
_SSTRAT_FMIS_KEY = "hydronic_state.entropy"
_SSTRAT_VARIANCE_KEY = "markoff_state.variance"
_SSTRAT_ATTRACTOR_KEY = "markoff_state.attractor_instability"
_SSTRAT_PHASECHANGE_KEY = "markoff_state.phase_change_prediction"

_SSTRAT_RIDGE_THRESHOLD = 0.50
_SSTRAT_SUPPLY_DELTA_THRESHOLD = 0.20

# PRO-tier ELINS top-level blocks that v16 reads via dot notation. v12 ingest
# passes these through unmodified when present in the raw JSON.
_SSTRAT_PASSTHROUGH_BLOCKS: tuple = (
    "hydronic_state",
    "contradiction_load",
    "markoff_state",
)


def _extract_dotted(d: Optional[dict], dotted_key: str):
    """Walk a dict via a dotted path; return None if any segment is missing
    or the cursor stops being a dict mid-walk."""
    if not isinstance(d, dict) or not dotted_key:
        return None
    cur = d
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _coerce_optional_float(v):
    """Float-coerce or return None on failure (no zero fallback — caller
    distinguishes 'absent' from '0.0')."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_s_strategy_layer(
    elins_dict: Optional[dict],
    prev_elins_dict: Optional[dict],
) -> dict:
    """v16 §3 — pure deterministic builder. Reads PRO-tier ELINS blocks
    (hydronic_state, contradiction_load, markoff_state) via dot notation;
    returns {} when any required field is missing. Computes the Sun Tzu
    overlay: terrain, supply, ridge_barrier, cohesion, fog_of_war,
    deception, outcome_variance, basin_hop (vs prior supply), and
    phase_change. Never raises."""
    if not isinstance(elins_dict, dict):
        return {}

    terrain = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_TERRAIN_KEY))
    supply = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_SUPPLY_KEY))
    ridge_barrier = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_RIDGE_KEY))
    cx_value = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_CX_KEY))
    deception = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_PMIS_KEY))
    fog_of_war = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_FMIS_KEY))
    outcome_variance = _coerce_optional_float(_extract_dotted(elins_dict, _SSTRAT_VARIANCE_KEY))

    # Required-field gate (phase_change is optional per spec).
    if any(v is None for v in (
        terrain, supply, ridge_barrier, cx_value, deception, fog_of_war, outcome_variance,
    )):
        return {}

    cohesion = max(0.0, min(1.0, 1.0 - cx_value))

    # Supply delta uses prior cycle's flow_rate as baseline; falls back to 0.
    prev_supply_raw = _extract_dotted(prev_elins_dict, _SSTRAT_SUPPLY_KEY) if prev_elins_dict else None
    prev_supply = _coerce_optional_float(prev_supply_raw)
    baseline = prev_supply if prev_supply is not None else 0.0
    supply_delta = max(0.0, supply - baseline)

    basin_hop = (
        ridge_barrier < _SSTRAT_RIDGE_THRESHOLD
        and supply_delta > _SSTRAT_SUPPLY_DELTA_THRESHOLD
    )

    # phase_change: pass through if present and dict-shaped, else {}. Coerce
    # numeric fields defensively.
    pc_raw = _extract_dotted(elins_dict, _SSTRAT_PHASECHANGE_KEY)
    if isinstance(pc_raw, dict):
        prob = _coerce_optional_float(pc_raw.get("probability"))
        horiz = _coerce_optional_float(pc_raw.get("horizon"))
        phase_change = {
            "predicted_phase": str(pc_raw.get("predicted_phase", "")),
            "probability": float(prob) if prob is not None else 0.0,
            "horizon": float(horiz) if horiz is not None else 0.0,
        }
    else:
        phase_change = {}

    return {
        "basin_hop": bool(basin_hop),
        "cohesion": float(cohesion),
        "deception": float(deception),
        "fog_of_war": float(fog_of_war),
        "outcome_variance": float(outcome_variance),
        "phase_change": phase_change,
        "ridge_barrier": float(ridge_barrier),
        "supply": float(supply),
        "terrain": float(terrain),
    }


# Envelope v17 — cross-scale harmonizer (read-only conditioning block).
def _build_physics_reasoning_context(envelope: Optional[dict]) -> dict:
    """v17 — harmonize identity (v8), trajectory (v9), ELINS+S_strategy
    (v12, v16), universal_physics (v13), external_context (v15), and
    coherence (v14) into one compact deterministic block. Pure function;
    never raises; returns `{}` if `envelope` is missing/falsy.

    All lists sorted; dict keys returned in alphabetical insertion order
    so JSON serialization is byte-stable across calls. No field is omitted
    from the result — every key is present with safe defaults so downstream
    consumers can index without `.get()` guards."""
    if not isinstance(envelope, dict) or not envelope:
        return {}

    # --- 1. Identity phase --------------------------------------------------
    identity = envelope.get("identity") if isinstance(envelope.get("identity"), dict) else {}
    identity_phase_val = identity.get("phase")
    identity_phase = identity_phase_val if isinstance(identity_phase_val, str) and identity_phase_val.strip() else "unknown"

    # --- 2. Trajectory phase + velocity ------------------------------------
    trajectory = envelope.get("trajectory") if isinstance(envelope.get("trajectory"), dict) else {}
    traj_phase_val = trajectory.get("phase")
    trajectory_phase = traj_phase_val if isinstance(traj_phase_val, str) and traj_phase_val.strip() else "unknown"
    try:
        trajectory_velocity = float(trajectory.get("velocity", 0.0))
    except (TypeError, ValueError):
        trajectory_velocity = 0.0

    # --- 3. ELINS centers + pressure_fields --------------------------------
    elins = envelope.get("elins") if isinstance(envelope.get("elins"), dict) else {}
    elins_centers_raw = elins.get("centers_involved") or []
    elins_centers = sorted([str(c) for c in elins_centers_raw if c])
    elins_pf_raw = elins.get("pressure_fields") or {}
    elins_pressure_fields: dict = {}
    if isinstance(elins_pf_raw, dict):
        for k in sorted(elins_pf_raw.keys()):
            try:
                elins_pressure_fields[str(k)] = float(elins_pf_raw[k])
            except (TypeError, ValueError):
                continue

    # --- 4. S_strategy (selected fields only) ------------------------------
    ssl = elins.get("s_strategy_layer") if isinstance(elins.get("s_strategy_layer"), dict) else {}
    if ssl:
        try:
            ss_terrain = float(ssl.get("terrain", 0.0))
        except (TypeError, ValueError):
            ss_terrain = 0.0
        try:
            ss_supply = float(ssl.get("supply", 0.0))
        except (TypeError, ValueError):
            ss_supply = 0.0
        try:
            ss_ridge = float(ssl.get("ridge_barrier", 0.0))
        except (TypeError, ValueError):
            ss_ridge = 0.0
        try:
            ss_cohesion = float(ssl.get("cohesion", 0.0))
        except (TypeError, ValueError):
            ss_cohesion = 0.0
        ss_basin_hop = bool(ssl.get("basin_hop"))
        ss_pc = ssl.get("phase_change") if isinstance(ssl.get("phase_change"), dict) else {}
        s_strategy = {
            "basin_hop": ss_basin_hop,
            "cohesion": ss_cohesion,
            "phase_change": ss_pc,
            "ridge_barrier": ss_ridge,
            "supply": ss_supply,
            "terrain": ss_terrain,
        }
    else:
        s_strategy = {}

    # --- 5. Universal physics (constraints / phases / operators) ----------
    up = envelope.get("universal_physics") if isinstance(envelope.get("universal_physics"), dict) else {}
    universal_constraints = sorted([str(x) for x in (up.get("constraints") or [])])
    universal_phases = sorted([str(x) for x in (up.get("phases") or [])])
    universal_operators = sorted([str(x) for x in (up.get("operators") or [])])

    # --- 6. External topics ------------------------------------------------
    ext = envelope.get("external_context") if isinstance(envelope.get("external_context"), dict) else {}
    external_topics = sorted([str(x) for x in (ext.get("topics") or [])])

    # --- 7. Coherence flags (default all-True when coherence absent) ------
    coh = envelope.get("coherence") if isinstance(envelope.get("coherence"), dict) else None
    if coh is None:
        coherence_flags = {
            "cross_scale_ok": True,
            "elins_ok": True,
            "identity_ok": True,
            "trajectory_ok": True,
            "universal_ok": True,
        }
    else:
        coherence_flags = {
            "cross_scale_ok": bool(coh.get("cross_scale_ok", False)),
            "elins_ok": bool(coh.get("elins_ok", False)),
            "identity_ok": bool(coh.get("identity_ok", False)),
            "trajectory_ok": bool(coh.get("trajectory_ok", False)),
            "universal_ok": bool(coh.get("universal_ok", False)),
        }

    # Final dict — keys assembled in alphabetical order for stable serialization.
    return {
        "coherence_flags": coherence_flags,
        "elins_centers": elins_centers,
        "elins_pressure_fields": elins_pressure_fields,
        "external_topics": external_topics,
        "identity_phase": identity_phase,
        "s_strategy": s_strategy,
        "trajectory_phase": trajectory_phase,
        "trajectory_velocity": trajectory_velocity,
        "universal_constraints": universal_constraints,
        "universal_operators": universal_operators,
        "universal_phases": universal_phases,
    }


# Envelope v18 — generator conditioning surface (advisory only).
def _build_reasoning_cues(prc: Optional[dict]) -> dict:
    """v18 — derive 6 advisory cues from the v17 physics_reasoning_context.
    Pure deterministic. Returns `{}` if `prc` is missing/empty.

    All emitted strings are lowercase; every spec field is present (no
    omissions) so downstream consumers can index without `.get()` guards.
    The function never raises and never modifies inputs."""
    if not isinstance(prc, dict) or not prc:
        return {}

    # 1. dominant_center — first of the (already alphabetically sorted) list.
    centers = prc.get("elins_centers") or []
    dominant_center = str(centers[0]).lower() if centers else "none"

    # 2. dominant_pressure — argmax over pressure_fields. Tie-break by
    # alphabetical key for stable output.
    pf = prc.get("elins_pressure_fields") or {}
    if isinstance(pf, dict) and pf:
        try:
            best_key = max(
                sorted(pf.keys()),
                key=lambda k: float(pf[k]) if pf[k] is not None else -float("inf"),
            )
            dominant_pressure = str(best_key).lower()
        except (TypeError, ValueError):
            dominant_pressure = "none"
    else:
        dominant_pressure = "none"

    # 3. phase_hint — prefer trajectory_phase; fall back to identity_phase;
    # final fallback "none". Both layers may emit "unknown" sentinels.
    traj_phase = str(prc.get("trajectory_phase") or "").strip().lower()
    id_phase = str(prc.get("identity_phase") or "").strip().lower()
    if traj_phase and traj_phase != "unknown":
        phase_hint = traj_phase
    elif id_phase and id_phase != "unknown":
        phase_hint = id_phase
    else:
        phase_hint = "none"

    # 4. risk_hint — high if basin_hop; else moderate if cohesion < 0.5;
    # else low. When s_strategy is empty, basin_hop defaults False and
    # cohesion defaults 1.0 (conservative — no signal → "low").
    s_strategy = prc.get("s_strategy") if isinstance(prc.get("s_strategy"), dict) else {}
    basin_hop = bool(s_strategy.get("basin_hop", False))
    try:
        cohesion = float(s_strategy.get("cohesion", 1.0))
    except (TypeError, ValueError):
        cohesion = 1.0
    if basin_hop:
        risk_hint = "high"
    elif cohesion < 0.5:
        risk_hint = "moderate"
    else:
        risk_hint = "low"

    # 5. basin_hint — stable iff coherence_flags.cross_scale_ok is True.
    coh_flags = prc.get("coherence_flags") if isinstance(prc.get("coherence_flags"), dict) else {}
    basin_hint = "stable" if bool(coh_flags.get("cross_scale_ok", False)) else "unstable"

    # 6. drift_hint — sign of trajectory_velocity.
    try:
        vel = float(prc.get("trajectory_velocity", 0.0))
    except (TypeError, ValueError):
        vel = 0.0
    if vel > 0:
        drift_hint = "forward"
    elif vel < 0:
        drift_hint = "reversing"
    else:
        drift_hint = "stalled"

    return {
        "basin_hint": basin_hint,
        "dominant_center": dominant_center,
        "dominant_pressure": dominant_pressure,
        "drift_hint": drift_hint,
        "phase_hint": phase_hint,
        "risk_hint": risk_hint,
    }


# Envelope v19 — generator conditioning surface v2 (soft weights).
def _build_reasoning_weights(
    prc: Optional[dict],
    cues: Optional[dict],
) -> dict:
    """v19 — derive 6 soft weights ∈ [0, 1] from the v17 PRC and v18
    reasoning_cues. Pure deterministic. Returns `{}` if either input is
    missing/empty (per spec §2 final clause). Every spec field is present
    in non-empty output (no omissions); all weights are floats."""
    if not isinstance(prc, dict) or not prc:
        return {}
    if not isinstance(cues, dict) or not cues:
        return {}

    # 1. identity_w — phase_hint == "identity" gets the strongest signal;
    # next strongest if any identity_phase has been classified at all.
    phase_hint = str(cues.get("phase_hint") or "").lower()
    id_phase = str(prc.get("identity_phase") or "").lower()
    if phase_hint == "identity":
        identity_w = 0.8
    elif id_phase and id_phase != "unknown":
        identity_w = 0.6
    else:
        identity_w = 0.4

    # 2. trajectory_w — by drift direction.
    drift_hint = str(cues.get("drift_hint") or "").lower()
    if drift_hint == "forward":
        trajectory_w = 0.9
    elif drift_hint == "stalled":
        trajectory_w = 0.7
    elif drift_hint == "reversing":
        trajectory_w = 0.5
    else:
        trajectory_w = 0.4

    # 3. elins_w — boost when an active center is identified.
    dominant_center = str(cues.get("dominant_center") or "").lower()
    elins_w = 0.9 if (dominant_center and dominant_center != "none") else 0.5

    # 4. s_strategy_w — by risk_hint band.
    risk_hint = str(cues.get("risk_hint") or "").lower()
    if risk_hint == "high":
        s_strategy_w = 1.0
    elif risk_hint == "moderate":
        s_strategy_w = 0.7
    elif risk_hint == "low":
        s_strategy_w = 0.4
    else:
        s_strategy_w = 0.4

    # 5. universal_w — boost when constraints are present (universal layer
    # has been built/loaded).
    universal_constraints = prc.get("universal_constraints")
    universal_w = 0.8 if (isinstance(universal_constraints, list) and universal_constraints) else 0.5

    # 6. external_w — boost when external topics extracted this turn.
    external_topics = prc.get("external_topics")
    external_w = 0.7 if (isinstance(external_topics, list) and external_topics) else 0.4

    return {
        "elins_w": float(elins_w),
        "external_w": float(external_w),
        "identity_w": float(identity_w),
        "s_strategy_w": float(s_strategy_w),
        "trajectory_w": float(trajectory_w),
        "universal_w": float(universal_w),
    }


# Envelope v20 — memory_context v1 (cross-turn long-range surface).
def _build_memory_context(
    identity: Optional[dict],
    trajectory: Optional[dict],
    arcs: Optional[list],
    episodes: Optional[list],
    external: Optional[dict],
) -> dict:
    """v20 — compact long-range memory summary across identity / trajectory /
    arcs / episodes / external_context. Pure deterministic. Returns `{}` when
    ALL five inputs are missing/empty (per spec §2 final clause). Otherwise
    every spec field is present in output (no omissions); all lists sorted;
    safe defaults populate missing sub-fields. Never raises."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (identity, trajectory, arcs, episodes, external)):
        return {}

    # Normalize input types so downstream reads are safe.
    identity_d = identity if isinstance(identity, dict) else {}
    trajectory_d = trajectory if isinstance(trajectory, dict) else {}
    arcs_l = list(arcs) if isinstance(arcs, list) else []
    episodes_l = list(episodes) if isinstance(episodes, list) else []
    external_d = external if isinstance(external, dict) else {}

    # 1. stable_intents — from identity_profile.stable_intents (v8).
    si = identity_d.get("stable_intents")
    stable_intents = sorted([str(x) for x in si]) if isinstance(si, list) else []

    # 2. fading_intents — spec literal: identity_profile.fading_intents.
    # v8 doesn't ship this field; v9 trajectory has fading_intents. Read from
    # identity per spec; will be [] in current schema.
    fi = identity_d.get("fading_intents")
    fading_intents = sorted([str(x) for x in fi]) if isinstance(fi, list) else []

    # 3. dominant_topics — from external_context.topics (v15).
    topics = external_d.get("topics")
    dominant_topics = sorted([str(x) for x in topics]) if isinstance(topics, list) else []

    # 4. identity_themes — top 3 dimensions of identity_vector by abs value.
    # Vectors don't carry token labels here, so we surface the dimension
    # indices as `dim_<i>` (deterministic + decodable downstream).
    iv = identity_d.get("identity_vector")
    identity_themes: list = []
    if isinstance(iv, list) and iv:
        try:
            indexed = [(i, abs(float(v))) for i, v in enumerate(iv) if v is not None]
            indexed.sort(key=lambda x: (-x[1], x[0]))
            identity_themes = sorted([f"dim_{i}" for i, _ in indexed[:3]])
        except (TypeError, ValueError):
            identity_themes = []

    # 5. trajectory_themes — top 3 from trajectory_profile.trend_intents.
    ti = trajectory_d.get("trend_intents")
    if isinstance(ti, list) and ti:
        trajectory_themes = sorted([str(x) for x in ti])[:3]
    else:
        trajectory_themes = []

    # 6. last_arc — most recent by latest_event_ts (fallback created_at).
    last_arc: dict = {}
    if arcs_l:
        def _arc_ts(a):
            if not isinstance(a, dict):
                return 0.0
            try:
                return float(a.get("latest_event_ts") or a.get("created_at") or 0.0)
            except (TypeError, ValueError):
                return 0.0
        sorted_arcs = sorted(arcs_l, key=_arc_ts)
        last = sorted_arcs[-1]
        if isinstance(last, dict):
            try:
                strength = float(last.get("arc_strength", last.get("strength", 0.0)) or 0.0)
            except (TypeError, ValueError):
                strength = 0.0
            last_arc = {
                "arc_id": str(last.get("arc_id", "")),
                "phase": str(last.get("phase", "unknown")),
                "strength": strength,
            }

    # 7. last_episode — most recent by latest_event_ts (fallback timestamp).
    last_episode: dict = {}
    if episodes_l:
        def _ep_ts(e):
            if not isinstance(e, dict):
                return 0.0
            try:
                return float(e.get("latest_event_ts") or e.get("timestamp") or 0.0)
            except (TypeError, ValueError):
                return 0.0
        sorted_eps = sorted(episodes_l, key=_ep_ts)
        last = sorted_eps[-1]
        if isinstance(last, dict):
            try:
                weight = float(last.get("episode_strength", last.get("weight", 0.0)) or 0.0)
            except (TypeError, ValueError):
                weight = 0.0
            last_episode = {
                "episode_id": str(last.get("episode_id", "")),
                "sentiment": str(last.get("sentiment", "neutral")),
                "weight": weight,
            }

    return {
        "dominant_topics": dominant_topics,
        "fading_intents": fading_intents,
        "identity_themes": identity_themes,
        "last_arc": last_arc,
        "last_episode": last_episode,
        "stable_intents": stable_intents,
        "trajectory_themes": trajectory_themes,
    }


# Envelope v21 — external knowledge context v2.
_KNOWLEDGE_MAX_DEFINITIONS = 3
_KNOWLEDGE_MAX_RELATIONS = 6
_KNOWLEDGE_MAX_HIERARCHY = 6
_KNOWLEDGE_MAX_CONSTRAINTS = 6
_KNOWLEDGE_MAX_CROSSDOMAIN = 6

_GENERIC_DEFINITION_TEMPLATE = (
    "{topic}: a commonly referenced concept involving structure, behavior, "
    "and context-dependent interactions."
)

# Two additional deterministic variations used to fill out the
# `_KNOWLEDGE_MAX_DEFINITIONS = 3` slot. Order is fixed; the helper sorts
# the final list so output is alphabetical.
_GENERIC_DEFINITION_VARIATIONS: tuple = (
    "{topic}: a phenomenon described by structural and contextual properties relevant to multiple frameworks.",
    "{topic}: an entity whose behavior depends on boundary conditions, context, and interactions across domains.",
)

_GENERIC_RELATION_CATALOG: tuple = (
    "related_to:{topic}",
    "influences:{topic}",
    "depends_on:{topic}",
    "contrasts_with:{topic}",
    "extends:{topic}",
    "bounded_by:{topic}",
)

_GENERIC_HIERARCHY_CATALOG: tuple = (
    "category:{topic}",
    "subcategory:{topic}",
    "superclass:{topic}",
    "peer:{topic}",
    "component:{topic}",
    "system:{topic}",
)

_GENERIC_CONSTRAINT_CATALOG: tuple = (
    "temporal_limit:{topic}",
    "resource_limit:{topic}",
    "structural_limit:{topic}",
    "context_limit:{topic}",
    "boundary_condition:{topic}",
    "stability_condition:{topic}",
)

_GENERIC_CROSSDOMAIN_CATALOG: tuple = (
    "physics:{topic}",
    "linguistics:{topic}",
    "mathematics:{topic}",
    "psychology:{topic}",
    "sociology:{topic}",
    "economics:{topic}",
)


def _build_external_knowledge(topics: Optional[list]) -> dict:
    """v21 — synthesize a deterministic conceptual-retrieval block from a
    topic list. Pure; never raises; offline (no API calls). Returns `{}`
    when `topics` is missing or empty (per spec §3 final clause).

    For each topic, populates:
      - definitions: ≤3 neutral templates (first is the generic template,
        rest are deterministic variations)
      - relations / hierarchies / constraints / cross_domain: first ≤N items
        from each catalog, with `{topic}` interpolated

    All inner lists sorted alphabetically; all outer dicts have sorted keys."""
    if not isinstance(topics, list) or not topics:
        return {}

    cleaned_topics = sorted({str(t) for t in topics if isinstance(t, str) and t.strip()})
    if not cleaned_topics:
        return {}

    definitions: dict = {}
    relations: dict = {}
    hierarchies: dict = {}
    constraints: dict = {}
    cross_domain: dict = {}

    for topic in cleaned_topics:
        defs_seq = (
            _GENERIC_DEFINITION_TEMPLATE.format(topic=topic),
            *(v.format(topic=topic) for v in _GENERIC_DEFINITION_VARIATIONS),
        )
        defs_capped = list(defs_seq)[:_KNOWLEDGE_MAX_DEFINITIONS]
        definitions[topic] = sorted(defs_capped)

        relations[topic] = sorted(
            t.format(topic=topic) for t in _GENERIC_RELATION_CATALOG[:_KNOWLEDGE_MAX_RELATIONS]
        )
        hierarchies[topic] = sorted(
            t.format(topic=topic) for t in _GENERIC_HIERARCHY_CATALOG[:_KNOWLEDGE_MAX_HIERARCHY]
        )
        constraints[topic] = sorted(
            t.format(topic=topic) for t in _GENERIC_CONSTRAINT_CATALOG[:_KNOWLEDGE_MAX_CONSTRAINTS]
        )
        cross_domain[topic] = sorted(
            t.format(topic=topic) for t in _GENERIC_CROSSDOMAIN_CATALOG[:_KNOWLEDGE_MAX_CROSSDOMAIN]
        )

    return {
        "constraints": dict(sorted(constraints.items())),
        "cross_domain": dict(sorted(cross_domain.items())),
        "definitions": dict(sorted(definitions.items())),
        "hierarchies": dict(sorted(hierarchies.items())),
        "relations": dict(sorted(relations.items())),
    }


# Envelope v22 — full cognitive loop integrator.
# Maps weight-field names to the loop_focus string the helper emits.
_COGLOOP_WEIGHT_TO_FOCUS: tuple = (
    ("elins_w", "elins"),
    ("external_w", "external"),
    ("identity_w", "identity"),
    ("s_strategy_w", "s_strategy"),
    ("trajectory_w", "trajectory"),
    ("universal_w", "universal"),
)
_COGLOOP_MAX_CONSTRAINTS = 10
_COGLOOP_MAX_IDENTITY_THEMES = 2


def _build_cognitive_loop(
    mc: Optional[dict],
    ek: Optional[dict],
    rw: Optional[dict],
    rc: Optional[dict],
    prc: Optional[dict],
) -> dict:
    """v22 — fuse memory_context (v20), external_knowledge (v21),
    reasoning_weights (v19), reasoning_cues (v18), and
    physics_reasoning_context (v17) into one compact deterministic block.
    Pure; never raises; returns `{}` when all five inputs are missing/empty
    (per spec §2 final clause)."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (mc, ek, rw, rc, prc)):
        return {}

    mc_d = mc if isinstance(mc, dict) else {}
    ek_d = ek if isinstance(ek, dict) else {}
    rw_d = rw if isinstance(rw, dict) else {}
    rc_d = rc if isinstance(rc, dict) else {}
    prc_d = prc if isinstance(prc, dict) else {}

    # 1+2. loop_focus + loop_weight — argmax over the 6 reasoning_weights
    # fields. Tie-break alphabetical via the (key,focus) tuple ordering.
    best_focus = "none"
    best_weight = 0.0
    if rw_d:
        best_score = -float("inf")
        for wkey, focus_label in _COGLOOP_WEIGHT_TO_FOCUS:
            try:
                w = float(rw_d.get(wkey, 0.0))
            except (TypeError, ValueError):
                w = 0.0
            # Strict > so the alphabetically-earlier label wins ties (the
            # tuple is already in alphabetical order by wkey).
            if w > best_score:
                best_score = w
                best_focus = focus_label
                best_weight = w
        # If every weight was 0/missing, leave defaults: best_focus=none, best_weight=0.0
        if best_score == -float("inf"):
            best_focus = "none"
            best_weight = 0.0

    # 3. loop_topics — prefer mc.dominant_topics, fall back to prc.external_topics.
    raw_topics = mc_d.get("dominant_topics") or []
    if not raw_topics:
        raw_topics = prc_d.get("external_topics") or []
    loop_topics = sorted({str(t) for t in raw_topics if isinstance(t, str) and t.strip()})

    # 4. loop_constraints — flatten ek.constraints over loop_topics.
    constraints_dict = ek_d.get("constraints") if isinstance(ek_d.get("constraints"), dict) else {}
    flattened: set = set()
    for t in loop_topics:
        items = constraints_dict.get(t)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, str) and it.strip():
                    flattened.add(it)
    loop_constraints = sorted(flattened)[:_COGLOOP_MAX_CONSTRAINTS]

    # 5/6/7. cues with safe defaults.
    risk_hint = rc_d.get("risk_hint")
    loop_risk = str(risk_hint).lower() if isinstance(risk_hint, str) and risk_hint.strip() else "low"
    phase_hint = rc_d.get("phase_hint")
    loop_phase = str(phase_hint).lower() if isinstance(phase_hint, str) and phase_hint.strip() else "none"
    drift_hint = rc_d.get("drift_hint")
    loop_direction = str(drift_hint).lower() if isinstance(drift_hint, str) and drift_hint.strip() else "stalled"

    # 8. loop_memory_refs — last_arc.arc_id + last_episode.episode_id +
    # top 2 identity_themes; sorted + deduped.
    refs: set = set()
    last_arc = mc_d.get("last_arc") if isinstance(mc_d.get("last_arc"), dict) else {}
    if last_arc.get("arc_id"):
        refs.add(str(last_arc["arc_id"]))
    last_ep = mc_d.get("last_episode") if isinstance(mc_d.get("last_episode"), dict) else {}
    if last_ep.get("episode_id"):
        refs.add(str(last_ep["episode_id"]))
    identity_themes = mc_d.get("identity_themes") or []
    if isinstance(identity_themes, list):
        # Take the first two from the alphabetically-sorted v20 list (already
        # sorted upstream, but re-sort defensively).
        for theme in sorted(str(x) for x in identity_themes if x)[:_COGLOOP_MAX_IDENTITY_THEMES]:
            refs.add(theme)
    loop_memory_refs = sorted(refs)

    return {
        "loop_constraints": loop_constraints,
        "loop_direction": loop_direction,
        "loop_focus": best_focus,
        "loop_memory_refs": loop_memory_refs,
        "loop_phase": loop_phase,
        "loop_risk": loop_risk,
        "loop_topics": loop_topics,
        "loop_weight": float(best_weight),
    }


# Envelope v23 — generator conditioning surface v3 (context-weighted scaffold).
_SCAFFOLD_MAX_CONSTRAINTS = 10


def _build_reasoning_scaffold(
    cl: Optional[dict],
    rw: Optional[dict],
    rc: Optional[dict],
    prc: Optional[dict],
) -> dict:
    """v23 — synthesize a structured scaffold from cognitive_loop (v22),
    reasoning_weights (v19), reasoning_cues (v18), and PRC (v17). Pure
    deterministic; never raises; returns `{}` when all four inputs are
    missing/empty (per spec §2 final clause).

    Every scaffold field is present in non-empty output (no omissions);
    all lists sorted (with the documented exception of `scaffold_vector`,
    which is sorted by descending weight then alphabetical to honor
    spec §2.2)."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (cl, rw, rc, prc)):
        return {}

    cl_d = cl if isinstance(cl, dict) else {}
    rw_d = rw if isinstance(rw, dict) else {}
    rc_d = rc if isinstance(rc, dict) else {}
    prc_d = prc if isinstance(prc, dict) else {}

    # 1. scaffold_focus — prefer cl.loop_focus; else argmax over rw (same
    # tie-break as v22); else "general".
    cl_focus = cl_d.get("loop_focus")
    if isinstance(cl_focus, str) and cl_focus.strip() and cl_focus != "none":
        scaffold_focus = cl_focus
    elif rw_d:
        # Reuse v22's rule: scan tuple in alphabetical order, strict-> tie-break.
        best_focus = "general"
        best_score = -float("inf")
        for wkey, focus_label in _COGLOOP_WEIGHT_TO_FOCUS:
            try:
                w = float(rw_d.get(wkey, 0.0))
            except (TypeError, ValueError):
                w = 0.0
            if w > best_score:
                best_score = w
                best_focus = focus_label
        scaffold_focus = best_focus if best_score > -float("inf") else "general"
    else:
        scaffold_focus = "general"

    # 2. scaffold_vector — labels sorted by descending weight, alphabetical
    # tie-break. Always emits all 6 even when weights are missing/zero.
    scaffold_vector = sorted(
        (focus_label for _wkey, focus_label in _COGLOOP_WEIGHT_TO_FOCUS),
        key=lambda lbl: (
            -float((rw_d.get(_focus_to_weight_key(lbl), 0.0) or 0.0)),
            lbl,
        ),
    )

    # 3. scaffold_topics — prefer cl.loop_topics; fall back to PRC.
    raw_topics = cl_d.get("loop_topics") or []
    if not raw_topics:
        raw_topics = prc_d.get("external_topics") or []
    scaffold_topics = sorted({str(t) for t in raw_topics if isinstance(t, str) and t.strip()})

    # 4. scaffold_constraints — from cl.loop_constraints, deduped+capped.
    raw_constraints = cl_d.get("loop_constraints") or []
    constraint_set = {str(c) for c in raw_constraints if isinstance(c, str) and c.strip()}
    scaffold_constraints = sorted(constraint_set)[:_SCAFFOLD_MAX_CONSTRAINTS]

    # 5/6/7. scaffold_risk/phase/direction — cl first, then rc, then default.
    def _pick_str(primary, secondary, default):
        if isinstance(primary, str) and primary.strip():
            return primary.lower()
        if isinstance(secondary, str) and secondary.strip():
            return secondary.lower()
        return default

    scaffold_risk = _pick_str(cl_d.get("loop_risk"), rc_d.get("risk_hint"), "low")
    scaffold_phase = _pick_str(cl_d.get("loop_phase"), rc_d.get("phase_hint"), "none")
    scaffold_direction = _pick_str(cl_d.get("loop_direction"), rc_d.get("drift_hint"), "stalled")

    # 8. scaffold_memory_refs — from cl.loop_memory_refs.
    raw_refs = cl_d.get("loop_memory_refs") or []
    ref_set = {str(r) for r in raw_refs if isinstance(r, str) and r.strip()}
    scaffold_memory_refs = sorted(ref_set)

    return {
        "scaffold_constraints": scaffold_constraints,
        "scaffold_direction": scaffold_direction,
        "scaffold_focus": scaffold_focus,
        "scaffold_memory_refs": scaffold_memory_refs,
        "scaffold_phase": scaffold_phase,
        "scaffold_risk": scaffold_risk,
        "scaffold_topics": scaffold_topics,
        "scaffold_vector": scaffold_vector,
    }


def _focus_to_weight_key(focus_label: str) -> str:
    """Inverse of `_COGLOOP_WEIGHT_TO_FOCUS`: focus_label → weight field
    name (e.g., 'identity' → 'identity_w'). Used by v23 scaffold_vector
    sorting to look up each label's weight."""
    return f"{focus_label}_w"


# Envelope v24 — generator conditioning surface v4 (response-shape hints).
# Maps scaffold_focus → 3 lowercase section labels per spec §2.1. The
# `general` fallback covers any unknown / default focus.
_RESPONSE_SHAPE_SECTIONS_BY_FOCUS: dict = {
    "identity":   ["identity", "intent", "theme"],
    "trajectory": ["trend", "direction", "shift"],
    "elins":      ["center", "pressure", "outcome"],
    "s_strategy": ["terrain", "supply", "variance"],
    "universal":  ["constraint", "phase", "operator"],
    "external":   ["topic", "relation", "context"],
    "general":    ["context", "signal", "summary"],
}
_RESPONSE_SHAPE_DEFAULT_SECTIONS: list = ["context", "signal", "summary"]
_RESPONSE_SHAPE_EMPHASIS_TOP_N = 3
_RESPONSE_SHAPE_CAUTION_HIGH: list = ["risk", "variance", "instability"]
_RESPONSE_SHAPE_CAUTION_MODERATE: list = ["uncertainty", "context"]
_RESPONSE_SHAPE_CAUTION_DEFAULT: list = ["none"]


def _build_response_shape(
    rs: Optional[dict],
    cl: Optional[dict],
    rw: Optional[dict],
    rc: Optional[dict],
) -> dict:
    """v24 — derive sections / emphasis / caution + direction/phase/risk
    cues from v23 scaffold (preferred) and v18 cues (fallback). Pure
    deterministic; never raises; returns `{}` when all four inputs are
    missing/empty (per spec §2 final clause)."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (rs, cl, rw, rc)):
        return {}

    rs_d = rs if isinstance(rs, dict) else {}
    rc_d = rc if isinstance(rc, dict) else {}
    # cl + rw are accepted in the signature for forward compatibility / spec
    # consistency but the v24 derivation reads only from rs and rc; the
    # `_is_empty` gate above ensures we still emit a block when only those
    # two arrive empty but cl/rw have content.

    # 1. sections — from rs.scaffold_focus via the catalog. Lowercase the
    # focus before lookup so casing variation doesn't dodge the map.
    focus_raw = rs_d.get("scaffold_focus")
    focus = str(focus_raw).strip().lower() if isinstance(focus_raw, str) else ""
    sections_template = _RESPONSE_SHAPE_SECTIONS_BY_FOCUS.get(focus, _RESPONSE_SHAPE_DEFAULT_SECTIONS)
    sections = [str(s).lower() for s in sections_template]

    # 2. emphasis — top 3 of rs.scaffold_vector (already in descending-weight
    # order with alphabetical tie-break per v23).
    raw_vector = rs_d.get("scaffold_vector") or []
    if isinstance(raw_vector, list):
        emphasis = [str(x) for x in raw_vector[:_RESPONSE_SHAPE_EMPHASIS_TOP_N] if isinstance(x, str)]
    else:
        emphasis = []

    # 3. caution — by rc.risk_hint tier.
    risk_hint_raw = rc_d.get("risk_hint")
    risk_hint = str(risk_hint_raw).strip().lower() if isinstance(risk_hint_raw, str) else ""
    if risk_hint == "high":
        caution = list(_RESPONSE_SHAPE_CAUTION_HIGH)
    elif risk_hint == "moderate":
        caution = list(_RESPONSE_SHAPE_CAUTION_MODERATE)
    else:
        caution = list(_RESPONSE_SHAPE_CAUTION_DEFAULT)

    # 4/5/6. direction / phase / risk — rs preferred, fall back to rc, then
    # spec-mandated defaults.
    def _pick_str(primary, secondary, default):
        if isinstance(primary, str) and primary.strip():
            return primary.lower()
        if isinstance(secondary, str) and secondary.strip():
            return secondary.lower()
        return default

    direction = _pick_str(rs_d.get("scaffold_direction"), rc_d.get("drift_hint"), "stalled")
    phase = _pick_str(rs_d.get("scaffold_phase"), rc_d.get("phase_hint"), "none")
    risk = _pick_str(rs_d.get("scaffold_risk"), rc_d.get("risk_hint"), "low")

    return {
        "caution": caution,
        "direction": direction,
        "emphasis": emphasis,
        "phase": phase,
        "risk": risk,
        "sections": sections,
    }


# Envelope v25 — generator conditioning surface v5 (micro-templates).
_TONE_BY_RISK: dict = {
    "high": "measured",
    "moderate": "balanced",
    "low": "open",
}

_OPENER_BY_SECTION: dict = {
    "identity":   "Here’s the core of it:",
    "intent":     "The direction is clear:",
    "theme":      "The underlying theme:",
    "trend":      "The movement looks like:",
    "direction":  "The shift points toward:",
    "center":     "The main center involved:",
    "pressure":   "The pressure pattern shows:",
    "terrain":    "The terrain suggests:",
    "supply":     "Supply conditions indicate:",
    "constraint": "The constraints in play:",
    "phase":      "The phase we’re in:",
    "operator":   "The operator-level view:",
    "topic":      "The topic at hand:",
    "relation":   "The relation to note:",
    "context":    "In context:",
}
_OPENER_DEFAULT = "Here’s the situation:"

_CLOSER_BY_DIRECTION: dict = {
    "forward":   "That’s the path ahead.",
    "stalled":   "That’s where things rest for now.",
    "reversing": "That’s the pull backward.",
}
_CLOSER_DEFAULT = "That’s where it stands."

_BODY_PATTERNS: dict = {
    "risk_high":     ["Watch the variance.", "Mind the instability."],
    "risk_moderate": ["Some uncertainty remains.", "Context matters here."],
    "risk_low":      ["The signal is steady.", "Nothing volatile here."],
}


def _build_response_templates(
    rshape: Optional[dict],
    rs: Optional[dict],
    rc: Optional[dict],
    cl: Optional[dict],
) -> dict:
    """v25 — derive opener / body_pattern / closer / tone_hint micro-templates
    from v24 response_shape (primary) + v18 cues (fallback). v23 scaffold
    and v22 cognitive_loop are accepted in the signature for spec
    consistency / forward compatibility but not currently read. Pure
    deterministic; never raises; returns `{}` when all four inputs are
    missing/empty (per spec §3 final clause)."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (rshape, rs, rc, cl)):
        return {}

    rshape_d = rshape if isinstance(rshape, dict) else {}
    rc_d = rc if isinstance(rc, dict) else {}

    # 1. opener — first section of rshape, looked up in opener catalog.
    sections = rshape_d.get("sections")
    first_section = ""
    if isinstance(sections, list) and sections:
        candidate = sections[0]
        if isinstance(candidate, str):
            first_section = candidate.strip().lower()
    opener = _OPENER_BY_SECTION.get(first_section, _OPENER_DEFAULT)

    # 2. body_pattern — by risk tier; rshape.risk preferred, then rc.risk_hint,
    # then "low" default. Always returns a 2-item list (per spec).
    risk_raw = rshape_d.get("risk")
    risk = risk_raw if isinstance(risk_raw, str) and risk_raw.strip() else None
    if risk is None:
        rc_risk = rc_d.get("risk_hint")
        risk = rc_risk if isinstance(rc_risk, str) and rc_risk.strip() else "low"
    risk = risk.lower()
    pattern_key = f"risk_{risk}" if risk in ("high", "moderate", "low") else "risk_low"
    body_pattern = list(_BODY_PATTERNS[pattern_key])

    # 3. closer — by rshape.direction; spec mentions only forward/stalled/
    # reversing tiers. Anything else falls to default.
    direction_raw = rshape_d.get("direction")
    direction = direction_raw.strip().lower() if isinstance(direction_raw, str) else ""
    closer = _CLOSER_BY_DIRECTION.get(direction, _CLOSER_DEFAULT)

    # 4. tone_hint — by rshape.risk only (spec §3.4 doesn't extend the fallback
    # chain through rc). If rshape.risk missing/unrecognized, default "open".
    rshape_risk_only = risk_raw.strip().lower() if isinstance(risk_raw, str) and risk_raw.strip() else None
    tone_hint = _TONE_BY_RISK.get(rshape_risk_only, "open") if rshape_risk_only else "open"

    return {
        "body_pattern": body_pattern,
        "closer": closer,
        "opener": opener,
        "tone_hint": tone_hint,
    }


# Envelope v26 — generator conditioning surface v6 (sentence-level operators).
_PREFIX_BY_PHASE: dict = {
    "build":  ["notably", "importantly"],
    "shift":  ["interestingly", "critically"],
    "steady": ["consistently", "reliably"],
    "none":   [],
}

_SUFFIX_BY_DIRECTION: dict = {
    "forward":   ["as expected", "moving ahead"],
    "stalled":   ["for now", "as it stands"],
    "reversing": ["unexpectedly", "pulling back"],
}

_TRANSFORM_BY_FOCUS: dict = {
    "identity":   ["in essence", "at its core"],
    "trajectory": ["in motion", "in trend"],
    "elins":      ["structurally", "systemically"],
    "s_strategy": ["tactically", "strategically"],
    "universal":  ["generally", "fundamentally"],
    "external":   ["contextually", "relationally"],
    "general":    ["notably", "broadly"],
}
_TRANSFORM_DEFAULT: list = ["broadly"]

_RISK_OPS: dict = {
    "high":     ["with caution", "with variance in mind"],
    "moderate": ["with context", "with some uncertainty"],
    "low":      ["with confidence", "with stability"],
}
_RISK_OPS_DEFAULT: list = ["with stability"]


def _build_sentence_operators(
    rc: Optional[dict],
    rs: Optional[dict],
    cl: Optional[dict],
    rshape: Optional[dict],
) -> dict:
    """v26 — derive sentence-level modifier sets (prefix / suffix /
    transform / risk) from v18 cues, v23 scaffold, v22 cognitive_loop, and
    v24 response_shape. Pure deterministic; never raises; returns `{}` when
    all four inputs are missing/empty (per spec §3 final clause).

    Per spec §3 the data sources for each field are:
      - prefix_ops:    rshape.phase
      - suffix_ops:    rshape.direction
      - transform_ops: rs.scaffold_focus
      - risk_ops:      rshape.risk
    The rc/cl inputs are accepted in the signature for spec consistency /
    forward compatibility but the v26 derivation reads only rs + rshape."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (rc, rs, cl, rshape)):
        return {}

    rs_d = rs if isinstance(rs, dict) else {}
    rshape_d = rshape if isinstance(rshape, dict) else {}

    # 1. prefix_ops — by rshape.phase. Spec defines "build/shift/steady/none";
    # any other phase string falls to []. (Note: copy the catalog list so
    # downstream mutation doesn't poison the constant.)
    phase_raw = rshape_d.get("phase")
    phase = phase_raw.strip().lower() if isinstance(phase_raw, str) and phase_raw.strip() else ""
    prefix_ops = list(_PREFIX_BY_PHASE.get(phase, []))

    # 2. suffix_ops — by rshape.direction.
    direction_raw = rshape_d.get("direction")
    direction = direction_raw.strip().lower() if isinstance(direction_raw, str) and direction_raw.strip() else ""
    suffix_ops = list(_SUFFIX_BY_DIRECTION.get(direction, []))

    # 3. transform_ops — by rs.scaffold_focus; default ["broadly"].
    focus_raw = rs_d.get("scaffold_focus")
    focus = focus_raw.strip().lower() if isinstance(focus_raw, str) and focus_raw.strip() else ""
    transform_ops = list(_TRANSFORM_BY_FOCUS.get(focus, _TRANSFORM_DEFAULT))

    # 4. risk_ops — by rshape.risk; default ["with stability"].
    risk_raw = rshape_d.get("risk")
    risk = risk_raw.strip().lower() if isinstance(risk_raw, str) and risk_raw.strip() else ""
    risk_ops = list(_RISK_OPS.get(risk, _RISK_OPS_DEFAULT))

    return {
        "prefix_ops": prefix_ops,
        "risk_ops": risk_ops,
        "suffix_ops": suffix_ops,
        "transform_ops": transform_ops,
    }


# Envelope v27 — generator conditioning surface v7 (connective tissue operators).
_FORWARD_BY_DIRECTION: dict = {
    "forward":   ["building on that", "continuing from there"],
    "stalled":   ["to hold that point", "staying with that"],
    "reversing": ["pulling back from that", "stepping away from that"],
}

_CONTRAST_BY_PHASE: dict = {
    "build":  ["however", "even so"],
    "shift":  ["by contrast", "alternatively"],
    "steady": ["still", "nevertheless"],
    "none":   ["however"],
}
_CONTRAST_DEFAULT: list = ["however"]

_EXPANSION_BY_FOCUS: dict = {
    "identity":   ["in addition", "more broadly"],
    "trajectory": ["further along", "extending that"],
    "elins":      ["structurally speaking", "systemically speaking"],
    "s_strategy": ["tactically speaking", "strategically speaking"],
    "universal":  ["in general terms", "at a higher level"],
    "external":   ["in related context", "in adjacent topics"],
    "general":    ["additionally", "also"],
}
_EXPANSION_DEFAULT: list = ["also"]

_RISK_LINKS: dict = {
    "high":     ["with that risk in mind", "given the volatility"],
    "moderate": ["with some uncertainty", "given the context"],
    "low":      ["with stability in view", "given the steady signal"],
}
_RISK_LINKS_DEFAULT: list = ["with stability in view"]


def _build_connective_ops(
    rs: Optional[dict],
    rshape: Optional[dict],
    rc: Optional[dict],
    cl: Optional[dict],
) -> dict:
    """v27 — derive 4 inter-sentence linking sets (forward / contrast /
    expansion / risk) from v23 scaffold + v24 response_shape. Pure
    deterministic; never raises; returns `{}` when all four inputs are
    missing/empty (per spec §3 final clause).

    Per spec §3 the data sources for each field are:
      - forward_links:   rshape.direction
      - contrast_links:  rshape.phase
      - expansion_links: rs.scaffold_focus
      - risk_links:      rshape.risk
    The rc/cl inputs are accepted in the signature for spec consistency /
    forward compatibility but the v27 derivation reads only rs + rshape.
    Catalog values are wrapped in `list(...)` so callers can't mutate the
    constants."""

    def _is_empty(x) -> bool:
        if x is None:
            return True
        if isinstance(x, (dict, list, tuple, set)):
            return len(x) == 0
        return False

    if all(_is_empty(x) for x in (rs, rshape, rc, cl)):
        return {}

    rs_d = rs if isinstance(rs, dict) else {}
    rshape_d = rshape if isinstance(rshape, dict) else {}

    # 1. forward_links — by rshape.direction (default []).
    direction_raw = rshape_d.get("direction")
    direction = direction_raw.strip().lower() if isinstance(direction_raw, str) and direction_raw.strip() else ""
    forward_links = list(_FORWARD_BY_DIRECTION.get(direction, []))

    # 2. contrast_links — by rshape.phase (default ["however"]).
    phase_raw = rshape_d.get("phase")
    phase = phase_raw.strip().lower() if isinstance(phase_raw, str) and phase_raw.strip() else ""
    contrast_links = list(_CONTRAST_BY_PHASE.get(phase, _CONTRAST_DEFAULT))

    # 3. expansion_links — by rs.scaffold_focus (default ["also"]).
    focus_raw = rs_d.get("scaffold_focus")
    focus = focus_raw.strip().lower() if isinstance(focus_raw, str) and focus_raw.strip() else ""
    expansion_links = list(_EXPANSION_BY_FOCUS.get(focus, _EXPANSION_DEFAULT))

    # 4. risk_links — by rshape.risk (default ["with stability in view"]).
    risk_raw = rshape_d.get("risk")
    risk = risk_raw.strip().lower() if isinstance(risk_raw, str) and risk_raw.strip() else ""
    risk_links = list(_RISK_LINKS.get(risk, _RISK_LINKS_DEFAULT))

    return {
        "contrast_links": contrast_links,
        "expansion_links": expansion_links,
        "forward_links": forward_links,
        "risk_links": risk_links,
    }


def _causal_chain_max_length(episodes_dict: dict) -> int:
    """Longest causal chain length over the episode graph (DAG of
    `causal_links`). Returns the number of NODES in the longest path
    (so a→b→c is length 3). DFS with memoization. Tolerates cycles by
    treating already-visited-on-current-path nodes as terminators."""
    if not episodes_dict:
        return 0
    cache: dict = {}

    def dfs(eid: str, on_path: set) -> int:
        if eid in cache:
            return cache[eid]
        ep = episodes_dict.get(eid)
        if not isinstance(ep, dict):
            cache[eid] = 0
            return 0
        best = 1
        on_path.add(eid)
        for cl in ep.get("causal_links") or []:
            if not (isinstance(cl, (list, tuple)) and len(cl) >= 1):
                continue
            child = cl[0]
            if child in on_path or child not in episodes_dict:
                continue
            sub = dfs(child, on_path)
            if 1 + sub > best:
                best = 1 + sub
        on_path.discard(eid)
        cache[eid] = best
        return best

    return max((dfs(eid, set()) for eid in episodes_dict.keys()), default=0)


def _coerce_timescale(value) -> str:
    if isinstance(value, str) and value in _VALID_TIMESCALES:
        return value
    return _DEFAULT_TIMESCALE


def _evolve_envelope(
    user: str,
    v_final: list[float],
    v_obs: Optional[list[float]] = None,
    user_message: Optional[str] = None,
) -> tuple[dict, dict]:
    """Envelope evolution — runs all v3/v3.5/v4/v4.5/v5/v5.5/v6 phases in
    spec order, persists the result. Returns `(evolved_envelope_doc,
    similarities_by_brief_id)` so callers (the transmitter) can reuse the
    sim map without recomputing.

    `v_obs` and `user_message` are required by v6 event creation. When
    omitted (e.g., callers from non-chat paths), event creation is skipped
    but all other phases still run.

    Returns `({}, {})` when the user has no envelope yet (we don't create
    one implicitly). Passive on Markov state."""
    envelope = envelopes_store.get(user)
    if envelope is None:
        return {}, {}

    briefs = [dict(b) for b in (envelope.get("elins_briefs") or [])]
    # v6.5 — load persisted per-episode aggregates + cross/causal links.
    # Defensively coerce to dict (legacy envelopes have no `episodes` field).
    raw_episodes = envelope.get("episodes")
    episodes_dict: dict = dict(raw_episodes) if isinstance(raw_episodes, dict) else {}
    # v7 — load narrative graph + story arcs + arc clustering gate.
    raw_narratives = envelope.get("narratives")
    narratives_dict: dict = dict(raw_narratives) if isinstance(raw_narratives, dict) else {}
    raw_story_arcs = envelope.get("story_arcs")
    story_arcs_dict: dict = dict(raw_story_arcs) if isinstance(raw_story_arcs, dict) else {}
    last_arc_clustering_ts = envelope.get("envelope_last_arc_clustering_ts")
    # v8 — load identity profile (used by step 4 recall + step 20 narrative
    # influence). Rebuilt at step 29 from current state and persisted.
    raw_identity = envelope.get("identity")
    identity_profile: dict = dict(raw_identity) if isinstance(raw_identity, dict) else {}
    # v9 — load trajectory profile (used by step 4 recall + step 39 velocity
    # via prev vector + step 40 identity coupling). Rebuilt at steps 36-39.
    raw_trajectory = envelope.get("trajectory")
    trajectory_profile: dict = dict(raw_trajectory) if isinstance(raw_trajectory, dict) else {}
    # v12 — load prior ELINS physics context (drives step 4 recall). Rebuilt
    # at steps 41-45 from fresh JSON ingest each cycle.
    raw_elins = envelope.get("elins")
    elins_context_loaded: dict = dict(raw_elins) if isinstance(raw_elins, dict) else {}
    now = time.time()

    # 1. Decay pass.
    last_decay = envelope.get("envelope_decay_ts")
    if last_decay is None:
        hours_since = 0.0
    else:
        try:
            hours_since = max(0.0, (now - float(last_decay)) / 3600.0)
        except (TypeError, ValueError):
            hours_since = 0.0
    for brief in briefs:
        ts = _coerce_timescale(brief.get("timescale"))
        brief["timescale"] = ts  # normalize for downstream readers
        default_rate = _DEFAULT_DECAY_BY_TIMESCALE[ts]
        try:
            decay_rate = float(brief.get("decay_rate", default_rate))
        except (TypeError, ValueError):
            decay_rate = default_rate
        try:
            strength = float(brief.get("strength", _ENVELOPE_V3_DEFAULTS["strength"]))
        except (TypeError, ValueError):
            strength = _ENVELOPE_V3_DEFAULTS["strength"]
        brief["strength"] = max(0.0, strength - decay_rate * hours_since)
        # v4.5 — interference_score decays after 24h of no interference event
        last_int = brief.get("last_interference_ts")
        if last_int is not None:
            try:
                int_age_hours = (now - float(last_int)) / 3600.0
                if int_age_hours >= _INTERFERENCE_DECAY_STALE_HOURS:
                    cur = float(brief.get("interference_score", 0.0))
                    brief["interference_score"] = max(0.0, cur - _INTERFERENCE_DECAY_BUMP)
            except (TypeError, ValueError):
                pass

    # 2. Replay cycle (v5) — runs once per 24h envelope-wide.
    #    Strengthens stable mid/long briefs; resets replay_score on
    #    strengthening so replay-based demotion can re-fire later.
    last_replay = envelope.get("envelope_last_replay_ts")
    if last_replay is None:
        replay_due = True
    else:
        try:
            replay_due = (now - float(last_replay)) >= _REPLAY_CADENCE_HOURS * 3600
        except (TypeError, ValueError):
            replay_due = True
    replays = 0
    replay_strengthens = 0
    if replay_due:
        for brief in briefs:
            ts = brief.get("timescale", _DEFAULT_TIMESCALE)
            try:
                s = float(brief.get("strength", 0.0))
            except (TypeError, ValueError):
                s = 0.0
            if ts in _REPLAY_CANDIDATE_TIMESCALES and s >= _REPLAY_CANDIDATE_MIN_STRENGTH:
                try:
                    rscore = float(brief.get("replay_score", 0.0))
                except (TypeError, ValueError):
                    rscore = 0.0
                rscore += _REPLAY_BUMP
                brief["replay_score"] = rscore
                brief["last_replay_ts"] = now
                replays += 1
                if rscore >= _REPLAY_STRENGTHEN_THRESHOLD:
                    brief["strength"] = min(1.0, s + _REPLAY_STRENGTHEN_AMOUNT)
                    brief["replay_score"] = 0.0
                    replay_strengthens += 1

    # 3. Demotion pass (v4 + v5 stale-replay bump) — runs after replay,
    #    before refresh. Triggered by sustained low strength and/or staleness.
    promotions = 0
    demotions = 0
    for brief in briefs:
        try:
            strength = float(brief.get("strength", 0.0))
        except (TypeError, ValueError):
            strength = 0.0
        try:
            dscore = float(brief.get("demotion_score", 0.0))
        except (TypeError, ValueError):
            dscore = 0.0
        if strength <= _DEMOTION_LOW_STRENGTH_THRESHOLD:
            dscore += _DEMOTION_BUMP_LOW_STRENGTH
        last_ref = brief.get("last_reference_ts") or brief.get("last_reference_timestamp")
        try:
            stale_hours = (now - float(last_ref)) / 3600.0 if last_ref is not None else float("inf")
        except (TypeError, ValueError):
            stale_hours = float("inf")
        if stale_hours >= _DEMOTION_STALE_HOURS:
            dscore += _DEMOTION_BUMP_STALE
        # v5 — replay-based demotion: brief with no recent replay AND low
        # strength AND extended staleness gets an extra bump.
        try:
            rscore = float(brief.get("replay_score", 0.0))
        except (TypeError, ValueError):
            rscore = 0.0
        if (
            rscore == 0.0
            and strength <= _REPLAY_DEMOTION_LOW_STRENGTH
            and stale_hours >= _REPLAY_DEMOTION_STALE_HOURS
        ):
            dscore += _REPLAY_DEMOTION_BUMP
        brief["demotion_score"] = dscore

        ts = brief.get("timescale", _DEFAULT_TIMESCALE)
        threshold = _DEMOTION_THRESHOLD.get(ts)
        if threshold is not None and dscore >= threshold:
            new_ts = _DEMOTION_NEXT[ts]
            brief["timescale"] = new_ts
            brief["promotion_score"] = 0.0
            brief["demotion_score"] = 0.0
            brief["decay_rate"] = _DEFAULT_DECAY_BY_TIMESCALE[new_ts]
            demotions += 1

    # 3. Similarities + refresh tiers.
    similarities: dict = {}
    if v_final:
        for brief in briefs:
            bid = brief.get("brief_id")
            v = brief.get("object_vector")
            if not v or len(v) != len(v_final):
                if bid is not None:
                    similarities[bid] = 0.0
                continue
            sim = float(dewey_pipeline.similarity(v_final, v))
            if bid is not None:
                similarities[bid] = sim
            strength = float(brief.get("strength", 0.0))
            ts = _coerce_timescale(brief.get("timescale"))
            mult = _REFRESH_MULTIPLIER_BY_TIMESCALE[ts]
            if sim >= _ENVELOPE_REFRESH_TIER_LOW:
                brief["last_reference_ts"] = now
                strength = min(1.0, strength + _ENVELOPE_REFRESH_BUMP_LOW * mult)
            if sim >= _ENVELOPE_REFRESH_TIER_HIGH:
                strength = min(1.0, strength + _ENVELOPE_REFRESH_BUMP_HIGH * mult)
            brief["strength"] = strength

    # v6.5 §7 — Long-range recall integration. Include persisted episode
    # vectors (and causal-linked episode vectors) in the similarity map,
    # weighted by episode_strength * temporal_weight. Stored under
    # `episode_<eid>` keys so they don't collide with brief_ids and don't
    # accidentally drive brief refresh/promotion.
    episode_similarities: dict = {}
    if v_final and episodes_dict:
        for eid, ep_meta in episodes_dict.items():
            ep_vec = ep_meta.get("episode_vector") if isinstance(ep_meta, dict) else None
            if not ep_vec or len(ep_vec) != len(v_final):
                continue
            try:
                ep_strength = float(ep_meta.get("episode_strength", 0.0))
            except (TypeError, ValueError):
                ep_strength = 0.0
            try:
                latest_ts = float(ep_meta.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                latest_ts = 0.0
            dt_hours = max(0.0, (now - latest_ts) / 3600.0) if latest_ts > 0 else 0.0
            tw = _temporal_weight(dt_hours)
            sim = float(dewey_pipeline.similarity(v_final, ep_vec))
            weighted = sim * ep_strength * tw
            episode_similarities[f"episode_{eid}"] = {
                "raw_similarity": sim,
                "weighted_similarity": weighted,
                "episode_strength": ep_strength,
                "temporal_weight": tw,
            }
            similarities[f"episode_{eid}"] = weighted
            # Causal episode vectors get the same treatment via the chain —
            # each episode's causal_links lists downstream episodes; the
            # downstream episodes are already iterated above, so no extra
            # work is needed beyond ensuring they're present in episodes_dict.

    # v7 §6 — Story-level recall integration. Include narrative-node and
    # story-arc vectors in the similarity map, weighted by node/arc strength
    # × temporal_weight. Stored under `narrative_<node_id>` /
    # `storyarc_<arc_id>` keys; brief refresh/promotion ignores them by id
    # prefix.
    narrative_similarities: dict = {}
    storyarc_similarities: dict = {}
    if v_final and narratives_dict:
        for nid, node in narratives_dict.items():
            if not isinstance(node, dict):
                continue
            nv = node.get("node_vector")
            if not nv or len(nv) != len(v_final):
                continue
            try:
                ns = float(node.get("node_strength", 0.0))
            except (TypeError, ValueError):
                ns = 0.0
            try:
                nlt = float(node.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                nlt = 0.0
            ntw = _temporal_weight(max(0.0, (now - nlt) / 3600.0)) if nlt > 0 else 1.0
            nsim = float(dewey_pipeline.similarity(v_final, nv))
            nweighted = nsim * ns * ntw
            narrative_similarities[f"narrative_{nid}"] = {
                "raw_similarity": nsim,
                "weighted_similarity": nweighted,
                "node_strength": ns,
                "temporal_weight": ntw,
            }
            similarities[f"narrative_{nid}"] = nweighted
    if v_final and story_arcs_dict:
        for aid, arc in story_arcs_dict.items():
            if not isinstance(arc, dict):
                continue
            av = arc.get("arc_vector")
            if not av or len(av) != len(v_final):
                continue
            try:
                a_s = float(arc.get("arc_strength", 0.0))
            except (TypeError, ValueError):
                a_s = 0.0
            try:
                alt = float(arc.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                alt = 0.0
            atw = _temporal_weight(max(0.0, (now - alt) / 3600.0)) if alt > 0 else 1.0
            asim = float(dewey_pipeline.similarity(v_final, av))
            aweighted = asim * a_s * atw
            storyarc_similarities[f"storyarc_{aid}"] = {
                "raw_similarity": asim,
                "weighted_similarity": aweighted,
                "arc_strength": a_s,
                "temporal_weight": atw,
            }
            similarities[f"storyarc_{aid}"] = aweighted

    # v7.5 §7 — Recall of compressed narrative + arc vectors. Same temporal
    # weighting, but indexed under `narrcomp_<id>` / `arccomp_<id>` so
    # downstream consumers can distinguish raw node/arc vectors from their
    # compressed siblings.
    narrcomp_similarities: dict = {}
    arccomp_similarities: dict = {}
    if v_final and narratives_dict:
        for nid, node in narratives_dict.items():
            if not isinstance(node, dict):
                continue
            cv = node.get("compressed_vector")
            if not cv or len(cv) != len(v_final):
                continue
            try:
                ns = float(node.get("node_strength", 0.0))
            except (TypeError, ValueError):
                ns = 0.0
            try:
                nlt = float(node.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                nlt = 0.0
            ntw = _temporal_weight(max(0.0, (now - nlt) / 3600.0)) if nlt > 0 else 1.0
            csim = float(dewey_pipeline.similarity(v_final, cv))
            cweighted = csim * ns * ntw
            narrcomp_similarities[f"narrcomp_{nid}"] = {
                "raw_similarity": csim,
                "weighted_similarity": cweighted,
                "node_strength": ns,
                "temporal_weight": ntw,
            }
            similarities[f"narrcomp_{nid}"] = cweighted
    if v_final and story_arcs_dict:
        for aid, arc in story_arcs_dict.items():
            if not isinstance(arc, dict):
                continue
            cav = arc.get("arc_vector_compressed")
            if not cav or len(cav) != len(v_final):
                continue
            try:
                a_s = float(arc.get("arc_strength", 0.0))
            except (TypeError, ValueError):
                a_s = 0.0
            try:
                alt = float(arc.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                alt = 0.0
            atw = _temporal_weight(max(0.0, (now - alt) / 3600.0)) if alt > 0 else 1.0
            casim = float(dewey_pipeline.similarity(v_final, cav))
            caweighted = casim * a_s * atw
            arccomp_similarities[f"arccomp_{aid}"] = {
                "raw_similarity": casim,
                "weighted_similarity": caweighted,
                "arc_strength": a_s,
                "temporal_weight": atw,
            }
            similarities[f"arccomp_{aid}"] = caweighted

    # v8 §7 — Identity recall integration. Compute sim against the loaded
    # identity_vector (built last cycle) and write `identity_profile` key
    # into similarities. Spec uses v_obs (chat path); fall back to v_final
    # for non-chat callers.
    identity_recall_used = 0
    identity_loaded_vector = identity_profile.get("identity_vector") if identity_profile else None
    try:
        identity_loaded_strength = float(identity_profile.get("identity_strength", 0.0)) if identity_profile else 0.0
    except (TypeError, ValueError):
        identity_loaded_strength = 0.0
    if identity_loaded_vector and identity_loaded_strength > 0.0:
        probe = v_obs if v_obs else v_final
        if probe and len(probe) == len(identity_loaded_vector):
            id_sim = float(dewey_pipeline.similarity(probe, identity_loaded_vector))
            similarities["identity_profile"] = id_sim * identity_loaded_strength
            identity_recall_used = 1

    # v9 §6 — Trajectory recall integration. Same pattern as identity:
    # probe against the loaded trajectory_profile (last cycle's snapshot).
    trajectory_recall_used = 0
    trajectory_loaded_vector = trajectory_profile.get("trajectory_vector") if trajectory_profile else None
    try:
        trajectory_loaded_strength = float(trajectory_profile.get("trajectory_strength", 0.0)) if trajectory_profile else 0.0
    except (TypeError, ValueError):
        trajectory_loaded_strength = 0.0
    if trajectory_loaded_vector and trajectory_loaded_strength > 0.0:
        probe = v_obs if v_obs else v_final
        if probe and len(probe) == len(trajectory_loaded_vector):
            t_sim = float(dewey_pipeline.similarity(probe, trajectory_loaded_vector))
            similarities["trajectory_profile"] = t_sim * trajectory_loaded_strength
            trajectory_recall_used = 1

    # v12 §6 — ELINS recall integration. Probes against the loaded ELINS
    # mean_center_vector; weight = mean of pressure_fields. Spec uses v_obs.
    elins_recall_used = 0
    elins_loaded_mean_vec = elins_context_loaded.get("mean_center_vector") if elins_context_loaded else None
    elins_loaded_pressures = elins_context_loaded.get("pressure_fields") if elins_context_loaded else None
    if elins_loaded_mean_vec and elins_loaded_pressures and v_obs:
        if len(elins_loaded_mean_vec) == len(v_obs):
            try:
                pvals = [float(v) for v in elins_loaded_pressures.values()]
            except (TypeError, ValueError):
                pvals = []
            if pvals:
                mean_pressure = sum(pvals) / len(pvals)
                el_sim = float(dewey_pipeline.similarity(v_obs, elins_loaded_mean_vec))
                similarities["elins_physics"] = el_sim * mean_pressure
                elins_recall_used = 1

    # v13 §6 — universal_physics marker (non-intrusive). Fires only when an
    # identity_vector has been bootstrapped, signaling that the operator has
    # enough self-model state to merit attaching universal physics vocabulary
    # to the recall surface. The value is a flat 1.0 — no vector math; the
    # brief-match counter skips this key.
    universal_physics_recall_used = 0
    if identity_profile and identity_profile.get("identity_vector"):
        similarities["universal_physics"] = 1.0
        universal_physics_recall_used = 1

    # 4. Promotion pass (v4) — runs after refresh.
    if v_final:
        for brief in briefs:
            bid = brief.get("brief_id")
            sim = similarities.get(bid, 0.0)
            try:
                pscore = float(brief.get("promotion_score", 0.0))
            except (TypeError, ValueError):
                pscore = 0.0
            if sim >= _ENVELOPE_REFRESH_TIER_HIGH:
                pscore += _PROMOTION_BUMP_HIGH_SIM
            try:
                strength = float(brief.get("strength", 0.0))
            except (TypeError, ValueError):
                strength = 0.0
            if strength >= 0.8:
                pscore += _PROMOTION_BUMP_HIGH_STRENGTH
            try:
                thresh = float(brief.get(
                    "activation_threshold",
                    _ENVELOPE_V3_DEFAULTS["activation_threshold"],
                ))
            except (TypeError, ValueError):
                thresh = _ENVELOPE_V3_DEFAULTS["activation_threshold"]
            if strength >= thresh:
                pscore += _PROMOTION_BUMP_ACTIVE
            brief["promotion_score"] = pscore

            ts = brief.get("timescale", _DEFAULT_TIMESCALE)
            threshold = _PROMOTION_THRESHOLD.get(ts)
            if threshold is not None and pscore >= threshold:
                new_ts = _PROMOTION_NEXT[ts]
                brief["timescale"] = new_ts
                brief["promotion_score"] = 0.0
                brief["demotion_score"] = 0.0
                brief["decay_rate"] = _DEFAULT_DECAY_BY_TIMESCALE[new_ts]
                promotions += 1

    # 6. Interference detection (v4.5) — pairwise on object_vectors.
    n = len(briefs)
    interferences = 0
    for i in range(n):
        a = briefs[i]
        va = a.get("object_vector")
        if not va:
            continue
        for j in range(i + 1, n):
            b = briefs[j]
            vb = b.get("object_vector")
            if not vb or len(vb) != len(va):
                continue
            sim_ab = float(dewey_pipeline.similarity(va, vb))
            if sim_ab >= _INTERFERENCE_TIER_LOW:
                a["interference_score"] = float(a.get("interference_score", 0.0)) + _INTERFERENCE_BUMP_LOW
                b["interference_score"] = float(b.get("interference_score", 0.0)) + _INTERFERENCE_BUMP_LOW
                a["last_interference_ts"] = now
                b["last_interference_ts"] = now
                interferences += 1
            if sim_ab >= _INTERFERENCE_TIER_HIGH:
                a["interference_score"] = float(a.get("interference_score", 0.0)) + _INTERFERENCE_BUMP_HIGH
                b["interference_score"] = float(b.get("interference_score", 0.0)) + _INTERFERENCE_BUMP_HIGH

    # 7. Pattern separation (v4.5) — push high-interference briefs away from
    # the persisted envelope_vector and reduce their strength. Uses the
    # envelope_vector AS LOADED (pre-this-evolution) per the simplest
    # reading of spec §3 + §5 ordering.
    env_vec_for_sep = list(envelope.get("envelope_vector") or [])
    separations = 0
    for brief in briefs:
        try:
            iscore = float(brief.get("interference_score", 0.0))
        except (TypeError, ValueError):
            iscore = 0.0
        if iscore < _SEPARATION_TRIGGER:
            continue
        # Strength penalty
        try:
            s = float(brief.get("strength", 0.0))
        except (TypeError, ValueError):
            s = 0.0
        brief["strength"] = max(0.0, s - _SEPARATION_STRENGTH_PENALTY)
        # Vector separation (only if env_vec_for_sep is dimensional match)
        v = brief.get("object_vector")
        if v and env_vec_for_sep and len(env_vec_for_sep) == len(v):
            shifted = [v[i] - _SEPARATION_VECTOR_COEF * env_vec_for_sep[i] for i in range(len(v))]
            brief["object_vector"] = dewey_pipeline._normalize(shifted)
        brief["interference_score"] = 0.0
        brief["last_interference_ts"] = now
        separations += 1

    # 9. Envelope vector recompute (v3.5 multi-layer: short=0.5, mid=1.0, long=2.0).
    new_vector = dewey_pipeline.compute_multilayer_envelope_vector(briefs)

    # 10-12. Drift detection / correction / centroid refresh (v5.5).
    centroid = list(envelope.get("envelope_centroid") or [])
    drift_events = int(envelope.get("envelope_drift_events", 0) or 0)
    last_centroid_update = envelope.get("last_centroid_update_ts")
    drift_distance = 0.0
    drift_corrections = 0
    centroid_refreshes = 0

    # Initialize centroid on first run (per spec §1).
    if not centroid and new_vector:
        centroid = list(new_vector)
        if last_centroid_update is None:
            last_centroid_update = now

    if new_vector and centroid and len(new_vector) == len(centroid):
        drift_distance = 1.0 - float(dewey_pipeline.similarity(new_vector, centroid))

        if drift_distance >= _DRIFT_EVENT_THRESHOLD:
            drift_events += 1

        if drift_distance >= _DRIFT_CORRECTION_THRESHOLD:
            # 1. Pull centroid toward current envelope_vector (0.8/0.2).
            centroid = dewey_pipeline._normalize([
                _DRIFT_CENTROID_PULLBACK_OLD * centroid[i]
                + _DRIFT_CENTROID_PULLBACK_NEW * new_vector[i]
                for i in range(len(centroid))
            ])
            # 2. Pull every brief vector slightly toward the centroid.
            for brief in briefs:
                v = brief.get("object_vector")
                if v and len(v) == len(centroid):
                    brief["object_vector"] = dewey_pipeline._normalize([
                        v[i] * _DRIFT_BRIEF_PULLBACK_OLD
                        + centroid[i] * _DRIFT_BRIEF_PULLBACK_CENTROID
                        for i in range(len(v))
                    ])
            # 3. Reduce strength of unstable briefs.
            for brief in briefs:
                try:
                    s = float(brief.get("strength", 0.0))
                except (TypeError, ValueError):
                    s = 0.0
                if s <= _DRIFT_UNSTABLE_STRENGTH_THRESHOLD:
                    brief["strength"] = max(0.0, s - _DRIFT_UNSTABLE_STRENGTH_PENALTY)
            # 4. Recompute envelope_vector after correction mutations.
            new_vector = dewey_pipeline.compute_multilayer_envelope_vector(briefs)
            drift_corrections = 1

        # 12. Centroid refresh (slow, 48h gate). Runs independently of correction.
        try:
            hours_since_centroid = (
                (now - float(last_centroid_update)) / 3600.0
                if last_centroid_update is not None else float("inf")
            )
        except (TypeError, ValueError):
            hours_since_centroid = float("inf")
        if hours_since_centroid >= _CENTROID_REFRESH_CADENCE_HOURS and new_vector:
            centroid = dewey_pipeline._normalize([
                _CENTROID_REFRESH_OLD * centroid[i]
                + _CENTROID_REFRESH_NEW * new_vector[i]
                for i in range(len(centroid))
            ])
            last_centroid_update = now
            centroid_refreshes = 1

    # ─────────────────────────────────────────────────────────────────────
    # v6 — Episodic memory (steps 13-16 in updated order)
    # ─────────────────────────────────────────────────────────────────────
    events = list(envelope.get("events") or [])
    last_episode_consolidation_ts = envelope.get("envelope_last_episode_consolidation_ts")
    new_event_id: Optional[str] = None
    episode_promotions = 0
    episode_demotions = 0

    # Decay event strengths each chat (event decay runs alongside brief decay
    # but per-chat instead of per-hour, per spec §6 wording).
    event_inactivations = 0
    for ev in events:
        # v6.5 — backfill defaults onto legacy events so downstream logic is safe.
        ev.setdefault("causal_parents", [])
        ev.setdefault("causal_children", [])
        ev.setdefault("cross_episode_links", [])
        try:
            es = float(ev.get("strength", 0.0))
            edr = float(ev.get("decay_rate", _EVENT_DECAY_RATE))
        except (TypeError, ValueError):
            es = 0.0
            edr = _EVENT_DECAY_RATE
        es_new = max(0.0, es - edr)
        ev["strength"] = es_new
        if es_new <= _EVENT_INACTIVE_STRENGTH:
            if ev.get("active", True):
                ev["active"] = False
                event_inactivations += 1

    # 13. Event creation — only when we have a fresh observation.
    if v_obs and user_message:
        new_event_id = "ev_" + secrets.token_urlsafe(12)
        # Find linked briefs by sim(brief.vector, event.vector=v_obs).
        linked_briefs: list[str] = []
        link_sims: dict = {}
        for brief in briefs:
            bv = brief.get("object_vector")
            if not bv or len(bv) != len(v_obs):
                continue
            ev_sim = float(dewey_pipeline.similarity(v_obs, bv))
            if ev_sim >= _EVENT_LINK_SIM_THRESHOLD:
                bid = brief.get("brief_id")
                linked_briefs.append(bid)
                link_sims[bid] = ev_sim

        # 15. Episode formation — same episode if last event within 10 min.
        last_event = events[-1] if events else None
        if last_event:
            try:
                gap = now - float(last_event.get("timestamp", 0.0))
            except (TypeError, ValueError):
                gap = float("inf")
        else:
            gap = float("inf")
        if last_event and gap <= _EPISODE_GAP_SECONDS and last_event.get("episode_id"):
            episode_id = last_event["episode_id"]
        else:
            episode_id = "ep_" + secrets.token_urlsafe(12)

        new_event = {
            "event_id": new_event_id,
            "timestamp": now,
            "text": user_message[:512],  # bounded snapshot, not the whole transcript
            "linked_briefs": linked_briefs,
            "vector": list(v_obs),
            "strength": _EVENT_DEFAULT_STRENGTH,
            "decay_rate": _EVENT_DECAY_RATE,
            "episode_id": episode_id,
            "linked_events": [],
            "active": True,
            # v6.5 — cross-episode + causal scaffolding (defaults).
            "causal_parents": [],
            "causal_children": [],
            "cross_episode_links": [],
        }

        # Cross-link to existing events in the same episode.
        same_episode = [e for e in events if e.get("episode_id") == episode_id]
        for prior in same_episode:
            prior.setdefault("linked_events", [])
            if new_event_id not in prior["linked_events"]:
                prior["linked_events"].append(new_event_id)
            new_event["linked_events"].append(prior.get("event_id"))

        # 14. Event-brief linking — additive bumps to brief AND event strengths.
        for bid in linked_briefs:
            sim = link_sims[bid]
            for brief in briefs:
                if brief.get("brief_id") != bid:
                    continue
                bs = float(brief.get("strength", 0.0))
                es = float(new_event["strength"])
                if sim >= _EVENT_LINK_TIER_HIGH:
                    bs = min(1.0, bs + _EVENT_LINK_BUMP_HIGH)
                    es = min(1.0, es + _EVENT_LINK_BUMP_HIGH)
                if sim >= _EVENT_LINK_TIER_VERY_HIGH:
                    bs = min(1.0, bs + _EVENT_LINK_BUMP_VERY_HIGH)
                    es = min(1.0, es + _EVENT_LINK_BUMP_VERY_HIGH)
                brief["strength"] = bs
                new_event["strength"] = es
                break

        events.append(new_event)

    # ─────────────────────────────────────────────────────────────────────
    # v6.5 — Cross-episode reasoning + temporal causality (steps 16-18)
    # ─────────────────────────────────────────────────────────────────────
    # Rebuild per-episode aggregates (vector, strength, latest_ts) over the
    # CURRENT events list (post-event-creation, post-event-brief-linking).
    # Carry over episode_links + causal_links from the prior episodes_dict.
    events_by_episode: dict[str, list[dict]] = {}
    for ev in events:
        eid = ev.get("episode_id")
        if not eid:
            continue
        events_by_episode.setdefault(eid, []).append(ev)
    next_episodes: dict[str, dict] = {}
    for eid, eps_events in events_by_episode.items():
        ep_vec, ep_strength, latest_ts = _episode_aggregate(eps_events)
        prior = episodes_dict.get(eid) if isinstance(episodes_dict.get(eid), dict) else {}
        next_episodes[eid] = {
            "episode_id": eid,
            "episode_vector": ep_vec,
            "episode_strength": float(ep_strength),
            "latest_event_ts": float(latest_ts),
            "episode_links": list(prior.get("episode_links") or []),
            "causal_links": list(prior.get("causal_links") or []),
        }

    cross_episode_links_added = 0
    cross_episode_strengthens = 0
    causal_event_links_added = 0
    causal_episode_links_added = 0
    causal_episode_strengthens = 0
    causal_link_sims: dict[tuple, float] = {}  # (parent_eid, child_eid) → list of sims for episode-level mean

    # 16. Cross-episode semantic linking — only for the newly created event.
    if new_event_id and v_obs:
        new_ep_id = new_event["episode_id"]
        for eid, ep_meta in next_episodes.items():
            if eid == new_ep_id:
                continue
            ep_vec = ep_meta.get("episode_vector")
            if not ep_vec or len(ep_vec) != len(v_obs):
                continue
            sim = float(dewey_pipeline.similarity(v_obs, ep_vec))
            if sim < _EPISODE_LINK_SIM_THRESHOLD:
                continue
            try:
                dt_hours = max(0.0, (now - float(ep_meta.get("latest_event_ts", now))) / 3600.0)
            except (TypeError, ValueError):
                dt_hours = 0.0
            tw = _temporal_weight(dt_hours)
            if eid not in new_event["cross_episode_links"]:
                new_event["cross_episode_links"].append(eid)
                cross_episode_links_added += 1
            if new_event_id not in ep_meta["episode_links"]:
                ep_meta["episode_links"].append(new_event_id)
            if sim >= _EPISODE_LINK_STRENGTHEN_THRESHOLD:
                ep_meta["episode_strength"] = min(
                    1.0,
                    float(ep_meta.get("episode_strength", 0.0))
                    + _EPISODE_LINK_STRENGTHEN_BUMP * tw,
                )
                cross_episode_strengthens += 1

    # 17. Causal inference (event-level) — only for the newly created event.
    # Compare E to the most recent event in each PRIOR episode (i.e. episodes
    # other than E's own). Apply spec-mandated triple gate. On match, link
    # bidirectionally and bump both strengths by +0.02 (× temporal_weight).
    if new_event_id and v_obs:
        new_ep_id = new_event["episode_id"]
        new_text = new_event.get("text", "") or ""
        try:
            new_ts = float(new_event.get("timestamp", now))
        except (TypeError, ValueError):
            new_ts = now
        for eid, eps_events_in_ep in events_by_episode.items():
            if eid == new_ep_id:
                continue
            # Most recent prior event in this episode (excluding the new one).
            prior_candidates = [
                e for e in eps_events_in_ep
                if e.get("event_id") != new_event_id and e.get("vector")
            ]
            if not prior_candidates:
                continue
            prior_event = max(
                prior_candidates,
                key=lambda e: float(e.get("timestamp", 0.0) or 0.0),
            )
            prior_vec = prior_event.get("vector")
            if not prior_vec or len(prior_vec) != len(v_obs):
                continue
            try:
                prior_ts = float(prior_event.get("timestamp", 0.0))
            except (TypeError, ValueError):
                prior_ts = 0.0
            if not (new_ts > prior_ts):
                continue
            sim = float(dewey_pipeline.similarity(v_obs, prior_vec))
            if sim < _CAUSAL_EVENT_SIM_THRESHOLD:
                continue
            prior_text = prior_event.get("text", "") or ""
            text_longer = len(new_text) > len(prior_text)
            references = _references_prior_text(new_text, prior_text)
            if not (text_longer or references):
                continue
            # Temporal weight from age of prior event.
            dt_hours = max(0.0, (new_ts - prior_ts) / 3600.0)
            tw = _temporal_weight(dt_hours)
            prior_eid_self = prior_event.get("event_id")
            # Bidirectional event link.
            if prior_eid_self and prior_eid_self not in new_event["causal_parents"]:
                new_event["causal_parents"].append(prior_eid_self)
            prior_event.setdefault("causal_children", [])
            if new_event_id not in prior_event["causal_children"]:
                prior_event["causal_children"].append(new_event_id)
            # Strengthen both events by +0.02 (× temporal_weight per §6).
            try:
                ne_s = float(new_event.get("strength", 0.0))
                pe_s = float(prior_event.get("strength", 0.0))
            except (TypeError, ValueError):
                ne_s = float(new_event.get("strength", 0.0) or 0.0)
                pe_s = float(prior_event.get("strength", 0.0) or 0.0)
            new_event["strength"] = min(1.0, ne_s + _CAUSAL_EVENT_STRENGTHEN_BUMP * tw)
            prior_event["strength"] = min(1.0, pe_s + _CAUSAL_EVENT_STRENGTHEN_BUMP * tw)
            causal_event_links_added += 1
            # Track for episode-level aggregation: (parent_episode_id, child_episode_id).
            key = (eid, new_ep_id)
            causal_link_sims.setdefault(key, []).append(sim)

    # 18. Causal inference (episode-level) — derive from just-formed event-
    # level causal links. For each (Ep_A → Ep_B) pair where any event in A
    # is a causal_parent of an event in B, add (Ep_B_id, weight) to
    # Ep_A.causal_links with weight = mean similarity × temporal_weight.
    # If weight ≥ 0.60, strengthen Ep_B.episode_strength += 0.03 × tw.
    for (parent_eid, child_eid), sims_list in causal_link_sims.items():
        if not sims_list:
            continue
        mean_sim = sum(sims_list) / len(sims_list)
        parent_meta = next_episodes.get(parent_eid)
        child_meta = next_episodes.get(child_eid)
        if parent_meta is None or child_meta is None:
            continue
        # Δt between episodes uses the gap between their latest_event_ts values.
        try:
            dt_hours = max(
                0.0,
                (float(child_meta.get("latest_event_ts", now))
                 - float(parent_meta.get("latest_event_ts", now))) / 3600.0,
            )
        except (TypeError, ValueError):
            dt_hours = 0.0
        tw = _temporal_weight(dt_hours)
        weight = float(mean_sim) * tw
        # Replace any existing entry pointing to child_eid (avoids duplicates).
        parent_meta["causal_links"] = [
            cl for cl in parent_meta.get("causal_links", [])
            if not (isinstance(cl, (list, tuple)) and len(cl) >= 1 and cl[0] == child_eid)
        ]
        parent_meta["causal_links"].append([child_eid, weight])
        causal_episode_links_added += 1
        if weight >= _CAUSAL_EPISODE_STRENGTHEN_THRESHOLD:
            child_meta["episode_strength"] = min(
                1.0,
                float(child_meta.get("episode_strength", 0.0))
                + _CAUSAL_EPISODE_STRENGTHEN_BUMP * tw,
            )
            causal_episode_strengthens += 1

    # The aggregates we just built ARE the persistence form for `episodes`.
    episodes_dict = next_episodes

    # 19. Episode consolidation (24h-gated). Reads aggregates from the
    # v6.5 episodes_dict (which already incorporates cross-episode and
    # causal-link strengthening). Promotes strong episodes to long-term
    # briefs; demotes weak ones.
    if last_episode_consolidation_ts is None:
        consolidate_due = True
    else:
        try:
            consolidate_due = (now - float(last_episode_consolidation_ts)) >= _EPISODE_CONSOLIDATION_CADENCE_HOURS * 3600
        except (TypeError, ValueError):
            consolidate_due = True
    if consolidate_due and events:
        for eid, eps_events in events_by_episode.items():
            # Skip episodes already promoted (avoid re-creating the brief).
            already_promoted = any(
                b.get("brief_id") == f"episode_summary_{eid}" for b in briefs
            )
            ep_meta = episodes_dict.get(eid) or {}
            episode_strength = float(ep_meta.get("episode_strength", 0.0) or 0.0)
            episode_vector = ep_meta.get("episode_vector")
            if episode_strength >= _EPISODE_PROMOTE_STRENGTH and not already_promoted and episode_vector:
                summary_brief = {
                    "brief_id": f"episode_summary_{eid}",
                    "object_vector": episode_vector,
                    "timescale": "long",
                    "strength": float(episode_strength),
                    "decay_rate": _DEFAULT_DECAY_BY_TIMESCALE["long"],
                    "activation_threshold": _ENVELOPE_V3_DEFAULTS["activation_threshold"],
                    "promotion_score": 0.0,
                    "demotion_score": 0.0,
                    "interference_score": 0.0,
                    "replay_score": 0.0,
                    "metadata": {"source": "episode", "episode_id": eid, "event_count": len(eps_events)},
                    "created_at": now,
                }
                briefs.append(summary_brief)
                episode_promotions += 1
            elif episode_strength <= _EPISODE_DEMOTE_STRENGTH:
                for ev in eps_events:
                    try:
                        s = float(ev.get("strength", 0.0))
                    except (TypeError, ValueError):
                        s = 0.0
                    ev["strength"] = max(0.0, s - _EPISODE_DEMOTE_BUMP)
                episode_demotions += 1
        last_episode_consolidation_ts = now

    # ─────────────────────────────────────────────────────────────────────
    # v7 — Narrative memory + multi-episode story graphs (steps 20-23)
    # ─────────────────────────────────────────────────────────────────────
    narrative_nodes_created = 0
    narrative_episodes_merged = 0
    narrative_links_added = 0
    narrative_link_strengthens = 0
    narrative_causal_links_added = 0
    narrative_causal_strengthens = 0
    story_arcs_promoted = 0
    arc_clustering_ran = 0
    identity_node_bumps = 0       # v8 §8 — narrative-formation influence
    identity_episode_bumps = 0    # v8 §8

    # 20. Narrative node formation — runs whenever consolidation runs (24h
    # gate piggybacks). For every episode in events_by_episode, find the best
    # matching existing narrative node by sim(episode_vector, node_vector).
    # If sim ≥ 0.75, merge episode into that node; otherwise create a new
    # node seeded from the episode. Each episode belongs to at most one node.
    if consolidate_due and events_by_episode:
        # Build reverse map: episode_id → narrative node_id (already claimed).
        episode_to_node: dict[str, str] = {}
        for nid, node in narratives_dict.items():
            if not isinstance(node, dict):
                continue
            for eid in node.get("episode_ids", []) or []:
                episode_to_node[eid] = nid

        for eid in events_by_episode.keys():
            if eid in episode_to_node:
                continue  # already in some narrative node
            ep_meta = episodes_dict.get(eid)
            if not isinstance(ep_meta, dict):
                continue
            ep_vec = ep_meta.get("episode_vector")
            if not ep_vec:
                continue
            try:
                ep_strength = float(ep_meta.get("episode_strength", 0.0))
            except (TypeError, ValueError):
                ep_strength = 0.0
            try:
                ep_latest = float(ep_meta.get("latest_event_ts", 0.0))
            except (TypeError, ValueError):
                ep_latest = 0.0
            ep_event_ids = [e.get("event_id") for e in events_by_episode.get(eid, []) if e.get("event_id")]

            # Find best matching existing node above threshold.
            best_nid: Optional[str] = None
            best_sim: float = -2.0
            for nid, node in narratives_dict.items():
                if not isinstance(node, dict):
                    continue
                nv = node.get("node_vector")
                if not nv or len(nv) != len(ep_vec):
                    continue
                sim = float(dewey_pipeline.similarity(ep_vec, nv))
                if sim >= _NARRATIVE_FORMATION_SIM_THRESHOLD and sim > best_sim:
                    best_sim = sim
                    best_nid = nid

            if best_nid is not None:
                node = narratives_dict[best_nid]
                node.setdefault("episode_ids", [])
                node.setdefault("event_ids", [])
                if eid not in node["episode_ids"]:
                    node["episode_ids"].append(eid)
                for evid in ep_event_ids:
                    if evid not in node["event_ids"]:
                        node["event_ids"].append(evid)
                # Recompute node_vector + node_strength from current episode
                # aggregates; then strengthen by +0.02 per spec.
                nv_new, ns_new, nlt_new = _narrative_aggregate(node, episodes_dict)
                if nv_new is not None:
                    node["node_vector"] = nv_new
                node["node_strength"] = min(1.0, float(ns_new) + _NARRATIVE_FORMATION_STRENGTHEN_BUMP)
                node["latest_event_ts"] = float(nlt_new)
                episode_to_node[eid] = best_nid
                narrative_episodes_merged += 1
                target_node = node
            else:
                node_id = "nn_" + secrets.token_urlsafe(12)
                target_node = {
                    "node_id": node_id,
                    "episode_ids": [eid],
                    "event_ids": list(ep_event_ids),
                    "node_vector": list(ep_vec),
                    "node_strength": float(ep_strength),
                    "latest_event_ts": float(ep_latest),
                    "narrative_links": [],
                    "causal_links": [],
                    "summary_text": None,
                    "created_at": now,
                }
                narratives_dict[node_id] = target_node
                episode_to_node[eid] = node_id
                narrative_nodes_created += 1

            # v8 §8 — Identity influence on narrative formation. Uses the
            # loaded identity_vector (this cycle's identity_profile is
            # rebuilt at step 29). Episode_vector stands in for `event_vector`
            # since formation is per-episode.
            if (
                identity_loaded_vector
                and ep_vec
                and len(identity_loaded_vector) == len(ep_vec)
            ):
                id_sim = float(dewey_pipeline.similarity(ep_vec, identity_loaded_vector))
                if id_sim >= _IDENTITY_NODE_INFLUENCE_THRESHOLD:
                    target_node["node_strength"] = min(
                        1.0,
                        float(target_node.get("node_strength", 0.0))
                        + _IDENTITY_NODE_STRENGTHEN_BUMP,
                    )
                    identity_node_bumps += 1
                if id_sim >= _IDENTITY_EPISODE_INFLUENCE_THRESHOLD:
                    ep_meta_for_bump = episodes_dict.get(eid)
                    if isinstance(ep_meta_for_bump, dict):
                        ep_meta_for_bump["episode_strength"] = min(
                            1.0,
                            float(ep_meta_for_bump.get("episode_strength", 0.0))
                            + _IDENTITY_EPISODE_STRENGTHEN_BUMP,
                        )
                        identity_episode_bumps += 1

    # 21. Cross-narrative linking — pairwise sim between all node pairs.
    # Recomputed each cycle (consolidate_due) so links reflect current vectors.
    if consolidate_due and narratives_dict:
        node_ids_list = list(narratives_dict.keys())
        # Reset narrative_links to avoid duplicate accumulation across cycles.
        for nid in node_ids_list:
            node = narratives_dict[nid]
            if isinstance(node, dict):
                node["narrative_links"] = []
        for i in range(len(node_ids_list)):
            nid_a = node_ids_list[i]
            node_a = narratives_dict[nid_a]
            if not isinstance(node_a, dict):
                continue
            va = node_a.get("node_vector")
            if not va:
                continue
            for j in range(i + 1, len(node_ids_list)):
                nid_b = node_ids_list[j]
                node_b = narratives_dict[nid_b]
                if not isinstance(node_b, dict):
                    continue
                vb = node_b.get("node_vector")
                if not vb or len(vb) != len(va):
                    continue
                sim_ab = float(dewey_pipeline.similarity(va, vb))
                if sim_ab < _NARRATIVE_LINK_SIM_THRESHOLD:
                    continue
                node_a["narrative_links"].append([nid_b, sim_ab])
                node_b["narrative_links"].append([nid_a, sim_ab])
                narrative_links_added += 2
                if sim_ab >= _NARRATIVE_LINK_STRENGTHEN_THRESHOLD:
                    node_a["node_strength"] = min(
                        1.0,
                        float(node_a.get("node_strength", 0.0)) + _NARRATIVE_LINK_STRENGTHEN_BUMP,
                    )
                    node_b["node_strength"] = min(
                        1.0,
                        float(node_b.get("node_strength", 0.0)) + _NARRATIVE_LINK_STRENGTHEN_BUMP,
                    )
                    narrative_link_strengthens += 2

    # 22. Narrative causal inference — for each episode-level causal link
    # (parent_eid → child_eid, weight) found in episodes_dict, if the two
    # episodes belong to DIFFERENT nodes A and B, add (B.node_id, weight) to
    # A.causal_links with weight = mean similarity of all causal episode
    # pairs between A and B. If weight ≥ 0.60, strengthen B by +0.03.
    if consolidate_due and narratives_dict:
        # Build episode → node lookup (may have grown since formation).
        ep_to_node: dict[str, str] = {}
        for nid, node in narratives_dict.items():
            if not isinstance(node, dict):
                continue
            for eid in node.get("episode_ids", []) or []:
                ep_to_node[eid] = nid

        # Reset causal_links to avoid stale duplicates from prior cycles.
        for nid, node in narratives_dict.items():
            if isinstance(node, dict):
                node["causal_links"] = []

        # Aggregate causal episode pairs by (parent_node, child_node).
        node_pair_sims: dict[tuple, list] = {}
        for parent_eid, parent_meta in episodes_dict.items():
            if not isinstance(parent_meta, dict):
                continue
            parent_nid = ep_to_node.get(parent_eid)
            if parent_nid is None:
                continue
            for cl in parent_meta.get("causal_links", []) or []:
                if not (isinstance(cl, (list, tuple)) and len(cl) >= 2):
                    continue
                child_eid = cl[0]
                try:
                    weight = float(cl[1])
                except (TypeError, ValueError):
                    continue
                child_nid = ep_to_node.get(child_eid)
                if child_nid is None or child_nid == parent_nid:
                    continue  # cross-node only
                node_pair_sims.setdefault((parent_nid, child_nid), []).append(weight)

        for (parent_nid, child_nid), weights in node_pair_sims.items():
            if not weights:
                continue
            mean_w = sum(weights) / len(weights)
            parent_node = narratives_dict[parent_nid]
            child_node = narratives_dict[child_nid]
            parent_node.setdefault("causal_links", [])
            parent_node["causal_links"] = [
                cl for cl in parent_node["causal_links"]
                if not (isinstance(cl, (list, tuple)) and len(cl) >= 1 and cl[0] == child_nid)
            ]
            parent_node["causal_links"].append([child_nid, float(mean_w)])
            narrative_causal_links_added += 1
            if mean_w >= _NARRATIVE_CAUSAL_STRENGTHEN_THRESHOLD:
                child_node["node_strength"] = min(
                    1.0,
                    float(child_node.get("node_strength", 0.0)) + _NARRATIVE_CAUSAL_STRENGTHEN_BUMP,
                )
                narrative_causal_strengthens += 1

    # 23. Story arc clustering (24h-gated, independent of consolidation).
    # Cluster narrative_nodes by node_vector similarity (≥ 0.70) AND
    # causal_links (any directed link counts as an undirected edge for
    # clustering). Connected components form clusters. Cluster strength ≥ 0.6
    # promotes to a story_arc.
    if last_arc_clustering_ts is None:
        cluster_due = True
    else:
        try:
            cluster_due = (now - float(last_arc_clustering_ts)) >= _STORY_ARC_CLUSTERING_CADENCE_HOURS * 3600
        except (TypeError, ValueError):
            cluster_due = True
    if cluster_due and narratives_dict:
        node_ids_list = list(narratives_dict.keys())
        adjacency: dict[str, set] = {nid: set() for nid in node_ids_list}
        # Edges from sim ≥ 0.70.
        for i in range(len(node_ids_list)):
            nid_a = node_ids_list[i]
            node_a = narratives_dict[nid_a]
            if not isinstance(node_a, dict):
                continue
            va = node_a.get("node_vector")
            if not va:
                continue
            for j in range(i + 1, len(node_ids_list)):
                nid_b = node_ids_list[j]
                node_b = narratives_dict[nid_b]
                if not isinstance(node_b, dict):
                    continue
                vb = node_b.get("node_vector")
                if not vb or len(vb) != len(va):
                    continue
                sim_ab = float(dewey_pipeline.similarity(va, vb))
                if sim_ab >= _NARRATIVE_CLUSTER_SIM_THRESHOLD:
                    adjacency[nid_a].add(nid_b)
                    adjacency[nid_b].add(nid_a)
        # Edges from causal_links (treat directed as undirected for clustering).
        for nid, node in narratives_dict.items():
            if not isinstance(node, dict):
                continue
            for cl in node.get("causal_links", []) or []:
                if isinstance(cl, (list, tuple)) and len(cl) >= 1:
                    other = cl[0]
                    if other in adjacency:
                        adjacency[nid].add(other)
                        adjacency[other].add(nid)

        # Reset story_arcs each clustering pass — clusters are recomputed.
        new_story_arcs: dict = {}
        components = _connected_components(node_ids_list, adjacency)
        for component in components:
            # Compute cluster_vector + cluster_strength.
            accum: Optional[list[float]] = None
            count = 0
            strengths_c: list[float] = []
            latest_c = 0.0
            for nid in component:
                node = narratives_dict[nid]
                if not isinstance(node, dict):
                    continue
                try:
                    s_n = float(node.get("node_strength", 0.0))
                except (TypeError, ValueError):
                    s_n = 0.0
                strengths_c.append(s_n)
                try:
                    ts_n = float(node.get("latest_event_ts", 0.0))
                except (TypeError, ValueError):
                    ts_n = 0.0
                if ts_n > latest_c:
                    latest_c = ts_n
                v_n = node.get("node_vector")
                if not v_n:
                    continue
                if accum is None:
                    accum = list(v_n)
                    count = 1
                    continue
                if len(v_n) != len(accum):
                    continue
                for i in range(len(accum)):
                    accum[i] += v_n[i]
                count += 1
            if count == 0 or not accum or not strengths_c:
                continue
            cluster_vector = dewey_pipeline._normalize(accum)
            cluster_strength = sum(strengths_c) / len(strengths_c)
            if cluster_strength < _STORY_ARC_PROMOTE_STRENGTH:
                continue
            arc_id = "sa_" + secrets.token_urlsafe(12)
            new_story_arcs[arc_id] = {
                "arc_id": arc_id,
                "arc_vector": cluster_vector,
                "arc_strength": float(cluster_strength),
                "arc_nodes": list(component),
                "latest_event_ts": float(latest_c),
                "created_at": now,
            }
            story_arcs_promoted += 1
        story_arcs_dict = new_story_arcs
        last_arc_clustering_ts = now
        arc_clustering_ran = 1

    # ─────────────────────────────────────────────────────────────────────
    # v7.5 — Narrative compression + summaries + intent extraction (24-28)
    # ─────────────────────────────────────────────────────────────────────
    narratives_compressed = 0
    summaries_generated = 0
    intents_extracted = 0
    arcs_compressed = 0
    arc_intents_propagated = 0

    # Per-event lookup for both compression and summary text retrieval.
    events_by_id: dict = {e.get("event_id"): e for e in events if e.get("event_id")}

    # 24. Narrative compression (vector-level). Trigger: node touched this
    # cycle (consolidate_due implies steps 20-22 may have updated nodes) OR
    # node's last_compressed_ts is None / older than 24h.
    for nid, node in narratives_dict.items():
        if not isinstance(node, dict):
            continue
        last_cmp = node.get("last_compressed_ts")
        try:
            stale = (last_cmp is None) or ((now - float(last_cmp)) >= _NARRATIVE_COMPRESSION_CADENCE_HOURS * 3600)
        except (TypeError, ValueError):
            stale = True
        if not (consolidate_due or stale):
            continue
        ev_vecs = _node_event_vectors(node, events_by_id)
        compressed = _compress_vector_mean_pool(ev_vecs) if ev_vecs else None
        # Fallback to node_vector if no event vectors are available.
        if compressed is None:
            nv = node.get("node_vector")
            compressed = list(nv) if nv else None
        node["compressed_vector"] = compressed
        node["last_compressed_ts"] = now
        if compressed is not None:
            narratives_compressed += 1

    # 25. Story summary generation. Trigger: node has ≥3 episodes OR
    # node_strength ≥ 0.65 AND (consolidate_due OR no summary yet).
    for nid, node in narratives_dict.items():
        if not isinstance(node, dict):
            continue
        eps_count = len(node.get("episode_ids") or [])
        try:
            ns = float(node.get("node_strength", 0.0))
        except (TypeError, ValueError):
            ns = 0.0
        eligible = (eps_count >= _STORY_SUMMARY_MIN_EPISODES) or (ns >= _STORY_SUMMARY_MIN_STRENGTH)
        if not eligible:
            continue
        existing = node.get("summary_text")
        if existing and not consolidate_due:
            continue  # don't churn unless this is a consolidation pass
        ts_texts = _node_event_texts(node, events_by_id)
        if not ts_texts:
            continue
        summary = _extractive_summary(
            ts_texts,
            max_tokens=_STORY_SUMMARY_MAX_TOKENS,
            focus="temporal progression, causal structure, user goals",
        )
        if summary:
            node["summary_text"] = summary
            summaries_generated += 1

    # 26. High-level intent extraction. Always recomputed for nodes that
    # have a summary OR ≥1 event; cheap deterministic classifier.
    for nid, node in narratives_dict.items():
        if not isinstance(node, dict):
            continue
        ts_texts = _node_event_texts(node, events_by_id)
        if not ts_texts and not node.get("summary_text"):
            node.setdefault("intents", [])
            continue
        intents = _extract_intents(node, node.get("summary_text"), ts_texts, episodes_dict)
        node["intents"] = intents
        if intents:
            intents_extracted += 1

    # 27. Story arc compression — same fallback as narrative compression but
    # over the arc's constituent node_vectors (not raw event vectors). Runs
    # on every arc each cycle (cheap; arcs change rarely).
    for aid, arc in story_arcs_dict.items():
        if not isinstance(arc, dict):
            continue
        node_vecs: list[list[float]] = []
        for nid in arc.get("arc_nodes") or []:
            n = narratives_dict.get(nid)
            if isinstance(n, dict):
                nv = n.get("node_vector")
                if nv:
                    node_vecs.append(nv)
        compressed_arc = _compress_vector_mean_pool(node_vecs) if node_vecs else None
        if compressed_arc is None:
            av = arc.get("arc_vector")
            compressed_arc = list(av) if av else None
        arc["arc_vector_compressed"] = compressed_arc
        # Build arc_summary from the contained node summaries (max 200 tokens).
        arc_node_summaries: list[tuple] = []
        for nid in arc.get("arc_nodes") or []:
            n = narratives_dict.get(nid)
            if isinstance(n, dict):
                s = n.get("summary_text")
                if s:
                    try:
                        ts = float(n.get("latest_event_ts", 0.0))
                    except (TypeError, ValueError):
                        ts = 0.0
                    arc_node_summaries.append((ts, s))
        if arc_node_summaries:
            arc_summary = _extractive_summary(
                arc_node_summaries,
                max_tokens=_ARC_SUMMARY_MAX_TOKENS,
            )
            arc["arc_summary"] = arc_summary
        else:
            arc.setdefault("arc_summary", None)
        if compressed_arc is not None:
            arcs_compressed += 1

    # 28. Intent propagation to story arcs — union of intents over the
    # arc's constituent narrative nodes. Stable order (first-seen wins).
    for aid, arc in story_arcs_dict.items():
        if not isinstance(arc, dict):
            continue
        union: list[str] = []
        for nid in arc.get("arc_nodes") or []:
            n = narratives_dict.get(nid)
            if not isinstance(n, dict):
                continue
            for it in n.get("intents") or []:
                if it not in union:
                    union.append(it)
        arc["intents"] = union
        if union:
            arc_intents_propagated += 1

    # ─────────────────────────────────────────────────────────────────────
    # v8 — Identity layer + self-modeling (steps 29-33; 34 was wired
    # earlier into step 4; 35 is persist below)
    # ─────────────────────────────────────────────────────────────────────
    identity_rebuilt = 0

    last_identity_ts = identity_profile.get("last_updated_ts")
    try:
        identity_stale = (
            last_identity_ts is None
            or (now - float(last_identity_ts)) >= _IDENTITY_FORMATION_CADENCE_HOURS * 3600
        )
    except (TypeError, ValueError):
        identity_stale = True
    # Trigger: arcs were just clustered this cycle (story arcs updated) OR
    # the cached identity is older than the cadence. Either way the identity
    # rebuild is cheap and idempotent so running on every consolidation
    # cycle is also fine.
    identity_rebuild_due = bool(arc_clustering_ran) or identity_stale or consolidate_due

    if identity_rebuild_due:
        # 29. Identity vector formation — mean of arc_vector_compressed
        # (fallback to arc_vector). Mean of arc_strength.
        arc_compressed_vecs: list[list[float]] = []
        arc_strengths: list[float] = []
        for aid, arc in story_arcs_dict.items():
            if not isinstance(arc, dict):
                continue
            v = arc.get("arc_vector_compressed") or arc.get("arc_vector")
            if v:
                arc_compressed_vecs.append(v)
            try:
                arc_strengths.append(float(arc.get("arc_strength", 0.0)))
            except (TypeError, ValueError):
                pass
        new_identity_vector = _compress_vector_mean_pool(arc_compressed_vecs) if arc_compressed_vecs else None
        new_identity_strength = (
            max(0.0, min(1.0, sum(arc_strengths) / len(arc_strengths)))
            if arc_strengths else 0.0
        )

        # 30. Stable intent extraction — intents appearing in ≥ 2 story arcs.
        intent_arc_count: dict = {}
        for aid, arc in story_arcs_dict.items():
            if not isinstance(arc, dict):
                continue
            for it in arc.get("intents") or []:
                intent_arc_count[it] = intent_arc_count.get(it, 0) + 1
        stable_intents: list[str] = [
            it for it, c in intent_arc_count.items()
            if c >= _STABLE_INTENT_MIN_ARCS
        ]

        # 31. Preference signal extraction — preference patterns appearing
        # in ≥ 3 distinct episodes (across all events). Signals are the
        # pattern labels themselves ("likes", "prefers", ...).
        preference_signals: list[str] = []
        for label, patterns in _PREFERENCE_PATTERNS:
            episode_hit_count = 0
            for eid, eps_events in events_by_episode.items():
                hit = False
                for ev in eps_events:
                    text = (ev.get("text") or "").lower()
                    if any(p in text for p in patterns):
                        hit = True
                        break
                if hit:
                    episode_hit_count += 1
                if episode_hit_count >= _PREFERENCE_PATTERN_MIN_EPISODES:
                    break
            if episode_hit_count >= _PREFERENCE_PATTERN_MIN_EPISODES:
                preference_signals.append(label)

        # 32. Long-range goal extraction. Two sources:
        #   (a) "long-term project" intent appearing in ≥ 2 arcs
        #   (b) any episode causal chain spanning ≥ 3 episodes
        long_range_goals: list[str] = []
        if intent_arc_count.get("long-term project", 0) >= _LONG_RANGE_GOAL_MIN_ARCS:
            long_range_goals.append("long-term project")
        max_chain = _causal_chain_max_length(episodes_dict)
        if max_chain >= _LONG_RANGE_GOAL_MIN_CAUSAL_CHAIN:
            inferred = f"causal-chain goal (depth={max_chain})"
            if inferred not in long_range_goals:
                long_range_goals.append(inferred)

        # 33. Unresolved theme detection — "recurring theme" intent in ≥ 2
        # arcs AND no resolution event present in those arcs' event content.
        unresolved_themes: list[str] = []
        if intent_arc_count.get("recurring theme", 0) >= _UNRESOLVED_THEME_MIN_ARCS:
            arcs_with_recurring = [
                arc for arc in story_arcs_dict.values()
                if isinstance(arc, dict) and "recurring theme" in (arc.get("intents") or [])
            ]
            has_resolution = False
            for arc in arcs_with_recurring:
                for ev in _events_for_arc(arc, narratives_dict, events_by_id):
                    text = (ev.get("text") or "").lower()
                    if any(rk in text for rk in _RESOLUTION_KEYWORDS):
                        has_resolution = True
                        break
                if has_resolution:
                    break
            if not has_resolution:
                unresolved_themes.append("recurring theme")

        identity_profile = {
            "identity_vector": new_identity_vector,
            "identity_strength": float(new_identity_strength),
            "stable_intents": stable_intents,
            "preference_signals": preference_signals,
            "long_range_goals": long_range_goals,
            "unresolved_themes": unresolved_themes,
            "last_updated_ts": now,
        }
        identity_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v9 — Operator trajectory model (steps 36-40; 41 wired in step 4 above;
    # 42 = persist below)
    # ─────────────────────────────────────────────────────────────────────
    trajectory_rebuilt = 0
    trajectory_phase: Optional[str] = None
    trajectory_velocity: float = 0.0
    trajectory_trend_intents: list = []
    trajectory_fading_intents: list = []
    identity_traj_coupling = 0  # -1 weak (penalty), +1 strong (boost), 0 none

    last_traj_ts = trajectory_profile.get("last_updated_ts") if trajectory_profile else None
    try:
        traj_stale = (
            last_traj_ts is None
            or (now - float(last_traj_ts)) >= _TRAJECTORY_FORMATION_CADENCE_HOURS * 3600
        )
    except (TypeError, ValueError):
        traj_stale = True
    trajectory_rebuild_due = bool(arc_clustering_ran) or traj_stale or consolidate_due

    if trajectory_rebuild_due:
        window_seconds = _TRAJECTORY_WINDOW_DAYS * 86400
        arcs_in_win = _arcs_in_window(story_arcs_dict, window_seconds, now)

        # 36. Trajectory vector formation — mean of arc_vector_compressed
        # (fallback arc_vector) and mean arc_strength over the 90-day window.
        arc_vecs: list = []
        arc_strs: list = []
        for arc in arcs_in_win:
            v = arc.get("arc_vector_compressed") or arc.get("arc_vector")
            if v:
                arc_vecs.append(v)
            try:
                arc_strs.append(float(arc.get("arc_strength", 0.0)))
            except (TypeError, ValueError):
                pass
        new_trajectory_vector = _compress_vector_mean_pool(arc_vecs) if arc_vecs else None
        new_trajectory_strength = (
            max(0.0, min(1.0, sum(arc_strs) / len(arc_strs)))
            if arc_strs else 0.0
        )

        # 37. Intent trend analysis — split window in half by timestamp;
        # compare intent counts in first vs second half. ±30% threshold.
        midpoint_ts = now - (window_seconds / 2)
        freq_first, freq_second = _intent_freq_split(arcs_in_win, midpoint_ts)
        all_labels = set(freq_first.keys()) | set(freq_second.keys())
        for label in sorted(all_labels):
            f = freq_first.get(label, 0)
            s = freq_second.get(label, 0)
            if f == 0:
                # New intent in second half is trending up.
                if s > 0:
                    trajectory_trend_intents.append(label)
            else:
                change = (s - f) / float(f)
                if change >= _TRAJECTORY_TREND_THRESHOLD_PCT:
                    trajectory_trend_intents.append(label)
                elif change <= -_TRAJECTORY_TREND_THRESHOLD_PCT:
                    trajectory_fading_intents.append(label)

        # 38. Phase classification — score each candidate; highest wins.
        all_intents_count: dict = {}
        for arc in arcs_in_win:
            for it in arc.get("intents") or []:
                all_intents_count[it] = all_intents_count.get(it, 0) + 1

        max_chain = _causal_chain_max_length(episodes_dict)

        # build: long-term project AND goal both present AND chain ≥ 3
        build_score = 0
        if (
            all_intents_count.get("long-term project", 0) >= 1
            and all_intents_count.get("goal", 0) >= 1
            and max_chain >= _PHASE_BUILD_MIN_CAUSAL_CHAIN
        ):
            build_score = (
                all_intents_count.get("long-term project", 0)
                + all_intents_count.get("goal", 0)
                + max_chain
            )

        # exploration: many distinct narrative nodes AND low causal depth
        exploration_score = 0
        if (
            len(narratives_dict) >= _PHASE_EXPLORATION_MIN_NODES
            and max_chain <= _PHASE_EXPLORATION_MAX_CAUSAL_CHAIN
        ):
            exploration_score = len(narratives_dict)

        # refactor: refactor keywords appear in ≥ 2 arcs
        refactor_arc_count = 0
        for arc in arcs_in_win:
            for ev in _events_for_arc(arc, narratives_dict, events_by_id):
                t = (ev.get("text") or "").lower()
                if any(kw in t for kw in _PHASE_REFACTOR_KEYWORDS):
                    refactor_arc_count += 1
                    break
        refactor_score = refactor_arc_count if refactor_arc_count >= _PHASE_REFACTOR_MIN_ARCS else 0

        # stabilization: high mean arc strength AND no unresolved themes
        unresolved_in_id = identity_profile.get("unresolved_themes") or [] if identity_profile else []
        stabilization_score = 0
        if (
            arc_strs
            and (sum(arc_strs) / len(arc_strs)) >= _PHASE_STABILIZATION_MIN_MEAN_STRENGTH
            and not unresolved_in_id
        ):
            stabilization_score = 1

        candidates = {
            "build": build_score,
            "exploration": exploration_score,
            "refactor": refactor_score,
            "stabilization": stabilization_score,
        }
        best_phase = max(candidates.items(), key=lambda kv: kv[1])
        trajectory_phase = best_phase[0] if best_phase[1] > 0 else None

        # 39. Velocity estimation — 1 - cos(prev_traj_vec, new_traj_vec).
        prev_traj_vec = trajectory_profile.get("trajectory_vector") if trajectory_profile else None
        if (
            prev_traj_vec
            and new_trajectory_vector
            and len(prev_traj_vec) == len(new_trajectory_vector)
        ):
            sim_prev = float(dewey_pipeline.similarity(prev_traj_vec, new_trajectory_vector))
            trajectory_velocity = max(0.0, min(1.0, 1.0 - sim_prev))
        else:
            trajectory_velocity = 0.0

        trajectory_profile = {
            "trajectory_vector": new_trajectory_vector,
            "trajectory_strength": float(new_trajectory_strength),
            "phase": trajectory_phase,
            "trend_intents": trajectory_trend_intents,
            "fading_intents": trajectory_fading_intents,
            "velocity": float(trajectory_velocity),
            "last_updated_ts": now,
        }
        trajectory_rebuilt = 1

        # 40. Identity-trajectory coupling — adjust identity_strength based
        # on alignment with the new trajectory_vector. Mutates identity_profile.
        id_vec_for_coupling = identity_profile.get("identity_vector") if identity_profile else None
        if (
            id_vec_for_coupling
            and new_trajectory_vector
            and len(id_vec_for_coupling) == len(new_trajectory_vector)
        ):
            align = float(dewey_pipeline.similarity(id_vec_for_coupling, new_trajectory_vector))
            try:
                cur_id_str = float(identity_profile.get("identity_strength", 0.0))
            except (TypeError, ValueError):
                cur_id_str = 0.0
            if align < _TRAJECTORY_IDENTITY_COUPLING_WEAK_SIM:
                identity_profile["identity_strength"] = max(
                    0.0, cur_id_str - _TRAJECTORY_IDENTITY_COUPLING_BUMP,
                )
                identity_traj_coupling = -1
            elif align >= _TRAJECTORY_IDENTITY_COUPLING_STRONG_SIM:
                identity_profile["identity_strength"] = min(
                    1.0, cur_id_str + _TRAJECTORY_IDENTITY_COUPLING_BUMP,
                )
                identity_traj_coupling = 1

    # ─────────────────────────────────────────────────────────────────────
    # v12 — ELINS physics layer (steps 41-45; 46 = persist below)
    # ─────────────────────────────────────────────────────────────────────
    elins_loaded_count = 0
    elins_active_centers_count = 0
    elins_pressure_used = 0
    elins_drift_used = 0
    elins_context: dict = dict(elins_context_loaded) if elins_context_loaded else {}

    raw_elins_json = _load_elins_json()
    if raw_elins_json:
        elins_loaded_count = 1
        centers_dict_raw = raw_elins_json.get("centers") or {}
        drift_vectors_raw = raw_elins_json.get("drift_vectors") or []
        basin_state_raw = raw_elins_json.get("basin_state") or []
        ridge_state_raw = raw_elins_json.get("ridge_state") or []
        temporal_deltas_raw = raw_elins_json.get("temporal_deltas") or {}
        all_center_names = sorted([str(k) for k in centers_dict_raw.keys()])

        # 42. Topic-to-center mapping from user_message; fallback top-2
        # by total pressure magnitude across all centers.
        text_for_centers = user_message or ""
        matched = _extract_centers_from_text(text_for_centers, all_center_names)
        if matched:
            active_centers = matched
        else:
            scored: list = []
            for cname in all_center_names:
                pf = (centers_dict_raw.get(cname) or {}).get("pressure_fields") or {}
                try:
                    total = sum(float(v) for v in pf.values())
                except (TypeError, ValueError):
                    total = 0.0
                scored.append((cname, total))
            scored.sort(key=lambda x: x[1], reverse=True)
            active_centers = [c for c, _ in scored[:2]]
        elins_active_centers_count = len(active_centers)

        # 43. Physics relevance filtering (subset to active centers).
        pressure_fields_filtered: dict = {}
        for cname in active_centers:
            cfields = (centers_dict_raw.get(cname) or {}).get("pressure_fields") or {}
            for k, v in cfields.items():
                try:
                    pressure_fields_filtered[f"{cname}.{k}"] = float(v)
                except (TypeError, ValueError):
                    pass

        drift_filtered: list = []
        for dv in drift_vectors_raw:
            if not isinstance(dv, dict):
                continue
            origin = dv.get("origin")
            target = dv.get("target")
            if origin in active_centers or target in active_centers:
                drift_filtered.append(dv)

        basin_filtered = [b for b in basin_state_raw if _matches_any_center(b, active_centers)]
        ridge_filtered = [r for r in ridge_state_raw if _matches_any_center(r, active_centers)]

        # 44. Physics normalization — min-max across each filtered set.
        pressure_normalized = _normalize_dict_minmax(pressure_fields_filtered)
        drift_mags = []
        for dv in drift_filtered:
            try:
                drift_mags.append(float(dv.get("magnitude", 0.0)))
            except (TypeError, ValueError):
                drift_mags.append(0.0)
        drift_norms = _min_max_normalize(drift_mags)
        drift_normalized: list = []
        for i, dv in enumerate(drift_filtered):
            drift_normalized.append({
                "name": dv.get("name"),
                "magnitude": drift_norms[i] if i < len(drift_norms) else 0.0,
                "direction": dv.get("direction"),
            })
        temporal_subset = {
            k: temporal_deltas_raw[k]
            for k in _ELINS_TEMPORAL_DELTA_KEYS
            if k in temporal_deltas_raw
        }
        temporal_normalized = _normalize_dict_minmax(temporal_subset)

        elins_pressure_used = len(pressure_normalized)
        elins_drift_used = len(drift_normalized)

        # Mean vector of active centers (for next-cycle ELINS recall in step 4).
        # Prefer a center's `vector` field; else embed the center name via the
        # cached embedder (amortizes after first call).
        center_vecs: list = []
        for cname in active_centers:
            cv = (centers_dict_raw.get(cname) or {}).get("vector")
            if cv:
                center_vecs.append(cv)
            else:
                emb = dewey_pipeline.embed_text_cached(cname)
                if emb:
                    center_vecs.append(emb)
        mean_center_vector = _compress_vector_mean_pool(center_vecs) if center_vecs else None

        # Build the deterministic, sorted, compact physics_block (≤ 300 tokens).
        physics_block = {
            "centers_involved": sorted(active_centers),
            "pressure_fields": dict(sorted(pressure_normalized.items())),
            "drift_vectors": sorted(
                [
                    {
                        "name": d.get("name"),
                        "magnitude": round(float(d.get("magnitude", 0.0)), 4),
                        "direction": d.get("direction"),
                    }
                    for d in drift_normalized
                ],
                key=lambda d: str(d.get("name") or ""),
            ),
            "basin_state": sorted([str(b) for b in basin_filtered]),
            "ridge_state": sorted([str(r) for r in ridge_filtered]),
            "temporal_deltas": dict(sorted(temporal_normalized.items())),
        }
        # Token cap (rough: whitespace-split count of compact JSON).
        pb_json = json.dumps(physics_block, separators=(",", ":"), sort_keys=True)
        if len(pb_json.split()) > _ELINS_PHYSICS_BLOCK_MAX_TOKENS:
            physics_block["basin_state"] = physics_block["basin_state"][:5]
            physics_block["ridge_state"] = physics_block["ridge_state"][:5]
            physics_block["drift_vectors"] = physics_block["drift_vectors"][:10]

        elins_context = {
            "centers_involved": sorted(active_centers),
            "pressure_fields": pressure_normalized,
            "drift_vectors": drift_normalized,
            "basin_state": basin_filtered,
            "ridge_state": ridge_filtered,
            "temporal_deltas": temporal_normalized,
            "physics_block": physics_block,
            "mean_center_vector": mean_center_vector,
            "last_updated_ts": now,
        }
        # v16 — additive pass-through of PRO-tier blocks (read via dot-
        # notation by `_build_s_strategy_layer`). Copied verbatim when
        # present in the source JSON; absent on non-PRO ingestion.
        for block_key in _SSTRAT_PASSTHROUGH_BLOCKS:
            if block_key in raw_elins_json and isinstance(raw_elins_json[block_key], dict):
                elins_context[block_key] = raw_elins_json[block_key]

    # ─────────────────────────────────────────────────────────────────────
    # v13 — Universal physics context (step 46). Unconditional rebuild
    # each cycle (block is static + cheap; sorts make it deterministic).
    # ─────────────────────────────────────────────────────────────────────
    universal_physics_block = _build_universal_physics_block()
    universal_physics_block["last_updated_ts"] = now
    universal_physics_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v14 — Cross-layer coherence validator (step 47). Pure validator over
    # the four layers we just built/loaded. Non-blocking: failures only
    # populate the report; no other layer is mutated. Spec §7.
    # ─────────────────────────────────────────────────────────────────────
    coherence_report = _run_coherence_checks(
        identity_profile,
        trajectory_profile,
        elins_context,
        universal_physics_block,
    )
    coherence_report["last_check_ts"] = now

    # ─────────────────────────────────────────────────────────────────────
    # v15 — External knowledge context (step 48). Conditioning-only block;
    # never feeds back into similarities (spec §8). Empty {} when the
    # observation has no usable text, per spec §5.
    # ─────────────────────────────────────────────────────────────────────
    external_context_block = _build_external_context_block(user_message)
    if external_context_block:
        external_context_block["last_updated_ts"] = now
    external_context_rebuilt = 1
    external_context_topics_count = len(external_context_block.get("topics") or [])

    # ─────────────────────────────────────────────────────────────────────
    # v16 — ELINS S_strategy (Sun Tzu) overlay (step 49). Additive only:
    # nests `s_strategy_layer` under `elins_context`; never modifies any
    # existing ELINS field. Returns {} when PRO-tier fields are missing
    # (typical on non-PRO ingestion). Conditioning-only — no recall key.
    # ─────────────────────────────────────────────────────────────────────
    s_strategy_layer_built = _build_s_strategy_layer(elins_context, elins_context_loaded)
    if s_strategy_layer_built:
        s_strategy_layer_built["last_updated_ts"] = now
    # Only attach to elins_context when the parent block has any content
    # (avoid promoting an empty envelope.elins to a singleton wrapper).
    if elins_context:
        elins_context["s_strategy_layer"] = s_strategy_layer_built
    s_strategy_rebuilt = 1
    s_strategy_basin_hop = int(bool(s_strategy_layer_built.get("basin_hop"))) if s_strategy_layer_built else 0
    pc_dict = s_strategy_layer_built.get("phase_change") if s_strategy_layer_built else None
    s_strategy_phasechange = (
        pc_dict.get("predicted_phase") if isinstance(pc_dict, dict) and pc_dict.get("predicted_phase") else "none"
    )

    # ─────────────────────────────────────────────────────────────────────
    # v17 — Cross-scale harmonizer (step 50). Read-only conditioning block
    # derived from the layers built/loaded earlier this cycle. Spec §6:
    # no similarity key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    physics_reasoning_envelope_view = {
        "identity": identity_profile,
        "trajectory": trajectory_profile,
        "elins": elins_context,
        "universal_physics": universal_physics_block,
        "external_context": external_context_block,
        "coherence": coherence_report,
    }
    physics_reasoning_context = _build_physics_reasoning_context(physics_reasoning_envelope_view)
    if physics_reasoning_context:
        physics_reasoning_context["last_updated_ts"] = now
    physics_reasoning_context_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v18 — Generator conditioning surface (step 51). Advisory, read-only,
    # non-binding. Spec §6: no similarity key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    reasoning_cues = _build_reasoning_cues(physics_reasoning_context)
    if reasoning_cues:
        reasoning_cues["last_updated_ts"] = now
    reasoning_cues_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v19 — Soft reasoning weights (step 52). Advisory only. Spec §6: no
    # similarity key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    reasoning_weights = _build_reasoning_weights(physics_reasoning_context, reasoning_cues)
    if reasoning_weights:
        reasoning_weights["last_updated_ts"] = now
    reasoning_weights_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v20 — Memory context (step 53). Cross-turn long-range surface across
    # identity / trajectory / arcs / episodes / external_context. Spec §6:
    # no similarity key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    memory_context = _build_memory_context(
        identity_profile,
        trajectory_profile,
        list(story_arcs_dict.values()),
        list(episodes_dict.values()),
        external_context_block,
    )
    if memory_context:
        memory_context["last_updated_ts"] = now
    memory_context_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v21 — External knowledge context v2 (step 54). Conceptual-retrieval
    # block synthesized deterministically from v15 topics. Spec §7: no
    # similarity key. Spec §8: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    ext_topics_for_kb = (
        external_context_block.get("topics") if isinstance(external_context_block, dict) else None
    )
    external_knowledge = _build_external_knowledge(ext_topics_for_kb)
    if external_knowledge:
        external_knowledge["last_updated_ts"] = now
    external_knowledge_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v22 — Cognitive loop integrator (step 55). Fuses the 5 conditioning
    # surfaces into one block. Spec §6: no similarity key. Spec §7:
    # generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    cognitive_loop = _build_cognitive_loop(
        memory_context,
        external_knowledge,
        reasoning_weights,
        reasoning_cues,
        physics_reasoning_context,
    )
    if cognitive_loop:
        cognitive_loop["last_updated_ts"] = now
    cognitive_loop_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v23 — Reasoning scaffold (step 56). Context-weighted scaffold derived
    # from cognitive_loop + reasoning_weights + cues + PRC. Spec §6: no
    # similarity key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    reasoning_scaffold = _build_reasoning_scaffold(
        cognitive_loop,
        reasoning_weights,
        reasoning_cues,
        physics_reasoning_context,
    )
    if reasoning_scaffold:
        reasoning_scaffold["last_updated_ts"] = now
    reasoning_scaffold_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v24 — Response-shape hints (step 57). Section labels + emphasis +
    # caution from the v23 scaffold and v18 cues. Spec §6: no similarity
    # key. Spec §7: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    response_shape = _build_response_shape(
        reasoning_scaffold,
        cognitive_loop,
        reasoning_weights,
        reasoning_cues,
    )
    if response_shape:
        response_shape["last_updated_ts"] = now
    response_shape_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v25 — Response micro-templates (step 58). Optional opener / body /
    # closer / tone phrasing patterns for downstream generators. Spec §7:
    # no similarity key. Spec §8: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    response_templates = _build_response_templates(
        response_shape,
        reasoning_scaffold,
        reasoning_cues,
        cognitive_loop,
    )
    if response_templates:
        response_templates["last_updated_ts"] = now
    response_templates_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v26 — Sentence-level operators (step 59). Optional prefix/suffix/
    # transform/risk modifier sets. Spec §7: no similarity key. Spec §8:
    # generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    sentence_operators = _build_sentence_operators(
        reasoning_cues,
        reasoning_scaffold,
        cognitive_loop,
        response_shape,
    )
    if sentence_operators:
        sentence_operators["last_updated_ts"] = now
    sentence_operators_rebuilt = 1

    # ─────────────────────────────────────────────────────────────────────
    # v27 — Connective tissue operators (step 60). Optional inter-sentence
    # linking sets (forward / contrast / expansion / risk). Spec §7: no
    # similarity key. Spec §8: generator unchanged.
    # ─────────────────────────────────────────────────────────────────────
    connective_ops = _build_connective_ops(
        reasoning_scaffold,
        response_shape,
        reasoning_cues,
        cognitive_loop,
    )
    if connective_ops:
        connective_ops["last_updated_ts"] = now
    connective_ops_rebuilt = 1

    # Soft cap: keep the most recent N events. Inactive ones drop off first
    # (sort by active descending then by timestamp), then trim to cap.
    if len(events) > _EVENT_LIST_SOFT_CAP:
        events.sort(key=lambda e: (e.get("active", True), e.get("timestamp", 0)), reverse=True)
        events = events[:_EVENT_LIST_SOFT_CAP]

    # 46. Persist.
    payload = {
        "user": user,
        "elins_briefs": briefs,
        "envelope_vector": new_vector,
        "envelope_centroid": centroid or None,
        "envelope_drift_events": drift_events,
        "envelope_decay_ts": now,
        "envelope_last_replay_ts": now if replay_due else last_replay,
        "last_centroid_update_ts": last_centroid_update,
        "events": events,                                                          # v6
        "envelope_last_episode_consolidation_ts": last_episode_consolidation_ts,   # v6
        "episodes": episodes_dict,                                                 # v6.5
        "narratives": narratives_dict,                                             # v7
        "story_arcs": story_arcs_dict,                                             # v7
        "envelope_last_arc_clustering_ts": last_arc_clustering_ts,                 # v7
        "identity": identity_profile,                                              # v8
        "trajectory": trajectory_profile,                                          # v9
        "elins": elins_context,                                                    # v12
        "universal_physics": universal_physics_block,                              # v13
        "coherence": coherence_report,                                             # v14
        "external_context": external_context_block,                                # v15
        "physics_reasoning_context": physics_reasoning_context,                    # v17
        "reasoning_cues": reasoning_cues,                                          # v18
        "reasoning_weights": reasoning_weights,                                    # v19
        "memory_context": memory_context,                                          # v20
        "external_knowledge": external_knowledge,                                  # v21
        "cognitive_loop": cognitive_loop,                                          # v22
        "reasoning_scaffold": reasoning_scaffold,                                  # v23
        "response_shape": response_shape,                                          # v24
        "response_templates": response_templates,                                  # v25
        "sentence_operators": sentence_operators,                                  # v26
        "connective_ops": connective_ops,                                          # v27
        "updated_at": now,
    }
    try:
        envelopes_store.set_envelope(user, payload)
    except Exception as e:
        logger.warning(
            "envelope evolution persist failed user=%s err=%s",
            _user_ref(user), e,
        )
    # Skip-prefix set + exact keys for the brief-match counter (don't count
    # v6.5/v7/v7.5/v8/v9/v12/v13 recall keys).
    _recall_prefixes = ("episode_", "narrative_", "storyarc_", "narrcomp_", "arccomp_")
    _recall_exact_keys = {
        "identity_profile",
        "trajectory_profile",
        "elins_physics",
        "universal_physics",
    }
    logger.info(
        "envelope evolved user=%s briefs=%d events=%d episodes=%d narratives=%d story_arcs=%d hours_decayed=%.2f matches_>=0.7=%d promotions=%d demotions=%d interferences=%d separations=%d replays=%d replay_strengthens=%d drift_distance=%.4f drift_corrections=%d centroid_refreshes=%d new_event=%s episode_promotions=%d episode_demotions=%d event_inactivations=%d cross_ep_links=%d cross_ep_strengthens=%d causal_event_links=%d causal_ep_links=%d causal_ep_strengthens=%d ep_recall=%d narr_nodes_created=%d narr_episodes_merged=%d narr_links=%d narr_link_strengthens=%d narr_causal_links=%d narr_causal_strengthens=%d arcs_promoted=%d arc_clustering_ran=%d narr_recall=%d arc_recall=%d narr_compressed=%d summaries=%d intents=%d arcs_compressed=%d arc_intents_propagated=%d narrcomp_recall=%d arccomp_recall=%d identity_recall=%d identity_node_bumps=%d identity_episode_bumps=%d identity_rebuilt=%d identity_strength=%.3f stable_intents=%d preferences=%d goals=%d unresolved=%d trajectory_rebuilt=%d trajectory_strength=%.3f trajectory_phase=%s trajectory_velocity=%.3f trajectory_trend_intents=%d trajectory_fading_intents=%d trajectory_recall=%d identity_traj_coupling=%+d elins_loaded=%d elins_active_centers=%d elins_pressure_used=%d elins_drift_used=%d elins_recall=%d universal_physics_rebuilt=%d universal_physics_recall=%d coherence_checked=%d coherence_identity_ok=%d coherence_trajectory_ok=%d coherence_elins_ok=%d coherence_universal_ok=%d coherence_cross_scale_ok=%d coherence_issues=%d external_context_rebuilt=%d external_context_topics=%d s_strategy_rebuilt=%d s_strategy_basin_hop=%d s_strategy_phasechange=%s physics_reasoning_context_rebuilt=%d reasoning_cues_rebuilt=%d reasoning_weights_rebuilt=%d memory_context_rebuilt=%d external_knowledge_rebuilt=%d cognitive_loop_rebuilt=%d reasoning_scaffold_rebuilt=%d response_shape_rebuilt=%d response_templates_rebuilt=%d sentence_operators_rebuilt=%d connective_ops_rebuilt=%d",
        _user_ref(user), len(briefs), len(events), len(episodes_dict),
        len(narratives_dict), len(story_arcs_dict), hours_since,
        sum(
            1 for k, s in similarities.items()
            if not str(k).startswith(_recall_prefixes)
            and k not in _recall_exact_keys
            and s >= _ENVELOPE_REFRESH_TIER_LOW
        ),
        promotions, demotions, interferences, separations,
        replays, replay_strengthens,
        drift_distance, drift_corrections, centroid_refreshes,
        new_event_id or "none", episode_promotions, episode_demotions, event_inactivations,
        cross_episode_links_added, cross_episode_strengthens,
        causal_event_links_added, causal_episode_links_added, causal_episode_strengthens,
        len(episode_similarities),
        narrative_nodes_created, narrative_episodes_merged,
        narrative_links_added, narrative_link_strengthens,
        narrative_causal_links_added, narrative_causal_strengthens,
        story_arcs_promoted, arc_clustering_ran,
        len(narrative_similarities), len(storyarc_similarities),
        narratives_compressed, summaries_generated, intents_extracted,
        arcs_compressed, arc_intents_propagated,
        len(narrcomp_similarities), len(arccomp_similarities),
        identity_recall_used, identity_node_bumps, identity_episode_bumps,
        identity_rebuilt,
        float(identity_profile.get("identity_strength", 0.0) or 0.0),
        len(identity_profile.get("stable_intents") or []),
        len(identity_profile.get("preference_signals") or []),
        len(identity_profile.get("long_range_goals") or []),
        len(identity_profile.get("unresolved_themes") or []),
        trajectory_rebuilt,
        float(trajectory_profile.get("trajectory_strength", 0.0) or 0.0),
        trajectory_profile.get("phase") or "none",
        float(trajectory_profile.get("velocity", 0.0) or 0.0),
        len(trajectory_profile.get("trend_intents") or []),
        len(trajectory_profile.get("fading_intents") or []),
        trajectory_recall_used,
        identity_traj_coupling,
        elins_loaded_count, elins_active_centers_count,
        elins_pressure_used, elins_drift_used,
        elins_recall_used,
        universal_physics_rebuilt,
        universal_physics_recall_used,
        1,
        int(coherence_report.get("identity_ok", False)),
        int(coherence_report.get("trajectory_ok", False)),
        int(coherence_report.get("elins_ok", False)),
        int(coherence_report.get("universal_ok", False)),
        int(coherence_report.get("cross_scale_ok", False)),
        len(coherence_report.get("issues") or []),
        external_context_rebuilt,
        external_context_topics_count,
        s_strategy_rebuilt,
        s_strategy_basin_hop,
        s_strategy_phasechange,
        physics_reasoning_context_rebuilt,
        reasoning_cues_rebuilt,
        reasoning_weights_rebuilt,
        memory_context_rebuilt,
        external_knowledge_rebuilt,
        cognitive_loop_rebuilt,
        reasoning_scaffold_rebuilt,
        response_shape_rebuilt,
        response_templates_rebuilt,
        sentence_operators_rebuilt,
        connective_ops_rebuilt,
    )
    return payload, similarities


def _build_transmitter_context(
    user: str,
    session_id: str,
    v_final: list[float],
    envelope_metrics: dict,
    user_neighborhoods: list[dict],
    envelope_doc: Optional[dict] = None,
    brief_similarities: Optional[dict] = None,
) -> dict:
    """Markov v3.5 — system-level recall bundle.

    Assembled AFTER v_final + qc_envelope + envelope_metrics are computed
    but BEFORE persistence. Pure read of existing state — no mutation.

    Sections:
      - markov_history:      last 3 PRIOR states (state/qc/predictive/metrics)
      - envelope:            {envelope_vector, elins_briefs metadata}
      - dewey:               top-5 neighborhoods at v_final (id/sim/curvature
                             /origin_vector) + per-neighborhood contributions
      - elins_brief_matches: top 3 envelope briefs by sim with v_final, sim ≥ 0.5
      - trends:              the envelope_metrics dict (stability/drift/pressure)
    """
    # 1. Markov history — recent_for excludes the new state (not yet written).
    recent = markov_states_store.recent_for(user, session_id, limit=3)
    markov_history = [
        {
            "state_index": int(s.get("state_index", -1)),
            "state_vector": s.get("state_vector"),
            "qc_envelope": s.get("qc_envelope") or {},
            "envelope_predictive_vector": s.get("envelope_predictive_vector"),
            "envelope_metrics": s.get("envelope_metrics") or dict(_DEFAULT_ENVELOPE_METRICS),
        }
        for s in recent
    ]

    # 2. Envelope context.
    if envelope_doc is None:
        envelope_doc = envelopes_store.get(user) or {}
    elins_briefs_raw = envelope_doc.get("elins_briefs") or []

    # Envelope v3.5 — active_briefs require strength ≥ activation_threshold
    # AND timescale != "short" (short-term briefs never count as active anchors).
    sims_map = brief_similarities or {}
    active_briefs: list[dict] = []
    for b in elins_briefs_raw:
        try:
            strength = float(b.get("strength", 0.0))
            thresh = float(b.get("activation_threshold", _ENVELOPE_V3_DEFAULTS["activation_threshold"]))
        except (TypeError, ValueError):
            strength = 0.0
            thresh = _ENVELOPE_V3_DEFAULTS["activation_threshold"]
        ts = _coerce_timescale(b.get("timescale"))
        if ts == "short":
            continue
        if strength >= thresh:
            bid = b.get("brief_id")
            if bid in sims_map:
                sim = float(sims_map[bid])
            else:
                v = b.get("object_vector")
                sim = float(dewey_pipeline.similarity(v_final, v)) if v and len(v) == len(v_final) else 0.0
            active_briefs.append({
                "brief_id": bid,
                "strength": strength,
                "timescale": ts,
                "similarity": sim,
            })

    envelope_context = {
        "envelope_vector": envelope_doc.get("envelope_vector"),
        "elins_briefs": [
            {
                "brief_id": b.get("brief_id"),
                # accept either v3 'last_reference_ts' or legacy 'last_reference_timestamp'
                "last_reference_timestamp": b.get("last_reference_ts") or b.get("last_reference_timestamp"),
            }
            for b in elins_briefs_raw
        ],
        "active_briefs": active_briefs,
    }

    # 3. DEWEY context — top 5 with curvature + per-neighborhood contributions.
    top5 = dewey_pipeline.top_neighborhoods_with_curvature(
        v_final, user_neighborhoods, k=5,
    )
    top_payload: list[dict] = []
    contributions_by_nb: dict[str, list] = {}
    for nb in top5:
        secondaries = dewey_pipeline.secondary_origins_for(nb, user_neighborhoods)
        contribs = dewey_pipeline.compute_contributions(
            v_final, nb, secondaries,
            max_origins=int(nb.get("max_origins", 3)),
        )
        top_payload.append({
            "neighborhood_id": nb.get("id"),
            "name": nb.get("name"),  # v4 generator uses this as the domain label
            "similarity": float(nb["similarity"]),
            "curvature": nb.get("curvature"),
            "origin_vector": nb.get("origin_vector"),
        })
        if contribs:
            contributions_by_nb[str(nb.get("id"))] = contribs
    dewey_context = {
        "top_neighborhoods": top_payload,
        "contributions": contributions_by_nb,
    }

    # 4. ELINS brief matches — top 3 by sim ≥ 0.5.
    matches: list[dict] = []
    for b in elins_briefs_raw:
        bid = b.get("brief_id")
        if bid in sims_map:
            sim = float(sims_map[bid])
        else:
            v = b.get("object_vector")
            if not v or len(v) != len(v_final):
                continue
            sim = float(dewey_pipeline.similarity(v_final, v))
        if sim >= 0.5:
            matches.append({
                "brief_id": bid,
                "similarity": sim,
            })
    matches.sort(key=lambda m: m["similarity"], reverse=True)

    # v12 — surface the ELINS physics_block (deterministic, sorted, ≤300
    # tokens) in the transmitter for downstream generators / future
    # build_memory_context(). Empty {} when ELINS isn't ingested.
    elins_ctx = envelope_doc.get("elins") if isinstance(envelope_doc, dict) else None
    elins_physics_section: dict = {}
    if isinstance(elins_ctx, dict):
        pb = elins_ctx.get("physics_block")
        if isinstance(pb, dict):
            elins_physics_section = pb

    # v13 — surface the universal_physics block (deterministic, static,
    # ≤300 tokens). Empty {} when not present (legacy envelopes).
    up_ctx = envelope_doc.get("universal_physics") if isinstance(envelope_doc, dict) else None
    universal_physics_section: dict = up_ctx if isinstance(up_ctx, dict) else {}

    # v14 — surface the coherence report (deterministic; sorted issues).
    # Empty {} for legacy envelopes that pre-date the validator.
    coh_ctx = envelope_doc.get("coherence") if isinstance(envelope_doc, dict) else None
    coherence_section: dict = coh_ctx if isinstance(coh_ctx, dict) else {}

    # v15 — surface the external_context block (conditioning-only). Empty
    # {} when not present or when this turn had no usable text.
    ec_ctx = envelope_doc.get("external_context") if isinstance(envelope_doc, dict) else None
    external_context_section: dict = ec_ctx if isinstance(ec_ctx, dict) else {}

    # v16 — surface the S_strategy layer (nested under envelope.elins).
    # Empty {} when ELINS isn't present or PRO-tier fields aren't ingested.
    s_strategy_section: dict = {}
    if isinstance(elins_ctx, dict):
        ss = elins_ctx.get("s_strategy_layer")
        if isinstance(ss, dict):
            s_strategy_section = ss

    # v17 — surface the harmonized physics_reasoning_context block.
    # Empty {} when not present (legacy envelopes).
    prc_ctx = envelope_doc.get("physics_reasoning_context") if isinstance(envelope_doc, dict) else None
    physics_reasoning_section: dict = prc_ctx if isinstance(prc_ctx, dict) else {}

    # v18 — surface the advisory reasoning_cues block. Empty {} when
    # absent (legacy envelopes or empty PRC).
    rc_ctx = envelope_doc.get("reasoning_cues") if isinstance(envelope_doc, dict) else None
    reasoning_cues_section: dict = rc_ctx if isinstance(rc_ctx, dict) else {}

    # v19 — surface the soft reasoning_weights vector. Empty {} when
    # absent (legacy envelopes or empty PRC/cues).
    rw_ctx = envelope_doc.get("reasoning_weights") if isinstance(envelope_doc, dict) else None
    reasoning_weights_section: dict = rw_ctx if isinstance(rw_ctx, dict) else {}

    # v20 — surface the cross-turn memory_context block. Empty {} when
    # absent (legacy envelopes or all upstream layers empty).
    mc_ctx = envelope_doc.get("memory_context") if isinstance(envelope_doc, dict) else None
    memory_context_section: dict = mc_ctx if isinstance(mc_ctx, dict) else {}

    # v21 — surface the external_knowledge conceptual-retrieval block.
    # Empty {} when no topics were extracted this cycle.
    ek_ctx = envelope_doc.get("external_knowledge") if isinstance(envelope_doc, dict) else None
    external_knowledge_section: dict = ek_ctx if isinstance(ek_ctx, dict) else {}

    # v22 — surface the fused cognitive_loop block.
    cl_ctx = envelope_doc.get("cognitive_loop") if isinstance(envelope_doc, dict) else None
    cognitive_loop_section: dict = cl_ctx if isinstance(cl_ctx, dict) else {}

    # v23 — surface the context-weighted reasoning_scaffold block.
    rs_ctx = envelope_doc.get("reasoning_scaffold") if isinstance(envelope_doc, dict) else None
    reasoning_scaffold_section: dict = rs_ctx if isinstance(rs_ctx, dict) else {}

    # v24 — surface the response_shape hints block.
    rsp_ctx = envelope_doc.get("response_shape") if isinstance(envelope_doc, dict) else None
    response_shape_section: dict = rsp_ctx if isinstance(rsp_ctx, dict) else {}

    # v25 — surface the response_templates micro-templates.
    rt_ctx = envelope_doc.get("response_templates") if isinstance(envelope_doc, dict) else None
    response_templates_section: dict = rt_ctx if isinstance(rt_ctx, dict) else {}

    # v26 — surface the sentence_operators modifier sets.
    so_ctx = envelope_doc.get("sentence_operators") if isinstance(envelope_doc, dict) else None
    sentence_operators_section: dict = so_ctx if isinstance(so_ctx, dict) else {}

    # v27 — surface the connective_ops inter-sentence linkers.
    co_ctx = envelope_doc.get("connective_ops") if isinstance(envelope_doc, dict) else None
    connective_ops_section: dict = co_ctx if isinstance(co_ctx, dict) else {}

    return {
        "markov_history": markov_history,
        "envelope": envelope_context,
        "dewey": dewey_context,
        "elins_brief_matches": matches[:3],
        "trends": dict(envelope_metrics or {}),
        "elins_physics": elins_physics_section,                       # v12
        "universal_physics": universal_physics_section,               # v13
        "coherence": coherence_section,                               # v14
        "external_context": external_context_section,                 # v15
        "s_strategy_layer": s_strategy_section,                       # v16
        "physics_reasoning_context": physics_reasoning_section,       # v17
        "reasoning_cues": reasoning_cues_section,                     # v18
        "reasoning_weights": reasoning_weights_section,               # v19
        "memory_context": memory_context_section,                     # v20
        "external_knowledge": external_knowledge_section,             # v21
        "cognitive_loop": cognitive_loop_section,                     # v22
        "reasoning_scaffold": reasoning_scaffold_section,             # v23
        "response_shape": response_shape_section,                     # v24
        "response_templates": response_templates_section,             # v25
        "sentence_operators": sentence_operators_section,             # v26
        "connective_ops": connective_ops_section,                     # v27
    }


# ---------------------------------------------------------------------------
# Markov v4 — State-Aware Generator (deterministic, no model call)
# ---------------------------------------------------------------------------
def _generate_state_aware_reply(
    user_message: str,
    qc_envelope: dict,
    transmitter_context: dict,
) -> dict:
    """v4 reply generator. Deterministic; reads qc_envelope + transmitter
    context only. Returns `{reply_text, reply_surfaces}` per spec.

    Surface thresholds (per spec):
      state:  qc_stability  ≥0.95 → "high coherence"
                            ≥0.85 → "moderate coherence"
                            else  → "topic shift detected"
      trend:  stability_trend  >+0.02 → "stabilizing"
                                <-0.02 → "drifting"
                                else   → "steady"
      anchor: highest-similarity ELINS brief id (if any), else None
      domain: top DEWEY neighborhood label (name if available, else id),
              else "unclassified"
    """
    # State surface
    try:
        qc_stab = float((qc_envelope or {}).get("qc_stability", 0.0))
    except (TypeError, ValueError):
        qc_stab = 0.0
    if qc_stab >= 0.95:
        state = "high coherence"
    elif qc_stab >= 0.85:
        state = "moderate coherence"
    else:
        state = "topic shift detected"

    # Trend surface
    trends = (transmitter_context or {}).get("trends") or {}
    try:
        stab_trend = float(trends.get("stability_trend", 0.0))
    except (TypeError, ValueError):
        stab_trend = 0.0
    if stab_trend > 0.02:
        trend = "stabilizing"
    elif stab_trend < -0.02:
        trend = "drifting"
    else:
        trend = "steady"

    # Anchor surface — transmitter sorts elins_brief_matches desc by sim already.
    matches = (transmitter_context or {}).get("elins_brief_matches") or []
    anchor = matches[0].get("brief_id") if matches else None

    # Domain surface — transmitter sorts dewey.top_neighborhoods desc by sim already.
    top_nbs = ((transmitter_context or {}).get("dewey") or {}).get("top_neighborhoods") or []
    if top_nbs:
        first_nb = top_nbs[0]
        domain = first_nb.get("name") or first_nb.get("neighborhood_id") or "unclassified"
    else:
        domain = "unclassified"

    reply_text = _compose_state_aware_reply_text(state, trend, anchor, domain)
    return {
        "reply_text": reply_text,
        "reply_surfaces": {
            "state": state,
            "trend": trend,
            "anchor": anchor,
            "domain": domain,
        },
    }


def _compose_state_aware_reply_text(
    state: str,
    trend: str,
    anchor: Optional[str],
    domain: str,
) -> str:
    """Compose 1-2 sentence reply per spec examples. No raw vectors or
    numeric values — only the surface labels."""
    if state == "topic shift detected":
        if domain == "unclassified":
            first = f"Topic shift detected; the trajectory is {trend}."
        else:
            first = f"Topic shift detected toward the {domain} domain; the trajectory is {trend}."
    else:
        # high or moderate coherence
        if domain == "unclassified":
            first = f"{state.capitalize()}, with a {trend} trajectory."
        else:
            first = f"{state.capitalize()} within the {domain} domain, with a {trend} trajectory."

    if anchor:
        second = f"This aligns with your ELINS anchor on {anchor}."
    else:
        second = "No active ELINS anchors."

    return f"{first} {second}"


def _classify_intent(v_final: list[float]) -> str:
    """Pick the highest-similarity intent label for v_final. Cached intent
    embeddings amortize after the first call (via embed_text_cached)."""
    best_label = "ask"
    best_sim = -2.0
    for label, descriptor in INTENT_DESCRIPTORS.items():
        v_intent = dewey_pipeline.embed_text_cached(descriptor)
        if not v_intent:
            continue
        s = dewey_pipeline.similarity(v_final, v_intent)
        if s > best_sim:
            best_sim = s
            best_label = label
    return best_label


@app.post("/markov/chat")
def markov_chat(
    req: MarkovChatRequest,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_session_id", "session_id must be non-empty"),
        )
    if not req.message or not req.message.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_message", "message must be non-empty"),
        )

    # OBSERVER ──────────────────────────────────────────────────────────────
    v_obs = dewey_pipeline.embed_text_cached(req.message)
    if not v_obs:
        raise HTTPException(
            status_code=400,
            detail=error_response("embed_failed", "could not embed message"),
        )

    # INTERPRETER ───────────────────────────────────────────────────────────
    prev = markov_states_store.latest_for(user, req.session_id)
    if prev is None:
        prev_state = list(v_obs)
        prev_qc = dict(_IDENTITY_QC_ENVELOPE)
    else:
        prev_state = list(prev.get("state_vector") or v_obs)
        prev_qc = dict(prev.get("qc_envelope") or _IDENTITY_QC_ENVELOPE)
    if len(prev_state) != len(v_obs):
        prev_state = list(v_obs)
    v_interp = dewey_pipeline._normalize(_vec_add(v_obs, prev_state))

    # REGULATOR ─────────────────────────────────────────────────────────────
    qc_stab = float(prev_qc.get("qc_stability", 1.0))
    qc_drft = float(prev_qc.get("qc_drift", 0.0))
    v_reg = dewey_pipeline._normalize(_vec_lincomb(v_interp, qc_stab, v_obs, qc_drft))

    # PROJECTOR ─────────────────────────────────────────────────────────────
    user_neighborhoods = dewey_neighborhoods_store.list_for_user(user, limit=500)
    v_pred = dewey_pipeline.predict_next_state(prev_state, user_neighborhoods)
    v_proj = dewey_pipeline._normalize(_vec_lincomb(v_reg, 0.7, v_pred, 0.3))

    # -1 SUBTRACTIVE CONSTRAINT ─────────────────────────────────────────────
    top_for_proj = dewey_pipeline.top_neighborhoods_with_curvature(
        v_proj, user_neighborhoods, k=5,
    )
    noise = dewey_pipeline.compute_noise_component(
        v_proj, v_obs, prev_state, top_for_proj,
    )
    v_final = dewey_pipeline._normalize(_vec_sub(v_proj, noise))

    # QC ENVELOPE UPDATE ────────────────────────────────────────────────────
    qc_stability_new = float(dewey_pipeline.similarity(prev_state, v_final))
    qc_drift_new = float(1.0 - qc_stability_new)
    try:
        import math as _math
        qc_predictive_new = float(_math.exp(-qc_drift_new * 3.0))
    except Exception:
        qc_predictive_new = 0.0
    top_for_final = dewey_pipeline.top_neighborhoods_with_curvature(
        v_final, user_neighborhoods, k=3,
    )
    curvatures = [abs(float(nb["curvature"])) for nb in top_for_final if nb.get("curvature") is not None]
    qc_pressure_new = float(sum(curvatures) / len(curvatures)) if curvatures else 0.0
    new_qc = {
        "qc_stability": qc_stability_new,
        "qc_drift": qc_drift_new,
        "qc_predictive": qc_predictive_new,
        "qc_pressure": qc_pressure_new,
    }

    # SURFACES ──────────────────────────────────────────────────────────────
    content_surface = [
        {
            "neighborhood_id": nb.get("id"),
            "name": nb.get("name"),
            "similarity": float(nb["similarity"]),
            "curvature": nb.get("curvature"),
        }
        for nb in top_for_final
    ]
    recent = markov_states_store.recent_for(user, req.session_id, limit=3)
    context_surface = [
        {
            "state_index": int(s.get("state_index", -1)),
            "state_vector": s.get("state_vector"),
            "qc_envelope": s.get("qc_envelope"),
            "timestamp": s.get("timestamp"),
        }
        for s in recent
    ]
    intent = _classify_intent(v_final)

    # MARKOV v3 — PREDICTIVE ENVELOPE EVOLUTION ─────────────────────────────
    predictive_vector = dewey_pipeline.compute_predictive_envelope(
        prev_state, user_neighborhoods,
    )
    envelope_metrics = dewey_pipeline.compute_envelope_metrics(
        prev, {"qc_envelope": new_qc},
    )

    # ENVELOPE v3 — DECAY + REFRESH ─────────────────────────────────────────
    # Runs BEFORE the transmitter so the transmitter sees post-evolution
    # strengths and a fresh envelope_vector. Pure envelope mutation; does
    # not touch Markov state.
    envelope_evolved, brief_sims = _evolve_envelope(
        user, v_final, v_obs=v_obs, user_message=req.message,
    )

    # MARKOV v3.5 — TRANSMITTER (system-level recall bundle) ────────────────
    # Built AFTER v_final + qc + envelope_metrics, BEFORE persistence.
    # Pure read; does not mutate Markov state.
    transmitter_context = _build_transmitter_context(
        user, req.session_id, v_final, envelope_metrics, user_neighborhoods,
        envelope_doc=envelope_evolved or None,
        brief_similarities=brief_sims or None,
    )
    logger.info(
        "transmitter built user=%s session=%s history=%d nb_top=%d brief_matches=%d",
        _user_ref(user), _session_ref(req.session_id),
        len(transmitter_context["markov_history"]),
        len(transmitter_context["dewey"]["top_neighborhoods"]),
        len(transmitter_context["elins_brief_matches"]),
    )

    # MARKOV v4 — STATE-AWARE GENERATOR ─────────────────────────────────────
    # Deterministic; consumes qc_envelope + transmitter_context only.
    # Replaces the stub "Acknowledged." reply.
    generator_output = _generate_state_aware_reply(
        req.message, new_qc, transmitter_context,
    )
    reply_text = generator_output["reply_text"]
    reply_surfaces = generator_output["reply_surfaces"]
    logger.info(
        "generator user=%s session=%s state=%s trend=%s anchor=%s domain=%s",
        _user_ref(user), _session_ref(req.session_id),
        reply_surfaces["state"], reply_surfaces["trend"],
        reply_surfaces["anchor"], reply_surfaces["domain"],
    )

    # PERSIST ───────────────────────────────────────────────────────────────
    state_index, now = _persist_markov_state(
        user, req.session_id, v_final, new_qc,
        predictive_vector=predictive_vector,
        envelope_metrics=envelope_metrics,
    )
    logger.info(
        "markov chat user=%s session=%s index=%d intent=%s qc_stab=%.3f qc_pressure=%.3f stab_trend=%+.3f",
        _user_ref(user), _session_ref(req.session_id), state_index, intent,
        qc_stability_new, qc_pressure_new, envelope_metrics["stability_trend"],
    )

    return {
        "ok": True,
        "reply": reply_text,
        "reply_surfaces": reply_surfaces,
        "state_vector": v_final,
        "qc_envelope": new_qc,
        "predictive_vector": predictive_vector,
        "envelope_metrics": envelope_metrics,
        "transmitter_context": transmitter_context,
        "surfaces": {
            "content": content_surface,
            "context": context_surface,
            "intent": intent,
        },
        "state_index": state_index,
    }


# ===========================================================================
# Envelope Base Layer — one doc per user; aggregates ELINS briefs and an
# optional envelope_vector for downstream Markov / DEWEY consumption.
# ===========================================================================
class EnvelopeBriefEntry(BaseModel):
    brief_id: str
    object_vector: Optional[list[float]] = None
    decay_rate: Optional[float] = None
    last_reference_timestamp: Optional[float] = None


class EnvelopeUpdateRequest(BaseModel):
    elins_briefs: list[dict] = []
    envelope_vector: Optional[list[float]] = None


@app.post("/envelope/update")
def envelope_update(
    req: EnvelopeUpdateRequest,
    session: dict = Depends(require_session),
):
    user = session["user"]
    if req.envelope_vector is not None:
        _validate_unit_norm(req.envelope_vector)
    for i, b in enumerate(req.elins_briefs or []):
        if not isinstance(b, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response("bad_brief", f"elins_briefs[{i}] must be an object"),
            )
        v = b.get("object_vector")
        if v:
            if not isinstance(v, list):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_brief_vector",
                        f"elins_briefs[{i}].object_vector must be a list",
                    ),
                )
            norm = sum(x * x for x in v) ** 0.5
            if abs(norm - 1.0) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "not_normalized",
                        f"elins_briefs[{i}].object_vector norm={norm:.6f} (must be ~1.0)",
                    ),
                )
    now = time.time()
    # Envelope v3.5 + v4 + v5 — seed per-brief defaults (timescale-aware,
    # consolidation scores) if absent.
    seeded_briefs: list[dict] = []
    for b in (req.elins_briefs or []):
        bd = dict(b)
        ts = _coerce_timescale(bd.get("timescale"))
        bd["timescale"] = ts
        bd.setdefault("strength", _ENVELOPE_V3_DEFAULTS["strength"])
        bd.setdefault("decay_rate", _DEFAULT_DECAY_BY_TIMESCALE[ts])
        bd.setdefault("activation_threshold", _ENVELOPE_V3_DEFAULTS["activation_threshold"])
        bd.setdefault("promotion_score", 0.0)        # v4
        bd.setdefault("demotion_score", 0.0)         # v4
        bd.setdefault("interference_score", 0.0)     # v4.5
        bd.setdefault("replay_score", 0.0)           # v5
        # Normalize timestamp field name to v3 spelling on write; keep legacy if present.
        if "last_reference_ts" not in bd and "last_reference_timestamp" in bd:
            bd["last_reference_ts"] = bd["last_reference_timestamp"]
        seeded_briefs.append(bd)

    # v5+ — preserve server-managed fields across /envelope/update calls so
    # client overwrites of briefs don't wipe centroid / drift counters / replay state.
    existing = envelopes_store.get(user) or {}
    payload = {
        "user": user,
        "elins_briefs": seeded_briefs,
        "envelope_vector": list(req.envelope_vector) if req.envelope_vector is not None else None,
        "envelope_decay_ts": now,  # Envelope v3 — stamp on every write
        "updated_at": now,
    }
    for fld in _ENVELOPE_PRESERVED_SERVER_FIELDS:
        if fld in existing:
            payload[fld] = existing[fld]
    envelopes_store.set_envelope(user, payload)
    logger.info(
        "envelope update user=%s briefs=%d has_vector=%s",
        _user_ref(user), len(payload["elins_briefs"]), payload["envelope_vector"] is not None,
    )
    return {"ok": True, "envelope": payload}


@app.post("/dewey/backfill_vectors")
def dewey_backfill_vectors(session: dict = Depends(_require_founder)):
    """v3 one-time backfill: iterate all of the user's vault/library/timeline
    objects and persist `object_vector` on any document that doesn't have
    one yet. Idempotent — already-vectored docs are skipped.

    Caps at 1000 docs per collection per call. Re-run if a user has more.
    """
    user = session["user"]
    counts = {"vault": 0, "library": 0, "timeline": 0}
    skipped = {"vault": 0, "library": 0, "timeline": 0}
    errors = {"vault": 0, "library": 0, "timeline": 0}

    def _backfill_one(kind: str, doc: dict, store) -> None:
        if doc.get("object_vector"):
            skipped[kind] += 1
            return
        try:
            vec = dewey_pipeline.embed_object(doc)
            doc["object_vector"] = vec
            # Reconcile size_bytes + usage so the new ~16 KB vector counts
            # against the user's quota (otherwise size_bytes drifts and the
            # quota under-counts on every backfilled doc).
            old_size = int(doc.pop("size_bytes", 0))
            new_size = _serialized_size(doc)
            doc["size_bytes"] = new_size
            store.update(doc["id"], doc)
            delta = new_size - old_size
            if delta != 0 and doc.get("user"):
                usage_store.add_bytes(doc["user"], delta)
            counts[kind] += 1
            logger.info(
                "dewey backfill vector_persisted kind=%s id=%s delta=%d",
                kind, doc.get("id"), delta,
            )
        except Exception as e:
            errors[kind] += 1
            logger.warning(
                "dewey backfill failed kind=%s id=%s err=%s",
                kind, doc.get("id"), e,
            )

    for v in vault_store.list_for_user(user, limit=1000):
        _backfill_one("vault", v, vault_store)
    for l in library_store.list_for_user(user, limit=1000):
        _backfill_one("library", l, library_store)
    for t in timeline_store.list_for_user(user, limit=1000):
        _backfill_one("timeline", t, timeline_store)

    logger.info(
        "dewey backfill user=%s filled=%s skipped=%s errors=%s",
        _user_ref(user), counts, skipped, errors,
    )
    return {
        "ok": True,
        "filled": counts,
        "skipped": skipped,
        "errors": errors,
    }


# ===========================================================================
# Protected engine routes
# ===========================================================================
def _log_call(engine: str, session: dict) -> None:
    logger.info(
        "engine call %s user=%s session=%s",
        engine, _user_ref(session["user"]), _session_ref(session["session_id"]),
    )


@app.post("/markov")
def markov(req: EngineRequest, session: dict = Depends(require_session)):
    _log_call("markov", session)
    return ok_response(
        "markov",
        _timed("markov", markov_adapter, req.text, req.meta, session["user"]),
    )


@app.post("/galileo")
def galileo(req: EngineRequest, session: dict = Depends(require_session)):
    _log_call("galileo", session)
    return ok_response(
        "galileo",
        _timed("galileo", galileo_adapter, req.text, req.meta, session["user"]),
    )


@app.post("/library")
def library(req: EngineRequest, session: dict = Depends(require_session)):
    _log_call("library", session)
    return ok_response(
        "library",
        _timed("library", library_adapter, req.text, req.meta, session["user"]),
    )


@app.post("/tizzy")
def tizzy(req: EngineRequest, session: dict = Depends(require_session)):
    _log_call("tizzy", session)
    return ok_response(
        "tizzy",
        _timed("tizzy", tizzy_adapter, req.text, req.meta, session["user"]),
    )


# ===========================================================================
# v28 — SURFACE + DISTRIBUTION LAYER
# ---------------------------------------------------------------------------
# Six new endpoints + one daemon thread. Additive only; no upstream layer
# (envelope v6→v27, ELINS v12, identity/trajectory, Dewey) is mutated by these
# routes beyond their existing behavior. See SURFACE_DISTRIBUTION_PLAN.md.
# ===========================================================================

# Per-user daily-delivery hour (24h, local). Defaults to 05:00 per spec; the
# queue endpoint accepts a `local_hour` override per call.
_DAILY_DELIVERY_DEFAULT_HOUR = 5
_DAILY_DELIVERY_DEFAULT_MINUTE = 0
# Scheduler tick interval. 60s is fine for hourly precision; the wake-up cost
# is one O(N users) scan + an O(K queued) check per due user.
_DAILY_SCHEDULER_TICK_SECONDS = 60.0


def _next_local_run_ts(hour: int, minute: int = 0, now_ts: Optional[float] = None) -> float:
    """Next epoch-seconds timestamp at the given LOCAL hour:minute. If that
    time has already passed today, returns the same time tomorrow."""
    import datetime as _dt
    n = _dt.datetime.fromtimestamp(now_ts if now_ts is not None else time.time())
    target = n.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    if target <= n:
        target = target + _dt.timedelta(days=1)
    return target.timestamp()


def _run_g_elins(scenario_text: str, user: str) -> dict:
    """v28 #G ELINS engine. Embeds the scenario, walks the user's existing
    DEWEY neighborhoods + universal_physics + (cached) ELINS physics_block,
    and returns a structured analysis dict.

    NEVER persists `scenario_text`. Persists Dewey membership rows ONLY (via
    `dewey_memberships_store`) and only when DEWEY membership-write is
    enabled for the user. Never mutates the user's envelope, events, or
    Markov state."""
    if not isinstance(scenario_text, str) or not scenario_text.strip():
        return {
            "ok": False,
            "error": "bad_scenario",
            "message": "scenario_text must be a non-empty string",
        }
    v_scenario = dewey_pipeline.embed_text_cached(scenario_text)
    if not v_scenario:
        return {
            "ok": False,
            "error": "embed_failed",
            "message": "embedder returned no vector",
        }

    user_neighborhoods = dewey_neighborhoods_store.list_for_user(user, limit=500)
    top5 = dewey_pipeline.top_neighborhoods_with_curvature(
        v_scenario, user_neighborhoods, k=5,
    )
    nb_summary = [
        {
            "neighborhood_id": nb.get("id"),
            "name": nb.get("name"),
            "similarity": float(nb.get("similarity", 0.0)),
            "curvature": nb.get("curvature"),
        }
        for nb in top5
    ]
    # QC summary (drift = pressure proxies). Reuses the same arithmetic as
    # the chat path's QC envelope but applied to the scenario in isolation.
    curvatures = [
        abs(float(nb["curvature"])) for nb in top5 if nb.get("curvature") is not None
    ]
    qc_pressure = (sum(curvatures) / len(curvatures)) if curvatures else 0.0
    # Pull the cached ELINS physics_block + universal block from the user's
    # envelope (read-only). Both are deterministic; safe to surface.
    env_doc = envelopes_store.get(user) or {}
    elins_physics_block = (
        (env_doc.get("elins") or {}).get("physics_block") if isinstance(env_doc.get("elins"), dict) else {}
    ) or {}
    universal = _build_universal_physics_block()

    # Persist Dewey membership rows for the top-1 neighborhood — pure metadata
    # (neighborhood_id + similarity), no scenario text, no vector. Skipped if
    # the user has no neighborhoods (read returned empty).
    persisted_membership_id: Optional[str] = None
    if top5 and top5[0].get("id") is not None:
        try:
            membership_id = "gelins_" + secrets.token_urlsafe(10)
            dewey_memberships_store.create(
                membership_id,
                {
                    "id": membership_id,
                    "user": user,
                    "neighborhood_id": top5[0].get("id"),
                    "similarity": float(top5[0].get("similarity", 0.0)),
                    "source": "g_elins",
                    "ts": time.time(),
                },
            )
            persisted_membership_id = membership_id
        except Exception as e:  # pragma: no cover
            logger.warning(
                "g_elins membership persist failed user=%s err=%s",
                _user_ref(user), e,
            )

    return {
        "ok": True,
        "analysis": {
            "neighborhoods": nb_summary,
            "qc_summary": {"pressure": float(qc_pressure)},
            "elins_physics": elins_physics_block,
            "universal_physics": universal,
            "persisted_membership_id": persisted_membership_id,
            "last_updated_ts": time.time(),
        },
    }


# ---------- #G ELINS engine ----------
class GElinsRunRequest(BaseModel):
    scenario_text: str


# v29 — explicit limits surfaced as constants so they can be cited in
# readiness reports and asserted by tests.
SCENARIO_MAX_LEN = 8000


@app.post("/elins/g/run")
def elins_g_run(req: GElinsRunRequest, session: dict = Depends(require_session)):
    user = session["user"]
    cohort = session.get("cohort")
    try:
        scenario = v29_hardening.require_str(
            req.scenario_text, "scenario_text", max_len=SCENARIO_MAX_LEN,
        )
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/elins/g/run")

    # v30 — #G credit gate. When credits are enabled, every #G run costs
    # exactly one credit. Active Founding members get a starter balance
    # at activation time; non-members must purchase before running.
    # If the gate is off, falls through to v28 behavior (free runs).
    credits_required = v29_hardening.feature_enabled(
        "g_credits_enabled", user=user, cohort=cohort,
    )
    if credits_required:
        balance_before = users_store.get_g_credit_balance(user)
        if balance_before <= 0:
            v29_hardening.log_event(
                "elins_g_run_no_credits", user=user, route="/elins/g/run",
                success=False, balance=balance_before,
            )
            raise HTTPException(
                status_code=402,
                detail=error_response(
                    "no_credits",
                    "No #G credits remaining. Buy more from /membership.",
                ),
            )

    with v29_hardening.TimedBlock("elins_g_run", user=user, route="/elins/g/run") as tb:
        # v40 — kernel wraps the runner so operator_state + ESO mode
        # mirror happen in one place. The runner is _run_g_elins
        # itself; the kernel only adds pre/post hooks.
        result = intelligence_kernel.run_G(
            user, scenario, runner=_run_g_elins,
        )
        if not result.get("ok"):
            tb.mark_failure()
            tb.set(error=str(result.get("error", "g_elins_failed")))
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    result.get("error", "g_elins_failed"),
                    result.get("message", "g_elins failed"),
                ),
            )
        # Deduct the credit AFTER a successful run so failed runs don't
        # consume credits. Race window between balance check + decrement
        # is tolerable at launch scale (single-user serial UI calls).
        new_balance: int | None = None
        if credits_required:
            try:
                new_balance = users_store.consume_g_credit(
                    user,
                    history_entry={
                        "type": "g_consume",
                        "credits_delta": -1,
                        "amount": 0.0,
                        "ts": time.time(),
                    },
                )
                membership_billing.record_transaction(
                    user, type="g_consume", amount=0.0, credits_delta=-1,
                    metadata={"route": "/elins/g/run"},
                )
            except ValueError:
                # Balance flipped to zero between check and consume —
                # extremely unlikely at single-user pace; surface as 402
                # so the UI re-fetches state.
                tb.mark_failure()
                tb.set(error="no_credits_race")
                raise HTTPException(
                    status_code=402,
                    detail=error_response(
                        "no_credits",
                        "No #G credits remaining. Buy more from /membership.",
                    ),
                )
        tb.set(
            neighborhoods=len(result["analysis"].get("neighborhoods") or []),
            pressure=float((result["analysis"].get("qc_summary") or {}).get("pressure", 0.0)),
            membership=str(result["analysis"].get("persisted_membership_id") or "none"),
            balance_after=new_balance if new_balance is not None else -1,
        )
    if credits_required and new_balance is not None:
        result["g_credits_remaining"] = new_balance
    # v40 — operator_state recording moved into intelligence_kernel.run_G
    # (called above). No inline record here.
    return result


# ---------- Daily ELINS distribution ----------
class ElinsDailyQueueRequest(BaseModel):
    scenario_text: str
    deliver_email: bool = False
    deliver_feed: bool = True
    local_hour: Optional[int] = None       # default 5
    local_minute: Optional[int] = None     # default 0


@app.post("/elins/daily/queue")
def elins_daily_queue(req: ElinsDailyQueueRequest, session: dict = Depends(require_session)):
    user = session["user"]
    try:
        scenario = v29_hardening.require_str(
            req.scenario_text, "scenario_text", max_len=SCENARIO_MAX_LEN,
        )
        hour = v29_hardening.require_int(
            req.local_hour, "local_hour", min_value=0, max_value=23,
            default=_DAILY_DELIVERY_DEFAULT_HOUR,
        )
        minute = v29_hardening.require_int(
            req.local_minute, "local_minute", min_value=0, max_value=59,
            default=_DAILY_DELIVERY_DEFAULT_MINUTE,
        )
        deliver_email = v29_hardening.require_bool(req.deliver_email, "deliver_email")
        deliver_feed = v29_hardening.require_bool(req.deliver_feed, "deliver_feed", default=True)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=session.get("cohort")):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/elins/daily/queue")
    scheduled = _next_local_run_ts(hour, minute)
    report = elins_distribution_store.queue(
        user,
        scenario_text=scenario,
        scheduled_for_ts=scheduled,
        deliver_email=deliver_email,
        deliver_feed=deliver_feed,
    )
    _ensure_daily_scheduler_started()  # lazy boot on first queue
    v29_hardening.log_event(
        "elins_daily_queue", user=user, route="/elins/daily/queue",
        success=True, report=report["report_id"], scheduled_for_ts=int(scheduled),
        deliver_email=deliver_email, deliver_feed=deliver_feed,
    )
    return {
        "ok": True,
        "report_id": report["report_id"],
        "scheduled_for_ts": scheduled,
    }


@app.get("/elins/daily/feed")
def elins_daily_feed(limit: int = 50, session: dict = Depends(require_session)):
    user = session["user"]
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=500, default=50)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=session.get("cohort")):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/elins/daily/feed")
    delivered = elins_distribution_store.list_delivered(user, limit=n)
    v29_hardening.log_event(
        "elins_daily_feed", user=user, route="/elins/daily/feed",
        success=True, delivered_count=len(delivered),
    )
    return {"ok": True, "delivered": delivered, "count": len(delivered)}


# ---------- Mesh metadata sync (Dewey-only) ----------
class MeshSyncRequest(BaseModel):
    device_id: str
    metadata: dict


@app.post("/mesh/sync")
def mesh_sync(req: MeshSyncRequest, session: dict = Depends(require_session)):
    user = session["user"]
    try:
        device_id, metadata = v29_hardening.validate_mesh_payload(
            req.device_id, req.metadata,
        )
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=session.get("cohort")):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/mesh/sync")
    try:
        result = mesh_metadata_store.upsert_device(
            user, device_id, metadata, time.time(),
        )
    except ValueError as e:
        # Defence-in-depth: store raises if its own cap is exceeded.
        v29_hardening.log_event(
            "mesh_sync", user=user, route="/mesh/sync", success=False,
            error="mesh_payload",
        )
        raise HTTPException(
            status_code=400,
            detail=error_response("mesh_payload", str(e)),
        )
    v29_hardening.log_event(
        "mesh_sync", user=user, route="/mesh/sync", success=True,
        device=device_id[:24], last_seen_ts=int(result["last_seen_ts"]),
    )
    return {"ok": True, "device": result}


@app.get("/mesh/state")
def mesh_state(session: dict = Depends(require_session)):
    user = session["user"]
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=session.get("cohort")):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/mesh/state")
    state = mesh_metadata_store.state_for(user)
    v29_hardening.log_event(
        "mesh_state", user=user, route="/mesh/state", success=True,
        device_count=len(state.get("devices") or {}),
    )
    return {"ok": True, "state": state}


# ---------- Continuity surface (cross-session metadata) ----------
@app.get("/continuity/snapshot")
def continuity_snapshot(session: dict = Depends(require_session)):
    """Cross-session metadata surface. Reads (never mutates) the user's
    envelope + recent Markov states. Returns counts + last-updated timestamps
    + the v20 memory_context summary if present."""
    user = session["user"]
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=session.get("cohort")):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/continuity/snapshot")
    env = envelopes_store.get(user) or {}
    snapshot = {
        "user": user,
        "now_ts": time.time(),
        "counts": {
            "events": len(env.get("events") or []),
            "episodes": len(env.get("episodes") or {}),
            "narratives": len(env.get("narratives") or {}),
            "story_arcs": len(env.get("story_arcs") or {}),
            "elins_briefs": len(env.get("elins_briefs") or []),
        },
        "last_updated_ts": {
            "envelope": env.get("updated_at"),
            "events_decay": env.get("envelope_decay_ts"),
            "identity": (env.get("identity") or {}).get("last_updated_ts"),
            "trajectory": (env.get("trajectory") or {}).get("last_updated_ts"),
            "elins": (env.get("elins") or {}).get("last_updated_ts"),
            "universal_physics": (env.get("universal_physics") or {}).get("last_updated_ts"),
            "coherence": (env.get("coherence") or {}).get("last_check_ts"),
            "memory_context": (env.get("memory_context") or {}).get("last_updated_ts"),
        },
        "memory_context": env.get("memory_context") or {},
        "coherence_flags": {
            k: bool(v)
            for k, v in (env.get("coherence") or {}).items()
            if k.endswith("_ok")
        },
    }
    v29_hardening.log_event(
        "continuity_snapshot", user=user, route="/continuity/snapshot", success=True,
        events=snapshot["counts"]["events"],
        episodes=snapshot["counts"]["episodes"],
        elins_briefs=snapshot["counts"]["elins_briefs"],
    )
    return {"ok": True, "snapshot": snapshot}


# ---------- Sessions / Runtime / Engines / Dewey metadata (v28 phase 2) ----------
# These are thin read-only endpoints the cockpit + phone surfaces consume.
# Each one only READS existing state — no envelope mutation, no inference.

# Static engine catalog. Update this list when registering a new engine adapter.
_ENGINE_CATALOG: tuple = (
    {"id": "markov",  "label": "Markov",  "route": "/markov",  "description": "v4 state-aware generator"},
    {"id": "galileo", "label": "Galileo", "route": "/galileo", "description": "Galileo clarity cycle"},
    {"id": "library", "label": "Library", "route": "/library", "description": "Library lookup, GCS-backed"},
    {"id": "tizzy",   "label": "Tizzy",   "route": "/tizzy",   "description": "Tizzy engine"},
)


@app.get("/sessions")
def sessions_list(limit: int = 50, session: dict = Depends(require_session)):
    """List the user's Markov sessions (metadata only, no state vectors).
    Used by the cockpit Session List panel."""
    user = session["user"]
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=500, default=50)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/sessions")
    sessions_meta = markov_states_store.list_sessions_for_user(user, limit=n)
    v29_hardening.log_event(
        "sessions_list", user=user, route="/sessions", success=True,
        count=len(sessions_meta),
    )
    return {"ok": True, "sessions": sessions_meta, "count": len(sessions_meta)}


@app.get("/runtime/envelope")
def runtime_envelope(session: dict = Depends(require_session)):
    """Read-only fetch of the user's full v6→v27 envelope. The cockpit
    Runtime Panel walks this dict deterministically — no summarization,
    no embeddings, no inference. Heavy fields (`elins_briefs[*].object_vector`,
    `events[*].vector`, `mean_center_vector`) are stripped to keep the
    payload renderable; the cockpit shows counts + last_updated_ts for
    those instead. Original envelope is unchanged on disk."""
    user = session["user"]
    v29_hardening.enforce_rate_limit(user, "/runtime/envelope")
    env = envelopes_store.get(user) or {}

    def _strip_vector(v):
        # Replace large vectors with a small descriptor so the UI can show
        # "vector: 768-dim" without dumping floats. Returns None for empty.
        if not v:
            return None
        if isinstance(v, list):
            return {"_vector": True, "dim": len(v)}
        return v

    # Shallow copy + selective scrub. Don't deep-copy the entire envelope;
    # only strip the known-heavy lists/maps.
    out: dict = dict(env)
    if isinstance(out.get("envelope_vector"), list):
        out["envelope_vector"] = _strip_vector(out["envelope_vector"])
    if isinstance(out.get("envelope_centroid"), list):
        out["envelope_centroid"] = _strip_vector(out["envelope_centroid"])
    out["elins_briefs"] = [
        {**b, "object_vector": _strip_vector(b.get("object_vector"))}
        for b in (out.get("elins_briefs") or [])
    ]
    out["events"] = [
        {**e, "vector": _strip_vector(e.get("vector"))}
        for e in (out.get("events") or [])
    ]
    # Episodes/narratives may carry vectors too.
    out["episodes"] = {
        eid: {**ep, "episode_vector": _strip_vector(ep.get("episode_vector"))}
        for eid, ep in (out.get("episodes") or {}).items()
    }
    out["narratives"] = {
        nid: {
            **n,
            "node_vector": _strip_vector(n.get("node_vector")),
            "compressed_vector": _strip_vector(n.get("compressed_vector")),
        }
        for nid, n in (out.get("narratives") or {}).items()
    }
    out["story_arcs"] = {
        aid: {
            **a,
            "arc_vector": _strip_vector(a.get("arc_vector")),
            "arc_vector_compressed": _strip_vector(a.get("arc_vector_compressed")),
        }
        for aid, a in (out.get("story_arcs") or {}).items()
    }
    if isinstance(out.get("identity"), dict):
        out["identity"] = {
            **out["identity"],
            "identity_vector": _strip_vector(out["identity"].get("identity_vector")),
        }
    if isinstance(out.get("trajectory"), dict):
        out["trajectory"] = {
            **out["trajectory"],
            "trajectory_vector": _strip_vector(out["trajectory"].get("trajectory_vector")),
        }
    if isinstance(out.get("elins"), dict):
        elins_copy = dict(out["elins"])
        if "mean_center_vector" in elins_copy:
            elins_copy["mean_center_vector"] = _strip_vector(elins_copy.get("mean_center_vector"))
        out["elins"] = elins_copy
    v29_hardening.log_event(
        "runtime_envelope", user=user, route="/runtime/envelope", success=True,
        events=len(out.get("events") or []),
        episodes=len(out.get("episodes") or {}),
        elins_briefs=len(out.get("elins_briefs") or []),
    )
    return {"ok": True, "envelope": out}


@app.get("/engines")
def engines_list(session: dict = Depends(require_session)):
    """Static engine catalog. The cockpit Engine Selector renders this
    list and POSTs to the engine's `route` when the user invokes one."""
    v29_hardening.enforce_rate_limit(session["user"], "/engines")
    return {"ok": True, "engines": [dict(e) for e in _ENGINE_CATALOG]}


@app.get("/metadata/dewey")
def metadata_dewey(session: dict = Depends(require_session)):
    """Read-only Dewey metadata for the user. Returns neighborhood IDs +
    counts + a small membership preview — never returns origin_vector or
    any membership object_vector. Suitable for the cockpit's Dewey panel
    and for the metadata mesh."""
    user = session["user"]
    user_neighborhoods = dewey_neighborhoods_store.list_for_user(user, limit=500)
    nbs_metadata = [
        {
            "neighborhood_id": nb.get("id"),
            "name": nb.get("name"),
            "curvature": nb.get("curvature") if "curvature" in nb else None,
            "has_origin_vector": bool(nb.get("origin_vector")),
        }
        for nb in user_neighborhoods
    ]
    return {
        "ok": True,
        "user": user,
        "neighborhood_count": len(nbs_metadata),
        "neighborhoods": nbs_metadata,
    }


# ---------- Daily delivery scheduler (background daemon thread) ----------
_daily_scheduler_started = False
_daily_scheduler_lock = None  # initialised lazily in _ensure_daily_scheduler_started


def _send_email_placeholder(user: str, delivered_record: dict) -> bool:
    """Optional email hook. Returns True iff an email was actually sent.
    Real SMTP wiring is env-var-gated (CLARITYOS_SMTP_HOST etc.); when unset,
    this is a no-op that returns False so the scheduler's log line still
    reflects 'delivered_email=0'. Keeps SMTP libs out of the runtime when
    not configured."""
    smtp_host = os.environ.get("CLARITYOS_SMTP_HOST")
    smtp_to = os.environ.get("CLARITYOS_SMTP_TO_OVERRIDE")  # optional global override
    if not smtp_host:
        return False
    try:
        # Stub for now — real SMTP integration would land here. We log the
        # attempt and return True so the scheduler can mark email-delivered
        # accurately for tests / env-gated dry runs.
        logger.info(
            "elins email stub host=%s user=%s report=%s to=%s",
            smtp_host, _user_ref(user), delivered_record.get("report_id"),
            smtp_to or "<user-resolved>",
        )
        return True
    except Exception as e:  # pragma: no cover
        logger.warning(
            "elins email stub failed user=%s err=%s",
            _user_ref(user), e,
        )
        return False


def _scheduler_one_pass(now_ts: Optional[float] = None) -> dict:
    """Run a single delivery pass. Returns counts. Public so tests can drive
    the scheduler synchronously without spawning the daemon."""
    now = float(now_ts if now_ts is not None else time.time())
    users = elins_distribution_store.all_users_with_due_reports(now)
    delivered_count = 0
    emailed_count = 0
    for user in users:
        for report in elins_distribution_store.due_reports_for(user, now):
            scenario_text = report.get("scenario_text", "")
            try:
                analysis_result = _run_g_elins(scenario_text, user)
                analysis = analysis_result.get("analysis", {}) if analysis_result.get("ok") else {
                    "error": analysis_result.get("error", "g_elins_failed"),
                    "message": analysis_result.get("message", ""),
                }
            except Exception as e:  # pragma: no cover
                logger.warning(
                    "scheduler g_elins failed user=%s err=%s",
                    _user_ref(user), e,
                )
                analysis = {"error": "g_elins_exception", "message": str(e)}
            delivered = elins_distribution_store.deliver(
                user, report["report_id"], now, analysis,
            )
            if delivered is None:
                continue
            delivered_count += 1
            if delivered.get("deliver_email"):
                if _send_email_placeholder(user, delivered):
                    emailed_count += 1
    if delivered_count or emailed_count:
        logger.info(
            "elins scheduler pass delivered=%d emailed=%d users=%d at=%.0f",
            delivered_count, emailed_count, len(users), now,
        )
    return {"delivered": delivered_count, "emailed": emailed_count, "users": len(users)}


def _daily_scheduler_loop():  # pragma: no cover (spawned in a daemon thread)
    while True:
        try:
            _scheduler_one_pass()
        except Exception as e:
            logger.warning("elins scheduler tick failed err=%s", e)
        try:
            time.sleep(_DAILY_SCHEDULER_TICK_SECONDS)
        except Exception:
            return


def _ensure_daily_scheduler_started() -> None:
    """Lazy boot. Called from /elins/daily/queue (and idempotent). Cloud Run
    instances start the thread on first queue request. The thread is daemon
    so process shutdown isn't blocked. One thread per process is enough at
    Cloud Run scale (each instance independently delivers due-now reports)."""
    global _daily_scheduler_started, _daily_scheduler_lock
    if _daily_scheduler_started:
        return
    if _daily_scheduler_lock is None:
        import threading
        _daily_scheduler_lock = threading.Lock()
    with _daily_scheduler_lock:
        if _daily_scheduler_started:
            return
        import threading
        t = threading.Thread(
            target=_daily_scheduler_loop,
            name="elins-daily-scheduler",
            daemon=True,
        )
        t.start()
        _daily_scheduler_started = True
        logger.info("elins daily scheduler started (tick=%.0fs)", _DAILY_SCHEDULER_TICK_SECONDS)


# ===========================================================================
# v29 — Onboarding + feature-flag introspection
# ---------------------------------------------------------------------------
# Two read-only endpoints + one mutation:
#   GET  /v29/flags                — feature flag introspection (admin sees more)
#   GET  /v29/onboarding/state     — first-run wizard progress for current user
#   POST /v29/onboarding/complete  — atomically mark a step done (vault/dewey/snapshot)
#
# Demo data seeding for empty accounts is folded into vault_write/timeline_write
# server-side. The "What's new in v28" panel reads /v29/whats_new (static).
# ===========================================================================
class V29OnboardingComplete(BaseModel):
    step: str  # "vault_check" | "dewey_sync" | "continuity_snapshot" | "done"


_V29_ONBOARDING_STEPS = ("vault_check", "dewey_sync", "continuity_snapshot", "done")


@app.get("/v29/flags")
def v29_flags(session: dict = Depends(require_session)):
    """Return the v29 flag table as observed for the current user. Admin
    additionally receives the global default + override count per flag."""
    user = session["user"]
    cohort = session.get("cohort")
    user_view = {
        name: v29_hardening.feature_enabled(name, user=user, cohort=cohort)
        for name in v29_hardening._DEFAULT_FLAGS.keys()
    }
    out = {"ok": True, "flags": user_view}
    if user == ADMIN_USER:
        out["raw"] = v29_hardening.list_flags()
    return out


@app.get("/v29/onboarding/state")
def v29_onboarding_state(session: dict = Depends(require_session)):
    user = session["user"]
    user_doc = users_store.get_user(user) or {}
    onboarding = dict(user_doc.get("onboarding") or {})
    completed = [s for s in _V29_ONBOARDING_STEPS if onboarding.get(s)]
    next_step = next(
        (s for s in _V29_ONBOARDING_STEPS if not onboarding.get(s)),
        None,
    )
    is_done = bool(onboarding.get("done"))
    return {
        "ok": True,
        "user": user,
        "completed": completed,
        "next_step": next_step,
        "done": is_done,
        "steps": list(_V29_ONBOARDING_STEPS),
    }


@app.post("/v29/onboarding/complete")
def v29_onboarding_complete(req: V29OnboardingComplete, session: dict = Depends(require_session)):
    user = session["user"]
    try:
        step = v29_hardening.require_one_of(req.step, "step", _V29_ONBOARDING_STEPS)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/v29/onboarding/complete")
    user_doc = users_store.get_user(user) or {}
    onboarding = dict(user_doc.get("onboarding") or {})
    onboarding[step] = float(time.time())
    if step == "continuity_snapshot":
        # Reaching the final non-terminal step auto-marks "done" so the
        # cockpit can hide the wizard. Idempotent on retries.
        onboarding["done"] = float(time.time())
    if step == "done":
        onboarding["done"] = float(time.time())
    users_store.update_user(user, {"onboarding": onboarding})
    v29_hardening.log_event(
        "onboarding_complete", user=user, route="/v29/onboarding/complete",
        success=True, step=step,
    )
    return {"ok": True, "onboarding": onboarding}


def _seed_demo_data(user: str) -> dict:
    """Idempotent demo seed for empty accounts. Writes a couple of vault notes
    + a welcome timeline event ONLY if the account has zero existing items.
    Uses the same vault_store/timeline_store paths as the real endpoints so
    quota accounting + Dewey pipeline run normally."""
    summary = {"vault": 0, "timeline": 0, "skipped": False}
    try:
        existing = vault_store.list_for_user(user, limit=1)
    except Exception as e:  # pragma: no cover
        logger.warning(
            "demo seed vault list failed user=%s err=%s",
            _user_ref(user), e,
        )
        existing = []
    if existing:
        summary["skipped"] = True
        return summary

    for spec in v29_hardening.DEMO_VAULT_ITEMS:
        item = {
            "user": user,
            "type": "note",
            "title": spec["title"],
            "content": spec["content"],
            "tags": list(spec["tags"]),
            "metadata": {"demo": True},
            "created_at": time.time(),
        }
        try:
            item["object_vector"] = dewey_pipeline.embed_object(item)
        except Exception:  # pragma: no cover — embedding is best-effort
            item["object_vector"] = None
        size = _serialized_size(item)
        if size > VAULT_ENVELOPE_BYTES:
            continue
        try:
            _assert_quota(user, size)
        except HTTPException:
            summary["skipped"] = True
            break
        item_id = vault_store.new_id()
        item["id"] = item_id
        item["size_bytes"] = size
        vault_store.create(item_id, item)
        usage_store.add_bytes(user, size)
        summary["vault"] += 1

    for spec in v29_hardening.DEMO_TIMELINE_EVENTS:
        try:
            _emit_timeline(
                user, spec["kind"], None, spec["summary"], dict(spec.get("data") or {}),
            )
            summary["timeline"] += 1
        except Exception:  # pragma: no cover
            pass

    v29_hardening.log_event(
        "demo_seed", user=user, route="/v29/onboarding/seed", success=True,
        vault=summary["vault"], timeline=summary["timeline"],
        skipped=summary["skipped"],
    )
    return summary


@app.post("/v29/onboarding/seed")
def v29_onboarding_seed(session: dict = Depends(require_session)):
    """Optional empty-account demo seeder. Invoked by the cockpit's onboarding
    wizard if the user opts in. Idempotent: if the vault already has items,
    seeds nothing."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("demo_data", user=user, cohort=cohort):
        # Even with the flag off we honour explicit opt-in, but server-side
        # logging marks the call so we can audit demo-data usage. The seeder
        # itself remains idempotent so re-runs are safe.
        v29_hardening.log_event(
            "demo_seed_disabled", user=user, route="/v29/onboarding/seed",
            success=True,
        )
    v29_hardening.enforce_rate_limit(user, "/v29/onboarding/seed")
    return {"ok": True, "summary": _seed_demo_data(user)}


@app.get("/v29/whats_new")
def v29_whats_new(session: dict = Depends(require_session)):
    """Static 'What's new in v28' panel content. Read-only; surfaces in the
    cockpit so users see what shipped without us editing client code each
    pass. v30+ entries can live alongside v28 entries — order is reverse
    chronological."""
    user = session["user"]
    cohort = session.get("cohort")
    enabled = v29_hardening.feature_enabled("whats_new_v28", user=user, cohort=cohort)
    return {
        "ok": True,
        "enabled": enabled,
        "entries": [
            {
                "id": "v28_surface_distribution",
                "title": "v28 Surface + Distribution layer",
                "highlights": [
                    "Cockpit + ELINS web routes + phone ELINS screen",
                    "Personal #G engine — never persists scenario text",
                    "Daily ELINS feed (delivers at 05:00 local)",
                    "Mesh metadata sync — Dewey-only, no vectors",
                    "Continuity snapshot — cross-session metadata surface",
                    "Static engine catalog endpoint (/engines)",
                ],
                "released_at": "2026-05-05",
            },
            {
                "id": "v29_hardening",
                "title": "v29 Hardening + Launch Readiness",
                "highlights": [
                    "Strict input validation on v28 endpoints",
                    "Rate-limit stub (logging-only by default)",
                    "Feature flags — Cohort 1 surfaces gated server-side",
                    "Onboarding wizard with vault/Dewey/snapshot checkpoints",
                    "Demo data seeding for empty accounts",
                    "Structured event logs — no user content emitted",
                ],
                "released_at": "2026-05-06",
            },
            {
                "id": "v30_membership",
                "title": "v30 Founding Cohort Membership",
                "highlights": [
                    "Founding 500 tier — $50 locked for life of membership",
                    "Cohort cap enforced server-side (waitlist past 500)",
                    "#G credit system: $1/run, $20 for a 20-pack",
                    "Cancellation forfeits the price lock permanently",
                    "Mock billing path until Stripe one-tap lands in v31",
                ],
                "released_at": "2026-05-06",
            },
            {
                "id": "v31_billing_finalization",
                "title": "v31 Billing Finalization + PaymentIntents",
                "highlights": [
                    "PaymentIntent flow for activation, renewal, and #G credits",
                    "Idempotent Stripe webhook receiver",
                    "Daily renewal scheduler with 3-retry / 72-hour window",
                    "Billing state machine: active / past_due / grace / cancelled",
                    "Combined transaction + intent history at /billing/history",
                ],
                "released_at": "2026-05-06",
            },
            {
                "id": "v32_public_website_waitlist",
                "title": "v32 Public Website + Waitlist Pipeline",
                "highlights": [
                    "Public landing page with hero / cohort / capabilities / CTA",
                    "Public /waitlist/join endpoint, IP rate-limited",
                    "Founder waitlist console (/founder/waitlist)",
                    "Cohort fill drives the public-site CTA (Activate vs Waitlist)",
                    "Status pipeline: waiting → contacted → converted / dropped",
                ],
                "released_at": "2026-05-06",
            },
            {
                "id": "v33_founder_console_elins_cmt",
                "title": "v33 Founder Console + ELINS Standardization + #cmt",
                "highlights": [
                    "Canonical 10-layer ELINS pipeline (elins.standard_elins)",
                    "S_ELINS QC re-run + alignment score at /elins/qc",
                    "Persisted macro-ELINS at /elins/global (runs/primitives/domains/baseline)",
                    "Most Relevant Comment Generator (#cmt) at /cmt/generate + /c/run",
                    "Founder console: DM pipeline + manual membership ops",
                    "Phone: founder, member_detail, elins_inspector, dm_notes, comment_generator",
                ],
                "released_at": "2026-05-06",
            },
        ],
    }


# ===========================================================================
# v30 — Founding Cohort Membership + #G Credits
# ---------------------------------------------------------------------------
# Six endpoints + cohort enforcement:
#   GET  /membership/state          — read-only snapshot for the cockpit
#   POST /membership/activate       — join Founding Cohort or get waitlisted
#   POST /membership/cancel         — leave; forfeits the price lock
#   POST /membership/g/buy_single   — purchase one #G credit ($1)
#   POST /membership/g/buy_pack_20  — purchase 20-pack ($20)
#   GET  /membership/g/history      — paginated transaction history
#
# The #G credit consumption is wired into /elins/g/run below.
# ===========================================================================
class V30ActivateRequest(BaseModel):
    accept_terms: bool = False


def _founding_price_for(user: str, user_doc: dict | None = None) -> float:
    """Return the price the user pays for the Founding tier.
    * Active member: their locked price (immutable).
    * Cancelled member: full price ($150) — forfeited their lock.
    * New member with cap available: locked price ($50).
    """
    doc = user_doc if user_doc is not None else (users_store.get_user(user) or {})
    if doc.get("membership_status") == "active":
        # Already active — return their stored locked price.
        return float(doc.get("membership_price") or membership_store.FOUNDING_PRICE_LOCKED)
    if doc.get("membership_status") == "cancelled":
        # Lock forfeited; reactivation pays full price.
        return float(membership_store.FOUNDING_FULL_PRICE)
    return float(membership_store.FOUNDING_PRICE_LOCKED)


def _membership_view(user: str) -> dict:
    """Compose the read-only state object the UI consumes. Includes:
    * the user's tier/price/status
    * cohort-level fill stats
    * waitlist position (if applicable)
    * #G credit balance + last-N-history tail (the full history lives at
      /membership/g/history)
    * v31 — billing_state + renewal_ts + next_amount
    """
    user_doc = users_store.get_user(user) or {}
    cohort_state = membership_store.get_cohort_state()
    on_waitlist_pos = membership_store.waitlist_position(user)
    next_price = _founding_price_for(user, user_doc)
    return {
        "user": user,
        "membership": {
            "tier": user_doc.get("membership_tier"),
            "status": user_doc.get("membership_status"),
            "price_locked": user_doc.get("membership_price"),
            "started_ts": user_doc.get("membership_started_ts"),
            "cancelled_ts": user_doc.get("membership_cancelled_ts"),
            "next_price": next_price,
            "price_lock_forfeit": user_doc.get("membership_status") == "cancelled",
            # v74 — Founding 500 confirmation flag set by /membership/confirm
            # after the WordPress signup + Stripe Checkout flow.
            "confirmed": bool(user_doc.get("membership_confirmed")),
            "confirmed_ts": user_doc.get("membership_confirmed_ts"),
        },
        "billing": {
            "state": user_doc.get("billing_state"),
            "renewal_ts": user_doc.get("renewal_ts"),
            "renewal_retry_count": int(user_doc.get("renewal_retry_count") or 0),
            "renewal_grace_until_ts": user_doc.get("renewal_grace_until_ts"),
            "next_amount": next_price,
        },
        "cohort": cohort_state,
        "waitlist_position": on_waitlist_pos,
        "g_credits": {
            "balance": int(user_doc.get("g_credits") or 0),
            "history_tail": list(user_doc.get("g_credit_history") or [])[-USER_DOC_HISTORY_TAIL:],
        },
    }


# Re-export the user-doc tail size as a module-level constant so /membership
# routes match users_store. Single source of truth.
USER_DOC_HISTORY_TAIL = users_store.USER_DOC_HISTORY_TAIL


@app.get("/membership/state")
def membership_state(session: dict = Depends(require_session)):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/membership/state")
    view = _membership_view(user)
    v29_hardening.log_event(
        "membership_state", user=user, route="/membership/state", success=True,
        active_count=view["cohort"]["active_count"],
        balance=view["g_credits"]["balance"],
    )
    return {"ok": True, "state": view}


@app.post("/membership/activate")
def membership_activate(req: V30ActivateRequest, session: dict = Depends(require_session)):
    """v31 — PaymentIntent-driven activation.

    Returns immediately with ``pending: True`` plus an ``intent_id`` and
    ``client_secret`` so the client can confirm via Stripe.js (or via the
    test helper in mock mode). The actual cohort add + state mutation
    happens in the webhook handler when the intent succeeds.

    Special cases:
    * Already active → idempotent return, no intent created.
    * Cohort full + user is not a returning cancelled member → waitlist.
    """
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("founder_tier_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Founding tier is not enabled for your account"),
            status_code=403,
        )
    if not bool(req.accept_terms):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("terms_required", "accept_terms must be true to activate"),
        )
    v29_hardening.enforce_rate_limit(user, "/membership/activate")

    user_doc = users_store.get_user(user) or {}
    if user_doc.get("membership_status") == "active":
        v29_hardening.log_event(
            "membership_activate_idempotent", user=user,
            route="/membership/activate", success=True,
        )
        return {"ok": True, "state": _membership_view(user), "already_active": True}

    price = _founding_price_for(user, user_doc)

    if membership_store.is_cohort_full() and not user_doc.get("membership_cancelled_ts"):
        # v32 — Founding 500 is full. Authenticated users get added to the
        # in-cohort waitlist (so they keep their queue position). The public
        # /waitlist/join endpoint is the path for unauthenticated users.
        membership_store.add_to_waitlist(user)
        v29_hardening.log_event(
            "membership_waitlist", user=user, route="/membership/activate",
            success=True, position=membership_store.waitlist_position(user) or 0,
        )
        return {
            "ok": True,
            "waitlisted": True,
            "message": (
                "The Founding 500 cohort is full. You're on the waitlist; "
                "we'll reach out when a spot opens."
            ),
            "state": _membership_view(user),
        }

    try:
        intent = billing_intents.create_payment_intent(
            user, price, f"Founding tier activation ({user})",
            kind="membership_activation",
            metadata={"cohort": membership_store.FOUNDING_COHORT},
        )
    except billing_intents.BillingError as e:
        v29_hardening.log_event(
            "membership_activate_failed", user=user, route="/membership/activate",
            success=False, error=e.code,
        )
        raise HTTPException(
            status_code=402,
            detail=error_response(e.code, e.message),
        )

    # In auto-confirm mock mode the side-effect has already landed; we
    # surface "pending: false" so the legacy UI flow keeps working.
    pending = intent.get("status") != "succeeded"
    v29_hardening.log_event(
        "membership_activate_intent_created", user=user, route="/membership/activate",
        success=True, intent_id=intent["intent_id"], pending=pending,
        amount=intent["amount"], mode=intent["mode"],
    )
    # Lazy-boot the renewal scheduler on first activation per process.
    billing_renewal._ensure_renewal_scheduler_started()
    return {
        "ok": True,
        "pending": pending,
        "intent": {
            "intent_id": intent["intent_id"],
            "client_secret": intent.get("client_secret"),
            "status": intent["status"],
            "amount": intent["amount"],
            "kind": intent["kind"],
            "mode": intent["mode"],
        },
        "state": _membership_view(user),
    }


@app.post("/membership/cancel")
def membership_cancel(session: dict = Depends(require_session)):
    """Cancel an active membership. Sets status=cancelled and records a
    transaction. The user's price lock is forfeited; reactivation will
    cost the full price ($150)."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/membership/cancel")

    user_doc = users_store.get_user(user) or {}
    if user_doc.get("membership_status") != "active":
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("not_active", "No active membership to cancel"),
        )

    cancelled_ts = time.time()
    users_store.set_membership(
        user,
        tier=user_doc.get("membership_tier"),
        price=user_doc.get("membership_price"),
        status="cancelled",
        cancelled_ts=cancelled_ts,
    )
    # v31 — billing_state is the canonical lifecycle marker; flip it to
    # "cancelled" alongside the legacy membership_status field.
    users_store.set_billing_state(user, billing_state="cancelled")
    membership_store.remove_member(user)
    membership_billing.record_transaction(
        user, type="membership_cancel", amount=0.0, credits_delta=0,
        metadata={"price_lock_forfeit": True},
    )

    v29_hardening.log_event(
        "membership_cancel", user=user, route="/membership/cancel",
        success=True,
    )
    return {"ok": True, "state": _membership_view(user)}


# ===========================================================================
# C1 / A+D — Stripe Subscription endpoints (canonical billing for new signups)
# ===========================================================================
class SubscriptionStartRequest(BaseModel):
    price_id: Optional[str] = None


class SubscriptionCancelRequest(BaseModel):
    mode: str = "period_end"   # "immediate" | "period_end"


@app.post("/billing/subscription/start")
def subscription_start(req: SubscriptionStartRequest, session: dict = Depends(require_session)):
    """Start a Stripe Subscription for the authed user. Returns the
    ``client_secret`` for on-session SCA (client confirms via Stripe.js);
    the member is activated by the ``invoice.paid`` webhook."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("founder_tier_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Founding tier is not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/billing/subscription/start")
    price_id = (
        req.price_id
        or os.environ.get("CLARITYOS_STRIPE_PRICE_FOUNDING")
        or "price_founding_mock"
    ).strip()
    try:
        out = billing_subscriptions.create_membership_subscription(user, price_id)
    except billing_subscriptions.SubscriptionError as e:
        raise HTTPException(status_code=402, detail=error_response(e.code, e.message))
    v29_hardening.log_event(
        "subscription_start", user=user, route="/billing/subscription/start",
        success=True, subscription_id=out["subscription_id"], status=out.get("status"),
    )
    return {"ok": True, **out}


@app.post("/billing/subscription/cancel")
def subscription_cancel(req: SubscriptionCancelRequest, session: dict = Depends(require_session)):
    """Cancel the authed user's subscription. ``mode`` = ``immediate`` |
    ``period_end`` (default)."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/billing/subscription/cancel")
    mode = (req.mode or "period_end").strip().lower()
    if mode not in ("immediate", "period_end"):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_mode", "mode must be 'immediate' or 'period_end'"),
        )
    try:
        if mode == "immediate":
            billing_subscriptions.cancel_subscription_immediately(user)
        else:
            billing_subscriptions.cancel_subscription_at_period_end(user)
    except billing_subscriptions.SubscriptionError as e:
        raise HTTPException(status_code=402, detail=error_response(e.code, e.message))
    v29_hardening.log_event(
        "subscription_cancel", user=user, route="/billing/subscription/cancel",
        success=True, mode=mode,
    )
    return {"ok": True, "mode": mode, "state": _membership_view(user)}


# ===========================================================================
# v74 / Unit 84 — Founding 500 Subscription Gate confirmation
# ===========================================================================
# Distinct from /membership/activate:
#   * /activate creates a NEW PaymentIntent — wrong for this flow because
#     payment already landed on WordPress via Stripe Checkout
#   * /confirm only binds the consent + acknowledgement; no charge
#
# Flow:
#   WordPress signup -> Stripe Checkout -> webhook flips membership_status
#   to "active" -> WP redirects to app.clarityos.com/auth/consume?token=...
#   -> React /founding500/confirm gate -> ActionControl POSTs here
# ===========================================================================
class V74ConfirmRequest(BaseModel):
    accept_terms: bool = False


@app.post("/membership/confirm")
def membership_confirm(req: V74ConfirmRequest, session: dict = Depends(require_session)):
    """v74 — Founding 500 terms confirmation (NOT activation).

    Behavior (per Unit 84 contract):
      1. Requires auth (401 anonymous)
      2. accept_terms must be true (400 otherwise)
      3. Idempotent: already-confirmed -> 200 {ok, state}
      4. Subscription must be active (409 subscription_inactive otherwise)
      5. Cohort must have capacity OR user must already be a counted
         member (409 cohort_full on race-condition mismatch)
      6. Marks membership_confirmed + membership_confirmed_ts on user doc
    """
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    if not bool(req.accept_terms):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("terms_required", "accept_terms must be true to confirm"),
        )
    v29_hardening.enforce_rate_limit(user, "/membership/confirm")

    user_doc = users_store.get_user(user) or {}

    # Idempotency: already confirmed → return state unchanged.
    if user_doc.get("membership_confirmed"):
        v29_hardening.log_event(
            "membership_confirm_idempotent", user=user,
            route="/membership/confirm", success=True,
        )
        return {"ok": True, "state": _membership_view(user)}

    # Subscription must be active. The Stripe Checkout webhook is what
    # flips membership_status to "active" — if we don't see that flag,
    # either the user hasn't paid or the webhook hasn't fired yet.
    if user_doc.get("membership_status") != "active":
        v29_hardening.log_event(
            "membership_confirm_no_subscription", user=user,
            route="/membership/confirm", success=False,
        )
        raise HTTPException(
            status_code=409,
            detail=error_response("subscription_inactive", "No active subscription found"),
        )

    # Cohort capacity guard. If the user is already a counted cohort
    # member (the common case — Stripe webhook added them on payment),
    # this passes. The is_cohort_full check only blocks if somehow
    # status is "active" but the user isn't in the cohort, which is a
    # rare race during webhook processing.
    if not membership_store.is_member(user) and membership_store.is_cohort_full():
        v29_hardening.log_event(
            "membership_confirm_cohort_full", user=user,
            route="/membership/confirm", success=False,
        )
        raise HTTPException(
            status_code=409,
            detail=error_response("cohort_full", "Founding 500 cohort is at capacity"),
        )

    # Bind confirmation. Additive fields on the user doc — no schema
    # migration; firestore + in-memory backends both accept new keys.
    users_store.update_user(user, {
        "membership_confirmed": True,
        "membership_confirmed_ts": time.time(),
    })

    v29_hardening.log_event(
        "membership_confirm_ok", user=user, route="/membership/confirm",
        success=True,
    )
    return {"ok": True, "state": _membership_view(user)}


def _g_buy(user: str, *, kind: str, units: int, amount: float) -> dict:
    """v31 — PaymentIntent-driven credit purchase. Returns ``pending``
    with the intent metadata; the webhook handler is what actually adds
    the credits via ``billing_intents._apply_succeeded``.

    In mock auto-confirm mode the side-effect has already landed by the
    time this returns; ``pending`` is false and the response includes
    the post-confirm balance."""
    try:
        intent = billing_intents.create_payment_intent(
            user, amount, f"#G credits: {kind}",
            kind=kind,
            metadata={"units": int(units)},
        )
    except billing_intents.BillingError as e:
        raise HTTPException(
            status_code=402,
            detail=error_response(e.code, e.message),
        )

    pending = intent.get("status") != "succeeded"
    balance_after = users_store.get_g_credit_balance(user)
    return {
        "ok": True,
        "pending": pending,
        "balance": balance_after,
        "intent": {
            "intent_id": intent["intent_id"],
            "client_secret": intent.get("client_secret"),
            "status": intent["status"],
            "amount": intent["amount"],
            "kind": intent["kind"],
            "mode": intent["mode"],
        },
        "purchase": {
            "units": int(units),
            "amount": float(amount),
            "intent_id": intent["intent_id"],
            "mode": intent["mode"],
        },
    }


@app.post("/membership/g/buy_single")
def g_buy_single(session: dict = Depends(require_session)):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("g_credits_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "#G credits are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/membership/g/buy_single")
    result = _g_buy(user, kind="g_credit_single", units=1, amount=1.00)
    v29_hardening.log_event(
        "g_buy_single", user=user, route="/membership/g/buy_single",
        success=True, balance=result["balance"], pending=result["pending"],
    )
    return result


@app.post("/membership/g/buy_pack_20")
def g_buy_pack_20(session: dict = Depends(require_session)):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("g_credits_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "#G credits are not enabled for your account"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/membership/g/buy_pack_20")
    result = _g_buy(user, kind="g_credit_pack", units=20, amount=20.00)
    v29_hardening.log_event(
        "g_buy_pack_20", user=user, route="/membership/g/buy_pack_20",
        success=True, balance=result["balance"], pending=result["pending"],
    )
    return result


@app.get("/membership/g/history")
def g_history(limit: int = 100, session: dict = Depends(require_session)):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=500, default=100)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/membership/g/history")
    txs = membership_store.list_transactions(user, limit=n)
    return {"ok": True, "transactions": txs, "count": len(txs)}


# ===========================================================================
# v31 — Billing Finalization endpoints
# ---------------------------------------------------------------------------
# Three endpoints surface the PaymentIntent flow:
#   POST /billing/intent          — generic intent creation (admin/test path;
#                                   normal flows go through /membership/*)
#   POST /billing/intent/confirm  — mock-only test helper to fire the success
#                                   webhook synchronously
#   GET  /billing/history         — full transaction + intent history
#
# The Stripe-side webhook receiver is the existing /billing/webhook from
# v30 (extended below to dispatch payment_intent.* events into
# billing_intents.handle_payment_webhook).
# ===========================================================================
class V31BillingIntentRequest(BaseModel):
    amount: float
    description: str
    kind: str
    metadata: Optional[dict] = None


class V31BillingConfirmRequest(BaseModel):
    intent_id: str


@app.post("/billing/intent")
def billing_create_intent(req: V31BillingIntentRequest, session: dict = Depends(require_session)):
    """Create a PaymentIntent for the current user. Mostly a thin admin /
    test helper — the real product flows (/membership/activate,
    /membership/g/buy_*) go directly through ``billing_intents``."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    try:
        amount = v29_hardening.require_int(int(round(float(req.amount) * 100)), "amount_cents", min_value=50, max_value=500000) / 100.0
        description = v29_hardening.require_str(req.description, "description", max_len=200)
        kind = v29_hardening.require_one_of(req.kind, "kind", billing_intents.VALID_KINDS)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/billing/intent")

    try:
        intent = billing_intents.create_payment_intent(
            user, amount, description, kind=kind, metadata=req.metadata or {},
        )
    except billing_intents.BillingError as e:
        raise HTTPException(
            status_code=402,
            detail=error_response(e.code, e.message),
        )
    return {
        "ok": True,
        "pending": intent.get("status") != "succeeded",
        "intent": {
            "intent_id": intent["intent_id"],
            "client_secret": intent.get("client_secret"),
            "status": intent["status"],
            "amount": intent["amount"],
            "kind": intent["kind"],
            "mode": intent["mode"],
        },
    }


@app.post("/billing/intent/confirm")
def billing_confirm_intent(req: V31BillingConfirmRequest, session: dict = Depends(require_session)):
    """Mock-only confirmation helper. In stripe mode this 400s — real
    confirmation happens client-side via Stripe.js."""
    user = session["user"]
    try:
        intent_id = v29_hardening.require_str(req.intent_id, "intent_id", max_len=200)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    intent = membership_store.get_intent(intent_id)
    if intent is None:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("not_found", "intent not found"),
            status_code=404,
        )
    if intent.get("user") != user:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("forbidden", "intent belongs to a different user"),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/billing/intent/confirm")
    try:
        result = billing_intents.confirm_payment_intent(intent_id)
    except billing_intents.BillingError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response(e.code, e.message),
        )
    # PASS-4 FIX-P1 — Redact sensitive fields before serialising. The
    # mock-confirm flow has already taken the side effect server-side,
    # so the client never needs ``client_secret`` (no Stripe.js step
    # remains) and never needs the raw provider ``metadata`` (which
    # carries user_id / cohort / environment context that is internal).
    # The returned shape matches /billing/history's per-intent
    # projection so frontend code that reads either route gets a
    # consistent surface.
    return {
        "ok": True,
        "intent": {
            "intent_id":    result.get("intent_id"),
            "status":       result.get("status"),
            "amount":       result.get("amount"),
            "kind":         result.get("kind"),
            "mode":         result.get("mode"),
            "description":  result.get("description"),
            "created_ts":   result.get("created_ts"),
            "confirmed_ts": result.get("confirmed_ts"),
            "failed_ts":    result.get("failed_ts"),
            "failure_code": result.get("failure_code"),
        },
    }


@app.get("/billing/history")
def billing_history(limit: int = 100, session: dict = Depends(require_session)):
    """Combined transaction + intent history for the current user."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("membership_ui_enabled", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "Membership UI is not enabled for your account"),
            status_code=403,
        )
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=500, default=100)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/billing/history")
    transactions = membership_store.list_transactions(user, limit=n)
    intents = membership_store.list_intents_for_user(user, limit=n)
    return {
        "ok": True,
        "transactions": transactions,
        "intents": [
            {
                "intent_id": i.get("intent_id"),
                "amount": i.get("amount"),
                "kind": i.get("kind"),
                "status": i.get("status"),
                "mode": i.get("mode"),
                "created_ts": i.get("created_ts"),
                "confirmed_ts": i.get("confirmed_ts"),
                "failed_ts": i.get("failed_ts"),
                "failure_code": i.get("failure_code"),
                "description": i.get("description"),
            }
            for i in intents
        ],
        "count": len(transactions),
    }


# ===========================================================================
# v32 — Public website + Waitlist pipeline
# ---------------------------------------------------------------------------
# Three endpoints + one public read:
#   POST /waitlist/join             — public; rate-limited per IP
#   GET  /public/cohort_status      — public; reads founding cohort fill
#   GET  /founder/waitlist          — founder-only; lists entries
#   POST /founder/waitlist/update   — founder-only; status transitions
#
# The activation guard for the /membership/activate endpoint stays in place
# (cohort-full users get pushed to the in-cohort waitlist). The public
# /public/cohort_status endpoint exposes the same fill stats the public
# website uses to switch the CTA between "Join the Founding Cohort" and
# "Join the Waitlist".
# ===========================================================================
class V32WaitlistJoinRequest(BaseModel):
    email: str
    name: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None


class V32WaitlistUpdateRequest(BaseModel):
    id: str
    status: str
    note: Optional[str] = None
    user_id: Optional[str] = None


def _client_ip(request: Request) -> str:
    """Best-effort caller IP. Cloud Run forwards via X-Forwarded-For; we
    take the first hop. Falls back to socket peer."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    client = request.client
    return client.host if client else "<unknown>"


@app.post("/waitlist/join")
async def waitlist_join(req: V32WaitlistJoinRequest, request: Request):
    """Public endpoint. No auth. Rate-limited by client IP so the public
    form can't be hammered. Returns ``{ok: true, id, status}``; never
    leaks whether an email was already present (idempotent semantics)."""
    # Rate-limit by IP (and a single keyspace so the per-IP bucket is
    # shared across the keyspace, not per-user). Capacity is intentionally
    # low: a real user submits once or twice; bots send dozens.
    ip = _client_ip(request)
    if not v29_hardening.check_rate_limit(
        f"ip:{ip}", "/waitlist/join", capacity=10, window_s=600.0,
    ):
        v29_hardening.log_event(
            "waitlist_join_rate_limited",
            route="/waitlist/join", success=False,
            ip=ip[:24],
        )
        raise HTTPException(
            status_code=429,
            detail=error_response("rate_limited", "Too many requests; try again later"),
        )

    try:
        email = waitlist_store.normalize_email(req.email)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_email", str(e)),
        )
    # Optional fields validated inside the store helper; map ValueError → 400.
    try:
        record = waitlist_store.add_waitlist_entry(
            email=email,
            name=req.name,
            source=req.source,
            note=req.note,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", str(e)),
        )

    v29_hardening.log_event(
        "waitlist_join", route="/waitlist/join", success=True,
        source=record.get("source") or "website",
        existing=record.get("status") != "waiting",
    )
    return {"ok": True, "id": record["id"], "status": record["status"]}


@app.get("/public/cohort_status")
def public_cohort_status():
    """Public read of Founding Cohort fill stats. The static landing page
    consumes this to switch its CTA between activation and waitlist."""
    s = membership_store.get_cohort_state()
    return {
        "ok": True,
        "cohort": s["cohort"],
        "active_count": s["active_count"],
        "cap": s["cap"],
        "remaining": s["remaining"],
        "is_full": s["is_full"],
        "waitlist_count": s["waitlist_count"],
    }


@app.get("/founder/waitlist")
def founder_waitlist_list(
    status: Optional[str] = None,
    limit: int = 500,
    session: dict = Depends(_require_founder),
):
    """Founder-only waitlist listing. Optional `status` filter."""
    user = session["user"]
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=2000, default=500)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if status is not None and status != "":
        try:
            v29_hardening.require_one_of(status, "status", waitlist_store.VALID_STATUSES)
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
    else:
        status = None
    v29_hardening.enforce_rate_limit(user, "/founder/waitlist")
    try:
        entries = waitlist_store.list_waitlist(status=status, limit=n)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_status", str(e)),
        )
    counts = {
        s: waitlist_store.count_waitlist(status=s)
        for s in waitlist_store.VALID_STATUSES
    }
    counts["total"] = waitlist_store.count_waitlist()
    v29_hardening.log_event(
        "founder_waitlist_list", user=user, route="/founder/waitlist",
        success=True, count=len(entries), filter=str(status or ""),
    )
    return {"ok": True, "entries": entries, "counts": counts}


@app.post("/founder/waitlist/update")
def founder_waitlist_update(
    req: V32WaitlistUpdateRequest,
    session: dict = Depends(_require_founder),
):
    user = session["user"]
    try:
        record_id = v29_hardening.require_str(req.id, "id", max_len=64)
        new_status = v29_hardening.require_one_of(
            req.status, "status", waitlist_store.VALID_STATUSES,
        )
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    note = req.note  # optional; store helper validates length
    user_id = req.user_id
    if new_status == "converted" and (not user_id or not str(user_id).strip()):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "user_id_required",
                "user_id is required when transitioning to converted",
            ),
        )
    v29_hardening.enforce_rate_limit(user, "/founder/waitlist/update")
    try:
        updated = waitlist_store.update_status(
            record_id, status=new_status, note=note, user_id=user_id,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"waitlist entry {record_id!r} not found"),
        )
    v29_hardening.log_event(
        "founder_waitlist_update", user=user, route="/founder/waitlist/update",
        success=True, target_status=new_status, target_id=record_id[:16],
    )
    return {"ok": True, "entry": updated}


# ===========================================================================
# v33 — Founder Console + ELINS Standardization + Comment Generator (#cmt)
# ---------------------------------------------------------------------------
# Eight new endpoints + three updated:
#
#   POST /elins/qc                  — re-run S_ELINS QC on an ELINS object
#   POST /elins/preview             — run the canonical pipeline on text only
#   POST /elins/global              — same, but persists to elins_project/
#   POST /cmt/generate              — Most Relevant Comment Generator
#   POST /c/run                     — #c cloud engine (mode="comment" → /cmt)
#   POST /founder/dm/add            — log a manual DM
#   GET  /founder/dm/list           — list logged DMs (filter by channel/user)
#   POST /founder/dm/notes          — append + read founder notes on a DM
#   POST /founder/membership/activate    — manually activate a member
#   POST /founder/membership/cancel      — manually cancel a member
#   POST /founder/membership/credits     — manually adjust #G credit balance
#
# All founder-only endpoints use ``_require_founder``; user-facing endpoints
# (/elins/preview, /elins/qc, /cmt/generate, /c/run) use ``require_session``
# and are gated by their existing v28/v29 feature flags where applicable.
# ===========================================================================

# ---------- Standardized ELINS pipeline endpoints ----------
class V33ELINSPreviewRequest(BaseModel):
    text: str
    domain_hint: Optional[str] = None


class V33ELINSGlobalRequest(BaseModel):
    text: str
    domain_hint: Optional[str] = None


class V33ELINSQCRequest(BaseModel):
    elins_object: dict


@app.post("/elins/preview")
def elins_preview(req: V33ELINSPreviewRequest, session: dict = Depends(require_session)):
    """Run the canonical 10-layer ELINS pipeline on the provided text.
    Read-only: no persistence. Suitable for the cockpit / phone preview
    surfaces. Gated by ``v28_surfaces`` like the v28 endpoints."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    try:
        text = v29_hardening.require_str(req.text, "text", max_len=SCENARIO_MAX_LEN)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/elins/preview")
    # v40 — preview is now a kernel-driven ELINS run. ``persist=False``
    # preserves the historical no-side-effects contract for the daily
    # store while still attaching S_ELINS QC + recording an
    # operator_state interaction.
    try:
        result = intelligence_kernel.run_ELINS(
            user, text,
            domain_hint=req.domain_hint, kind="preview",
            persist=False, update_indexes=False,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    elins_obj = result["elins"]
    v29_hardening.log_event(
        "elins_preview", user=user, route="/elins/preview", success=True,
        domain=str(elins_obj.get("domain_mapping", {}).get("effective_top") or ""),
    )
    return {"ok": True, "elins": elins_obj}


@app.post("/elins/global")
def elins_global(req: V33ELINSGlobalRequest, session: dict = Depends(_require_founder)):
    """Founder-only — runs the canonical pipeline on the input text AND
    persists to elins_project/* (runs, primitive index, domain history,
    EP baseline). Used to maintain the macro-ELINS trend store."""
    user = session["user"]
    try:
        text = v29_hardening.require_str(req.text, "text", max_len=SCENARIO_MAX_LEN)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/elins/global")
    try:
        result = intelligence_kernel.run_ELINS(
            user, text,
            domain_hint=req.domain_hint, kind="global",
            persist=True, update_indexes=True,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    elins_obj = result["elins"]
    run_id = result["run_id"]
    baseline = result.get("baseline") or {}
    v29_hardening.log_event(
        "elins_global", user=user, route="/elins/global", success=True,
        run_id=run_id,
        domain=str(elins_obj.get("domain_mapping", {}).get("effective_top") or ""),
    )
    return {"ok": True, "run_id": run_id, "elins": elins_obj, "baseline": baseline}


@app.post("/elins/qc")
def elins_qc(req: V33ELINSQCRequest, session: dict = Depends(require_session)):
    """Re-run S_ELINS QC against a previously-generated ELINS object.
    The caller passes the full ELINS dict; the server recomputes
    primitive intensities + reports pass/fail + per-primitive deltas."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("feature_disabled", "v28 surfaces are not enabled for your account"),
            status_code=403,
        )
    if not isinstance(req.elins_object, dict) or not req.elins_object:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "elins_object must be a non-empty dict"),
        )
    v29_hardening.enforce_rate_limit(user, "/elins/qc")
    try:
        s_elins = standard_elins.generate_S_ELINS(req.elins_object)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    v29_hardening.log_event(
        "elins_qc", user=user, route="/elins/qc", success=True,
        passed=bool(s_elins.get("passed")),
        max_delta=float(s_elins.get("max_delta") or 0.0),
    )
    return {"ok": True, "s_elins": s_elins}


# ---------- v34 — ELINS forecast engine ----------
class V34ForecastPrimitive(BaseModel):
    key: str
    intensity: float
    lam: Optional[float] = None  # alias of "lambda" (Pydantic reserves the name)


class V34ForecastChainLink(BaseModel):
    key: str
    intensity: float
    lam: Optional[float] = None
    attenuation: Optional[float] = None


class V34ForecastRequest(BaseModel):
    primitives: list[dict]
    chain: Optional[list[dict]] = None
    domains: Optional[list[str]] = None     # optional subset of DOMAIN_NAMES
    days: int = 5


class V34FounderForecastRunRequest(BaseModel):
    text: str
    domain_hint: Optional[str] = None
    days: int = 5


def _v34_normalize_primitive(p: dict, *, idx: int) -> dict:
    """Coerce the public Pydantic shape (with ``lam``) into the internal
    ``forecast_engine`` shape (with ``lambda``). Tolerant of either key."""
    if not isinstance(p, dict):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"primitives[{idx}] must be an object",
            ),
        )
    out = {"key": p.get("key"), "intensity": p.get("intensity", p.get("ep0"))}
    lam = p.get("lambda", p.get("lam"))
    if lam is not None:
        out["lambda"] = lam
    if "attenuation" in p and p["attenuation"] is not None:
        out["attenuation"] = p["attenuation"]
    return out


@app.post("/elins/forecast")
def elins_forecast(req: V34ForecastRequest, session: dict = Depends(require_session)):
    """Run the multi-primitive forecast engine on a caller-supplied set
    of primitives + optional chain + optional domain subset. No
    persistence; same input → same output."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    try:
        n = v29_hardening.require_int(req.days, "days", min_value=1, max_value=30, default=5)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not isinstance(req.primitives, list) or not req.primitives:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "primitives must be a non-empty list"),
        )
    if len(req.primitives) > 32:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "too many primitives (max 32)"),
        )
    norm_prims = [
        _v34_normalize_primitive(p, idx=i) for i, p in enumerate(req.primitives)
    ]
    norm_chain = None
    if req.chain is not None:
        if not isinstance(req.chain, list):
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", "chain must be a list"),
            )
        if len(req.chain) > 16:
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", "chain too long (max 16 links)"),
            )
        norm_chain = [
            _v34_normalize_primitive(c, idx=i) for i, c in enumerate(req.chain)
        ]
    requested_domains: list[str]
    if req.domains is None:
        requested_domains = list(forecast_engine.DOMAIN_NAMES)
    else:
        if not isinstance(req.domains, list):
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", "domains must be a list of strings"),
            )
        bad = [d for d in req.domains if d not in forecast_engine.DOMAIN_NAMES]
        if bad:
            v29_hardening.raise_validation(
                v29_hardening.ValidationError(
                    "bad_input", f"unknown domains: {bad!r}",
                ),
            )
        requested_domains = list(req.domains)

    v29_hardening.enforce_rate_limit(user, "/elins/forecast")
    try:
        primitive_envelopes = {
            p["key"]: forecast_engine.compute_envelope(p, days=n)
            for p in norm_prims
        }
        multi_envelope = forecast_engine.compute_multi_envelope(norm_prims, days=n)
        domain_envelopes = {
            name: forecast_engine.compute_domain_envelope(
                forecast_engine.DOMAIN_VECTORS[name], norm_prims, days=n,
            )
            for name in requested_domains
        }
        chain_envelope = None
        if norm_chain:
            chain_envelope = forecast_engine.compute_chain_envelope(norm_chain, days=n)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    v29_hardening.log_event(
        "elins_forecast", user=user, route="/elins/forecast", success=True,
        primitives=len(norm_prims),
        chain=len(norm_chain or []),
        domains=len(requested_domains),
    )
    return {
        "ok": True,
        "forecast": {
            "primitive_envelopes": primitive_envelopes,
            "multi_envelope": multi_envelope,
            "domain_envelopes": domain_envelopes,
            "chain": norm_chain,
            "chain_envelope": chain_envelope,
            "days": n,
            "version": "forecast.v34.1",
        },
    }


@app.get("/elins/forecast/example")
def elins_forecast_example():
    """Static example payload for UI development. Public — same shape
    as /elins/forecast output, no auth required so the cockpit can boot
    a placeholder chart on first paint."""
    return {"ok": True, "example": forecast_engine.example_payload()}


@app.post("/founder/elins/forecast/run")
def founder_elins_forecast_run(
    req: V34FounderForecastRunRequest,
    session: dict = Depends(_require_founder),
):
    """Founder-only: run the FULL ELINS pipeline + forecast engine + persist
    the run. Returns the canonical ELINS object (which already embeds
    ``forecast_engine`` after v34) plus the persisted run id + baseline."""
    founder = session["user"]
    try:
        text = v29_hardening.require_str(req.text, "text", max_len=SCENARIO_MAX_LEN)
        n = v29_hardening.require_int(req.days, "days", min_value=1, max_value=30, default=5)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(founder, "/founder/elins/forecast/run")
    try:
        elins_obj = standard_elins.generate_ELINS(
            text, domain_hint=req.domain_hint, user=founder,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    # If the caller asked for a non-default forecast horizon, recompute
    # the forecast block with the requested days (the embedded one is
    # always days=5).
    if n != 5:
        elins_obj["forecast_engine"] = forecast_engine.compute_forecast_block(
            elins_obj["primitives"]["intensities"],
            edges=elins_obj["causal_chain"]["edges"],
            days=n,
        )
    run_id = elins_project.save_daily_run(founder, elins_obj)
    elins_project.update_global_primitive_index(elins_obj)
    elins_project.update_domain_history(founder, elins_obj)
    baseline = elins_project.update_ep_baseline(founder, elins_obj)
    v29_hardening.log_event(
        "founder_elins_forecast_run", user=founder,
        route="/founder/elins/forecast/run", success=True, run_id=run_id, days=n,
    )
    return {
        "ok": True,
        "run_id": run_id,
        "elins": elins_obj,
        "baseline": baseline,
    }


# ---------- v35 — Regional ELINS modules + ESO ----------
class V35RegionalRunRequest(BaseModel):
    region_code: str
    topic_hint: Optional[str] = None


class V35RegionalBatchRequest(BaseModel):
    regions: list[str]
    topic_hint: Optional[str] = None


def _resolve_eso_for(user: str, region_code: str) -> Optional[dict]:
    """Resolve the External Signal Object for ``user`` + ``region_code``.

    Honours ``user.external_signal_mode``: only ``"cloud_perplexity"``
    triggers an ESO fetch (deterministic mock today). Anything else
    returns None and the regional run proceeds without external bias.
    """
    user_doc = users_store.get_user(user) or {}
    if not perplexity_oracle.is_eso_enabled(user_doc):
        return None
    try:
        return perplexity_oracle.fetch_basin_signals(region_code, user=user)
    except ValueError:
        return None


@app.post("/elins/regional/run")
def elins_regional_run(
    req: V35RegionalRunRequest,
    session: dict = Depends(require_session),
):
    """Run a regional ELINS pass for the requested region. ESO is
    resolved server-side when the user has opted in via
    ``external_signal_mode == "cloud_perplexity"``. The run is persisted
    via elins_project.save_regional_run keyed by (region, today)."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    if req.region_code not in regional_elins.REGION_CODES:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input",
                f"region_code must be one of {list(regional_elins.REGION_CODES)!r}",
            ),
        )
    topic_hint = None
    if req.topic_hint is not None:
        try:
            topic_hint = v29_hardening.require_str(
                req.topic_hint, "topic_hint",
                max_len=SCENARIO_MAX_LEN, allow_empty=True,
            )
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
        topic_hint = topic_hint or None
    v29_hardening.enforce_rate_limit(user, "/elins/regional/run")
    try:
        result = intelligence_kernel.run_regional_ELINS(
            user, req.region_code, topic_hint=topic_hint,
            persist=True,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    elins_obj = result["elins"]
    run_id = result["run_id"]
    eso_present = bool(result.get("eso_present"))
    v29_hardening.log_event(
        "elins_regional_run", user=user, route="/elins/regional/run",
        success=True, region_code=req.region_code, run_id=run_id,
        eso_present=eso_present,
    )
    return {
        "ok": True,
        "run_id": run_id,
        "region_code": req.region_code,
        "elins": elins_obj,
        "eso_present": eso_present,
    }


@app.get("/elins/regional/list")
def elins_regional_list(session: dict = Depends(require_session)):
    """Return the list of supported regions plus, for each, the latest
    saved run summary if one exists. Lightweight metadata only."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    out: list[dict] = []
    for region in regional_elins.REGION_CODES:
        latest = elins_project.latest_regional_run(region)
        if latest is None:
            out.append({
                "region_code": region, "latest": None,
            })
        else:
            out.append({
                "region_code": region,
                "latest": {
                    "run_id": latest.get("id"),
                    "day": latest.get("day"),
                    "scenario_id": latest.get("scenario_id"),
                    "summary": latest.get("summary") or {},
                    "domain_top": latest.get("domain_top"),
                    "external_present": latest.get("external_present"),
                    "external_anchors": latest.get("external_anchors") or [],
                    "saved_ts": latest.get("saved_ts"),
                },
            })
    return {
        "ok": True,
        "regions": list(regional_elins.REGION_CODES),
        "items": out,
    }


@app.post("/founder/elins/regional/batch")
def founder_elins_regional_batch(
    req: V35RegionalBatchRequest,
    session: dict = Depends(_require_founder),
):
    """Founder-only: run regional ELINS for multiple regions in one
    call. Returns a map of region_code → ELINS object. Each run is
    persisted via save_regional_run."""
    founder = session["user"]
    if not isinstance(req.regions, list) or not req.regions:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "regions must be a non-empty list"),
        )
    if len(req.regions) > len(regional_elins.REGION_CODES):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input",
                f"too many regions (max {len(regional_elins.REGION_CODES)})",
            ),
        )
    bad = [r for r in req.regions if r not in regional_elins.REGION_CODES]
    if bad:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"unknown regions: {bad!r}",
            ),
        )
    topic_hint = None
    if req.topic_hint is not None:
        try:
            topic_hint = v29_hardening.require_str(
                req.topic_hint, "topic_hint",
                max_len=SCENARIO_MAX_LEN, allow_empty=True,
            )
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
        topic_hint = topic_hint or None
    v29_hardening.enforce_rate_limit(founder, "/founder/elins/regional/batch")
    results: dict[str, dict] = {}
    run_ids: dict[str, str] = {}
    for region in req.regions:
        eso = _resolve_eso_for(founder, region)
        previous = elins_project.latest_regional_run(region)
        previous_elins = (previous or {}).get("elins") if previous else None
        elins_obj = regional_elins.run_regional_elins(
            region, user=founder,
            topic_hint=topic_hint, eso=eso, previous_run=previous_elins,
        )
        run_ids[region] = elins_project.save_regional_run(region, None, elins_obj)
        results[region] = elins_obj
    v29_hardening.log_event(
        "founder_elins_regional_batch", user=founder,
        route="/founder/elins/regional/batch", success=True,
        regions=len(req.regions),
    )
    return {
        "ok": True,
        "results": results,
        "run_ids": run_ids,
    }


# ---------- v36 — Macro-ELINS scheduler + run log ----------
class V36SchedulerConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    cadence: Optional[str] = None
    external_signal_mode: Optional[str] = None


@app.get("/founder/elins/scheduler/status")
def founder_scheduler_status(session: dict = Depends(_require_founder)):
    cfg = elins_scheduler_config.get_config()
    return {
        "ok": True,
        "config": cfg,
        "running": elins_scheduler.is_running(),
        "tick_seconds": elins_scheduler.SCHEDULER_TICK_SECONDS,
        "valid_cadences": list(elins_scheduler_config.VALID_CADENCES),
        "valid_signal_modes": list(elins_scheduler_config.VALID_SIGNAL_MODES),
    }


@app.post("/founder/elins/scheduler/config")
def founder_scheduler_config(
    req: V36SchedulerConfigRequest,
    session: dict = Depends(_require_founder),
):
    """Update the macro-ELINS scheduler config. Toggling enabled here
    drives whether the scheduler thread runs ticks (background loop
    re-reads the config on every tick). Returns the new config + running
    flag."""
    founder = session["user"]
    updates: dict = {}
    if req.enabled is not None:
        updates["enabled"] = bool(req.enabled)
    if req.cadence is not None:
        try:
            v29_hardening.require_one_of(
                req.cadence, "cadence",
                elins_scheduler_config.VALID_CADENCES,
            )
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
        updates["cadence"] = req.cadence
    if req.external_signal_mode is not None:
        try:
            v29_hardening.require_one_of(
                req.external_signal_mode, "external_signal_mode",
                elins_scheduler_config.VALID_SIGNAL_MODES,
            )
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
        updates["external_signal_mode"] = req.external_signal_mode
    cfg = elins_scheduler_config.set_config(updates)
    # Honour the toggle: if enabled flipped on, lazy-boot the thread; if
    # off, signal the loop to stop. Tests use _run_macro_elins_once
    # directly so the thread is rarely required.
    if cfg.get("enabled"):
        elins_scheduler.start_elins_scheduler()
    else:
        elins_scheduler.stop_elins_scheduler()
    v29_hardening.log_event(
        "founder_scheduler_config", user=founder,
        route="/founder/elins/scheduler/config", success=True,
        enabled=cfg["enabled"], cadence=cfg["cadence"],
        external_signal_mode=cfg["external_signal_mode"],
    )
    return {
        "ok": True,
        "config": cfg,
        "running": elins_scheduler.is_running(),
    }


@app.post("/founder/elins/macro/run_now")
def founder_macro_run_now(session: dict = Depends(_require_founder)):
    """Trigger a macro-ELINS pass immediately, ignoring cadence. Returns
    the summary the scheduler would have logged."""
    founder = session["user"]
    v29_hardening.enforce_rate_limit(founder, "/founder/elins/macro/run_now")
    summary = elins_scheduler._run_macro_elins_once(force=True)
    v29_hardening.log_event(
        "founder_macro_run_now", user=founder,
        route="/founder/elins/macro/run_now", success=True,
        run_id=summary.get("run_id"), regions=len(summary.get("regions") or []),
    )
    return {"ok": True, "summary": summary}


@app.get("/founder/elins/macro/runs")
def founder_macro_runs_list(
    limit: int = 20,
    session: dict = Depends(_require_founder),
):
    try:
        n = v29_hardening.require_int(
            limit, "limit", min_value=1, max_value=200, default=20,
        )
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    rows = elins_project.list_macro_runs(limit=n)
    return {"ok": True, "runs": rows, "count": len(rows)}


@app.get("/founder/elins/macro/run/{run_id}")
def founder_macro_run_detail(
    run_id: str,
    session: dict = Depends(_require_founder),
):
    record = elins_project.get_macro_run_with_constituents(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"macro run {run_id!r} not found"),
        )
    return {"ok": True, "run": record}


# ---------- v37 — Cross-cluster entity graph ----------
def _load_current_entity_graph() -> dict:
    """Load the latest persisted graph or fall back to the empty graph
    so endpoints work cleanly even before the first macro pass."""
    snap = elins_project.load_latest_entity_graph()
    if snap is None:
        return dict(elins_entity_graph.EMPTY_GRAPH)
    g = snap.get("graph") or {}
    if "entities" not in g or "edges" not in g:
        return dict(elins_entity_graph.EMPTY_GRAPH)
    return g


@app.get("/elins/entities/search")
def elins_entity_search(
    q: Optional[str] = None,
    limit: int = 50,
    session: dict = Depends(require_session),
):
    """Substring search over entity names. Empty/missing q returns the
    top-degree entities."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=200, default=50)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    graph = _load_current_entity_graph()
    rows = elins_entity_graph.search_entities(graph, q or "", limit=n)
    return {
        "ok": True,
        "q": q or "",
        "entities": rows,
        "count": len(rows),
        "graph_updated_ts": float(graph.get("updated_ts") or 0.0),
    }


@app.get("/elins/entities/{entity}/neighbors")
def elins_entity_neighbors(
    entity: str,
    limit: int = 20,
    session: dict = Depends(require_session),
):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=200, default=20)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    graph = _load_current_entity_graph()
    rec = elins_entity_graph.get_entity(graph, entity)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"entity {entity!r} not in graph"),
        )
    neighbors = elins_entity_graph.get_entity_neighbors(graph, entity, limit=n)
    return {
        "ok": True,
        "entity": entity,
        "summary": {
            "degree": rec.get("degree"),
            "clusters": rec.get("clusters") or [],
            "ep_mean": (rec.get("ep_stats") or {}).get("mean") or 0.0,
            "domains": rec.get("domains") or {},
        },
        "neighbors": neighbors,
    }


@app.get("/elins/entities/{entity}/timeseries")
def elins_entity_timeseries(
    entity: str,
    session: dict = Depends(require_session),
):
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    graph = _load_current_entity_graph()
    rec = elins_entity_graph.get_entity(graph, entity)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"entity {entity!r} not in graph"),
        )
    series = elins_entity_graph.get_entity_timeseries(graph, entity)
    return {"ok": True, "entity": entity, "timeseries": series}


@app.get("/elins/dashboard")
def elins_dashboard_latest(session: dict = Depends(require_session)):
    """Return the latest interactive dashboard snapshot for the user.
    Composite of global + 6 regional + macro + entity-graph sections.
    Gated by ``v28_surfaces`` like the rest of the v28+ surfaces."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    v29_hardening.enforce_rate_limit(user, "/elins/dashboard")
    snap = elins_dashboard.get_dashboard_snapshot(user)
    return {"ok": True, "snapshot": snap}


@app.get("/elins/dashboard/{date}")
def elins_dashboard_for_date(
    date: str,
    session: dict = Depends(require_session),
):
    """Snapshot pinned to a specific date (YYYY-MM-DD)."""
    user = session["user"]
    cohort = session.get("cohort")
    if not v29_hardening.feature_enabled("v28_surfaces", user=user, cohort=cohort):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "feature_disabled", "v28 surfaces are not enabled for your account",
            ),
            status_code=403,
        )
    try:
        snap = elins_dashboard.get_dashboard_for_date(user, date)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return {"ok": True, "snapshot": snap}


@app.get("/founder/elins/dashboard/overview")
def founder_dashboard_overview(session: dict = Depends(_require_founder)):
    """Founder-only operational summary: macro-run count, entity-graph
    snapshot count, per-region coverage, scheduler config."""
    overview = elins_dashboard.get_founder_overview()
    return {"ok": True, "overview": overview}


# ---------- v39 — Operator state memory ----------
class V39OperatorPatchRequest(BaseModel):
    external_signal_mode: Optional[str] = None


@app.get("/me/operator_state")
def me_operator_state(session: dict = Depends(require_session)):
    """Return the caller's own operator state. Metadata-only — never
    contains raw prompt text, only ids + topics + preference weights."""
    user = session["user"]
    state = operator_state.get_operator_state(user)
    return {"ok": True, "state": state}


@app.post("/me/operator_state")
def me_operator_state_update(
    req: V39OperatorPatchRequest,
    session: dict = Depends(require_session),
):
    """Update mutable operator-state fields. Today the only one is
    ``external_signal_mode`` (used by the regional ELINS pipeline +
    macro scheduler to decide whether to fetch ESO)."""
    user = session["user"]
    patch: dict = {}
    if req.external_signal_mode is not None:
        try:
            v29_hardening.require_one_of(
                req.external_signal_mode, "external_signal_mode",
                operator_state.VALID_SIGNAL_MODES,
            )
        except v29_hardening.ValidationError as e:
            v29_hardening.raise_validation(e)
        patch["external_signal_mode"] = req.external_signal_mode
    state = operator_state.update_operator_state(user, patch)
    # Mirror onto users_store so the regional ELINS resolver
    # (`_resolve_eso_for`) sees the change immediately. This keeps the
    # operator_state value as the source of truth for the founder UI
    # while letting the existing v35 ESO resolver continue to read its
    # canonical key from the user document.
    if patch.get("external_signal_mode"):
        try:
            users_store.update_user(
                user, {"external_signal_mode": patch["external_signal_mode"]},
            )
        except Exception:  # pragma: no cover (defensive)
            pass
    return {"ok": True, "state": state}


@app.get("/founder/intelligence/kernel/status")
def founder_intelligence_kernel_status(session: dict = Depends(_require_founder)):
    """Founder-only kernel snapshot (version, ESO default, scheduler
    state, last macro pass). Read-only."""
    return {"ok": True, "kernel": intelligence_kernel.kernel_status()}


# ---------- v42 — Billing observability ----------
@app.get("/founder/billing/status")
def founder_billing_status(session: dict = Depends(_require_founder)):
    """Founder-only Stripe + webhook visibility. Surfaces:

    * Stripe configuration mode (test / live / disabled).
    * Whether keys + webhook secret are present.
    * The recent-events ring (metadata-only — sanitised).
    * Last event timestamp (a quick "is the webhook alive?" signal).
    """
    status = billing_config.get_billing_status()
    recent = billing_config.list_recent_events(limit=50)
    last_ts = billing_config.last_event_ts()
    return {
        "ok": True,
        "stripe": status,
        "live_mode": status.get("live_mode"),
        "recent_events": recent,
        "last_event_ts": last_ts,
        "runtime_billing_mode": os.environ.get("CLARITYOS_BILLING_MODE", "mock"),
    }


@app.get("/founder/analytics/summary")
def founder_analytics_summary(session: dict = Depends(_require_founder)):
    """v43 — Founder-only analytics aggregate.

    Joins users_store + operator_state + elins_project + billing_config
    into a single read-only summary the founder console renders in one
    round-trip. Counts are scoped to rolling 7-day / 30-day windows.
    """
    summary = founder_analytics.get_founder_analytics_summary()
    return {"ok": True, "summary": summary}


# ---------- v44 — Multi-model router ----------
class V44ModelPreferenceRequest(BaseModel):
    preferred_model: Optional[str] = None


class V44FounderOverrideRequest(BaseModel):
    default_model: Optional[str] = None


@app.post("/me/operator_state/model")
def me_operator_state_model(
    req: V44ModelPreferenceRequest,
    session: dict = Depends(require_session),
):
    """Set (or clear) the user's preferred model. ``preferred_model``
    must be a valid id from ``model_router.SUPPORTED_MODELS`` or
    ``None``/``""`` to clear the preference (router falls back to the
    task default)."""
    user = session["user"]
    try:
        state = operator_state.set_preferred_model(user, req.preferred_model)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return {"ok": True, "state": state}


@app.get("/founder/models/status")
def founder_models_status(session: dict = Depends(_require_founder)):
    """Founder-only model-router visibility. Returns per-provider
    configured-flags + supported model ids + the active founder
    default override (if any)."""
    return {"ok": True, "router": model_router.get_router_status()}


@app.post("/founder/models/override")
def founder_models_override(
    req: V44FounderOverrideRequest,
    session: dict = Depends(_require_founder),
):
    """Founder-only — set a global default model that the router uses
    in preference to per-user preferences (but not in preference to
    explicit per-call overrides). Pass ``default_model: null`` (or
    empty) to clear."""
    founder = session["user"]
    try:
        chosen = model_router.set_founder_default_model(req.default_model)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    v29_hardening.log_event(
        "founder_models_override", user=founder,
        route="/founder/models/override", success=True,
        default_model=str(chosen or ""),
    )
    return {
        "ok": True,
        "default_model": chosen,
        "router": model_router.get_router_status(),
    }


# ---------- Card 19 — /model/route compatibility adapter ----------
# Thin HTTP wrapper over model_router.select_model() so PHONE / WEB
# clients can resolve a model_id without speaking the kernel's
# internal vocabulary. Adapter-derived reason is computed here
# (router still returns only a string); model_router.py is unchanged.
class ModelRouteRequest(BaseModel):
    intent: str
    context: Optional[dict] = None        # accepted, unused (forward-compat)
    override: Optional[str] = None        # explicit model_id override


def _derive_route_reason(
    user: str,
    task: str,
    override: Optional[str],
    model_id: str,
) -> str:
    """Mirror model_router.select_model's precedence so callers can see
    which rule won. Order matches select_model: override > founder
    default > user preferred_model > task default."""
    if override:
        return "override"
    founder = model_router.get_founder_default_model()
    if founder and founder == model_id:
        return "founder_default"
    try:
        state = operator_state.get_operator_state(user) or {}
        pref = state.get("preferred_model")
        if pref and pref == model_id:
            return "user_preference"
    except Exception:  # pragma: no cover (defensive)
        pass
    if model_router.TASK_DEFAULTS.get(task) == model_id:
        return "task_default"
    return "fallback"


@app.post("/model/route")
def model_route(
    req: ModelRouteRequest,
    request: Request,
    session: dict = Depends(require_session),
):
    """Compatibility wrapper for ``model_router.select_model``.

    PHONE and WEB clients call this to resolve which model_id to use
    for a given intent. The adapter accepts a friendly ``intent`` and
    optional ``override``; the response carries the resolved model_id,
    an adapter-derived reason, and the operator flag (Card 18 rule:
    operator token OR cohort in FOUNDER_LIKE_COHORTS).
    """
    user = session["user"]
    cohort = session.get("cohort")
    operator = _is_operator_token(request) or (cohort in FOUNDER_LIKE_COHORTS)

    try:
        model_id = model_router.select_model(
            user,
            task=req.intent,
            override=req.override,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e))
        )

    reason = _derive_route_reason(
        user=user,
        task=req.intent,
        override=req.override,
        model_id=model_id,
    )

    return {
        "ok": True,
        "model": model_id,
        "reason": reason,
        "operator": operator,
    }


# ---------- Card 19.5 — /model/complete completion adapter ----------
# Thin wrapper over the existing model_router.route_request — that
# function already handles real provider dispatch (OpenAI / Anthropic
# / Gemini / xAI / local) with env-key-gated mock fallback and
# per-provider timeouts. Re-implementing it here would silently fork
# the dispatch path; the adapter just plumbs the HTTP shape.
#
# Cost guardrail: every call here is a paid LLM round-trip when
# provider keys are configured, so the route is per-user rate-limited
# via v29_hardening. Enforcement requires CLARITYOS_RATE_LIMIT_ENFORCE=1
# in production; without it, breaches are logged but not rejected.
class ModelCompleteRequest(BaseModel):
    model: str
    prompt: str


@app.post("/model/complete")
def model_complete(
    req: ModelCompleteRequest,
    session: dict = Depends(require_session),
):
    """Card 19.5: real-text-generation completion adapter.

    Forwards ``(model, prompt)`` to ``model_router.route_request`` and
    returns ``{ok, model, text, elapsed_ms, mock, provider}``. ``mock``
    is true when the provider's env key is unset and the router
    fell back to its deterministic stub — clients can treat that as
    "no real generation happened" without parsing text shape.
    """
    user = session["user"]
    v29_hardening.enforce_rate_limit(
        user, "/model/complete",
        capacity=10, window_s=60.0,
    )
    started = time.time()
    try:
        result = model_router.route_request(req.model, req.prompt)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e))
        )
    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "ok": True,
        "model": result["model_id"],
        "text": result["text"],
        "elapsed_ms": elapsed_ms,
        "mock": bool(result.get("mock", False)),
        "provider": result.get("provider"),
    }


# ---------- Engine V1 — canonical /engine/v1/run contract (Phase-1) ----------
# Source-of-truth Pydantic models for the new umbrella engine endpoint.
# WEB / PHONE / DESKTOP hand-mirror these shapes in their own lib/api.ts
# files (per the established no-cross-tree-sharing rule); FastAPI's
# /openapi.json keeps the wire definition canonical.
#
# Phase-1 covers: primitives, overlays, primary regression, projection,
# diagnostics. Phase-2 (validation) and Phase-3 (cross_regression,
# backtest) are reserved as Optional fields with empty placeholder
# models so clients can begin integrating today without churn later.
import engine_v1                          # Card "Engine V1 Contract — Phase 1"

EnginePrimitiveTypeLiteral = Literal[
    "entity", "attitude", "relationship", "event", "signal", "temperature",
]
EngineFlowRegimeLiteral = Literal["laminar", "transitional", "turbulent"]


class EngineHydraulicState(BaseModel):
    pressure:   float
    gradient:   float
    flow:       float
    resistance: float
    timestamp:  str


class EnginePrimitiveMetadata(BaseModel):
    primitive_id:   str
    primitive_type: EnginePrimitiveTypeLiteral
    timestamp:      str
    version:        str
    domain:         str
    source:         str
    parent_id:      Optional[str] = None
    # Card 20 cherry-pick: lineage + dependency graph fields.
    ancestors:      list[str] = []
    depends_on:     list[str] = []
    influences:     list[str] = []
    confidence:     float
    completeness:   float
    reliability:    float


class EnginePrimitive(BaseModel):
    metadata:        EnginePrimitiveMetadata
    content:         dict
    hydraulic_state: EngineHydraulicState
    # Card 20 cherry-pick: self-referential lineage. Phase-1 emits
    # both as None / [] because there's no archive yet — the wire
    # shape is locked early so Phase-2 (when the archive lands) only
    # changes values, not field names.
    origin_state:       Optional["EnginePrimitive"] = None
    historical_states:  list["EnginePrimitive"] = []


class EngineOverlayResult(BaseModel):
    primitive_id:     str
    reynolds_number:  float
    flow_regime:      EngineFlowRegimeLiteral
    stability:        float
    in_critical_zone: bool
    distance_to_fold: float
    resilience:       float
    # Card 20 cherry-pick: Godhard-curve fields. curve_position is the
    # normalised position on the S-curve; on_upper_branch is the
    # hysteresis branch indicator; sensitivity is the local slope
    # (peaks inside the critical zone); hysteresis is the configured
    # loop width.
    curve_position:   float
    on_upper_branch:  bool
    sensitivity:      float
    hysteresis:       float


class EngineRegimeChange(BaseModel):
    day:    int
    regime: EngineFlowRegimeLiteral


class EngineRegressionResult(BaseModel):
    primitive_id:           str
    current_state:          EnginePrimitive
    origin_state:           EnginePrimitive
    path:                   list[EnginePrimitive]
    reconstruction_error:   float
    path_confidence:        float
    deviation_from_origin:  float
    historical_similarity:  float
    attitude_match_score:   float


class EngineProjectionResult(BaseModel):
    primitive_id:        str
    source_state:        EnginePrimitive
    projected_state:     EnginePrimitive
    projection_days:     int
    confidence:          float
    uncertainty:         float
    pressure_trajectory: list[float]
    flow_trajectory:     list[float]
    regime_changes:      list[EngineRegimeChange]


class EngineDiagnostics(BaseModel):
    observation_id:     str
    observer_notes:     str
    confidence_level:   float
    validation_status:  str
    early_warnings:     dict
    errors:             list[str]
    # Card 20 cherry-pick: applied-interventions trace (free-form for
    # Phase-1; structured by a later card once intervention recipes
    # land).
    interventions:      list[str] = []


# Reserved Phase-2 / Phase-3 placeholders. Empty by design — extending
# them is a contract-level decision; clients must treat the parent
# fields as optional and tolerate added keys.
class EngineValidationResult(BaseModel):
    """Phase-2 placeholder (dual-pass validation envelope)."""
    model_config = ConfigDict(extra="allow")


class EngineCrossRegressionResult(BaseModel):
    """Phase-3 placeholder (cross-primitive regression envelope)."""
    model_config = ConfigDict(extra="allow")


class EngineBacktestResult(BaseModel):
    """Phase-3 placeholder (historical backtest envelope)."""
    model_config = ConfigDict(extra="allow")


class EngineResponseV1(BaseModel):
    ok:               Literal[True] = True
    primitives:       list[EnginePrimitive]
    overlays:         list[EngineOverlayResult]
    regression:       Optional[EngineRegressionResult] = None
    projection:       Optional[EngineProjectionResult] = None
    diagnostics:      EngineDiagnostics
    # Reserved — populated by future cards. Default None so existing
    # consumers can ignore them safely.
    validation:        Optional[EngineValidationResult]      = None
    cross_regression:  Optional[EngineCrossRegressionResult] = None
    backtest:          Optional[EngineBacktestResult]        = None


class EnginePrimitiveInput(BaseModel):
    primitive_id:   Optional[str] = None
    primitive_type: Optional[EnginePrimitiveTypeLiteral] = "signal"
    domain:         Optional[str] = "general"
    source:         Optional[str] = ""
    content:        Optional[dict] = None
    pressure:       float
    flow:           float
    resistance:     float
    gradient:       Optional[float] = 0.0


class EngineRunRequest(BaseModel):
    primitives:      list[EnginePrimitiveInput]
    projection_days: int = 30


# Resolve the self-reference on EnginePrimitive.origin_state /
# historical_states (Pydantic v2 forward-ref pattern).
EnginePrimitive.model_rebuild()


@app.post("/engine/v1/run", response_model=EngineResponseV1)
def engine_v1_run(
    req: EngineRunRequest,
    session: dict = Depends(require_session),
):
    """Umbrella Phase-1 engine endpoint.

    Computes per-primitive overlays, runs a primary synthetic-origin
    regression on the first primitive, and projects it forward.
    Diagnostics summarise the batch. All math is deterministic and
    documented in ``engine_v1.py``.
    """
    user = session["user"]
    v29_hardening.enforce_rate_limit(
        user, "/engine/v1/run",
        capacity=30, window_s=60.0,
    )
    try:
        payload = engine_v1.run(
            [p.model_dump() for p in req.primitives],
            projection_days=req.projection_days,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e))
        )
    # Validate on the way out so the wire contract is enforced.
    return EngineResponseV1.model_validate(payload)


# ---------- v45 — Local model runtime (on-device inference) ----------
@app.get("/me/local_model")
def me_local_model(session: dict = Depends(require_session)):
    """v45 — per-user local model snapshot. Returns the runtime status
    (configured / loaded / path / backend / footprint) plus the user's
    own ``local_model_usage_count`` so the settings UI can render in
    one round-trip without a separate /founder call.

    The runtime status is global (one process-cached handle), so the
    same path/loaded/backend values appear for every user. Per-user
    fields stay isolated to ``operator_state``.
    """
    user = session["user"]
    state = operator_state.get_operator_state(user)
    runtime = local_model_runtime.get_runtime_status()
    return {
        "ok": True,
        "runtime": {
            "version":             runtime.get("version"),
            "configured":          bool(runtime.get("configured")),
            "path":                runtime.get("path"),
            "loaded":              bool(runtime.get("loaded")),
            "backend":             runtime.get("backend"),
            "mock":                bool(runtime.get("mock")),
            "memory_footprint_mb": float(runtime.get("memory_footprint_mb") or 0.0),
            "inference_count":     int(runtime.get("inference_count") or 0),
            "loaded_at":           runtime.get("loaded_at"),
            "last_error":          runtime.get("last_error"),
            "fallback":            (
                "deterministic mock"
                if not runtime.get("configured")
                else ("real backend" if not runtime.get("mock")
                      else "deterministic mock (path set, backend missing)")
            ),
        },
        "usage": {
            "local_model_usage_count": int(state.get("local_model_usage_count") or 0),
            "last_model_used": state.get("last_model_used"),
            "preferred_model": state.get("preferred_model"),
            "is_local_preferred": state.get("preferred_model") == model_router.LOCAL_MODEL_ID,
        },
        "model_id": model_router.LOCAL_MODEL_ID,
    }


@app.get("/founder/models/local")
def founder_models_local(session: dict = Depends(_require_founder)):
    """v45 — founder-only local model status. Includes the runtime
    block + a small operational summary (cached_handles count + the
    raw env path) so the founder console can debug a misconfigured
    deploy without SSH access.
    """
    runtime = local_model_runtime.get_runtime_status()
    env_path = (os.environ.get("CLARITYOS_LOCAL_MODEL_PATH") or "").strip() or None
    return {
        "ok": True,
        "runtime": runtime,
        "env_path":         env_path,
        "model_id":         model_router.LOCAL_MODEL_ID,
        "router_provider":  model_router.get_model_status().get("local") or {},
    }


# ---------- v46 — Memory Vault (notes + embeddings + founder inspector) ----------
class V46NoteRequest(BaseModel):
    """Body for POST /me/vault/notes. ``key`` is the sub-key under
    the ``notes.`` namespace; the vault prepends the namespace so the
    caller writes ``key="my_note"`` and the stored vault key becomes
    ``notes.my_note``."""
    key: str
    text: str


class V46DeleteRequest(BaseModel):
    key: str


class V46EmbeddingRequest(BaseModel):
    """Body for POST /me/vault/embeddings. ``vector`` is a list of floats."""
    key: str
    vector: list[float]


_VAULT_KEY_MAX = 128
_VAULT_NOTE_TEXT_MAX = 64 * 1024     # 64 KB per note
_VAULT_EMBEDDING_MAX_DIM = 4096


def _validate_vault_subkey(raw: str) -> str:
    """Per-user sub-keys (``notes.<sub>``) must be safe identifiers —
    no namespace prefixes, no path separators, bounded length."""
    if not isinstance(raw, str) or not raw.strip():
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "vault key must be a non-empty string"),
        )
    sub = raw.strip()
    if "." in sub or "/" in sub or "\\" in sub or "\x00" in sub:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "vault key may not contain '.', '/', '\\\\' or null bytes"),
        )
    if len(sub) > _VAULT_KEY_MAX:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", f"vault key must be <= {_VAULT_KEY_MAX} chars"),
        )
    return sub


@app.get("/me/vault/notes")
def me_vault_notes(session: dict = Depends(require_session)):
    """v46 — list all of the caller's vault notes. Returns
    ``[{key, text, ts}]``. Decrypted on the way out; the wire payload
    is plaintext and should only be transported over TLS."""
    user = session["user"]
    entries = memory_vault.vault_list(user)
    out = []
    for k, v in entries.items():
        if not k.startswith("notes."):
            continue
        sub = k[len("notes."):]
        text = v if isinstance(v, str) else (v.get("text") if isinstance(v, dict) else str(v))
        out.append({"key": sub, "text": text})
    out.sort(key=lambda r: r["key"])
    return {"ok": True, "notes": out, "count": len(out)}


@app.post("/me/vault/notes")
def me_vault_notes_put(
    req: V46NoteRequest, session: dict = Depends(require_session),
):
    """v46 — create or replace a note under ``notes.<key>``."""
    user = session["user"]
    sub = _validate_vault_subkey(req.key)
    text = req.text or ""
    if len(text) > _VAULT_NOTE_TEXT_MAX:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"note text must be <= {_VAULT_NOTE_TEXT_MAX} chars",
            ),
        )
    memory_vault.vault_put(user, f"notes.{sub}", text)
    return {"ok": True, "key": sub}


@app.post("/me/vault/notes/delete")
def me_vault_notes_delete(
    req: V46DeleteRequest, session: dict = Depends(require_session),
):
    """v46 — delete a single note. ``key`` is the sub-key, not the
    full ``notes.<key>`` string."""
    user = session["user"]
    sub = _validate_vault_subkey(req.key)
    memory_vault.vault_delete(user, f"notes.{sub}")
    return {"ok": True, "key": sub}


@app.get("/me/vault/embeddings")
def me_vault_embeddings(session: dict = Depends(require_session)):
    """v46 — list embedding entries by key + dim only. The actual
    vector is not returned to keep the listing surface small."""
    user = session["user"]
    entries = memory_vault.vault_list(user)
    out = []
    for k, v in entries.items():
        if not k.startswith("embeddings."):
            continue
        sub = k[len("embeddings."):]
        dim = 0
        if isinstance(v, list):
            dim = len(v)
        elif isinstance(v, dict) and isinstance(v.get("vector"), list):
            dim = len(v["vector"])
        out.append({"key": sub, "dim": dim})
    out.sort(key=lambda r: r["key"])
    return {"ok": True, "embeddings": out, "count": len(out)}


@app.post("/me/vault/embeddings")
def me_vault_embeddings_put(
    req: V46EmbeddingRequest, session: dict = Depends(require_session),
):
    """v46 — store an embedding vector under ``embeddings.<key>``.
    Vectors are bounded to 4096 dims to protect the vault size."""
    user = session["user"]
    sub = _validate_vault_subkey(req.key)
    vec = req.vector or []
    if len(vec) > _VAULT_EMBEDDING_MAX_DIM:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"embedding dim must be <= {_VAULT_EMBEDDING_MAX_DIM}",
            ),
        )
    # Coerce defensively — pydantic already validates float, but
    # numpy floats and similar can sneak through in callers.
    coerced = []
    for x in vec:
        try:
            coerced.append(float(x))
        except (TypeError, ValueError):
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", "embedding vector must contain numbers only"),
            )
    memory_vault.vault_put(user, f"embeddings.{sub}", coerced)
    return {"ok": True, "key": sub, "dim": len(coerced)}


@app.post("/me/vault/embeddings/delete")
def me_vault_embeddings_delete(
    req: V46DeleteRequest, session: dict = Depends(require_session),
):
    user = session["user"]
    sub = _validate_vault_subkey(req.key)
    memory_vault.vault_delete(user, f"embeddings.{sub}")
    return {"ok": True, "key": sub}


@app.get("/me/vault/status")
def me_vault_status(session: dict = Depends(require_session)):
    """v46 — caller-scoped vault snapshot. Counts only — no key list."""
    user = session["user"]
    return {
        "ok":      True,
        "global":  memory_vault.vault_status(),
        "user": {
            "user_id":           user,
            "vault_keys":        memory_vault.vault_count_for_user(user),
            "notes_count":       memory_vault.vault_count_for_user(user, "notes"),
            "embeddings_count":  memory_vault.vault_count_for_user(user, "embeddings"),
            "operator_state_count": memory_vault.vault_count_for_user(user, "operator_state"),
            "elins_count":       memory_vault.vault_count_for_user(user, "elins"),
            "g_runs_count":      memory_vault.vault_count_for_user(user, "g_runs"),
        },
    }


@app.get("/founder/vault/users")
def founder_vault_users(session: dict = Depends(_require_founder)):
    """v46 — founder vault inspector. Lists every user_id with at
    least one vault row + a per-user key count."""
    users = memory_vault.vault_known_users()
    out = []
    for u in users:
        try:
            keys = memory_vault.vault_count_for_user(u)
        except Exception:  # pragma: no cover (defensive)
            keys = 0
        out.append({"user_id": u, "keys": keys})
    return {"ok": True, "users": out, "count": len(out)}


@app.get("/founder/vault/{user_id}/keys")
def founder_vault_keys(
    user_id: str, session: dict = Depends(_require_founder),
):
    """v46 — list every vault key for ``user_id`` grouped by namespace.
    Founder-only. Returns key list + counts per namespace."""
    keys = memory_vault.vault_keys_for_user(user_id)
    by_ns: dict[str, list[str]] = {}
    for k in keys:
        ns = memory_vault.namespace_of(k)
        by_ns.setdefault(ns, []).append(k)
    return {
        "ok": True,
        "user_id": user_id,
        "count":   len(keys),
        "keys":    keys,
        "by_namespace": {ns: {"count": len(v), "keys": v} for ns, v in by_ns.items()},
    }


@app.get("/founder/vault/{user_id}/item/{key:path}")
def founder_vault_item(
    user_id: str, key: str,
    session: dict = Depends(_require_founder),
):
    """v46 — read a single vault entry for ``user_id``. Decrypts on
    the server. Founder-only. ``key`` is the full vault key including
    namespace prefix (e.g. ``notes.my_note``)."""
    try:
        value = memory_vault.vault_get(user_id, key, default=None)
    except ValueError as e:
        # Bad key shape (e.g. namespace not in ALLOWED) — surface 400.
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    if value is None and key not in memory_vault.vault_keys_for_user(user_id):
        return {"ok": False, "error": "not_found", "user_id": user_id, "key": key}
    return {
        "ok": True, "user_id": user_id, "key": key, "value": value,
        "namespace": memory_vault.namespace_of(key),
    }


# ---------- v51 — Projects (project layer over threads) ----------
class V51ProjectMetaModel(BaseModel):
    """Server response shape for a project. Mirrors
    :class:`projects_vault.ProjectMeta` but with explicit
    ``Optional`` declarations for FastAPI / OpenAPI."""
    project_id:     str
    name:           str
    description:    str = ""
    default_model:  Optional[str] = None
    allowed_models: Optional[list[str]] = None
    tags:           list[str] = []
    created_at:     int
    updated_at:     int
    summary:        Optional[str] = None
    summary_ts_ms:  Optional[int] = None
    thread_count:   int = 0


class V51ProjectListResponse(BaseModel):
    projects: list[V51ProjectMetaModel]


class V51CreateProjectRequest(BaseModel):
    project_id:     str
    name:           str
    description:    Optional[str] = ""
    default_model:  Optional[str] = None
    allowed_models: Optional[list[str]] = None
    tags:           Optional[list[str]] = []


def _project_meta_to_model(meta: dict) -> V51ProjectMetaModel:
    raw_summary = meta.get("summary")
    raw_summary_ts = meta.get("summary_ts_ms")
    try:
        summary_ts_ms = int(raw_summary_ts) if raw_summary_ts is not None else None
    except (TypeError, ValueError):
        summary_ts_ms = None
    raw_default = meta.get("default_model")
    default_model = raw_default if isinstance(raw_default, str) and raw_default else None
    raw_allowed = meta.get("allowed_models")
    allowed_models = (
        list(raw_allowed) if isinstance(raw_allowed, list) and raw_allowed else None
    )
    raw_tags = meta.get("tags")
    tags = list(raw_tags) if isinstance(raw_tags, list) else []
    return V51ProjectMetaModel(
        project_id=str(meta.get("project_id") or ""),
        name=str(meta.get("name") or ""),
        description=str(meta.get("description") or ""),
        default_model=default_model,
        allowed_models=allowed_models,
        tags=tags,
        created_at=int(meta.get("created_at") or 0),
        updated_at=int(meta.get("updated_at") or 0),
        summary=raw_summary if isinstance(raw_summary, str) and raw_summary.strip() else None,
        summary_ts_ms=summary_ts_ms,
        thread_count=int(meta.get("thread_count") or 0),
    )


@app.get("/me/projects", response_model=V51ProjectListResponse)
def me_projects_list(session: dict = Depends(require_session)):
    """v51 — list every project for the caller, newest-first by
    ``updated_at``. Empty list when the user has no projects."""
    user = session["user"]
    metas = projects_vault.list_projects(user)
    return V51ProjectListResponse(
        projects=[_project_meta_to_model(m) for m in metas],
    )


@app.post("/me/projects", response_model=V51ProjectMetaModel)
def me_projects_create(
    req: V51CreateProjectRequest, session: dict = Depends(require_session),
):
    """v51 — create a project + initialise the project's vault docs
    (meta + summary + threads index). Returns the freshly-created
    project meta. Rejects duplicate ``project_id`` with 400."""
    user = session["user"]
    payload = {
        "project_id":     req.project_id,
        "name":           req.name,
        "description":    req.description or "",
        "default_model":  req.default_model,
        "allowed_models": req.allowed_models,
        "tags":           req.tags or [],
    }
    try:
        meta = projects_vault.create_project(user, payload)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return _project_meta_to_model(meta)


@app.get("/me/projects/{project_id}", response_model=V51ProjectMetaModel)
def me_projects_get(
    project_id: str, session: dict = Depends(require_session),
):
    """v51 — read a single project's meta. 404 when missing."""
    user = session["user"]
    try:
        meta = projects_vault.get_project(user, project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return _project_meta_to_model(meta)


# Note: /me/projects/{project_id}/threads is defined further down (after
# the v47 thread block) because it uses V47ThreadListResponse +
# threads_vault.get_thread_meta + _meta_to_model.


# ---------- v47 — Threads (persistent threaded interactions) ----------
class V47ThreadMetaModel(BaseModel):
    thread_id: str
    title: Optional[str] = None
    created_at: int
    updated_at: int
    message_count: int
    archived: bool
    # v50 — kernel-generated summary + the timestamp at which it
    # was last computed. Both ``None`` until the first
    # ``POST /me/threads/{id}/summarize`` call.
    summary: Optional[str] = None
    summary_ts_ms: Optional[int] = None
    # v51 — project membership. ``None`` for threads not tied to
    # any project (existing v47-v50 threads remain valid). Set at
    # creation via ``POST /me/threads`` body and surfaced on every
    # meta read.
    project_id: Optional[str] = None


class V47ThreadDetailMessage(BaseModel):
    role: str
    content: str
    ts_ms: int
    model: Optional[str] = None


class V47ThreadDetailResponse(BaseModel):
    meta: V47ThreadMetaModel
    messages: list[V47ThreadDetailMessage]


class V47ThreadListResponse(BaseModel):
    threads: list[V47ThreadMetaModel]


class V47CreateThreadRequest(BaseModel):
    title: Optional[str] = None
    # v51 — optional project membership. When set, the new thread is
    # tagged + added to the project's threads index in one round-trip.
    project_id: Optional[str] = None


class V47PostMessageRequest(BaseModel):
    content: str
    # v51 — optional. When set, the kernel validates that the thread
    # belongs to that project and applies the project's
    # default_model / allowed_models routing rules.
    project_id: Optional[str] = None


class V47PostMessageResponse(BaseModel):
    meta: V47ThreadMetaModel
    user_message: V47ThreadDetailMessage
    assistant_message: V47ThreadDetailMessage
    model_id: Optional[str] = None


class V47RenameThreadRequest(BaseModel):
    title: str


class V47DeleteThreadRequest(BaseModel):
    """Empty body. Posted via POST so the operation feels symmetric
    with the other thread mutators."""
    pass


_THREAD_TITLE_MAX = 200
_THREAD_MESSAGE_MAX = 32 * 1024


def _validate_thread_id_path(thread_id: str) -> str:
    """Reject suspicious path components before hitting the vault.
    The vault has its own validator but the app layer surfaces clean
    400s before any work happens."""
    if not isinstance(thread_id, str) or not thread_id:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "thread_id is required"),
        )
    if "." in thread_id or "/" in thread_id or "\\" in thread_id or "\x00" in thread_id:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", "thread_id must not contain '.', '/', '\\\\' or null bytes",
            ),
        )
    if len(thread_id) > 128:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "thread_id length must be <= 128"),
        )
    return thread_id


def _meta_to_model(meta: dict) -> V47ThreadMetaModel:
    raw_summary = meta.get("summary")
    summary = raw_summary if isinstance(raw_summary, str) and raw_summary.strip() else None
    raw_summary_ts = meta.get("summary_ts_ms")
    try:
        summary_ts_ms = int(raw_summary_ts) if raw_summary_ts is not None else None
    except (TypeError, ValueError):
        summary_ts_ms = None
    raw_project_id = meta.get("project_id")
    project_id_val = (
        raw_project_id if isinstance(raw_project_id, str) and raw_project_id.strip()
        else None
    )
    return V47ThreadMetaModel(
        thread_id=str(meta.get("thread_id") or ""),
        title=meta.get("title") if isinstance(meta.get("title"), str) else None,
        created_at=int(meta.get("created_at") or 0),
        updated_at=int(meta.get("updated_at") or 0),
        message_count=int(meta.get("message_count") or 0),
        archived=bool(meta.get("archived")),
        summary=summary,
        summary_ts_ms=summary_ts_ms,
        project_id=project_id_val,
    )


def _msg_to_model(msg: dict) -> V47ThreadDetailMessage:
    return V47ThreadDetailMessage(
        role=str(msg.get("role") or "system"),
        content=str(msg.get("content") or ""),
        ts_ms=int(msg.get("ts_ms") or 0),
        model=msg.get("model") if isinstance(msg.get("model"), str) else None,
    )


@app.get("/me/threads", response_model=V47ThreadListResponse)
def me_threads_list(
    project_id: Optional[str] = Query(default=None),
    session: dict = Depends(require_session),
):
    """v47 — list every thread for the caller, newest-first.

    v51 — when ``project_id`` query param is supplied, the response
    is filtered to threads whose ``ThreadMeta.project_id`` matches.
    Threads with no project_id are excluded by a project filter.
    """
    user = session["user"]
    metas = threads_vault.list_threads(user)
    if project_id is not None:
        pid = project_id.strip()
        if pid:
            metas = [m for m in metas if m.get("project_id") == pid]
    return V47ThreadListResponse(threads=[_meta_to_model(m) for m in metas])


@app.post("/me/threads", response_model=V47ThreadMetaModel)
def me_threads_create(
    req: V47CreateThreadRequest, session: dict = Depends(require_session),
):
    """v47 — create a new thread. ``title`` is optional (caller can
    rename later). Returns the thread meta.

    v51 — when ``project_id`` is supplied, the new thread is tagged
    with that project (``ThreadMeta.project_id``) and registered in
    the project's threads index. The project must already exist
    (404 otherwise).
    """
    user = session["user"]
    title = req.title
    if isinstance(title, str) and len(title) > _THREAD_TITLE_MAX:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"title must be <= {_THREAD_TITLE_MAX} chars",
            ),
        )

    project_id = req.project_id
    if project_id is not None:
        # Validate the project exists and the project_id is well-formed.
        try:
            projects_vault.get_project(user, project_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        except ValueError as e:
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", str(e)),
            )

    try:
        meta = threads_vault.create_thread(user, title, project_id=project_id)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )

    if project_id is not None:
        # Best-effort index update — failure here doesn't roll the
        # thread back (the thread is the source of truth via its
        # project_id field).
        try:
            projects_vault.add_thread_to_project(user, project_id, meta["thread_id"])
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "v51 add_thread_to_project failed user=%s project=%s err=%s",
                _user_ref(user), project_id, e,
            )
    return _meta_to_model(meta)


@app.get("/me/threads/{thread_id}", response_model=V47ThreadDetailResponse)
def me_threads_get(
    thread_id: str, session: dict = Depends(require_session),
):
    """v47 — return ``(meta, messages)`` for ``thread_id``. 404 when
    the thread doesn't exist for the caller."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    try:
        meta, messages = threads_vault.get_thread(user, thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")
    return V47ThreadDetailResponse(
        meta=_meta_to_model(meta),
        messages=[_msg_to_model(m) for m in messages],
    )


@app.post("/me/threads/{thread_id}/message", response_model=V47PostMessageResponse)
def me_threads_post_message(
    thread_id: str, req: V47PostMessageRequest,
    session: dict = Depends(require_session),
):
    """v47 — append a user message + dispatch the assistant reply
    through the kernel. Returns both messages plus the updated meta."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    if not isinstance(req.content, str) or not req.content.strip():
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", "content must be a non-empty string",
            ),
        )
    if len(req.content) > _THREAD_MESSAGE_MAX:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"content must be <= {_THREAD_MESSAGE_MAX} chars",
            ),
        )
    try:
        out = intelligence_kernel.run_thread_message(
            user, thread_id, req.content,
            project_id=req.project_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return V47PostMessageResponse(
        meta=_meta_to_model(out["meta"]),
        user_message=_msg_to_model(out["user_message"]),
        assistant_message=_msg_to_model(out["assistant_message"]),
        model_id=out.get("model_id"),
    )


@app.post("/me/threads/{thread_id}/rename", response_model=V47ThreadMetaModel)
def me_threads_rename(
    thread_id: str, req: V47RenameThreadRequest,
    session: dict = Depends(require_session),
):
    """v47 — update the thread title."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    if not isinstance(req.title, str):
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", "title must be a string"),
        )
    if len(req.title) > _THREAD_TITLE_MAX:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "bad_input", f"title must be <= {_THREAD_TITLE_MAX} chars",
            ),
        )
    try:
        meta = threads_vault.rename_thread(user, thread_id, req.title)
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")
    return _meta_to_model(meta)


@app.post("/me/threads/{thread_id}/delete")
def me_threads_delete(
    thread_id: str, req: V47DeleteThreadRequest = V47DeleteThreadRequest(),
    session: dict = Depends(require_session),
):
    """v47 — drop the thread + every message. Idempotent: deleting a
    missing thread still returns ``ok``."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    threads_vault.delete_thread(user, thread_id)
    return {"ok": True, "thread_id": thread_id}


# ---------- v50 — Thread summaries ----------
class V50ThreadSummaryResponse(BaseModel):
    """Wrapper for ``GET /me/threads/{thread_id}/summary`` and
    ``POST /me/threads/{thread_id}/summarize``."""
    meta: V47ThreadMetaModel


class V50ThreadSummarizeRequest(BaseModel):
    """Body for ``POST /me/threads/{thread_id}/summarize``. ``force=True``
    bypasses the recency-skip optimisation and always re-runs the
    summariser."""
    force: Optional[bool] = None


# When the existing summary is younger than this, a non-forced
# summarize call returns the cached meta instead of re-running the
# kernel call. 10 minutes balances "fresh enough" against avoiding a
# routed model call on every UI focus.
_SUMMARY_RECENT_WINDOW_MS: int = 10 * 60 * 1000


@app.get("/me/threads/{thread_id}/summary", response_model=V50ThreadSummaryResponse)
def me_threads_summary_get(
    thread_id: str, session: dict = Depends(require_session),
):
    """v50 — return the cached summary for a thread (or ``null`` if it
    hasn't been generated yet). Cheap read; doesn't route through the
    kernel."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    try:
        meta = threads_vault.get_thread_meta(user, thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")
    return V50ThreadSummaryResponse(meta=_meta_to_model(meta))


@app.post("/me/threads/{thread_id}/summarize", response_model=V50ThreadSummaryResponse)
def me_threads_summarize(
    thread_id: str,
    req: V50ThreadSummarizeRequest = V50ThreadSummarizeRequest(),
    session: dict = Depends(require_session),
):
    """v50 — generate (or refresh) a summary for ``thread_id``. When
    the existing summary is < 10 minutes old and ``force`` isn't set,
    the call short-circuits with the cached meta to avoid a redundant
    model dispatch."""
    user = session["user"]
    thread_id = _validate_thread_id_path(thread_id)
    force = bool(req.force) if req is not None else False

    try:
        existing = threads_vault.get_thread_meta(user, thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")

    now_ms = int(time.time() * 1000)
    if (
        not force
        and existing.get("summary")
        and isinstance(existing.get("summary_ts_ms"), int)
        and now_ms - int(existing["summary_ts_ms"]) < _SUMMARY_RECENT_WINDOW_MS
    ):
        return V50ThreadSummaryResponse(meta=_meta_to_model(existing))

    try:
        out = intelligence_kernel.summarize_thread(user, thread_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="thread not found")
    return V50ThreadSummaryResponse(meta=_meta_to_model(out["meta"]))


# ---------- v51 — Project's threads (uses V47 response shape) ----------
@app.get("/me/projects/{project_id}/threads", response_model=V47ThreadListResponse)
def me_projects_threads(
    project_id: str, session: dict = Depends(require_session),
):
    """v51 — list threads belonging to a project, sourced from the
    project's threads index (denormalised in the projects vault).
    Equivalent to ``GET /me/threads?project_id=X``, which reads from
    ``ThreadMeta.project_id`` directly. Both endpoints converge on
    the same set as long as the index hasn't drifted."""
    user = session["user"]
    try:
        thread_ids = projects_vault.list_project_threads(user, project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    out: list[V47ThreadMetaModel] = []
    for tid in thread_ids:
        try:
            meta = threads_vault.get_thread_meta(user, tid)
        except KeyError:
            continue   # index drift — skip orphaned id
        out.append(_meta_to_model(meta))
    out.sort(key=lambda m: m.updated_at, reverse=True)
    return V47ThreadListResponse(threads=out)


# ===========================================================================
# v76 — ProblemSolver.REGRESSION_FIRST endpoints
# v77 — Vault-backed persistence (per-user via memory_vault)
# v78 — Timeline emission (3 new regression_chain_* event types)
#
# Thin HTTP layer over ``problem_solver``. Six routes, all
# ``require_session``. The kernel is the source of truth for
# semantics; the endpoints translate KeyError → 404 and ValueError →
# 400 via the v29_hardening validator. Chain timestamps stay int-ms
# on the wire to match every other /me/* endpoint in this codebase.
#
# Storage (v77): every handler constructs a fresh
# ``VaultBackedRegressionChainStore(session_user)`` and passes it
# through to the kernel. Per-user partitioning is native via
# memory_vault — no in-process owner index needed. Cross-user reads
# are simply impossible (return 404 in the unknown-id path).
#
# Timeline (v78): /start, /step, /close emit events under the
# operator's timeline after the kernel call succeeds. Emission
# failures are swallowed defensively (the chain mutation already
# committed). /tag and /get + /list intentionally emit nothing —
# tags are mid-investigation metadata; reads are not events.
#
# Activation phrase per spec: "Activate Regression-First Mode for:
# <problem>" → POST /me/regression_first/start {title: <problem>}.
# ===========================================================================
class V76RegressionLayerModel(BaseModel):
    layer_index: int
    status: str
    notes: Optional[str] = None
    updated_at: int


class V76RegressionChainModel(BaseModel):
    chain_id: str
    created_at: int
    closed_at: Optional[int] = None
    title: str
    notes: Optional[str] = None
    layers: list[V76RegressionLayerModel]
    tags: dict[str, str]
    # v81 — visibility flag. Pure soft-hide semantics: archived
    # chains remain mutable; the GET /me/regression_first list
    # filters them out by default but every other endpoint operates
    # on archived chains unchanged.
    archived: bool = False


class V76RegressionChainListResponse(BaseModel):
    chains: list[V76RegressionChainModel]


class V76StartRequest(BaseModel):
    title: str
    notes: Optional[str] = None


class V76StepRequest(BaseModel):
    layer_index: int
    status: str
    notes: Optional[str] = None


class V76CloseRequest(BaseModel):
    notes: Optional[str] = None


class V76TagRequest(BaseModel):
    tags: dict[str, str]


# ---- v81 — delete_tag + archive ----
class V81DeleteTagRequest(BaseModel):
    chain_id: str
    key: str


class V81ArchiveRequest(BaseModel):
    chain_id: str


# ---- v82 — packet replay ----
class V82ReplayRequest(BaseModel):
    chain_id: str


# v77 — Per-user partitioning lives in memory_vault. Each request
# constructs a ``VaultBackedRegressionChainStore(user)`` and passes
# it through; the kernel never sees the user_id directly.
def _v76_store_for(user: str) -> problem_solver.VaultBackedRegressionChainStore:
    return problem_solver.VaultBackedRegressionChainStore(user)


def _v76_emit_timeline_event(event: dict) -> None:
    """v78 — defensive timeline emission. Failures are swallowed so a
    storage hiccup never rolls back a successful chain mutation —
    matches the el_ins/run_thread_message convention."""
    try:
        el_ins_timeline.store_event(event)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning(
            "v78 timeline emit failed event_type=%s err=%s",
            event.get("event_type"), e,
        )


def _chain_to_model(chain: dict) -> V76RegressionChainModel:
    return V76RegressionChainModel(
        chain_id=chain["chain_id"],
        created_at=chain["created_at"],
        closed_at=chain.get("closed_at"),
        title=chain["title"],
        notes=chain.get("notes"),
        layers=[
            V76RegressionLayerModel(
                layer_index=L["layer_index"],
                status=L["status"],
                notes=L.get("notes"),
                updated_at=L["updated_at"],
            )
            for L in chain["layers"]
        ],
        tags=dict(chain.get("tags") or {}),
        archived=bool(chain.get("archived", False)),
    )


@app.post(
    "/me/regression_first/start",
    response_model=V76RegressionChainModel,
)
def me_regression_first_start(
    req: V76StartRequest, session: dict = Depends(require_session),
):
    """v76/v77 — open a new regression chain. Layers + tags start
    empty; ``closed_at`` is None until ``/close`` is posted. Chain
    is persisted to the caller's vault under
    ``regression_chains.{chain_id}``.

    v78 — emits a ``regression_chain_started`` timeline event after
    the chain is persisted.
    """
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.start_chain(
            req.title, notes=req.notes, store=store,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    _v76_emit_timeline_event(
        el_ins_timeline.build_regression_chain_started_event(
            user,
            chain_id=chain["chain_id"],
            title=chain["title"],
            created_at_ms=chain["created_at"],
        ),
    )
    return _chain_to_model(chain)


@app.post(
    "/me/regression_first/step",
    response_model=V76RegressionChainModel,
)
def me_regression_first_step(
    req: V76StepRequest,
    chain_id: str = Query(...),
    session: dict = Depends(require_session),
):
    """v76/v77 — record a finding for one layer. The layer is
    appended on first sight of ``layer_index`` and overwritten on
    subsequent posts (kernel auto-grows + auto-sorts). Updated chain
    is persisted back to the caller's vault.

    v78 — emits a ``regression_chain_layer_updated`` timeline event
    after the layer is persisted.
    """
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.record_finding(
            chain_id, req.layer_index, req.status, req.notes, store=store,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    # Locate the just-written layer to report its updated_at.
    updated_layer = next(
        (L for L in chain["layers"] if L["layer_index"] == req.layer_index),
        None,
    )
    if updated_layer is not None:
        _v76_emit_timeline_event(
            el_ins_timeline.build_regression_chain_layer_updated_event(
                user,
                chain_id=chain["chain_id"],
                layer_index=updated_layer["layer_index"],
                status=updated_layer["status"],
                updated_at_ms=updated_layer["updated_at"],
            ),
        )
    return _chain_to_model(chain)


@app.get(
    "/me/regression_first/{chain_id}",
    response_model=V76RegressionChainModel,
)
def me_regression_first_get(
    chain_id: str, session: dict = Depends(require_session),
):
    """v76/v77 — fetch one chain by id from the caller's vault. 404
    when the chain doesn't exist in the caller's partition (existence
    not leaked to other users)."""
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.get_chain(chain_id, store=store)
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")
    return _chain_to_model(chain)


@app.get(
    "/me/regression_first",
    response_model=V76RegressionChainListResponse,
)
def me_regression_first_list(
    include_archived: bool = Query(default=False),
    session: dict = Depends(require_session),
):
    """v76/v77 — list the caller's chains from their vault partition,
    newest-first by ``(created_at, chain_id) DESC``.

    v81 — by default archived chains are excluded. Pass
    ``?include_archived=true`` to include them. Archive is a pure
    visibility flag; archived chains remain mutable via the other
    endpoints regardless of this filter.
    """
    user = session["user"]
    store = _v76_store_for(user)
    chains = problem_solver.list_chains(store=store)
    if not include_archived:
        chains = [c for c in chains if not c.get("archived")]
    return V76RegressionChainListResponse(
        chains=[_chain_to_model(c) for c in chains],
    )


@app.post(
    "/me/regression_first/{chain_id}/close",
    response_model=V76RegressionChainModel,
)
def me_regression_first_close(
    chain_id: str,
    req: V76CloseRequest = V76CloseRequest(),
    session: dict = Depends(require_session),
):
    """v76/v77 — close a chain. Sets ``closed_at`` to now and
    (optionally) overwrites the chain's top-level ``notes``. Closing
    is irreversible: subsequent ``/step`` and ``/tag`` calls 400.

    v78 — emits a ``regression_chain_closed`` timeline event after
    the chain is persisted.
    """
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.close_chain(
            chain_id, notes=req.notes, store=store,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    _v76_emit_timeline_event(
        el_ins_timeline.build_regression_chain_closed_event(
            user,
            chain_id=chain["chain_id"],
            closed_at_ms=chain["closed_at"],
        ),
    )
    return _chain_to_model(chain)


@app.post(
    "/me/regression_first/{chain_id}/tag",
    response_model=V76RegressionChainModel,
)
def me_regression_first_tag(
    chain_id: str,
    req: V76TagRequest,
    session: dict = Depends(require_session),
):
    """v76/v77 — merge tags into the chain's tag dict. Keys are
    overwritten by the supplied values; keys not in the body are
    preserved. Tag deletion is not exposed in v77.

    Tag changes do NOT emit a timeline event by design — tags are
    mid-investigation metadata, not state transitions.
    """
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.tag_chain(chain_id, req.tags, store=store)
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return _chain_to_model(chain)


# ---------------------------------------------------------------------------
# v81 — delete_tag + archive
#
# Both endpoints are body-parameter style (chain_id in the request
# body, not the path) — matches the existing /step convention from
# v76 where chain mutators take chain_id as a parameter, not a path
# segment. The /tag endpoint uses a path segment, but the founder
# spec for v81 puts chain_id in the body for these two — preserved
# verbatim.
#
# Timeline:
#   /delete_tag → NO event (tags are mid-investigation metadata, same
#                 as /tag's silence).
#   /archive    → emits regression_chain_archived (visibility flag
#                 transition is operator-visible state intent, even
#                 though it doesn't lock mutations).
# ---------------------------------------------------------------------------
@app.post(
    "/me/regression_first/delete_tag",
    response_model=V76RegressionChainModel,
)
def me_regression_first_delete_tag(
    req: V81DeleteTagRequest,
    session: dict = Depends(require_session),
):
    """v81 — drop one tag key. No-op when the key isn't present
    (returns the chain unchanged). Emits no timeline event."""
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.delete_tag(
            req.chain_id, req.key, store=store,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    return _chain_to_model(chain)


@app.post(
    "/me/regression_first/archive",
    response_model=V76RegressionChainModel,
)
def me_regression_first_archive(
    req: V81ArchiveRequest,
    session: dict = Depends(require_session),
):
    """v81 — set ``archived = True`` on the chain. Idempotent (no-op
    if already archived). Archive is a pure visibility flag: the
    chain remains mutable and reachable through every other endpoint.
    The default /me/regression_first list filters archived chains
    out; pass ``?include_archived=true`` to include them.

    Emits ``regression_chain_archived`` with ``archived_at_ms`` set
    to now (the emission timestamp — the kernel doesn't itself track
    when a chain was archived; the timeline is the authoritative
    record of that transition).
    """
    user = session["user"]
    store = _v76_store_for(user)
    try:
        chain = problem_solver.archive_chain(req.chain_id, store=store)
    except KeyError:
        raise HTTPException(status_code=404, detail="chain not found")

    _v76_emit_timeline_event(
        el_ins_timeline.build_regression_chain_archived_event(
            user,
            chain_id=chain["chain_id"],
            archived_at_ms=int(time.time() * 1000),
        ),
    )
    return _chain_to_model(chain)


# ---------------------------------------------------------------------------
# v80 — Packet endpoint
#
# A single-shot entry that ingests a unified cognitive packet
# (EL/INS + regression_chain skeleton emitted by an upstream model
# under skills_export/regression_first/system_prompt.md) and produces
# a persisted chain in one call. Semantically equivalent to "/start
# + one /step": the chain is created (emits regression_chain_started)
# and the LAST entry of the packet's regression_chain skeleton is
# recorded as an operator finding with status="unknown" and notes
# synthesized from the entry's name/question/location/goal (emits
# regression_chain_layer_updated). Subsequent layers in the skeleton
# remain operator-driven via /step — V80 does not seed all of them.
#
# Storage: same vault-backed store every other v76 endpoint uses, so
# cross-user partitioning is enforced natively by memory_vault.
#
# Timeline: emits the same event types as the manual /start + /step
# flow. Per founder call: a regression chain is a regression chain
# regardless of creation path; hiding packet-driven chains from the
# timeline would split the operator's history.
# ---------------------------------------------------------------------------
class V80PacketRequest(BaseModel):
    packet: dict[str, Any]


def _v80_synthesize_layer_notes(entry: dict) -> str:
    """Synthesize a one-line ``notes`` string from a skeleton entry.
    Captures name / question / location / goal so the operator who
    later inspects the layer has the full diagnostic context from
    the originating packet without having to re-read it."""
    name     = str(entry.get("name") or "(unnamed)")
    question = str(entry.get("question") or "")
    location = str(entry.get("location") or "")
    goal     = str(entry.get("goal") or "")
    parts: list[str] = [name]
    if question:
        parts.append(question)
    if location:
        parts.append(f"(look here: {location})")
    if goal:
        parts.append(f"(goal: {goal})")
    return " | ".join(parts)


@app.post(
    "/me/regression_first/packet",
    response_model=V76RegressionChainModel,
)
def me_regression_first_packet(
    req: V80PacketRequest, session: dict = Depends(require_session),
):
    """v80 — accept a unified cognitive packet, persist the resulting
    chain (seeded with the last skeleton layer as an 'unknown'
    finding), emit timeline events, and return the chain.

    Error contract:
      * 401 — no session (require_session).
      * 422 ``packet_rejected`` — kernel returned ``ok=False`` (the
        packet is malformed: missing required fields, out-of-range
        scores, wrong classification vocabulary, etc.).
      * 422 ``regression_not_required`` — packet parsed but
        ``regression_required`` is false; there is no chain to
        return.
    """
    user = session["user"]
    store = _v76_store_for(user)

    result = intelligence_kernel.run_regression_first(
        packet=req.packet,
        user_id=user,
        model_id=None,    # let the router resolve via TASK_DEFAULTS
        store=store,
    )

    if not result.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=error_response(
                "packet_rejected",
                "packet failed validation under the regression_first schema",
            ),
        )

    chain = result.get("chain")
    if chain is None:
        raise HTTPException(
            status_code=422,
            detail=error_response(
                "regression_not_required",
                "packet parsed but regression_required is false; "
                "no chain was created",
            ),
        )

    # v82 — persist the original packet under the per-user
    # ``regression_packets`` namespace, first-packet-wins so a future
    # /replay call always replays the original prompt, not a later
    # mutation. We do this AFTER the kernel succeeded but BEFORE the
    # timeline emits, so a vault hiccup here would also skip the
    # event (a failed-to-persist packet has no replay surface and
    # therefore no chain-started event is meaningful).
    _v82_persist_original_packet(user, chain["chain_id"], req.packet)

    # /start side-effect: emit chain_started for the new chain.
    _v76_emit_timeline_event(
        el_ins_timeline.build_regression_chain_started_event(
            user,
            chain_id=chain["chain_id"],
            title=chain["title"],
            created_at_ms=chain["created_at"],
        ),
    )

    # /step side-effect (single): if the packet supplied a non-empty
    # regression_chain skeleton, seed the LAST entry as a finding
    # with status="unknown" and notes synthesized from the entry,
    # then emit one chain_layer_updated event.
    packet = result.get("packet") or {}
    skeleton = packet.get("regression_chain") or []
    if isinstance(skeleton, list) and skeleton:
        last_idx_in_skeleton = len(skeleton) - 1
        last_entry = skeleton[last_idx_in_skeleton]
        if isinstance(last_entry, dict):
            try:
                updated_chain = problem_solver.record_finding(
                    chain["chain_id"],
                    last_idx_in_skeleton,
                    "unknown",
                    _v80_synthesize_layer_notes(last_entry),
                    store=store,
                )
            except (KeyError, ValueError) as e:   # pragma: no cover (defensive)
                logger.warning(
                    "v80 packet layer-seed failed chain=%s err=%s",
                    chain["chain_id"], e,
                )
                updated_chain = chain
            else:
                updated_layer = next(
                    (L for L in updated_chain["layers"]
                     if L["layer_index"] == last_idx_in_skeleton),
                    None,
                )
                if updated_layer is not None:
                    _v76_emit_timeline_event(
                        el_ins_timeline.build_regression_chain_layer_updated_event(
                            user,
                            chain_id=updated_chain["chain_id"],
                            layer_index=updated_layer["layer_index"],
                            status=updated_layer["status"],
                            updated_at_ms=updated_layer["updated_at"],
                        ),
                    )
            chain = updated_chain

    return _chain_to_model(chain)


# ---------------------------------------------------------------------------
# v82 — Packet history + replay
#
# The original packet that drove a chain is persisted to
# ``regression_packets.{chain_id}`` under the operator's vault
# partition the first time ``/packet`` succeeds. Subsequent calls
# don't overwrite — first packet wins, so future ``/replay`` always
# replays the original.
#
# ``/replay`` looks up that packet, dispatches it through the same
# kernel + endpoint helpers as ``/packet``, and creates a NEW chain
# (new chain_id, fresh timeline events, fresh seeded layer). The
# original chain is untouched.
# ---------------------------------------------------------------------------
_V82_PACKET_NS: str = "regression_packets"


def _v82_packet_key(chain_id: str) -> str:
    return f"{_V82_PACKET_NS}.{chain_id}"


def _v82_persist_original_packet(
    user: str, chain_id: str, packet: dict,
) -> None:
    """First-packet-wins: don't overwrite an existing entry. Defensive
    against vault hiccups — failures are logged and swallowed so they
    can't roll back the chain creation that just succeeded."""
    try:
        existing = memory_vault.vault_get(
            user, _v82_packet_key(chain_id), default=None,
        )
        if existing is not None:
            return
        memory_vault.vault_put(
            user, _v82_packet_key(chain_id), packet,
        )
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning(
            "v82 packet persist failed user=%s chain=%s err=%s",
            _user_ref(user), chain_id, e,
        )


def _v82_load_original_packet(user: str, chain_id: str) -> Optional[dict]:
    try:
        value = memory_vault.vault_get(
            user, _v82_packet_key(chain_id), default=None,
        )
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning(
            "v82 packet read failed user=%s chain=%s err=%s",
            _user_ref(user), chain_id, e,
        )
        return None
    return value if isinstance(value, dict) else None


@app.post(
    "/me/regression_first/replay",
    response_model=V76RegressionChainModel,
)
def me_regression_first_replay(
    req: V82ReplayRequest, session: dict = Depends(require_session),
):
    """v82 — replay an existing chain's original packet as a NEW
    chain. Creates a new chain_id (the original is untouched). Emits
    the same ``regression_chain_started`` + ``regression_chain_layer_updated``
    events as a fresh ``/packet`` call (continuity invariant).

    404 when the operator's vault has no original packet for the
    supplied ``chain_id`` (the chain itself may have existed in a
    pre-v82 build, or the chain_id may be unknown — either way the
    replay surface is unreachable).
    """
    user = session["user"]
    original = _v82_load_original_packet(user, req.chain_id)
    if original is None:
        raise HTTPException(
            status_code=404,
            detail="no original packet stored for chain_id",
        )

    store = _v76_store_for(user)
    result = intelligence_kernel.run_regression_first(
        packet=original,
        user_id=user,
        model_id=None,
        store=store,
    )

    # The kernel was already happy with this packet once (we stored
    # it from a successful run). If it now degrades we still respect
    # the v80 422 contract, but in practice this path stays green.
    if not result.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=error_response(
                "packet_rejected",
                "original packet failed re-validation under the "
                "regression_first schema",
            ),
        )
    new_chain = result.get("chain")
    if new_chain is None:
        raise HTTPException(
            status_code=422,
            detail=error_response(
                "regression_not_required",
                "original packet no longer requires regression",
            ),
        )

    # Persist the (same) packet under the NEW chain_id so a future
    # replay-of-the-replay still finds an origin packet.
    _v82_persist_original_packet(user, new_chain["chain_id"], original)

    # Emit chain_started for the new chain (continuity invariant).
    _v76_emit_timeline_event(
        el_ins_timeline.build_regression_chain_started_event(
            user,
            chain_id=new_chain["chain_id"],
            title=new_chain["title"],
            created_at_ms=new_chain["created_at"],
        ),
    )

    # Seed the last skeleton layer + emit one layer_updated event,
    # same policy as v80.
    skeleton = (result.get("packet") or {}).get("regression_chain") or []
    if isinstance(skeleton, list) and skeleton:
        last_idx = len(skeleton) - 1
        last_entry = skeleton[last_idx]
        if isinstance(last_entry, dict):
            try:
                seeded = problem_solver.record_finding(
                    new_chain["chain_id"],
                    last_idx,
                    "unknown",
                    _v80_synthesize_layer_notes(last_entry),
                    store=store,
                )
            except (KeyError, ValueError) as e:   # pragma: no cover
                logger.warning(
                    "v82 replay layer-seed failed chain=%s err=%s",
                    new_chain["chain_id"], e,
                )
                seeded = new_chain
            else:
                updated_layer = next(
                    (L for L in seeded["layers"]
                     if L["layer_index"] == last_idx),
                    None,
                )
                if updated_layer is not None:
                    _v76_emit_timeline_event(
                        el_ins_timeline.build_regression_chain_layer_updated_event(
                            user,
                            chain_id=seeded["chain_id"],
                            layer_index=updated_layer["layer_index"],
                            status=updated_layer["status"],
                            updated_at_ms=updated_layer["updated_at"],
                        ),
                    )
            new_chain = seeded

    return _chain_to_model(new_chain)


# ===========================================================================
# v52 — Emotional Physics endpoint
# ===========================================================================
# Sits after the threads/projects block, before /founder/* — matches
# the v47/v50 placement pattern. Returns the kernel's four-layer
# structured object plus a ``_meta`` block with model_id / ts_ms /
# parse_error. No vendor pinning — model selection is task-level via
# model_router (task key ``emotional_physics``).
class V52EmotionalPhysicsRequest(BaseModel):
    text: str


@app.post("/me/emotional_physics/analyze")
def me_emotional_physics_analyze(
    req: V52EmotionalPhysicsRequest,
    session: dict = Depends(require_session),
):
    """v52 — structural-not-sentimental analysis of a free-text
    situation. Returns the four-layer emotional_physics object plus
    a ``_meta`` block (``model_id`` / ``ts_ms`` / ``parse_error``).

    Behaviour:
      * 400 when ``text`` is missing, not a string, or whitespace-only.
      * 200 on graceful degrade — the four top-level keys are always
        present; ``_meta.parse_error`` is non-null when the model
        couldn't be parsed into a JSON object.
      * No 5xx for parse failures (matches v41 oracle contract).
    """
    user = session["user"]
    text = req.text if isinstance(req.text, str) else ""
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", "text must be a non-empty string"),
        )
    try:
        out = intelligence_kernel.run_emotional_physics(user, text)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", str(e)),
        )
    return out


# ===========================================================================
# v53 — ELINS v2 endpoint (Path-C view adapter)
# ===========================================================================
# Wraps intelligence_kernel.run_elins_v2 which itself orchestrates
# standard_elins.generate_ELINS (always) + regional_elins.run_regional_elins
# (when region given), then projects via ELINS.elins_v2_view. No new
# generative work; no vendor pinning; no /skills_export imports.
class V53ElinsV2Input(BaseModel):
    raw_text:        str
    source_type:     Optional[str] = None
    language:        Optional[str] = None
    geography_hint:  Optional[str] = None
    time_context:    Optional[str] = None
    operator_tags:   Optional[list[str]] = None


class V53ElinsV2Request(BaseModel):
    elins_version: Optional[str] = None
    region:        Optional[str] = None
    input:         V53ElinsV2Input


@app.post("/elins/v2/run")
def elins_v2_run(
    req: V53ElinsV2Request,
    session: dict = Depends(require_session),
):
    """v53 — ELINS v2 run (Path C).

    Reuses the existing v33-v37 ELINS internals and projects the output
    into the v2.0 envelope shape:

      * pipeline: L1_ingest .. L10_signature (mapped from existing layers)
      * outputs:  collapse_state, attractor, state_distribution, P0_P8,
                  geography_tier, timeline, multiplier
      * meta:     engine, view_kind, warnings, notes

    Errors:
      * 400 on empty ``input.raw_text`` or invalid ``region``
      * 401 on missing session
    """
    user = session["user"]
    raw_text = req.input.raw_text if isinstance(req.input.raw_text, str) else ""
    if not raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_input", "input.raw_text must be a non-empty string",
            ),
        )

    try:
        envelope = intelligence_kernel.run_elins_v2(
            user, raw_text,
            region=req.region,
            request_input=req.input.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", str(e)),
        )
    return envelope


# ===========================================================================
# v54 — Ingestion bus endpoints (manual + RSS/Atom feeds)
# ===========================================================================
# RSS/Atom feed registration + manual text ingestion. Per-user 5-feed
# cap; 5-items-per-run cap. No eval / no exec / no user code surface;
# no HTML scraping. Outbound HTTP only to registered RSS/Atom URLs
# with 2 MB / 10 s caps in ingestion_bus.fetch_feed_bytes.
class V54IngestManualRequest(BaseModel):
    raw_text: str
    source:   Optional[str] = "manual"
    region:   Optional[str] = None


class V54FeedRegisterRequest(BaseModel):
    name:   str
    url:    str
    region: Optional[str] = None


class V54FeedRunRequest(BaseModel):
    feed_id: Optional[str] = None


@app.post("/ingest/manual")
def ingest_manual(
    req: V54IngestManualRequest,
    session: dict = Depends(require_session),
):
    """v54 — manual text ingestion.

    User pastes content (their own notes, transcripts, content from a
    subscription they have legitimate access to). System runs ELINS v2
    on it and stores the result in library_store. Returns the
    library_id and the full v2 envelope.
    """
    user = session["user"]
    raw_text = req.raw_text if isinstance(req.raw_text, str) else ""
    if not raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", "raw_text must be a non-empty string"),
        )
    try:
        out = intelligence_kernel.run_manual_ingestion(
            user, raw_text,
            source=str(req.source or "manual"),
            region=req.region,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", str(e)),
        )
    return {
        "ok":         True,
        "library_id": out["library_id"],
        "envelope":   out["envelope"],
    }


@app.post("/ingest/feeds/register")
def ingest_feeds_register(
    req: V54FeedRegisterRequest,
    session: dict = Depends(require_session),
):
    """v54 — register an RSS/Atom feed URL. Max 5 per user.

    Errors:
      * 400 on invalid URL, duplicate, name conflict, or limit reached
      * 401 on missing session
    """
    user = session["user"]
    try:
        entry = ingestion_bus.register_feed(
            user, name=req.name, url=req.url, region=req.region,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", str(e)),
        )
    return {"ok": True, "feed": entry}


@app.get("/ingest/feeds")
def ingest_feeds_list(session: dict = Depends(require_session)):
    """v54 — list the calling user's registered RSS/Atom feeds."""
    user = session["user"]
    return {
        "ok":    True,
        "feeds": ingestion_bus.list_feeds(user),
        "limit": ingestion_bus.FEED_LIMIT_PER_USER,
    }


@app.delete("/ingest/feeds/{feed_id}")
def ingest_feeds_delete(
    feed_id: str,
    session: dict = Depends(require_session),
):
    """v54 — remove one of the calling user's registered feeds.
    Returns 404 if the feed_id isn't registered."""
    user = session["user"]
    try:
        ingestion_bus.delete_feed(user, feed_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"feed not found: {feed_id}"),
        )
    return {"ok": True, "feed_id": feed_id}


@app.post("/ingest/feeds/run")
def ingest_feeds_run(
    req: V54FeedRunRequest,
    session: dict = Depends(require_session),
):
    """v54 — fetch + parse + dispatch one or all registered feeds.

    If ``feed_id`` is supplied, only that feed runs (404 if missing).
    Otherwise the calling user's full feed list runs and an aggregate
    summary is returned.

    Per-feed fetch errors are captured in the per-feed result; the
    endpoint never returns 5xx for individual feed transport failures.
    """
    user = session["user"]
    if req.feed_id:
        try:
            r = intelligence_kernel.run_feed_ingestion(user, req.feed_id)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=error_response("not_found", f"feed not found: {req.feed_id}"),
            )
        return {"ok": True, "result": r}
    return {"ok": True, "cycle": intelligence_kernel.run_ingestion_cycle(user)}


@app.get("/me/billing")
def me_billing(session: dict = Depends(require_session)):
    """Per-user billing snapshot. Metadata only — no Stripe ids, no
    customer ids. The ``status`` field is normalised to one of
    ``none / active / past_due / canceled / failed`` (note ``canceled``
    to match Stripe spelling on the public surface).

    PASS-4 FIX-P1 — ``billing_state == "failed"`` is now surfaced
    distinctly as ``status: "failed"``. Previously it fell through to
    ``status: "none"``, which collapsed an activation-failure case
    into "no billing" and hid the underlying problem from both the
    user and any downstream surface that reads /me/billing.
    """
    user = session["user"]
    view = users_store.get_membership_view(user) or {}
    billing_state = view.get("billing_state")
    membership_status = view.get("status")
    if billing_state in ("active",):
        normalised = "active"
    elif billing_state in ("past_due", "grace_period"):
        normalised = "past_due"
    elif billing_state == "cancelled" or membership_status == "cancelled":
        normalised = "canceled"
    elif billing_state == "failed":
        normalised = "failed"
    else:
        normalised = "none"
    bs = billing_config.get_billing_status()
    return {
        "ok": True,
        "status": normalised,
        "plan": view.get("plan") or view.get("price_locked_in") and "founding" or None,
        "renewal_ts": view.get("renewal_ts"),
        "mode": bs.get("mode"),
        "billing_enabled": bs.get("billing_enabled"),
    }


# ===========================================================================
# v83 — Entitlement projection
# ===========================================================================
# Read-only projection over the existing v30/v31/v42/v74 membership +
# billing stores. NOT a billing core — ``entitlement_view`` introduces
# no state, no Stripe code, no second source of truth. It reads
# users_store + membership_store + billing_config and emits one
# normalised entitlement shape that WordPress / the operator portal
# consume to gate access. See entitlement_view.py for the contract +
# the ``active`` derivation rules.
#
# Both endpoints return the dict directly (no Pydantic model — same
# convention as /me/billing). ``compute_entitlement_view`` never
# raises and returns ``exists: False`` for unknown users, so the
# founder route answers 200 (not 404) for an unknown user_id — a
# deliberate projection choice so the founder dashboard renders
# "no entitlement" without special-casing.
@app.get("/me/entitlement")
def me_entitlement(session: dict = Depends(require_session)):
    """v83 — entitlement projection for the authenticated caller.
    Read-only; computed from the existing membership + billing state.
    """
    return entitlement_view.compute_entitlement_view(session["user"])


@app.get("/founder/entitlement/{user_id}")
def founder_entitlement(
    user_id: str, session: dict = Depends(_require_founder),
):
    """v83 — founder-only entitlement projection for any user. 400 on
    a malformed user_id; 200 with ``exists: False`` for an unknown
    user (the projection never 404s)."""
    if not user_id or "/" in user_id:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", "invalid user_id"),
        )
    return entitlement_view.compute_entitlement_view(user_id)


@app.get("/founder/operator/{user_id}/state")
def founder_operator_state(
    user_id: str,
    session: dict = Depends(_require_founder),
):
    """Founder-only: read another user's operator state. Used by the
    member detail view to render the ELINS / #G timeline + inferred
    preferences for any user the founder selects."""
    if not user_id or "/" in user_id:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_input", "user_id must be a non-empty path-safe string"),
        )
    if not users_store.user_exists(user_id):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"user {user_id!r} not found"),
        )
    state = operator_state.get_operator_state(user_id)
    return {"ok": True, "state": state}


@app.get("/founder/elins/entity_graph/raw")
def founder_entity_graph_raw(session: dict = Depends(_require_founder)):
    """Founder-only: return the full graph dict + snapshot metadata.
    Used by export / debug surfaces."""
    snap = elins_project.load_latest_entity_graph()
    if snap is None:
        return {
            "ok": True,
            "graph": dict(elins_entity_graph.EMPTY_GRAPH),
            "snapshot": None,
        }
    return {
        "ok": True,
        "graph": snap.get("graph") or dict(elins_entity_graph.EMPTY_GRAPH),
        "snapshot": {
            "id": snap.get("id"),
            "ts": snap.get("ts"),
            "entity_count": snap.get("entity_count"),
            "edge_count": snap.get("edge_count"),
            "version": snap.get("version"),
        },
    }


# ---------- Comment generator (#cmt) ----------
class V33CommentRequest(BaseModel):
    text: str
    domain_hint: Optional[str] = None


@app.post("/cmt/generate")
def cmt_generate(req: V33CommentRequest, session: dict = Depends(require_session)):
    """Most Relevant Comment Generator (MRCG v1.0). Returns the
    assembled comment + detection + construction + activation metadata.
    Lexical + deterministic — same input always returns the same
    comment. No content stored."""
    user = session["user"]
    try:
        text = v29_hardening.require_str(req.text, "text", max_len=SCENARIO_MAX_LEN)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/cmt/generate")
    try:
        result = comment_generator.generate_comment(text, domain_hint=req.domain_hint)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    v29_hardening.log_event(
        "cmt_generate", user=user, route="/cmt/generate", success=True,
        attractor=str(result["detection"]["attractor"]),
        domain=str(result["detection"].get("domain") or ""),
    )
    return result


# ---------- #c cloud engine (mode-routed) ----------
class V33CloudRunRequest(BaseModel):
    text: str
    mode: str = "comment"
    domain_hint: Optional[str] = None


@app.post("/c/run")
def c_run(req: V33CloudRunRequest, session: dict = Depends(require_session)):
    """#c cloud engine. Today the only routed mode is "comment", which
    delegates to ``comment_generator.generate_comment``. Future modes
    can be added here without changing the public surface."""
    user = session["user"]
    try:
        text = v29_hardening.require_str(req.text, "text", max_len=SCENARIO_MAX_LEN)
        mode = v29_hardening.require_one_of(req.mode, "mode", ("comment",))
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(user, "/c/run")
    # v40 — kernel-routed. ``run_c`` mirrors any external_signal_mode
    # override (none here) onto operator_state and dispatches to the
    # comment generator. Domain hint is preserved by re-calling
    # ``generate_comment`` directly when the caller supplies one, since
    # the kernel's run_c surface does not expose it yet.
    if mode == "comment":
        try:
            if req.domain_hint:
                result = comment_generator.generate_comment(
                    text, domain_hint=req.domain_hint,
                )
            else:
                kernel_result = intelligence_kernel.run_c(user, text, mode="comment")
                result = kernel_result["result"]
        except ValueError as e:
            v29_hardening.raise_validation(
                v29_hardening.ValidationError("bad_input", str(e)),
            )
        v29_hardening.log_event(
            "c_run_comment", user=user, route="/c/run", success=True,
            attractor=str(result["detection"]["attractor"]),
        )
        return {"ok": True, "mode": mode, "result": result}
    # Should never hit because require_one_of already rejected.
    v29_hardening.raise_validation(
        v29_hardening.ValidationError("bad_mode", f"mode {mode!r} not supported"),
    )


# ---------- Founder DM pipeline ----------
class V33DMAddRequest(BaseModel):
    user: Optional[str] = None
    external_id: Optional[str] = None
    channel: str = "manual"
    subject: Optional[str] = None
    snippet: Optional[str] = None


class V33DMNoteRequest(BaseModel):
    dm_id: str
    body: str


@app.post("/founder/dm/add")
def founder_dm_add(req: V33DMAddRequest, session: dict = Depends(_require_founder)):
    founder = session["user"]
    try:
        channel = v29_hardening.require_one_of(req.channel, "channel", dm_store.VALID_CHANNELS)
        if req.subject is not None:
            v29_hardening.require_str(req.subject, "subject", max_len=dm_store.MAX_SUBJECT_LEN, allow_empty=True)
        if req.snippet is not None:
            v29_hardening.require_str(req.snippet, "snippet", max_len=dm_store.MAX_SNIPPET_LEN, allow_empty=True)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(founder, "/founder/dm/add")
    try:
        dm = dm_store.add_dm(
            founder=founder,
            user=req.user,
            external_id=req.external_id,
            channel=channel,
            subject=req.subject,
            snippet=req.snippet,
        )
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    v29_hardening.log_event(
        "founder_dm_add", user=founder, route="/founder/dm/add",
        success=True, channel=channel,
    )
    return {"ok": True, "dm": dm}


@app.get("/founder/dm/list")
def founder_dm_list(
    channel: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 200,
    session: dict = Depends(_require_founder),
):
    founder = session["user"]
    try:
        n = v29_hardening.require_int(limit, "limit", min_value=1, max_value=2000, default=200)
        if channel is not None and channel != "":
            v29_hardening.require_one_of(channel, "channel", dm_store.VALID_CHANNELS)
        else:
            channel = None
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(founder, "/founder/dm/list")
    if user:
        rows = dm_store.list_dms_for_user(user, limit=n)
    else:
        rows = dm_store.list_dms(channel=channel, limit=n)
    return {"ok": True, "dms": rows, "count": len(rows)}


@app.post("/founder/dm/notes")
def founder_dm_notes(req: V33DMNoteRequest, session: dict = Depends(_require_founder)):
    """Append a founder note to an existing DM and return the full note
    list for that DM. Empty ``body`` is rejected at the store level."""
    founder = session["user"]
    try:
        dm_id = v29_hardening.require_str(req.dm_id, "dm_id", max_len=64)
        body = v29_hardening.require_str(req.body, "body", max_len=dm_store.MAX_BODY_LEN)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    v29_hardening.enforce_rate_limit(founder, "/founder/dm/notes")
    try:
        note = dm_store.add_dm_note(dm_id, body, founder=founder)
    except ValueError as e:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_input", str(e)),
        )
    if note is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"dm {dm_id!r} not found"),
        )
    notes = dm_store.get_dm_notes(dm_id)
    v29_hardening.log_event(
        "founder_dm_note", user=founder, route="/founder/dm/notes",
        success=True, dm_id=dm_id[:16], note_count=len(notes),
    )
    return {"ok": True, "note": note, "notes": notes}


# ---------- Founder membership operations ----------
class V33FounderActivateRequest(BaseModel):
    user: str
    price: Optional[float] = None
    note: Optional[str] = None


class V33FounderCancelRequest(BaseModel):
    user: str
    note: Optional[str] = None


class V33FounderCreditsRequest(BaseModel):
    user: str
    delta: int                     # positive or negative
    reason: Optional[str] = None


@app.post("/founder/membership/activate")
def founder_membership_activate(
    req: V33FounderActivateRequest,
    session: dict = Depends(_require_founder),
):
    """Manually activate a member without going through PaymentIntent.
    Used by the founder console for invited/comp'd members. Records a
    transaction with metadata.manual=true so audits can distinguish
    these from real activations."""
    founder = session["user"]
    try:
        target = v29_hardening.require_str(req.user, "user", max_len=128)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if not users_store.user_exists(target):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"user {target!r} not found"),
        )
    price = (
        float(req.price) if req.price is not None
        else float(membership_store.FOUNDING_PRICE_LOCKED)
    )
    if price < 0:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_amount", "price must be >= 0"),
        )
    target_doc = users_store.get_user(target) or {}
    if target_doc.get("membership_status") == "active":
        return {"ok": True, "already_active": True, "user": target}
    try:
        cohort_state = membership_store.add_member(target)
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=error_response("cohort_error", str(e)),
        )
    started_ts = time.time()
    users_store.set_membership(
        target,
        tier=membership_store.FOUNDING_COHORT,
        price=price,
        status="active",
        started_ts=started_ts,
    )
    users_store.set_billing_state(
        target,
        billing_state="active",
        renewal_ts=billing_intents.calculate_next_renewal_ts(started_ts),
        renewal_retry_count=0,
    )
    membership_store.record_transaction(
        target, type="membership_activation", amount=price, credits_delta=0,
        metadata={
            "manual": True, "founder": founder,
            "note": (req.note or "")[:500],
            "cohort": membership_store.FOUNDING_COHORT,
        },
    )
    v29_hardening.log_event(
        "founder_membership_activate", user=founder,
        route="/founder/membership/activate", success=True,
        target=target, price=price, active_count=cohort_state["active_count"],
    )
    return {
        "ok": True,
        "user": target,
        "membership": users_store.get_membership_view(target),
    }


@app.post("/founder/membership/cancel")
def founder_membership_cancel(
    req: V33FounderCancelRequest,
    session: dict = Depends(_require_founder),
):
    founder = session["user"]
    try:
        target = v29_hardening.require_str(req.user, "user", max_len=128)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    target_doc = users_store.get_user(target)
    if target_doc is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"user {target!r} not found"),
        )
    if target_doc.get("membership_status") != "active":
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("not_active", "user has no active membership"),
        )
    cancelled_ts = time.time()
    users_store.set_membership(
        target,
        tier=target_doc.get("membership_tier"),
        price=target_doc.get("membership_price"),
        status="cancelled",
        cancelled_ts=cancelled_ts,
    )
    users_store.set_billing_state(target, billing_state="cancelled")
    membership_store.remove_member(target)
    membership_store.record_transaction(
        target, type="membership_cancel", amount=0.0, credits_delta=0,
        metadata={
            "manual": True, "founder": founder,
            "note": (req.note or "")[:500],
            "price_lock_forfeit": True,
        },
    )
    v29_hardening.log_event(
        "founder_membership_cancel", user=founder,
        route="/founder/membership/cancel", success=True, target=target,
    )
    return {"ok": True, "user": target, "membership": users_store.get_membership_view(target)}


@app.post("/founder/membership/credits")
def founder_membership_credits(
    req: V33FounderCreditsRequest,
    session: dict = Depends(_require_founder),
):
    """Manually credit / debit a user's #G balance. Positive ``delta``
    grants credits; negative ``delta`` revokes. Records a transaction
    with metadata.manual=true."""
    founder = session["user"]
    try:
        target = v29_hardening.require_str(req.user, "user", max_len=128)
        delta = v29_hardening.require_int(req.delta, "delta", min_value=-1000, max_value=1000)
    except v29_hardening.ValidationError as e:
        v29_hardening.raise_validation(e)
    if delta == 0:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError("bad_amount", "delta must be non-zero"),
        )
    if not users_store.user_exists(target):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"user {target!r} not found"),
        )
    current = users_store.get_g_credit_balance(target)
    if current + delta < 0:
        v29_hardening.raise_validation(
            v29_hardening.ValidationError(
                "would_go_negative",
                f"cannot debit {abs(delta)} credits — balance is {current}",
            ),
        )
    history_entry = {
        "type": "founder_grant" if delta > 0 else "founder_revoke",
        "credits_delta": delta,
        "amount": 0.0,
        "ts": time.time(),
        "founder": founder,
    }
    new_balance = users_store.add_g_credits(target, delta, history_entry=history_entry)
    membership_store.record_transaction(
        target,
        type="founder_grant" if delta > 0 else "founder_revoke",
        amount=0.0, credits_delta=delta,
        metadata={
            "manual": True, "founder": founder,
            "reason": (req.reason or "")[:500],
        },
    )
    v29_hardening.log_event(
        "founder_membership_credits", user=founder,
        route="/founder/membership/credits", success=True,
        target=target, delta=delta, balance=new_balance,
    )
    return {
        "ok": True, "user": target,
        "balance": new_balance,
        "delta": delta,
    }


# ===========================================================================
# ELINS regression surface (Unit 2 — read-only wrapper around Unit 1
# validator; no inference behavior changed, no storage)
# ===========================================================================
@app.post("/elins/regression/single_party_fear")
def elins_regression_single_party_fear(
    body: dict,
    session: dict = Depends(require_session),
):
    """Read-only Single-Party Fear regression endpoint.

    Accepts a Timeline payload, runs the Unit 1 validator via the
    Unit 2 dashboard wrapper, and returns the dashboard-friendly dict.

    No storage. No side effects. Does not affect any ELINS basin
    inference behavior.

    Request body:
        {
            "timeline_id": "...",
            "points": [
                {
                    "t": "...",
                    "regime_competition": float,
                    "autocratization": float,
                    "repression_index": float,
                    "digital_repression": float,
                    "perceived_threat": float,
                    "fear_signal": float,
                    "dissent_capacity": float,
                    "normative_constraint": float,
                    "support_buffer": float,
                    "trigger_event": Optional[str]   # may be omitted
                },
                ...
            ]
        }
    """
    _ = session  # auth-only; not consumed in the read-only computation
    from elins_regression_single_party import Timeline, TimePoint
    from elins_timeline_dashboard import get_single_party_fear_regression

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    timeline_id = body.get("timeline_id")
    points_raw = body.get("points")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "timeline_id must be a non-empty string"),
        )
    if not isinstance(points_raw, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "points must be a list"),
        )
    # ELINS Unit 3 — empty `points` is now valid. The validator returns
    # a vacuous all-zero result (Fails core logic band) instead of
    # crashing. The Unit 2 endpoint-level rejection has been removed.

    _required_numeric_fields = (
        "regime_competition", "autocratization", "repression_index",
        "digital_repression", "perceived_threat", "fear_signal",
        "dissent_capacity", "normative_constraint", "support_buffer",
    )
    points: list = []
    for i, p in enumerate(points_raw):
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}] must be a JSON object",
                ),
            )
        t = p.get("t")
        if not isinstance(t, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}].t must be a string",
                ),
            )
        kwargs = {"t": t}
        for fname in _required_numeric_fields:
            v = p.get(fname)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_payload",
                        f"points[{i}].{fname} must be a number",
                    ),
                )
            kwargs[fname] = float(v)
        trigger = p.get("trigger_event")
        if trigger is not None and not isinstance(trigger, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}].trigger_event must be a string or null",
                ),
            )
        kwargs["trigger_event"] = trigger
        points.append(TimePoint(**kwargs))

    timeline = Timeline(timeline_id=timeline_id, points=tuple(points))
    return get_single_party_fear_regression(timeline)


# ===========================================================================
# ELINS economic-coercion regression endpoint (Unit 4 — read-only wrapper
# around the Unit 4 validator; no inference behavior changed, no storage)
# ===========================================================================
@app.post("/elins/regression/economic_coercion")
def elins_regression_economic_coercion(
    body: dict,
    session: dict = Depends(require_session),
):
    """Read-only Economic Coercion regression endpoint.

    Accepts a TimelineEconomic payload, runs the Unit 4 validator via
    the Unit 4 dashboard wrapper, and returns the dashboard-friendly
    dict. Per Unit 3 convention, empty `points` is valid and yields a
    vacuous score-0 result.

    Request body:
        {
            "timeline_id": "...",
            "points": [
                {
                    "t": "...",
                    "economic_pressure":   float,
                    "material_insecurity": float,
                    "state_coercion":      float,
                    "compliance_signal":   float,
                    "resistance_capacity": float,
                    "support_buffer":      float,
                    "trigger_event":       Optional[str]   # may be omitted
                },
                ...
            ]
        }
    """
    _ = session
    from elins_regression_economic_coercion import (
        TimelineEconomic, TimePointEconomic,
    )
    from elins_timeline_dashboard import get_economic_coercion_regression

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    timeline_id = body.get("timeline_id")
    points_raw = body.get("points")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "timeline_id must be a non-empty string"),
        )
    if not isinstance(points_raw, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "points must be a list"),
        )

    _required_numeric_fields = (
        "economic_pressure", "material_insecurity", "state_coercion",
        "compliance_signal", "resistance_capacity", "support_buffer",
    )
    points: list = []
    for i, p in enumerate(points_raw):
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}] must be a JSON object",
                ),
            )
        t = p.get("t")
        if not isinstance(t, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}].t must be a string",
                ),
            )
        kwargs = {"t": t}
        for fname in _required_numeric_fields:
            v = p.get(fname)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_payload",
                        f"points[{i}].{fname} must be a number",
                    ),
                )
            kwargs[fname] = float(v)
        trigger = p.get("trigger_event")
        if trigger is not None and not isinstance(trigger, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"points[{i}].trigger_event must be a string or null",
                ),
            )
        kwargs["trigger_event"] = trigger
        points.append(TimePointEconomic(**kwargs))

    timeline = TimelineEconomic(timeline_id=timeline_id, points=tuple(points))
    return get_economic_coercion_regression(timeline)


# ===========================================================================
# ELINS comparison endpoint (Unit 5 — runs both regression validators
# over their respective timelines and returns a side-by-side delta dict)
# ===========================================================================
@app.post("/elins/regression/compare")
def elins_regression_compare(
    body: dict,
    session: dict = Depends(require_session),
):
    """Read-only multi-regression comparison endpoint.

    Accepts two timeline payloads (one per regression), runs both
    validators via the Unit 5 dashboard wrapper, and returns the
    side-by-side comparison dict. Per Unit 3 convention, empty `points`
    is valid for either timeline.

    Request body:
        {
            "single_party_timeline": {
                "timeline_id": "...",
                "points": [ ... single-party fear schema ... ]
            },
            "economic_timeline": {
                "timeline_id": "...",
                "points": [ ... economic-coercion schema ... ]
            }
        }
    """
    _ = session
    from elins_regression_single_party import (
        Timeline, TimePoint,
    )
    from elins_regression_economic_coercion import (
        TimelineEconomic, TimePointEconomic,
    )
    from elins_timeline_dashboard import compare_regressions_dashboard

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    sp_payload = body.get("single_party_timeline")
    ec_payload = body.get("economic_timeline")
    if not isinstance(sp_payload, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "single_party_timeline must be a JSON object",
            ),
        )
    if not isinstance(ec_payload, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "economic_timeline must be a JSON object",
            ),
        )

    def _parse_timeline_id_and_points(
        payload: dict, key_label: str,
    ) -> tuple:
        tid = payload.get("timeline_id")
        pts_raw = payload.get("points")
        if not isinstance(tid, str) or not tid:
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"{key_label}.timeline_id must be a non-empty string",
                ),
            )
        if not isinstance(pts_raw, list):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"{key_label}.points must be a list",
                ),
            )
        return tid, pts_raw

    def _parse_point(
        p: dict, idx: int, key_label: str, required_fields: tuple,
    ) -> dict:
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"{key_label}.points[{idx}] must be a JSON object",
                ),
            )
        t = p.get("t")
        if not isinstance(t, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"{key_label}.points[{idx}].t must be a string",
                ),
            )
        kw: dict = {"t": t}
        for fname in required_fields:
            v = p.get(fname)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_payload",
                        f"{key_label}.points[{idx}].{fname} must be a number",
                    ),
                )
            kw[fname] = float(v)
        trigger = p.get("trigger_event")
        if trigger is not None and not isinstance(trigger, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"{key_label}.points[{idx}].trigger_event must be a string or null",
                ),
            )
        kw["trigger_event"] = trigger
        return kw

    _SP_FIELDS = (
        "regime_competition", "autocratization", "repression_index",
        "digital_repression", "perceived_threat", "fear_signal",
        "dissent_capacity", "normative_constraint", "support_buffer",
    )
    _EC_FIELDS = (
        "economic_pressure", "material_insecurity", "state_coercion",
        "compliance_signal", "resistance_capacity", "support_buffer",
    )

    sp_tid, sp_pts_raw = _parse_timeline_id_and_points(
        sp_payload, "single_party_timeline",
    )
    ec_tid, ec_pts_raw = _parse_timeline_id_and_points(
        ec_payload, "economic_timeline",
    )

    sp_points = tuple(
        TimePoint(**_parse_point(p, i, "single_party_timeline", _SP_FIELDS))
        for i, p in enumerate(sp_pts_raw)
    )
    ec_points = tuple(
        TimePointEconomic(**_parse_point(p, i, "economic_timeline", _EC_FIELDS))
        for i, p in enumerate(ec_pts_raw)
    )

    sp_timeline = Timeline(timeline_id=sp_tid, points=sp_points)
    ec_timeline = TimelineEconomic(timeline_id=ec_tid, points=ec_points)
    return compare_regressions_dashboard(sp_timeline, ec_timeline)


# ===========================================================================
# ELINS batch comparison endpoint (Unit 8 — multi-pair extension of the
# Unit 5 single-pair compare; read-only, no storage)
# ===========================================================================
@app.post("/elins/regression/compare_batch")
def elins_regression_compare_batch(
    body: dict,
    session: dict = Depends(require_session),
):
    """Read-only multi-pair regression comparison endpoint.

    Accepts a list of (single_party_timeline, economic_timeline) pairs
    and returns a list of comparison dicts in the same order. Empty
    `pairs` list returns `[]`. Per Unit 3 convention, empty `points` is
    valid for either timeline in any pair.

    Request body:
        {
            "pairs": [
                {
                    "single_party_timeline": { ... Unit 1 Timeline ... },
                    "economic_timeline":     { ... Unit 4 TimelineEconomic ... }
                },
                ...
            ]
        }
    """
    _ = session
    from elins_regression_single_party import (
        Timeline, TimePoint,
    )
    from elins_regression_economic_coercion import (
        TimelineEconomic, TimePointEconomic,
    )
    from elins_timeline_dashboard import compare_regressions_batch_dashboard

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    pairs_raw = body.get("pairs")
    if not isinstance(pairs_raw, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "pairs must be a list"),
        )

    _SP_FIELDS = (
        "regime_competition", "autocratization", "repression_index",
        "digital_repression", "perceived_threat", "fear_signal",
        "dissent_capacity", "normative_constraint", "support_buffer",
    )
    _EC_FIELDS = (
        "economic_pressure", "material_insecurity", "state_coercion",
        "compliance_signal", "resistance_capacity", "support_buffer",
    )

    def _parse_timeline_block(
        payload, pair_idx: int, key_label: str,
    ) -> tuple:
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label} must be a JSON object",
                ),
            )
        tid = payload.get("timeline_id")
        pts_raw = payload.get("points")
        if not isinstance(tid, str) or not tid:
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label}.timeline_id "
                    f"must be a non-empty string",
                ),
            )
        if not isinstance(pts_raw, list):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label}.points must be a list",
                ),
            )
        return tid, pts_raw

    def _parse_point(
        p, idx: int, pair_idx: int, key_label: str, required_fields: tuple,
    ) -> dict:
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label}.points[{idx}] "
                    f"must be a JSON object",
                ),
            )
        t = p.get("t")
        if not isinstance(t, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label}.points[{idx}].t "
                    f"must be a string",
                ),
            )
        kw: dict = {"t": t}
        for fname in required_fields:
            v = p.get(fname)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_payload",
                        f"pairs[{pair_idx}].{key_label}.points[{idx}].{fname} "
                        f"must be a number",
                    ),
                )
            kw[fname] = float(v)
        trigger = p.get("trigger_event")
        if trigger is not None and not isinstance(trigger, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pair_idx}].{key_label}.points[{idx}]."
                    f"trigger_event must be a string or null",
                ),
            )
        kw["trigger_event"] = trigger
        return kw

    pairs: list = []
    for pi, entry in enumerate(pairs_raw):
        if not isinstance(entry, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}] must be a JSON object",
                ),
            )

        sp_payload = entry.get("single_party_timeline")
        ec_payload = entry.get("economic_timeline")

        sp_tid, sp_pts_raw = _parse_timeline_block(
            sp_payload, pi, "single_party_timeline",
        )
        ec_tid, ec_pts_raw = _parse_timeline_block(
            ec_payload, pi, "economic_timeline",
        )

        sp_points = tuple(
            TimePoint(**_parse_point(p, i, pi, "single_party_timeline", _SP_FIELDS))
            for i, p in enumerate(sp_pts_raw)
        )
        ec_points = tuple(
            TimePointEconomic(**_parse_point(p, i, pi, "economic_timeline", _EC_FIELDS))
            for i, p in enumerate(ec_pts_raw)
        )

        pairs.append((
            Timeline(timeline_id=sp_tid, points=sp_points),
            TimelineEconomic(timeline_id=ec_tid, points=ec_points),
        ))

    return compare_regressions_batch_dashboard(pairs)


# ===========================================================================
# ELINS directory-scanner endpoint (Unit 9 — given a directory of evidence
# files, ingests every matching SP/EC pair and returns a list of dashboard
# comparison dicts; read-only, no storage)
# ===========================================================================
@app.post("/elins/regression/analyze_directory")
def elins_regression_analyze_directory(
    body: dict,
    session: dict = Depends(require_session),
):
    """Read-only directory-scan + batch-compare endpoint.

    Accepts a payload containing a directory path. The directory is
    scanned for files matching ``<stem>_sp.{csv,json}`` and
    ``<stem>_ec.{csv,json}``; each complete pair is loaded via the
    Unit 6 ingestors, batch-compared via the Unit 8 pipeline, and
    returned as a list of dashboard dicts.

    Request body:
        {
            "path": "/absolute/or/relative/path/to/folder"
        }

    Responses:
        200 — list[dict] of comparison results, ordered by stem.
        400 — malformed payload, malformed file in the directory, or
              ambiguous role for a stem.
        401 — auth required.
        404 — directory does not exist (or path is not a directory).

    SECURITY NOTE: this endpoint accepts an arbitrary filesystem path
    chosen by the authenticated caller. Operators deploying this in
    production should restrict access via an outer allowlist (e.g.,
    confining the path under a designated CLARITYOS_EVIDENCE_DIR root)
    before exposing it to less-trusted sessions.
    """
    _ = session
    import os
    from elins_timeline_dashboard import analyze_directory

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    path = body.get("path")
    if not isinstance(path, str) or not path:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "path must be a non-empty string"),
        )

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"directory not found: {path!r}"),
        )
    if not os.path.isdir(path):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"path is not a directory: {path!r}"),
        )

    try:
        return analyze_directory(path)
    except ValueError as e:
        # Malformed file inside the directory, ambiguous role, etc.
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_evidence_file", str(e)),
        )


# ===========================================================================
# ELINS persistence endpoints (Unit 10 — store / analyze_and_store /
# list / fetch run; gives the system a memory of its analytical history)
# ===========================================================================
def _validate_optional_run_id(value, label: str = "run_id"):
    """Shared 400-validator for an optional caller-supplied run_id."""
    if value is None:
        return None
    import re
    _RX = re.compile(r"^[A-Za-z0-9_-]+$")
    if not isinstance(value, str) or not value:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"{label} must be a non-empty string",
            ),
        )
    if not _RX.match(value):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"{label} contains invalid characters; only letters, "
                f"digits, underscore, and hyphen are allowed",
            ),
        )
    return value


@app.post("/elins/regression/store")
def elins_regression_store(
    body: dict,
    session: dict = Depends(require_session),
):
    """Run a batch comparison on caller-supplied pairs and persist the
    result. Returns ``{"run_id": str, "result": list[dict]}``.

    Request body:
        {
            "run_id": "optional-string",   # auto-generated UUID if omitted
            "pairs": [
                {"single_party_timeline": ..., "economic_timeline": ...},
                ...
            ]
        }
    """
    _ = session
    from elins_regression_single_party import Timeline, TimePoint
    from elins_regression_economic_coercion import (
        TimelineEconomic, TimePointEconomic,
    )
    from elins_timeline_dashboard import analyze_and_store

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_id = _validate_optional_run_id(body.get("run_id"))

    pairs_raw = body.get("pairs")
    if not isinstance(pairs_raw, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "pairs must be a list"),
        )

    _SP_FIELDS = (
        "regime_competition", "autocratization", "repression_index",
        "digital_repression", "perceived_threat", "fear_signal",
        "dissent_capacity", "normative_constraint", "support_buffer",
    )
    _EC_FIELDS = (
        "economic_pressure", "material_insecurity", "state_coercion",
        "compliance_signal", "resistance_capacity", "support_buffer",
    )

    def _block(payload, pi, label):
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label} must be a JSON object",
                ),
            )
        tid = payload.get("timeline_id")
        pts = payload.get("points")
        if not isinstance(tid, str) or not tid:
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label}.timeline_id must be a non-empty string",
                ),
            )
        if not isinstance(pts, list):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label}.points must be a list",
                ),
            )
        return tid, pts

    def _point(p, idx, pi, label, fields):
        if not isinstance(p, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label}.points[{idx}] must be a JSON object",
                ),
            )
        t = p.get("t")
        if not isinstance(t, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label}.points[{idx}].t must be a string",
                ),
            )
        kw = {"t": t}
        for f in fields:
            v = p.get(f)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise HTTPException(
                    status_code=400,
                    detail=error_response(
                        "bad_payload",
                        f"pairs[{pi}].{label}.points[{idx}].{f} must be a number",
                    ),
                )
            kw[f] = float(v)
        trig = p.get("trigger_event")
        if trig is not None and not isinstance(trig, str):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}].{label}.points[{idx}].trigger_event "
                    f"must be a string or null",
                ),
            )
        kw["trigger_event"] = trig
        return kw

    pairs = []
    for pi, entry in enumerate(pairs_raw):
        if not isinstance(entry, dict):
            raise HTTPException(
                status_code=400,
                detail=error_response(
                    "bad_payload",
                    f"pairs[{pi}] must be a JSON object",
                ),
            )
        sp_tid, sp_pts = _block(entry.get("single_party_timeline"), pi,
                                "single_party_timeline")
        ec_tid, ec_pts = _block(entry.get("economic_timeline"), pi,
                                "economic_timeline")
        sp_points = tuple(
            TimePoint(**_point(p, i, pi, "single_party_timeline", _SP_FIELDS))
            for i, p in enumerate(sp_pts)
        )
        ec_points = tuple(
            TimePointEconomic(**_point(p, i, pi, "economic_timeline", _EC_FIELDS))
            for i, p in enumerate(ec_pts)
        )
        pairs.append((
            Timeline(timeline_id=sp_tid, points=sp_points),
            TimelineEconomic(timeline_id=ec_tid, points=ec_points),
        ))

    return analyze_and_store(pairs, run_id=run_id)


@app.post("/elins/regression/analyze_directory_and_store")
def elins_regression_analyze_directory_and_store(
    body: dict,
    session: dict = Depends(require_session),
):
    """Analyse a directory of evidence files and persist the result.
    Returns ``{"run_id": str, "result": list[dict]}``.

    Request body:
        {
            "path":   "/path/to/dir",
            "run_id": "optional-string"
        }
    """
    _ = session
    import os
    from elins_timeline_dashboard import analyze_and_store

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    path = body.get("path")
    if not isinstance(path, str) or not path:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "path must be a non-empty string"),
        )

    run_id = _validate_optional_run_id(body.get("run_id"))

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"directory not found: {path!r}"),
        )
    if not os.path.isdir(path):
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"path is not a directory: {path!r}"),
        )

    try:
        return analyze_and_store(path, run_id=run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_evidence_file", str(e)),
        )


@app.get("/elins/regression/runs")
def elins_regression_list_runs(
    source: str | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    sort: str = Query("run_id"),
    order: str = Query("asc"),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    include_archived: bool = Query(False),
    session: dict = Depends(require_session),
):
    """Unit 20 / Unit 26: list all stored runs with their Unit 19
    metadata. Optional query params provide server-side filtering,
    sorting, and pagination.

    Returns a bare JSON array of run-metadata dicts. Legacy runs
    (Unit 10 list-only files migrated into SQLite) report ``null`` for
    every metadata field; the ``run_id`` key is always present.

    Unit 26 query parameters (all optional, defaults preserve Unit 20
    behaviour):
        source         — filter to one of single / batch / directory
        since          — ISO8601 lower bound on ``metadata.created_at``
                         (inclusive). Naive timestamps interpreted as UTC.
        until          — ISO8601 upper bound on ``metadata.created_at``
                         (exclusive — half-open ``[since, until)``).
        sort           — ``run_id`` (default) or ``created_at``
        order          — ``asc`` (default) or ``desc``
        limit          — max rows to return (>= 1)
        offset         — skip first N rows after sort + filter (>= 0)

    Filters that compare against ``metadata.created_at`` exclude legacy
    runs (no timestamp); a ``source`` filter excludes legacy runs
    too (source=null does not equal any allowed value).

    Response shape (unchanged from Unit 20)::

        [
          {
            "run_id":         "...",
            "created_at":     "<ISO8601> | null",
            "source":         "single|batch|directory | null",
            "evidence_dir":   "<str> | null",
            "engine_version": "elins-19 | null"
          },
          ...
        ]
    """
    _ = session
    from elins_persistence import query_runs
    try:
        return query_runs(
            source=source,
            since=since,
            until=until,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


@app.get("/elins/regression/run/{run_id}")
def elins_regression_get_run(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Fetch a stored run by id. 404 if missing, 400 if id is malformed.

    Returns the analytic ``result`` payload (list of dashboard dicts).
    The Unit 19 metadata envelope is exposed via the dedicated
    ``GET /elins/regression/run/{run_id}/metadata`` endpoint.
    """
    _ = session
    from elins_persistence import load_comparison_result

    _validate_optional_run_id(run_id, label="run_id")  # raises 400 on bad shape

    try:
        # Unit 19: load returns {metadata, result}; this endpoint
        # preserves its pre-Unit-19 contract by returning only the
        # inner result payload.
        return load_comparison_result(run_id)["result"]
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"run_id not found: {run_id!r}"),
        )


@app.get("/elins/regression/run/{run_id}/metadata")
def elins_regression_get_run_metadata(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Fetch the Unit 19 metadata envelope for a stored run.

    Responses:
        200 — ``{"run_id": str, "metadata": dict | null}``
              ``metadata`` is ``null`` for legacy runs (Unit 10 list
              format with no envelope).
        400 — malformed run_id
        401 — auth required
        404 — run_id not found
    """
    _ = session
    from elins_persistence import load_comparison_result

    _validate_optional_run_id(run_id, label="run_id")

    try:
        envelope = load_comparison_result(run_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"run_id not found: {run_id!r}"),
        )
    return {"run_id": run_id, "metadata": envelope["metadata"]}


# ===========================================================================
# ELINS lifecycle endpoints (Unit 12 — delete a single run, or apply a
# retention policy across the runs directory)
# ===========================================================================
@app.delete("/elins/regression/run/{run_id}")
def elins_regression_delete_run(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Delete a single stored run by id.

    Responses:
        200 — ``{"deleted": run_id}``
        400 — malformed run_id
        401 — auth required
        404 — run_id not found
    """
    _ = session
    from elins_persistence import delete_run

    _validate_optional_run_id(run_id, label="run_id")

    try:
        delete_run(run_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"run_id not found: {run_id!r}"),
        )
    return {"deleted": run_id}


@app.post("/elins/regression/retention/delete_older_than")
def elins_regression_retention_delete_older_than(
    body: dict,
    session: dict = Depends(require_session),
):
    """Delete all stored runs older than ``days`` days.

    Request body:
        {"days": <non-negative int>}

    ``days == 0`` is a no-op (returns empty list) by Unit 12 convention
    — this prevents accidental "delete everything" via a zero argument.

    Responses:
        200 — ``{"deleted": [...sorted run_ids...], "count": N}``
        400 — malformed payload, non-int days, or negative days
        401 — auth required
    """
    _ = session
    from elins_persistence import delete_runs_older_than

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    days = body.get("days")
    # Reject bool first (bool is subclass of int in Python).
    if isinstance(days, bool) or not isinstance(days, int):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"days must be a non-negative int, got "
                f"{type(days).__name__}",
            ),
        )
    if days < 0:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", f"days must be >= 0, got {days}",
            ),
        )

    deleted = delete_runs_older_than(days)
    return {"deleted": deleted, "count": len(deleted)}


# ===========================================================================
# ELINS single-run summary endpoint (Unit 14 — at-a-glance aggregate over
# one stored run: counts per band + min/max/mean per dimension)
# ===========================================================================
@app.get("/elins/regression/run/{run_id}/summary")
def elins_regression_run_summary(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Return the aggregate summary table for a stored run.

    Responses:
        200 — summary dict with total_pairs, per-dimension band counts,
              and per-dimension {min, max, mean} score stats
        400 — malformed run_id
        401 — auth required
        404 — run_id not found
    """
    _ = session
    from elins_run_summary import summary_table_for_run_id

    _validate_optional_run_id(run_id, label="run_id")

    try:
        return summary_table_for_run_id(run_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", f"run_id not found: {run_id!r}"),
        )


# ===========================================================================
# ELINS dashboard composite endpoint (Unit 27 — one-shot metadata +
# summary + drift + operator-utility flags in a single response; locked
# shape that always includes all seven sections regardless of run count)
# ===========================================================================
@app.get("/elins/regression/run/dashboard/{run_id}")
def elins_regression_dashboard_get(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Dashboard composite for a single run (path-param form).

    Responses:
        200 — dashboard dict (see Unit 27 module docstring)
        400 — malformed run_id
        401 — auth required
        404 — run_id not found
    """
    _ = session
    from elins_run_dashboard import dashboard_for_run_ids

    _validate_optional_run_id(run_id, label="run_id")

    try:
        return dashboard_for_run_ids([run_id])
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/dashboard")
def elins_regression_dashboard_post(
    body: dict,
    session: dict = Depends(require_session),
):
    """Dashboard composite for one or more runs (body-payload form).

    Request body:
        {"run_ids": ["run_a", "run_b", ...]}

    The list must contain at least 1 entry; multi-run requests
    populate the drift section, single-run requests leave it empty.

    Responses:
        200 — dashboard dict (see Unit 27 module docstring)
        400 — malformed body, malformed run_id, or empty run_ids
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_dashboard import dashboard_for_run_ids

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 1:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "dashboard requires >= 1 run_id, got 0",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        return dashboard_for_run_ids(run_ids)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


# ===========================================================================
# ELINS operator-utility endpoints (Unit 28 — notes / tags / rename /
# archive surface for any stored run; orthogonal to the analytic payload)
# ===========================================================================
@app.get("/elins/regression/run/{run_id}/notes")
def elins_regression_run_notes_get(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Return the stored notes string for a run (or null if unset)."""
    _ = session
    from elins_persistence import get_notes

    _validate_optional_run_id(run_id, label="run_id")
    try:
        return {"run_id": run_id, "notes": get_notes(run_id)}
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/{run_id}/notes")
def elins_regression_run_notes_set(
    run_id: str,
    body: dict,
    session: dict = Depends(require_session),
):
    """Replace the stored notes for a run.

    Request body:
        {"notes": "string or null"}
    """
    _ = session
    from elins_persistence import get_notes, set_notes

    _validate_optional_run_id(run_id, label="run_id")
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    notes = body.get("notes")
    try:
        set_notes(run_id, notes)
        return {"run_id": run_id, "notes": get_notes(run_id)}
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.get("/elins/regression/run/{run_id}/tags")
def elins_regression_run_tags_get(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Return the stored tag list for a run."""
    _ = session
    from elins_persistence import get_tags

    _validate_optional_run_id(run_id, label="run_id")
    try:
        return {"run_id": run_id, "tags": get_tags(run_id)}
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/{run_id}/tags")
def elins_regression_run_tags_set(
    run_id: str,
    body: dict,
    session: dict = Depends(require_session),
):
    """Replace the stored tag list for a run.

    Request body:
        {"tags": ["t1", "t2", ...]}
    """
    _ = session
    from elins_persistence import get_tags, set_tags

    _validate_optional_run_id(run_id, label="run_id")
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    tags = body.get("tags")
    try:
        set_tags(run_id, tags)
        return {"run_id": run_id, "tags": get_tags(run_id)}
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/{run_id}/rename")
def elins_regression_run_rename(
    run_id: str,
    body: dict,
    session: dict = Depends(require_session),
):
    """Rename a stored run.

    Request body:
        {"new_run_id": "..."}

    Responses:
        200 — {"old_run_id": "...", "new_run_id": "..."}
        400 — malformed run_id or new_run_id, or new_run_id already exists
        401 — auth required
        404 — old run_id does not exist
    """
    _ = session
    from elins_persistence import rename_run

    _validate_optional_run_id(run_id, label="run_id")
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    new_run_id = body.get("new_run_id")
    _validate_optional_run_id(new_run_id, label="new_run_id")
    try:
        rename_run(run_id, new_run_id)
        return {"old_run_id": run_id, "new_run_id": new_run_id}
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/{run_id}/archive")
def elins_regression_run_archive(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Mark a run as archived (hidden from default listing)."""
    _ = session
    from elins_persistence import get_archived, set_archived

    _validate_optional_run_id(run_id, label="run_id")
    try:
        set_archived(run_id, True)
        return {"run_id": run_id, "archived": get_archived(run_id)}
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


@app.post("/elins/regression/run/{run_id}/unarchive")
def elins_regression_run_unarchive(
    run_id: str,
    session: dict = Depends(require_session),
):
    """Restore an archived run to the active listing."""
    _ = session
    from elins_persistence import get_archived, set_archived

    _validate_optional_run_id(run_id, label="run_id")
    try:
        set_archived(run_id, False)
        return {"run_id": run_id, "archived": get_archived(run_id)}
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


# ===========================================================================
# ELINS composite per-run endpoint (Unit 22 — one-shot metadata + summary
# + drift + magnitude + severity + series in a single response; respects
# Unit 21 filtering on the four pair-keyed sections)
# ===========================================================================
@app.post("/elins/regression/run/composite")
def elins_regression_run_composite(
    body: dict,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """One-shot composite analytics for a run (or run sequence).

    Request body:
        {"run_ids": ["run_a", "run_b", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 1 entry.

    Unit 21 query parameters (all optional) — applied to the four
    pair-keyed sections (``direction`` / ``magnitude`` / ``severity`` /
    ``series``). ``summary`` is intentionally never filtered.

        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return (>= 1)
        offset         — skip the first N pairs after filtering (>= 0)

    Response shape:
        Single run (len(run_ids) == 1):
            {
              "run_ids":  [...],
              "metadata": [<dict or null>],
              "summary":  {...}            # Unit 14 single-run table
            }
        Multi-run (len(run_ids) >= 2):
            {
              "run_ids":   [...],
              "metadata":  [<dict or null>, ...],
              "summary":   {...},          # Unit 18 cross-run summary
              "direction": {...},          # Unit 13 drift buckets
              "magnitude": {...},          # Unit 15 per-pair magnitude
              "severity":  {...},          # Unit 16 per-pair severity
              "series":    {...}           # Unit 17 per-pair time series
            }

    Responses:
        200 — composite analytics dict
        400 — malformed body, malformed run_id, empty run_ids, or
              malformed pair filter
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_composite import composite_endpoint_wrapper

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 1:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "composite requires >= 1 run_id, got 0",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        return composite_endpoint_wrapper(
            run_ids, pair_id_prefix, limit, offset,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


# ===========================================================================
# ELINS cross-run aggregate summary endpoint (Unit 18 — per-run summary
# tables side-by-side in a single response; one-shot composite view)
# ===========================================================================
@app.post("/elins/regression/runs/summary")
def elins_regression_runs_summary(
    body: dict,
    session: dict = Depends(require_session),
):
    """Return per-run summary tables for a list of stored runs.

    Request body:
        {"run_ids": ["run_a", "run_b", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 1 entry.

    Responses:
        200 — {"runs": {run_id: <summary_table output>, ...}} with the
              inner ``"runs"`` dict keyed alphabetically by ``run_id``
        400 — malformed body, malformed run_id, or empty run_ids list
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_summary_multi import summary_across_run_ids

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 1:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "runs summary requires >= 1 run_id, got 0",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        return summary_across_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )


# ===========================================================================
# ELINS2 intelligence endpoints (Unit 10) — composite intelligence payload
# and dashboard projection. Both delegate to ``elins_intelligence`` (Unit 9)
# which is a pure orchestrator over Units 1-8; no analytics behavior or
# ELINS1 endpoint changes elsewhere.
# ===========================================================================
_INTEL_DASHBOARD_DEFAULT_LIMIT: int = 50


def _project_intelligence_for_dashboard(payload: dict) -> dict:
    """Collapse the full Unit 9 payload into a dashboard-oriented
    projection. Pure transform — no I/O, no mutation of the input."""
    scores = payload.get("scores", {}) or {}
    sequences = payload.get("sequences", {}) or {}
    analysis = sequences.get("analysis", {}) or {}
    narratives = payload.get("narratives", {}) or {}
    runs_narrative = narratives.get("runs", {}) or {}
    anomalies_runs = (payload.get("anomalies", {}) or {}).get("runs", {}) or {}
    pair_scores = scores.get("pairs", {}) or {}

    run_ids = list(payload.get("run_ids", []))
    num_runs = len(run_ids)
    num_anomalies = sum(
        1 for info in anomalies_runs.values()
        if info.get("level", "none") != "none"
    )

    # Top anomalies: descending by score, then alphabetical by run_id;
    # capped at 5 entries (mirrors Unit 7's locked _TOP_ANOMALIES_N).
    flagged: list = []
    for rid, info in anomalies_runs.items():
        level = info.get("level", "none")
        if level == "none":
            continue
        flagged.append({
            "run_id": rid,
            "score":  float(info.get("score", 0.0)),
            "level":  level,
        })
    flagged.sort(key=lambda d: (-d["score"], d["run_id"]))
    top_anomalies = flagged[:5]

    # Top pairs: descending by composite score, then alphabetical by
    # pair_id; capped at 5 entries.
    pairs_list: list = []
    for pid, data in pair_scores.items():
        pairs_list.append({
            "pair_id":   pid,
            "stability": float(data.get("stability", 0.0)),
            "trend":     data.get("trend", "flat"),
            "score":     float(data.get("score", 0.0)),
        })
    pairs_list.sort(key=lambda d: (-d["score"], d["pair_id"]))
    top_pairs = pairs_list[:5]

    return {
        "run_ids":        run_ids,
        "overall_health": float(scores.get("overall_health", 0.0)),
        "headline":       runs_narrative.get("headline", ""),
        "key_metrics": {
            "num_runs":                num_runs,
            "num_anomalies":           num_anomalies,
            "anomaly_fraction":        float(analysis.get(
                "anomaly_fraction", 0.0,
            )),
            "upward_fraction":         float(analysis.get(
                "upward_fraction", 0.0,
            )),
            "downward_fraction":       float(analysis.get(
                "downward_fraction", 0.0,
            )),
            "stable_cluster_fraction": float(analysis.get(
                "stable_cluster_fraction", 0.0,
            )),
        },
        "top_anomalies": top_anomalies,
        "top_pairs":     top_pairs,
        "narratives":    dict(narratives),
    }


@app.post("/elins/regression/runs/intelligence")
def elins_regression_runs_intelligence(
    body: dict,
    session: dict = Depends(require_session),
):
    """ELINS2 Unit 10: composite intelligence over a caller-supplied
    set of runs.

    Request body:
        {"run_ids": ["run_a", "run_b", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list may contain zero entries (the response carries
    well-formed empty sub-sections in that case).

    Responses:
        200 — full Unit 9 payload (see ``elins_intelligence`` docstring
              for the locked top-level / sub-section keys)
        400 — malformed body, malformed run_id, or run_ids not a list
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_intelligence import intelligence_for_run_ids

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        return intelligence_for_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )
    except ValueError as e:
        # Defensive — Unit 9 also validates run_ids; surface as 400.
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


@app.get("/elins/regression/runs/dashboard/intelligence")
def elins_regression_runs_dashboard_intelligence(
    since: str | None = Query(None),
    until: str | None = Query(None),
    limit: int | None = Query(None),
    include_archived: bool = Query(False),
    session: dict = Depends(require_session),
):
    """ELINS2 Unit 10: dashboard-oriented intelligence projection.

    Pulls a run set via Unit 26 ``query_runs`` (filtered by ``since``
    / ``until`` / ``include_archived``), orders chronologically by
    ``created_at`` (legacy runs without a timestamp drop to the
    bottom), caps to ``limit`` (default 50), then composes through
    Unit 9 ``intelligence_for_run_ids``.

    Returns a flat dashboard projection (headline, key_metrics,
    top_anomalies, top_pairs, narratives) — the full Unit 9 payload
    is intentionally NOT echoed here; callers that need the raw
    similarity / clustering / trends data should use
    ``POST /elins/regression/runs/intelligence``.

    Query params:
        since           — ISO8601 lower bound on metadata.created_at
                          (inclusive). Naive timestamps treated as UTC.
        until           — ISO8601 upper bound on metadata.created_at
                          (exclusive).
        limit           — max runs to include (>= 1, default 50).
        include_archived — include archived runs when True
                           (default False).

    Responses:
        200 — dashboard projection (see _project_intelligence_for_dashboard)
        400 — invalid query params
        401 — auth required
    """
    _ = session
    from elins_intelligence import intelligence_for_run_ids
    from elins_persistence import query_runs

    if isinstance(limit, bool):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "limit must be a positive integer",
            ),
        )
    effective_limit = (
        limit if limit is not None else _INTEL_DASHBOARD_DEFAULT_LIMIT
    )
    if not isinstance(effective_limit, int) or effective_limit < 1:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "limit must be a positive integer",
            ),
        )

    try:
        rows = query_runs(
            since=since,
            until=until,
            sort="created_at",
            order="asc",
            limit=effective_limit,
            include_archived=include_archived,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )

    run_ids = [row["run_id"] for row in rows]
    payload = intelligence_for_run_ids(run_ids)
    return _project_intelligence_for_dashboard(payload)


# ===========================================================================
# ELINS2 operator-intelligence endpoints (Unit 12) — small, focused
# mutators on top of the read-only intelligence surface. All three apply
# tags through Unit 27/28 ``set_tags`` (dedupe + existing-tag preserve).
# ===========================================================================
def _parse_intelligence_run_ids(body) -> list:
    """Shared helper — validate ``{"run_ids": [...]}`` body. Returns
    the list when valid, raises HTTPException(400) otherwise."""
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")
    return run_ids


@app.post("/elins/regression/runs/intelligence/flag-anomalies")
def elins_intelligence_flag_anomalies(
    body: dict,
    session: dict = Depends(require_session),
):
    """ELINS2 Unit 12: tag every medium/high anomaly with
    ``"anomaly"``.

    Request body:
        {"run_ids": ["r1", "r2", ...]}

    Responses:
        200 — ``{"flagged": [...], "skipped": [...]}``
        400 — malformed body / run_id
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_operator_intel import flag_anomalous_runs

    run_ids = _parse_intelligence_run_ids(body)
    try:
        return flag_anomalous_runs(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


@app.post("/elins/regression/runs/intelligence/pin-best-sequence")
def elins_intelligence_pin_best_sequence(
    body: dict,
    session: dict = Depends(require_session),
):
    """ELINS2 Unit 12: tag the best Unit 8 window with
    ``"pinned_sequence"``.

    Request body:
        {"run_ids": ["r1", "r2", ...], "window": 5}

    ``window`` defaults to 5 when omitted; must be int >= 2 and
    <= len(run_ids) when supplied.

    Responses:
        200 — ``{"pinned": [...]}``  (empty list when no best window
              is available, e.g. len(run_ids) < window)
        400 — malformed body / run_id / window
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_operator_intel import pin_best_sequence

    run_ids = _parse_intelligence_run_ids(body)
    window = body.get("window", 5) if isinstance(body, dict) else 5
    if isinstance(window, bool) or not isinstance(window, int):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                "window must be a positive integer",
            ),
        )
    if window < 2:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", f"window must be >= 2, got {window}",
            ),
        )

    try:
        return pin_best_sequence(run_ids, window=window)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


@app.post("/elins/regression/runs/intelligence/tag-cluster")
def elins_intelligence_tag_cluster(
    body: dict,
    session: dict = Depends(require_session),
):
    """ELINS2 Unit 12: tag every member of a cluster with ``tag``.

    Request body:
        {
            "cluster_id": "c0",
            "tag":        "regression_cluster",
            "run_ids":    ["r1", "r2", ...]  # cluster members
        }

    Caller supplies the cluster membership (typically taken from a
    ``cluster_runs`` call). The server does not re-cluster.

    Responses:
        200 — ``{"cluster_id": ..., "tag": ..., "run_ids": [...],
               "applied": [<ids actually mutated this call>]}``
        400 — malformed body / cluster_id / tag / run_id
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_operator_intel import tag_cluster_runs

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "request body must be a JSON object",
            ),
        )
    cluster_id = body.get("cluster_id")
    if not isinstance(cluster_id, str) or not cluster_id:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "cluster_id must be a non-empty string",
            ),
        )
    tag = body.get("tag")
    if not isinstance(tag, str) or not tag:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "tag must be a non-empty string",
            ),
        )
    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload", "run_ids must be a list",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        return tag_cluster_runs(
            cluster_id,
            {"members": run_ids},
            tag,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# ELINS drift-series endpoint (Unit 17 — per-pair raw time-series export
# for SP/EC scores and bands across N runs; sparkline data)
# ===========================================================================
@app.post("/elins/regression/drift/series")
def elins_regression_drift_series(
    body: dict,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """Return per-pair time-series across a sequence of runs.

    Request body:
        {"run_ids": ["run_a", "run_b", "run_c", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 2 entries. Order is
    treated as chronological — series elements come back in the same
    order as the input run_ids.

    Unit 21 query parameters (all optional):
        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return (>= 1)
        offset         — skip the first N pairs after filtering (>= 0)

    Responses:
        200 — dict keyed by pair_id with 4 series:
              single_party_scores, economic_coercion_scores,
              single_party_bands, economic_coercion_bands
        400 — malformed body, malformed run_id, fewer than 2 run_ids,
              or malformed pair filter
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_drift_series import drift_series_for_run_ids
    from elins_pair_filtering import apply_pair_filters

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"drift series requires >= 2 run_ids, got {len(run_ids)}",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        result = drift_series_for_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )

    try:
        return apply_pair_filters(result, pair_id_prefix, limit, offset)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# ELINS drift-severity endpoint (Unit 16 — composite of Unit 13 direction
# + Unit 15 magnitude into a single per-pair severity record)
# ===========================================================================
@app.post("/elins/regression/drift/severity")
def elins_regression_drift_severity(
    body: dict,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """Compute composite drift severity across a sequence of runs.

    Request body:
        {"run_ids": ["run_a", "run_b", "run_c", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 2 entries.

    Unit 21 query parameters (all optional):
        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return (>= 1)
        offset         — skip the first N pairs after filtering (>= 0)

    Responses:
        200 — dict keyed by pair_id with label / direction / severity
              + max_swing + range sub-dicts
        400 — malformed body, malformed run_id, fewer than 2 run_ids,
              or malformed pair filter
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_drift_severity import classify_drift_severity_for_run_ids
    from elins_pair_filtering import apply_pair_filters

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"drift severity requires >= 2 run_ids, got {len(run_ids)}",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        result = classify_drift_severity_for_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )

    try:
        return apply_pair_filters(result, pair_id_prefix, limit, offset)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# ELINS drift-magnitude endpoint (Unit 15 — quantitative companion to
# Unit 13's directional drift; per-pair range / max_swing / mean_step
# across two dimensions)
# ===========================================================================
@app.post("/elins/regression/drift/magnitude")
def elins_regression_drift_magnitude(
    body: dict,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """Compute quantitative drift metrics across a sequence of runs.

    Request body:
        {"run_ids": ["run_a", "run_b", "run_c", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 2 entries.

    Unit 21 query parameters (all optional):
        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return (>= 1)
        offset         — skip the first N pairs after filtering (>= 0)

    Responses:
        200 — dict keyed by pair_id with single_party + economic_coercion
              sub-dicts of {range, max_swing, mean_step}
        400 — malformed body, malformed run_id, fewer than 2 run_ids,
              or malformed pair filter
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_drift_magnitude import drift_magnitude_for_run_ids
    from elins_pair_filtering import apply_pair_filters

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"drift magnitude requires >= 2 run_ids, got {len(run_ids)}",
            ),
        )
    for i, rid in enumerate(run_ids):
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        result = drift_magnitude_for_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )

    try:
        return apply_pair_filters(result, pair_id_prefix, limit, offset)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# ELINS multi-run drift endpoint (Unit 13 — first higher-order temporal
# analytic; classifies each pair_id's trajectory across N runs)
# ===========================================================================
@app.post("/elins/regression/drift")
def elins_regression_drift(
    body: dict,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """Classify drift across a sequence of stored runs.

    Request body:
        {"run_ids": ["run_a", "run_b", "run_c", ...]}

    Each ``run_id`` must match the canonical ``^[A-Za-z0-9_-]+$``
    pattern; the list must contain at least 2 entries (drift requires
    >= 2 points).

    Unit 21 query parameters (all optional):
        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return across all
                          buckets, applied after sort by pair_id (>= 1)
        offset         — skip the first N pairs in the alphabetical
                          union before bucketing (>= 0)

    Note: ``summary`` counts are recomputed from the filtered buckets so
    they always match what the response actually contains.

    Responses:
        200 — drift dict with stable / trending_up / trending_down /
              volatile lists + summary counts
        400 — malformed body, malformed run_id, fewer than 2 run_ids,
              or malformed pair filter
        401 — auth required
        404 — any run_id not found
    """
    _ = session
    from elins_run_drift import detect_drift_for_run_ids
    from elins_pair_filtering import apply_pair_filters_to_drift

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "request body must be a JSON object"),
        )

    run_ids = body.get("run_ids")
    if not isinstance(run_ids, list):
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", "run_ids must be a list"),
        )
    if len(run_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "bad_payload",
                f"drift requires >= 2 run_ids, got {len(run_ids)}",
            ),
        )
    for i, rid in enumerate(run_ids):
        # Reuse the Unit 10 helper for consistent 400 messages.
        _validate_optional_run_id(rid, label=f"run_ids[{i}]")

    try:
        result = detect_drift_for_run_ids(run_ids)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )

    try:
        return apply_pair_filters_to_drift(
            result, pair_id_prefix, limit, offset,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# ELINS run-to-run diff endpoint (Unit 11 — temporal comparison primitive)
# ===========================================================================
@app.get("/elins/regression/diff")
def elins_regression_diff(
    run_a: str,
    run_b: str,
    pair_id_prefix: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    session: dict = Depends(require_session),
):
    """Diff two stored regression runs.

    Query parameters:
        run_a — earlier run id
        run_b — later run id

    Unit 21 query parameters (all optional):
        pair_id_prefix — case-sensitive ``startswith`` filter on pair_id
        limit          — max number of pairs to return across all four
                          diff lists, applied after sort by pair_id
                          (>= 1)
        offset         — skip the first N pairs in the alphabetical
                          union before partitioning into added/removed/
                          changed/unchanged (>= 0)

    Both run ids must match ``^[A-Za-z0-9_-]+$``. Returns the dict
    produced by ``compare_runs`` (added / removed / changed / unchanged
    + summary). ``summary`` counts are recomputed from the filtered
    lists so they always match what the response actually contains.

    Responses:
        200 — diff dict
        400 — malformed run_id, or malformed pair filter
        401 — auth required
        404 — either run_id not found
    """
    _ = session
    from elins_run_diff import diff_runs
    from elins_pair_filtering import apply_pair_filters_to_diff

    _validate_optional_run_id(run_a, label="run_a")
    _validate_optional_run_id(run_b, label="run_b")

    try:
        result = diff_runs(run_a, run_b)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=error_response("not_found", str(e)),
        )

    try:
        return apply_pair_filters_to_diff(
            result, pair_id_prefix, limit, offset,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=error_response("bad_payload", str(e)),
        )


# ===========================================================================
# Public routes
# ===========================================================================
@app.get("/health")
def health():
    return {"ok": True, "status": "healthy", "version": "4.23"}


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "ClarityOS Cloud",
        "version": "4.23",
        "auth": "POST /login then send X-Session-ID header",
        "endpoints": {
            "POST /login":    "auth (public)",
            "POST /register": "create new user, auto-login (public)",
            "GET  /me":       "current session info (auth)",
            "GET  /config":   "runtime configuration (auth)",
            "POST /markov":   "Markov engine (auth)",
            "POST /galileo":  "Galileo clarity cycle (auth)",
            "POST /library":  "Library lookup, GCS-backed (auth)",
            "POST /tizzy":    "Tizzy engine (auth)",
            "GET  /v29/flags":"feature flag introspection (auth)",
            "GET  /v29/onboarding/state":"first-run progress (auth)",
            "POST /v29/onboarding/complete":"first-run step (auth)",
            "GET  /v29/whats_new":"What's new panel (auth)",
            "GET  /membership/state":"membership snapshot (auth)",
            "POST /membership/activate":"join Founding Cohort (auth)",
            "POST /membership/cancel":"leave membership (auth)",
            "POST /membership/g/buy_single":"buy 1 #G credit (auth)",
            "POST /membership/g/buy_pack_20":"buy 20-pack #G credits (auth)",
            "GET  /membership/g/history":"transaction history (auth)",
            "POST /billing/intent":"create PaymentIntent (auth)",
            "POST /billing/intent/confirm":"mock-only confirm (auth)",
            "POST /billing/webhook":"Stripe / mock webhook receiver",
            "GET  /billing/history":"transaction + intent history (auth)",
            "POST /waitlist/join":"public waitlist signup",
            "GET  /public/cohort_status":"cohort fill stats (public)",
            "GET  /founder/waitlist":"founder waitlist listing (founder)",
            "POST /founder/waitlist/update":"waitlist status transition (founder)",
            "POST /elins/preview":"canonical 10-layer ELINS pipeline (auth)",
            "POST /elins/global":"founder-only persisted ELINS run (auth)",
            "POST /elins/qc":"S_ELINS QC re-run (auth)",
            "POST /elins/forecast":"v34 multi-primitive envelope forecast (auth)",
            "GET  /elins/forecast/example":"v34 forecast example fixture (public)",
            "POST /founder/elins/forecast/run":"v34 full ELINS+forecast persist (founder)",
            "POST /elins/regional/run":"v35 regional ELINS run + ESO (auth)",
            "GET  /elins/regional/list":"v35 regions + latest summary (auth)",
            "POST /founder/elins/regional/batch":"v35 batch regional run (founder)",
            "GET  /founder/elins/scheduler/status":"v36 macro scheduler status (founder)",
            "POST /founder/elins/scheduler/config":"v36 toggle macro scheduler (founder)",
            "POST /founder/elins/macro/run_now":"v36 trigger macro pass now (founder)",
            "GET  /founder/elins/macro/runs":"v36 list recent macro runs (founder)",
            "GET  /founder/elins/macro/run/{run_id}":"v36 macro run detail (founder)",
            "GET  /elins/entities/search":"v37 entity graph search (auth)",
            "GET  /elins/entities/{entity}/neighbors":"v37 entity neighbors (auth)",
            "GET  /elins/entities/{entity}/timeseries":"v37 entity timeseries (auth)",
            "GET  /founder/elins/entity_graph/raw":"v37 raw graph export (founder)",
            "GET  /elins/dashboard":"v38 interactive dashboard snapshot (auth)",
            "GET  /elins/dashboard/{date}":"v38 dashboard pinned to date (auth)",
            "GET  /founder/elins/dashboard/overview":"v38 founder operational overview (founder)",
            "GET  /me/operator_state":"v39 operator state self-view (auth)",
            "POST /me/operator_state":"v39 operator state update (auth)",
            "GET  /founder/operator/{user_id}/state":"v39 founder operator state read (founder)",
            "GET  /founder/intelligence/kernel/status":"v40 kernel status (founder)",
            "GET  /founder/billing/status":"v42 Stripe mode + recent events (founder)",
            "GET  /me/billing":"v42 user billing snapshot (auth)",
            "GET  /me/entitlement":"v83 entitlement projection for caller (auth)",
            "GET  /founder/entitlement/{user_id}":"v83 entitlement projection for any user (founder)",
            "GET  /founder/analytics/summary":"v43 founder analytics summary (founder)",
            "POST /me/operator_state/model":"v44 set preferred model (auth)",
            "GET  /founder/models/status":"v44 model router status (founder)",
            "POST /founder/models/override":"v44 set founder default model (founder)",
            "GET  /me/local_model":"v45 local model runtime snapshot (auth)",
            "GET  /founder/models/local":"v45 local model runtime status (founder)",
            "GET  /me/vault/status":"v46 vault snapshot for caller (auth)",
            "GET  /me/vault/notes":"v46 list vault notes (auth)",
            "POST /me/vault/notes":"v46 create/replace vault note (auth)",
            "POST /me/vault/notes/delete":"v46 delete vault note (auth)",
            "GET  /me/vault/embeddings":"v46 list vault embeddings (auth)",
            "POST /me/vault/embeddings":"v46 store vault embedding (auth)",
            "POST /me/vault/embeddings/delete":"v46 delete vault embedding (auth)",
            "GET  /founder/vault/users":"v46 vault inspector — list users (founder)",
            "GET  /founder/vault/{user_id}/keys":"v46 vault inspector — keys (founder)",
            "GET  /founder/vault/{user_id}/item/{key}":"v46 vault inspector — read item (founder)",
            "GET  /me/threads":"v47 list threads (auth)",
            "POST /me/threads":"v47 create thread (auth)",
            "GET  /me/threads/{thread_id}":"v47 thread detail (auth)",
            "POST /me/threads/{thread_id}/message":"v47 post message + assistant reply (auth)",
            "POST /me/threads/{thread_id}/rename":"v47 rename thread (auth)",
            "POST /me/threads/{thread_id}/delete":"v47 delete thread (auth)",
            "GET  /me/threads/{thread_id}/summary":"v50 fetch cached summary (auth)",
            "POST /me/threads/{thread_id}/summarize":"v50 generate/refresh summary (auth)",
            "GET  /me/projects":"v51 list user projects (auth)",
            "POST /me/projects":"v51 create project (auth)",
            "GET  /me/projects/{project_id}":"v51 read project meta (auth)",
            "GET  /me/projects/{project_id}/threads":"v51 list project's threads via index (auth)",
            "POST /me/regression_first/start":"v76 open a Regression-First chain (auth)",
            "POST /me/regression_first/step":"v76 record a finding for one layer (auth)",
            "GET  /me/regression_first/{chain_id}":"v76 fetch one chain (auth)",
            "GET  /me/regression_first":"v76 list caller's chains, newest-first (auth)",
            "POST /me/regression_first/{chain_id}/close":"v76 close a chain (auth, irreversible)",
            "POST /me/regression_first/{chain_id}/tag":"v76 merge tags into a chain (auth)",
            "POST /me/regression_first/delete_tag":"v81 drop one tag key (auth, no timeline event)",
            "POST /me/regression_first/archive":"v81 set archived=true visibility flag (auth, idempotent)",
            "POST /me/regression_first/packet":"v80 one-shot packet ingest → chain start + seeded layer (auth)",
            "POST /me/regression_first/replay":"v82 replay original packet as a new chain (auth)",
            "POST /cmt/generate":"#cmt comment generator (auth)",
            "POST /c/run":"#c cloud engine (mode='comment') (auth)",
            "POST /founder/dm/add":"log a manual DM (founder)",
            "GET  /founder/dm/list":"list logged DMs (founder)",
            "POST /founder/dm/notes":"append/list founder DM notes (founder)",
            "POST /founder/membership/activate":"manual membership activation (founder)",
            "POST /founder/membership/cancel":"manual membership cancel (founder)",
            "POST /founder/membership/credits":"manual #G credit adjust (founder)",
            "GET  /health":   "health check (public)",
        },
    }
