"""
Cloud Run IAM auth verification for SOS Runtime.

The WordPress SOS Connector plugin authenticates the operator
itself, then signs a Google-issued ID token with the configured
service account and sends:

    Authorization: Bearer <token>

The Cloud Run platform enforces IAM at ingress — only invocations
from the configured service-account principal reach this service.
This module performs a SECOND, in-service check so we can:

    1. Lock the audience to our service URL (extra defense if the
       Cloud Run IAM layer is ever misconfigured).
    2. Surface the caller's email in logs.
    3. Provide an ``insecure`` bypass mode for tests + local dev.

Modes
-----
* ``iam``      — verify the ID token with Google's tokeninfo endpoint
                 (or PyJWT + cached JWKs in a follow-up unit).
* ``insecure`` — skip verification. Used by pytest + local Docker.
                 NEVER set ``SOS_AUTH_MODE=insecure`` in production.

Mode selection:
    1. ``SOS_AUTH_MODE`` env var (``iam`` | ``insecure``) if set.
    2. ``insecure`` when ``SOS_BACKEND=memory`` (test convention).
    3. ``iam`` otherwise.

Returns a small ``Principal`` namedtuple with the email + raw claims
on success; raises ``HTTPException(401)`` on failure.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.parse
from typing import Any, NamedTuple, Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger("sos_runtime.auth")

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
HTTP_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
class Principal(NamedTuple):
    email: Optional[str]
    audience: Optional[str]
    mode: str
    raw_claims: dict


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def _mode_name() -> str:
    explicit = (os.environ.get("SOS_AUTH_MODE") or "").strip().lower()
    if explicit in ("iam", "insecure"):
        return explicit
    if (os.environ.get("SOS_BACKEND") or "").lower() == "memory":
        return "insecure"
    return "iam"


def _expected_audience() -> Optional[str]:
    """The Cloud Run service URL — what the WordPress connector
    targets and what the ID token's ``aud`` claim should match."""
    return (os.environ.get("SOS_AUDIENCE") or "").strip() or None


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------
def _verify_via_tokeninfo(token: str) -> dict:   # pragma: no cover (live HTTP)
    """Verify a Google-signed ID token via the public tokeninfo
    endpoint. Trades a network hop for the operational simplicity of
    not bundling JWKs in the container. A follow-up unit can swap
    this for local JWK verification if latency matters."""
    url = (
        f"{GOOGLE_TOKENINFO_URL}?"
        + urllib.parse.urlencode({"id_token": token})
    )
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read()
        claims = json.loads(body)
    except Exception as e:
        logger.warning("tokeninfo verification failed err=%s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": str(e)},
        )
    if "error" in claims or "error_description" in claims:
        logger.warning("tokeninfo returned error: %s", claims)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": claims.get(
                    "error_description", "tokeninfo rejected the bearer",
                ),
            },
        )
    expected_aud = _expected_audience()
    if expected_aud and claims.get("aud") != expected_aud:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "audience_mismatch",
                "message": (
                    "ID token audience does not match SOS_AUDIENCE; "
                    "the WordPress connector is signing tokens for a "
                    "different service URL."
                ),
            },
        )
    return claims


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def require_caller(
    authorization: Optional[str] = Header(default=None),
) -> Principal:
    """FastAPI dependency. Decodes the bearer token, verifies it
    according to ``SOS_AUTH_MODE``, and returns the caller principal.

    Raises ``HTTPException(401)`` on missing / malformed / rejected
    bearer when running in ``iam`` mode. Returns a stub principal
    in ``insecure`` mode.
    """
    mode = _mode_name()
    if mode == "insecure":
        return Principal(
            email="insecure-bypass@local",
            audience=None,
            mode="insecure",
            raw_claims={},
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_bearer",
                "message": "Authorization: Bearer header required.",
            },
        )
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "malformed_bearer",
                "message": "Authorization header must be 'Bearer <token>'.",
            },
        )
    token = parts[1].strip()

    claims = _verify_via_tokeninfo(token)
    return Principal(
        email=claims.get("email"),
        audience=claims.get("aud"),
        mode="iam",
        raw_claims=claims,
    )


def auth_status() -> dict:
    """Introspection helper for /health — confirms which mode is
    active without leaking the bearer."""
    return {
        "mode":      _mode_name(),
        "audience":  _expected_audience(),
        "audience_required": bool(_expected_audience()),
    }
