"""
v29 — Hardening + launch-readiness helpers.

Centralizes the launch-pass concerns so app.py stays additive and the test
suite can exercise the rules in isolation:

* Input validation primitives (type / length / required-field checks) with
  consistent ``ValidationError`` -> ``HTTPException`` mapping via
  ``raise_validation``.
* A no-op-but-structured rate limiter (in-memory token bucket per user/route).
  Real persistence/distribution is intentionally deferred; the structure is
  sufficient for the launch cohort and stable for future swap-in.
* Structured logging helpers (``log_event`` / ``redact_user``) — never logs
  user content; only event type + redacted user id + timing + outcome.
* A feature-flag registry + per-user gate (``feature_enabled`` / ``set_flag``)
  used to scope v28 surfaces to the Cohort 1 rollout.

All helpers are import-safe (no FastAPI dependency at module import time);
``raise_validation`` lazily imports HTTPException so unit tests can call the
plain validators without standing up the full app.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Iterable, Optional

logger = logging.getLogger("clarityos.v29")


# ===========================================================================
# Validation
# ===========================================================================
class ValidationError(Exception):
    """Raised by the validators below. ``code`` is wire-stable; ``message``
    is human-readable. Callers should translate this to the project's
    ``error_response`` envelope (helper provided as ``raise_validation``)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def raise_validation(err: ValidationError, status_code: int = 400) -> None:
    """Translate a ``ValidationError`` to FastAPI's ``HTTPException`` with the
    project's ``error_response`` envelope. Imported lazily so test code can
    use ``ValidationError`` without pulling FastAPI."""
    from fastapi import HTTPException  # type: ignore

    detail = {"ok": False, "error": err.code, "message": err.message}
    raise HTTPException(status_code=status_code, detail=detail)


def require_str(
    value: Any,
    field: str,
    *,
    min_len: int = 1,
    max_len: int = 8000,
    allow_empty: bool = False,
) -> str:
    if value is None:
        if allow_empty:
            return ""
        raise ValidationError("missing_field", f"'{field}' is required")
    if not isinstance(value, str):
        raise ValidationError("bad_type", f"'{field}' must be a string")
    s = value.strip()
    if not s and not allow_empty:
        raise ValidationError("empty_field", f"'{field}' must be non-empty")
    if min_len and len(s) < min_len and not (allow_empty and not s):
        raise ValidationError(
            "field_too_short",
            f"'{field}' must be at least {min_len} characters",
        )
    if max_len and len(s) > max_len:
        raise ValidationError(
            "field_too_long",
            f"'{field}' must be at most {max_len} characters",
        )
    return s


def require_int(
    value: Any,
    field: str,
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    default: Optional[int] = None,
) -> int:
    if value is None:
        if default is not None:
            return int(default)
        raise ValidationError("missing_field", f"'{field}' is required")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError("bad_type", f"'{field}' must be an integer")
    if min_value is not None and n < min_value:
        raise ValidationError(
            "out_of_range", f"'{field}' must be >= {min_value}"
        )
    if max_value is not None and n > max_value:
        raise ValidationError(
            "out_of_range", f"'{field}' must be <= {max_value}"
        )
    return n


def require_dict(value: Any, field: str, *, max_keys: int = 256) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("bad_type", f"'{field}' must be an object")
    if len(value) > max_keys:
        raise ValidationError(
            "too_many_keys", f"'{field}' has too many keys (max {max_keys})"
        )
    return value


def require_bool(value: Any, field: str, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)) and value in (0, 1):
        return bool(value)
    raise ValidationError("bad_type", f"'{field}' must be a boolean")


def require_one_of(
    value: Any, field: str, allowed: Iterable[str]
) -> str:
    s = require_str(value, field)
    if s not in set(allowed):
        raise ValidationError(
            "invalid_value",
            f"'{field}' must be one of: {', '.join(sorted(allowed))}",
        )
    return s


# ===========================================================================
# Rate limiter (in-memory; structured for swap-out)
# ===========================================================================
# Per-user-route token bucket. Defaults match a soft "no abuse" target
# rather than enforcement: 60 calls / 60s per (user, route). The bucket
# refills at ``capacity / window_s`` per second.
#
# On capacity overflow ``check_rate_limit`` returns False; the caller
# decides whether to 429 or just log. v29 wires logging-only by default;
# a future v30 can flip the env switch to enforce.
_DEFAULT_CAPACITY = int(os.environ.get("CLARITYOS_RATE_LIMIT_CAPACITY", "60"))
_DEFAULT_WINDOW_S = float(os.environ.get("CLARITYOS_RATE_LIMIT_WINDOW_S", "60"))
_RATE_ENFORCE = os.environ.get("CLARITYOS_RATE_LIMIT_ENFORCE", "0") == "1"

_bucket_lock = threading.Lock()
_buckets: dict[tuple[str, str], dict] = {}


def _bucket(user: str, route: str) -> dict:
    key = (user or "<anon>", route)
    b = _buckets.get(key)
    if b is None:
        b = {
            "tokens": float(_DEFAULT_CAPACITY),
            "last_refill_ts": time.time(),
        }
        _buckets[key] = b
    return b


def check_rate_limit(
    user: str,
    route: str,
    *,
    cost: float = 1.0,
    capacity: int = _DEFAULT_CAPACITY,
    window_s: float = _DEFAULT_WINDOW_S,
) -> bool:
    """Token-bucket check. Returns True iff the call fits inside the bucket
    (tokens consumed). Returns False if the bucket lacks tokens; caller may
    enforce or just log depending on ``CLARITYOS_RATE_LIMIT_ENFORCE``.
    Stateful but bounded — at most one bucket per (user, route)."""
    if window_s <= 0 or capacity <= 0:
        return True
    refill_per_s = float(capacity) / float(window_s)
    now = time.time()
    with _bucket_lock:
        b = _bucket(user, route)
        elapsed = max(0.0, now - float(b["last_refill_ts"]))
        b["tokens"] = min(float(capacity), float(b["tokens"]) + elapsed * refill_per_s)
        b["last_refill_ts"] = now
        if b["tokens"] >= cost:
            b["tokens"] -= cost
            return True
        return False


def enforce_rate_limit(user: str, route: str, **kw) -> None:
    """If the bucket is empty AND enforcement is on, raises 429. Otherwise
    logs and returns. The default is logging-only so the launch pass doesn't
    accidentally lock users out before traffic is observed."""
    if check_rate_limit(user, route, **kw):
        return
    log_event("rate_limit_exceeded", user=user, route=route, enforced=_RATE_ENFORCE)
    if _RATE_ENFORCE:
        raise_validation(
            ValidationError("rate_limited", "Too many requests; please slow down"),
            status_code=429,
        )


def _reset_rate_limits_for_tests() -> None:
    with _bucket_lock:
        _buckets.clear()


# ===========================================================================
# Structured logging
# ===========================================================================
# Single-line key=value records. Stable enough for log scraping; never
# embeds user content (only event type, redacted user id, route, timing,
# outcome, and explicit numeric counts).
_LOG_USER_PREFIX = 12  # truncate user id in logs


def redact_user(user: Optional[str]) -> str:
    if not user:
        return "<anon>"
    return user[:_LOG_USER_PREFIX] + ("…" if len(user) > _LOG_USER_PREFIX else "")


def log_event(
    event: str,
    *,
    user: Optional[str] = None,
    route: Optional[str] = None,
    duration_ms: Optional[float] = None,
    success: Optional[bool] = None,
    **extra: Any,
) -> None:
    """Emit a structured ``logger.info`` line. `extra` is whitelisted to
    primitives + counts; nested objects are coerced to ``len(...)`` so the
    log channel never carries user-text."""
    parts: list[str] = [f"event={event}"]
    parts.append(f"user={redact_user(user)}")
    if route:
        parts.append(f"route={route}")
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms:.1f}")
    if success is not None:
        parts.append(f"success={'1' if success else '0'}")
    for k, v in extra.items():
        if v is None:
            continue
        if isinstance(v, (int, float, bool, str)):
            parts.append(f"{k}={v}")
        elif isinstance(v, (list, tuple, set, dict)):
            parts.append(f"{k}_count={len(v)}")
        else:
            parts.append(f"{k}={type(v).__name__}")
    logger.info(" ".join(parts))


class TimedBlock:
    """Context manager + decorator for ``log_event`` timing.

    Usage::

        with TimedBlock("elins_g_run", user=user, route="/elins/g/run") as tb:
            ...do work...
            tb.set("neighborhoods", len(top5))
    """

    def __init__(self, event: str, **kw: Any):
        self.event = event
        self.fields = kw
        self._start: Optional[float] = None
        self._success: Optional[bool] = None

    def set(self, **kw: Any) -> None:
        self.fields.update(kw)

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        dur = (time.perf_counter() - (self._start or time.perf_counter())) * 1000.0
        success = self._success if self._success is not None else exc_type is None
        log_event(self.event, duration_ms=dur, success=success, **self.fields)
        return False  # never swallow

    def mark_failure(self) -> None:
        self._success = False


# ===========================================================================
# Feature flags
# ===========================================================================
# In-process registry: one dict of { flag_name -> { default: bool,
# user_overrides: { user_id -> bool } } }. Cohort 1 surfaces are gated
# under "v28_surfaces" (default off; cohorts/users opt-in via overrides).
#
# Persistence is intentionally deferred — flags re-init from defaults on
# process boot. The launch cohort is small (Founders + Terrace 1) so the
# user_overrides dict is bounded.
_DEFAULT_FLAGS: dict[str, bool] = {
    "v28_surfaces": False,        # gates /elins/* + /mesh/* + /continuity/snapshot
    "onboarding_v1": True,        # first-run onboarding wizard
    "whats_new_v28": True,        # cockpit "What's new" panel
    "demo_data": False,           # populate empty accounts with demo seeds
    "rate_limit_logging": True,   # emit log_event on rate-limit overflow
}
_flag_lock = threading.Lock()
_flags: dict[str, dict] = {}


def _flag_entry(name: str) -> dict:
    e = _flags.get(name)
    if e is None:
        e = {"default": _DEFAULT_FLAGS.get(name, False), "user_overrides": {}}
        _flags[name] = e
    return e


def feature_enabled(name: str, *, user: Optional[str] = None, cohort: Optional[str] = None) -> bool:
    """Default-off unless declared in ``_DEFAULT_FLAGS``. User overrides
    take precedence over defaults; cohort-level overrides take precedence
    over defaults but lose to user overrides. ``cohort`` is matched by
    ``"cohort:<name>"`` keys in user_overrides."""
    with _flag_lock:
        e = _flag_entry(name)
        if user and user in e["user_overrides"]:
            return bool(e["user_overrides"][user])
        if cohort:
            ck = f"cohort:{cohort}"
            if ck in e["user_overrides"]:
                return bool(e["user_overrides"][ck])
        return bool(e["default"])


def set_flag(name: str, value: bool, *, user: Optional[str] = None, cohort: Optional[str] = None) -> None:
    """Toggle a flag. Without ``user``/``cohort``, sets the default. With
    either, scopes the override."""
    with _flag_lock:
        e = _flag_entry(name)
        if user:
            e["user_overrides"][user] = bool(value)
        elif cohort:
            e["user_overrides"][f"cohort:{cohort}"] = bool(value)
        else:
            e["default"] = bool(value)


def list_flags() -> dict:
    with _flag_lock:
        out = {}
        for k in sorted(set(list(_flags.keys()) + list(_DEFAULT_FLAGS.keys()))):
            e = _flag_entry(k)
            out[k] = {
                "default": e["default"],
                "override_count": len(e["user_overrides"]),
            }
        return out


def _reset_flags_for_tests() -> None:
    with _flag_lock:
        _flags.clear()


# ===========================================================================
# Demo data — empty-account seeds
# ===========================================================================
# Exposed as constants so tests + onboarding endpoint share one source.
DEMO_VAULT_ITEMS: tuple = (
    {
        "title": "Welcome to ClarityOS",
        "content": (
            "This is a starter vault note. Use the Vault to capture sessions "
            "and notes. Nothing here leaves your account."
        ),
        "tags": ["welcome", "demo"],
    },
    {
        "title": "ELINS — first scenario",
        "content": (
            "Try the ELINS surface to run a #G scenario. The personal engine "
            "uses your Dewey neighborhoods and never persists scenario text."
        ),
        "tags": ["welcome", "elins"],
    },
)

DEMO_TIMELINE_EVENTS: tuple = (
    {
        "kind": "system.welcome",
        "summary": "Account created — welcome to ClarityOS",
        "data": {"version": "v29"},
    },
)


# ===========================================================================
# Mesh-payload pre-validation (used by /mesh/sync to surface a 400 with the
# project's envelope shape before it reaches the store-level ValueError).
# ===========================================================================
import json as _json

MESH_MAX_DEVICE_BLOB_BYTES = 16 * 1024  # mirrors mesh_metadata_store cap
MESH_MAX_DEVICE_ID_LEN = 128


def validate_mesh_payload(device_id: Any, metadata: Any) -> tuple[str, dict]:
    did = require_str(device_id, "device_id", max_len=MESH_MAX_DEVICE_ID_LEN)
    md = require_dict(metadata, "metadata", max_keys=64)
    serialized = _json.dumps(md, separators=(",", ":"), default=str)
    if len(serialized.encode("utf-8")) > MESH_MAX_DEVICE_BLOB_BYTES:
        raise ValidationError(
            "mesh_payload",
            f"metadata exceeds {MESH_MAX_DEVICE_BLOB_BYTES}-byte cap",
        )
    return did, md
