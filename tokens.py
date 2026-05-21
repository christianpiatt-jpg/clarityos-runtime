"""
HMAC-SHA256 signed tokens for invite links.

Token format: <base64url(json_payload)>.<base64url(hmac_sha256(payload))>

Required env: INVITE_HMAC_SECRET (32+ random bytes, set in Cloud Run env).

verify_token() returns the decoded payload on success, None on:
  - malformed token
  - signature mismatch
  - expired (exp claim, unix seconds)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional


class TokenError(RuntimeError):
    pass


def _secret() -> bytes:
    s = os.environ.get("INVITE_HMAC_SECRET", "")
    if not s or len(s) < 16:
        raise TokenError(
            "INVITE_HMAC_SECRET is missing or too short. "
            "Set a 32+ char random value in the Cloud Run service env."
        )
    return s.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))


def sign_token(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_secret(), body, hashlib.sha256).digest()
    return f"{_b64url_encode(body)}.{_b64url_encode(sig)}"


def verify_token(token: str) -> Optional[dict]:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _b64url_decode(body_b64)
        sig = _b64url_decode(sig_b64)
    except Exception:
        return None
    expected = hmac.new(_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        return None
    return payload
