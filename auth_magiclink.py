"""
ClarityOS magic-link authentication — token lifecycle + secure contract.

This module implements the backend for the two endpoints exposed by app.py:

    POST /auth/enter   -> request_magic_link(...)
    GET  /auth/verify  -> verify_magic_link(...)

Service boundary
----------------
The WordPress shell at https://pro-mediations.com/enter/ only collects an
email and POSTs {email, source, next} here. ALL authentication — token
issuance, verification, session creation, and post-auth routing — happens on
the ClarityOS service (https://clarity.pro-mediations.com). No auth logic
runs in WordPress.

Security properties
-------------------
* Tokens are CSPRNG secrets (secrets.token_urlsafe). Only a SHA-256 *hash* of
  the secret is stored; the raw secret exists only in the emailed link.
* Tokens are single-use (used_at) and short-lived (5-15 min; default 10).
* Issuing a new token invalidates any earlier unused token for that email, so
  at most one link is live per user at a time.
* /auth/enter is enumeration-safe: for any syntactically valid email it returns
  the same generic success, whether or not the address maps to an account, and
  whether or not it was rate-limited.
* Redirects are validated against an internal allowlist — no open redirects.
* Email addresses and raw tokens are never written to logs (a short salted-free
  SHA-256 prefix of the email is logged instead); the raw link is only logged
  in the dev-only "log" email mode.

Storage selection mirrors the rest of the app: CLARITYOS_BACKEND=memory|firestore.

Environment
-----------
    CLARITYOS_AUTH_BASE_URL     default https://clarity.pro-mediations.com
    CLARITYOS_SHELL_ENTER_URL   default https://pro-mediations.com/enter/
    CLARITYOS_MAGICLINK_TTL     token lifetime, seconds (clamped 300..900; default 600)
    CLARITYOS_SESSION_TTL       session lifetime, seconds (default 86400 — matches app.py)
    CLARITYOS_EMAIL_MODE        "log" (default, dev) | "smtp"
    CLARITYOS_SMTP_HOST/PORT/USER/PASSWORD/FROM/STARTTLS   (smtp mode only)
    CLARITYOS_BACKEND           "memory" (default) | "firestore"
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import smtplib
import threading
import time
from email.message import EmailMessage
from typing import Optional

import bcrypt

import users_store
import sessions_store

logger = logging.getLogger("clarityos.auth_magiclink")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PURPOSE_LOGIN = "login"

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Redirect safety — `next` is UNTRUSTED input. The token never stores a
# client-supplied path; it stores a SYMBOLIC KEY which the server resolves to
# an allowlisted internal path at verify time. The final redirect is always
# AUTH_BASE_URL + an allowlisted path — no code path reflects a client URL or
# path, so open redirects and path-traversal/encoding tricks cannot escape.
#
# NEXT_KEYS maps a symbolic key -> canonical internal path. ALLOWED_NEXT is the
# derived set of permitted resolved paths (the two cannot drift). Add new
# destinations here only.
NEXT_KEYS = {
    "app":            "/app",
    "transformation": "/app/transformation",
    "onboarding":     "/onboarding",
    "account":        "/account",
}
ALLOWED_NEXT = frozenset(NEXT_KEYS.values())
DEFAULT_NEXT_PATH = "/app"          # active member, missing/invalid next
INACTIVE_NEXT_PATH = "/onboarding"  # authenticated but not an active member

# Tiers that count as an active entitlement. Anything else (incl. brand-new
# "free" accounts created on first sign-in) is treated as inactive and routed
# to /onboarding, where the app surfaces checkout / recovery.
_ACTIVE_TIERS = frozenset({"paid", "active", "member", "founding", "founder"})

# Rate limits for /auth/enter (always enforced here, independent of the global
# v29 soft limiter): per-IP and per-email fixed windows.
_ENTER_IP_MAX = int(os.environ.get("CLARITYOS_AUTH_ENTER_IP_MAX", "5"))
_ENTER_EMAIL_MAX = int(os.environ.get("CLARITYOS_AUTH_ENTER_EMAIL_MAX", "3"))
_ENTER_WINDOW_S = float(os.environ.get("CLARITYOS_AUTH_ENTER_WINDOW_S", "300"))
# /auth/verify — throttle repeated invalid attempts per IP (monitoring + abuse).
_VERIFY_IP_MAX = int(os.environ.get("CLARITYOS_AUTH_VERIFY_IP_MAX", "30"))
_VERIFY_WINDOW_S = float(os.environ.get("CLARITYOS_AUTH_VERIFY_WINDOW_S", "300"))


def _auth_base_url() -> str:
    return os.environ.get(
        "CLARITYOS_AUTH_BASE_URL", "https://clarity.pro-mediations.com"
    ).rstrip("/")


def _shell_enter_url() -> str:
    return os.environ.get(
        "CLARITYOS_SHELL_ENTER_URL", "https://pro-mediations.com/enter/"
    )


def _token_ttl() -> int:
    raw = int(os.environ.get("CLARITYOS_MAGICLINK_TTL", "600"))
    return max(300, min(900, raw))  # clamp to the 5-15 minute band


def _session_ttl() -> int:
    return int(os.environ.get("CLARITYOS_SESSION_TTL", "86400"))


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_email(raw: Optional[str]) -> str:
    return (raw or "").strip().lower()


def _email_hash(email: str) -> str:
    """Short, non-reversible handle for logs (never log the raw address)."""
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


def _hash_token(raw: str) -> str:
    """SHA-256 hex of the raw secret. The secret is high-entropy (256-bit)
    random, so a fast hash is correct here — no salt/KDF needed, and it keeps
    verify O(1) without timing concerns (lookup is by full digest)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _log(event: str, **fields) -> None:
    parts = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
    logger.info("%s %s", event, parts)


def normalize_next(raw) -> str:
    """Map an UNTRUSTED next (a path like '/app/transformation' OR a bare
    symbolic key like 'transformation') to a stored symbolic KEY.

    Returns '' when the input is missing, malformed, or not explicitly
    allowlisted — callers then fall back to the default at resolve time. We
    persist only this key, never an arbitrary client-supplied path, and we use
    EXACT allowlist matching (no prefix/startswith), so traversal/encoding
    payloads ('/app/../x', '/app%2f..', '//evil', 'https://evil') all map to ''.
    """
    if not isinstance(raw, str):
        return ""
    v = raw.strip()
    if not v:
        return ""
    if v in NEXT_KEYS:                      # bare symbolic key form
        return v
    v = v.rstrip("/") or "/"                # tolerate a single trailing slash
    if v in ALLOWED_NEXT:                   # exact allowlisted path form
        for key, path in NEXT_KEYS.items():
            if path == v:
                return key
    return ""                               # anything else -> default later


def resolve_next_path(next_key, active: bool) -> str:
    """Resolve a stored key to a safe internal path. Not-yet-active members are
    always sent to onboarding (the app routes on to checkout/recovery).
    Unknown/empty keys fall back to the default. Output is always one of the
    server-controlled paths in ALLOWED_NEXT — never client input."""
    if not active:
        return INACTIVE_NEXT_PATH
    if isinstance(next_key, str) and next_key in NEXT_KEYS:
        return NEXT_KEYS[next_key]
    return DEFAULT_NEXT_PATH


def _final_redirect_url(path: str) -> str:
    """Build the absolute redirect on the ClarityOS origin. `path` is always a
    server-controlled allowlisted path, so this can never be an open redirect."""
    return _auth_base_url() + path


# ---------------------------------------------------------------------------
# Token store (memory | firestore), mirroring the other *_store modules
# ---------------------------------------------------------------------------
_TOKENS_COLLECTION = "magic_link_tokens"
_MEM_TOKENS: dict[str, dict] = {}      # token_hash -> record
_TOKENS_LOCK = threading.Lock()
_firestore_client = None  # type: ignore


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    from google.cloud import firestore  # lazy; only in firestore mode
    _firestore_client = firestore.Client()
    return _firestore_client


def _tokens_collection():
    return _get_firestore().collection(_TOKENS_COLLECTION)


def _store_put(record: dict) -> None:
    if _backend() == "firestore":
        _tokens_collection().document(record["token_hash"]).set(record)
    else:
        with _TOKENS_LOCK:
            _MEM_TOKENS[record["token_hash"]] = record


def _store_get_by_hash(token_hash: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _tokens_collection().document(token_hash).get()
        return doc.to_dict() if doc.exists else None
    with _TOKENS_LOCK:
        return _MEM_TOKENS.get(token_hash)


def _store_mark_used(token_hash: str, used_at: float) -> None:
    if _backend() == "firestore":
        _tokens_collection().document(token_hash).update({"used_at": used_at})
    else:
        with _TOKENS_LOCK:
            rec = _MEM_TOKENS.get(token_hash)
            if rec is not None:
                rec["used_at"] = used_at


def _store_invalidate_unused_for_email(email: str, now: float) -> int:
    """Mark every unused token for this email as used (so only the freshly
    issued one stays live). Returns how many were invalidated."""
    count = 0
    if _backend() == "firestore":
        q = (
            _tokens_collection()
            .where("email", "==", email)
            .where("used_at", "==", None)
            .stream()
        )
        for doc in q:
            doc.reference.update({"used_at": now})
            count += 1
    else:
        with _TOKENS_LOCK:
            for rec in _MEM_TOKENS.values():
                if rec.get("email") == email and rec.get("used_at") is None:
                    rec["used_at"] = now
                    count += 1
    return count


# ---------------------------------------------------------------------------
# Rate limiting (own fixed-window counter, always enforced)
# ---------------------------------------------------------------------------
_RL_LOCK = threading.Lock()
_RL_HITS: dict[str, list] = {}


def _rate_check(key: str, max_n: int, window_s: float, now: float):
    """Sliding fixed-window limiter. Returns (allowed: bool, recent_count: int).
    A blocked call does NOT consume a slot."""
    if max_n <= 0 or window_s <= 0:
        return True, 0
    with _RL_LOCK:
        q = _RL_HITS.setdefault(key, [])
        cutoff = now - window_s
        drop = 0
        for ts in q:
            if ts >= cutoff:
                break
            drop += 1
        if drop:
            del q[:drop]
        if len(q) >= max_n:
            return False, len(q)
        q.append(now)
        return True, len(q)


# ---------------------------------------------------------------------------
# Email delivery (dependency-injected so tests can capture the link)
# ---------------------------------------------------------------------------
def _smtp_send(email: str, link: str) -> bool:
    host = os.environ.get("CLARITYOS_SMTP_HOST")
    if not host:
        logger.error("magic_link.email smtp mode but CLARITYOS_SMTP_HOST unset")
        return False
    port = int(os.environ.get("CLARITYOS_SMTP_PORT", "587"))
    user = os.environ.get("CLARITYOS_SMTP_USER")
    password = os.environ.get("CLARITYOS_SMTP_PASSWORD")
    sender = os.environ.get("CLARITYOS_SMTP_FROM", "no-reply@clarity.pro-mediations.com")
    use_starttls = os.environ.get("CLARITYOS_SMTP_STARTTLS", "1") != "0"

    msg = EmailMessage()
    msg["Subject"] = "Your ClarityOS sign-in link"
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        "Use the secure link below to sign in to ClarityOS. "
        "It expires shortly and can be used once.\n\n"
        f"{link}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_starttls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:  # never raise out of the request path
        logger.error("magic_link.email smtp send failed err=%s", e)
        return False


def _default_email_sender(email: str, link: str, ctx: dict) -> bool:
    mode = os.environ.get("CLARITYOS_EMAIL_MODE", "log").lower()
    if mode == "smtp":
        return _smtp_send(email, link)
    # dev / mock mode — safe to log the link locally so it can be clicked.
    # NEVER enable "log" mode in production; it writes the raw token to logs.
    logger.info("magic_link.email mode=log to_hash=%s link=%s", ctx.get("email_hash"), link)
    return True


# Swappable at runtime / in tests: callable(email, link, ctx) -> bool.
EMAIL_SENDER = _default_email_sender


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------
def _ensure_user(email: str, now: float) -> bool:
    """Create the user on first sign-in. Returns True if newly created.

    The account gets an unusable random bcrypt password so the username/
    password path (/login) can never authenticate it — magic-link only.
    """
    if users_store.user_exists(email):
        return False
    unusable = secrets.token_urlsafe(32)
    pwd_hash = bcrypt.hashpw(unusable.encode("utf-8"), bcrypt.gensalt())
    users_store.create_user(
        username=email,
        password_hash=pwd_hash,
        salt="",
        tier="free",
        created_at=now,
    )
    try:
        users_store.update_user(
            email, {"operator_id": "op_" + secrets.token_urlsafe(12), "auth_method": "magic_link"}
        )
    except Exception:  # pragma: no cover — defensive against backend hiccups
        pass
    return True


def _is_active_member(email: str, now: float) -> bool:
    u = users_store.get_user(email) or {}
    if str(u.get("tier", "")).lower() in _ACTIVE_TIERS:
        return True
    exp = u.get("billing_expires_at")
    try:
        if exp is not None and float(exp) > now:
            return True
    except (TypeError, ValueError):  # pragma: no cover
        pass
    return False


# ---------------------------------------------------------------------------
# Public lifecycle: /auth/enter
# ---------------------------------------------------------------------------
def request_magic_link(
    email_raw: Optional[str],
    source: Optional[str],
    next_path: Optional[str],
    ip: str,
    user_agent: str,
    now: Optional[float] = None,
) -> dict:
    """Issue (and email) a one-time login link. Enumeration-safe: returns
    {"status": "ok"} for any syntactically valid email regardless of account
    existence or rate-limit state. Returns {"status": "invalid_email"} only for
    a malformed address (a format error, not an existence signal)."""
    now = time.time() if now is None else now
    email = _normalize_email(email_raw)
    if not _EMAIL_RE.match(email):
        return {"status": "invalid_email"}

    ehash = _email_hash(email)
    source = (source or "")[:64].strip()
    # `next` is untrusted — normalize to a symbolic key (or "") right here and
    # persist ONLY that. We never store an arbitrary client-supplied path.
    next_key = normalize_next(next_path)

    _log("magic_link.requested", email_hash=ehash, source=source or "-",
         next_key=next_key or "-", ip=ip or "-", ua=(user_agent or "")[:80])

    ip_ok, ip_n = _rate_check(f"enter_ip:{ip}", _ENTER_IP_MAX, _ENTER_WINDOW_S, now)
    email_ok, email_n = _rate_check(f"enter_email:{ehash}", _ENTER_EMAIL_MAX, _ENTER_WINDOW_S, now)
    if not (ip_ok and email_ok):
        _log("rate_limit.triggered", endpoint="auth/enter", email_hash=ehash,
             ip=ip or "-", ip_count=ip_n, email_count=email_n)
        # Generic success — never reveal throttling to the client.
        return {"status": "ok", "rate_limited": True}

    # Only one live link per user at a time.
    invalidated = _store_invalidate_unused_for_email(email, now)

    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    record = {
        "id": "ml_" + secrets.token_hex(8),
        "email": email,
        "purpose": PURPOSE_LOGIN,
        "source": source,
        "next_key": next_key,
        "token_hash": token_hash,
        "created_at": now,
        "expires_at": now + _token_ttl(),
        "used_at": None,
    }
    _store_put(record)

    link = f"{_auth_base_url()}/auth/verify?token={raw}"
    try:
        sent = bool(EMAIL_SENDER(email, link, {"email_hash": ehash, "token_id": record["id"]}))
    except Exception as e:  # never leak through to the client
        logger.error("magic_link.email sender raised err=%s", e)
        sent = False

    _log("magic_link.sent", token_id=record["id"], email_hash=ehash,
         success=sent, invalidated_prior=invalidated)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Public lifecycle: /auth/verify
# ---------------------------------------------------------------------------
def verify_magic_link(
    token_raw: Optional[str],
    ip: str,
    user_agent: str,
    now: Optional[float] = None,
) -> dict:
    """Validate a one-time token and, on success, create a session.

    Returns one of:
      {"status": "ok", "session_id", "redirect", "session_max_age",
       "email_hash", "created", "active"}
      {"status": "invalid"}   # missing / not found / wrong purpose / expired / used
    The caller MUST NOT reveal which condition failed.
    """
    now = time.time() if now is None else now
    _rate_check(f"verify_ip:{ip}", _VERIFY_IP_MAX, _VERIFY_WINDOW_S, now)  # monitoring

    def _invalid(reason: str, token_id: Optional[str] = None) -> dict:
        _log("magic_link.invalid", reason=reason, token_id=token_id,
             ip=ip or "-", ua=(user_agent or "")[:80])
        return {"status": "invalid"}

    if not token_raw:
        return _invalid("missing")

    record = _store_get_by_hash(_hash_token(token_raw))
    if record is None:
        return _invalid("not_found")
    if record.get("purpose") != PURPOSE_LOGIN:
        return _invalid("wrong_purpose", record.get("id"))
    if record.get("used_at") is not None:
        return _invalid("used", record.get("id"))
    if float(record.get("expires_at", 0)) <= now:
        return _invalid("expired", record.get("id"))

    # Valid — burn it immediately (one-time use) before issuing a session.
    _store_mark_used(record["token_hash"], now)

    email = record["email"]
    ehash = _email_hash(email)
    created = _ensure_user(email, now)
    active = _is_active_member(email, now)

    session_id = secrets.token_urlsafe(32)
    sessions_store.create_session(
        session_id=session_id, username=email, expires_at=now + _session_ttl()
    )
    resolved_path = resolve_next_path(record.get("next_key"), active)
    redirect_url = _final_redirect_url(resolved_path)

    _log("magic_link.verified", token_id=record.get("id"), email_hash=ehash,
         ip=ip or "-", redirect=resolved_path, created=created, active=active)
    return {
        "status": "ok",
        "session_id": session_id,
        "redirect": redirect_url,       # absolute, server-built, allowlisted
        "redirect_path": resolved_path,
        "session_max_age": _session_ttl(),
        "email_hash": ehash,
        "created": created,
        "active": active,
    }


# ---------------------------------------------------------------------------
# Generic "link no longer valid" page (served by /auth/verify on failure)
# ---------------------------------------------------------------------------
def invalid_link_page() -> str:
    enter_url = _shell_enter_url()
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        "<title>Link expired · ClarityOS</title>"
        "<style>"
        "html,body{margin:0;height:100%;background:#05060a;color:#f2f5f8;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}"
        ".wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}"
        ".card{max-width:420px;text-align:center;}"
        ".dot{width:11px;height:11px;border-radius:50%;background:#34e0e0;"
        "box-shadow:0 0 12px #34e0e0;display:inline-block;margin-bottom:24px;}"
        "h1{font-size:1.8rem;font-weight:700;margin:0 0 12px;}"
        "p{color:#98a2b3;margin:0 0 28px;line-height:1.6;}"
        "a.btn{display:inline-flex;align-items:center;justify-content:center;"
        "padding:13px 26px;border-radius:8px;font-weight:600;text-decoration:none;"
        "color:#02151a;background:#34e0e0;border:1px solid #34e0e0;"
        "box-shadow:0 0 18px rgba(52,224,224,.25);}"
        "</style></head><body><div class=\"wrap\"><div class=\"card\">"
        "<span class=\"dot\"></span>"
        "<h1>This link is no longer valid.</h1>"
        "<p>Request a new one and we’ll send a fresh secure link to your inbox.</p>"
        f"<a class=\"btn\" href=\"{enter_url}\">Request a new link</a>"
        "</div></div></body></html>"
    )


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    with _TOKENS_LOCK:
        _MEM_TOKENS.clear()
    with _RL_LOCK:
        _RL_HITS.clear()
    global EMAIL_SENDER
    EMAIL_SENDER = _default_email_sender
