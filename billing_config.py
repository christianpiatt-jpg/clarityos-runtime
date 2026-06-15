"""
v42 — Stripe billing config + observability layer.

Centralises Stripe mode/key resolution, idempotent webhook event
tracking, and structured billing-event recording. Co-exists with the
v2 ``billing.py`` env vars (``STRIPE_SECRET_KEY``,
``STRIPE_WEBHOOK_SECRET``) and the v31 ``CLARITYOS_BILLING_MODE`` flag;
the new v42 vars take precedence when both are set.

Public API:
    STRIPE_VERSION
    VALID_MODES

    get_secret_key()        -> str | None
    get_webhook_secret()    -> str | None
    get_stripe_mode()       -> "test" | "live" | "disabled"
    is_billing_enabled()    -> bool
    is_live_mode()          -> bool
    get_billing_status()    -> dict

    record_billing_event(event_type, user_id=None, payload_meta=None,
                         event_id=None, mode=None) -> dict
    list_recent_events(limit=50) -> list[dict]
    seen_event(event_id)    -> bool
    mark_event_seen(event_id) -> None

Env vars (v42 names take precedence over v2 names):
    CLARITYOS_STRIPE_MODE          ∈ {"test", "live"}  — explicit override
    CLARITYOS_STRIPE_SECRET_KEY    sk_test_... or sk_live_...
    CLARITYOS_STRIPE_WEBHOOK_SECRET whsec_...

Backwards-compatible fallbacks (v2):
    STRIPE_SECRET_KEY
    STRIPE_WEBHOOK_SECRET
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any, Optional

logger = logging.getLogger("clarityos.billing_config")

STRIPE_VERSION: str = "billing_config.v42.1"
VALID_MODES: tuple = ("test", "live")

# Cap on the in-process recent-events ring buffer. The /founder/billing/status
# endpoint surfaces this list so a small cap keeps payloads bounded.
_RECENT_EVENTS_MAX: int = 50

_recent_events: deque = deque(maxlen=_RECENT_EVENTS_MAX)
_seen_event_ids: set = set()
_seen_event_max: int = 5000  # FIFO eviction once exceeded

# Module 18 — webhook-failure ring buffer (content-free: reason code + ts only).
_WEBHOOK_FAILURES_MAX: int = 200
_webhook_failures: deque = deque(maxlen=_WEBHOOK_FAILURES_MAX)


# ---------------------------------------------------------------------------
# Env-var resolution
# ---------------------------------------------------------------------------
def _clean_secret(raw: Optional[str]) -> Optional[str]:
    """Normalise a secret read from env / Secret Manager.

    Strips surrounding whitespace AND a single layer of matching wrapping
    quotes. A quoted secret (the value stored as "whsec_..." with the quotes
    included) is a common Secret-Manager / shell paste error that ``.strip()``
    alone leaves intact — the quote characters then become part of the HMAC
    key and EVERY Stripe signature check fails with a generic ``bad_signature``.
    Returns None for empty input.
    """
    if raw is None:
        return None
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v or None


def get_secret_key() -> Optional[str]:
    """Return the Stripe secret key, prioritising v42 env names."""
    for name in ("CLARITYOS_STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY"):
        v = _clean_secret(os.environ.get(name))
        if v:
            return v
    return None


def get_webhook_secret() -> Optional[str]:
    for name in ("CLARITYOS_STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET"):
        v = _clean_secret(os.environ.get(name))
        if v:
            return v
    return None


def get_stripe_mode() -> str:
    """Resolve the active Stripe mode.

    Precedence:
        1. ``CLARITYOS_STRIPE_MODE`` if set to a valid value.
        2. Inspect the secret key prefix (``sk_test_`` / ``sk_live_``).
        3. Fall back to ``"disabled"`` when no key is present.
    """
    explicit = (os.environ.get("CLARITYOS_STRIPE_MODE") or "").strip().lower()
    if explicit in VALID_MODES:
        return explicit
    key = get_secret_key()
    if not key:
        return "disabled"
    if key.startswith("sk_live_"):
        return "live"
    if key.startswith("sk_test_"):
        return "test"
    # Key present but unrecognised prefix — treat as test (safer default
    # than live; the founder console will surface this in status).
    return "test"


def is_billing_enabled() -> bool:
    """True iff a Stripe key is configured (test or live)."""
    return get_stripe_mode() in VALID_MODES


def is_live_mode() -> bool:
    return get_stripe_mode() == "live"


def get_billing_status() -> dict:
    """Single-call status snapshot used by the founder console + the
    membership view. Never returns the actual key — only booleans +
    mode label."""
    mode = get_stripe_mode()
    return {
        "mode": mode,
        "has_secret": bool(get_secret_key()),
        "has_webhook_secret": bool(get_webhook_secret()),
        "live_mode": mode == "live",
        "billing_enabled": mode in VALID_MODES,
        "version": STRIPE_VERSION,
    }


# ---------------------------------------------------------------------------
# Idempotent event seen-set
# ---------------------------------------------------------------------------
def seen_event(event_id: Optional[str]) -> bool:
    """True iff the event id was already processed in this process."""
    if not event_id:
        return False
    return str(event_id) in _seen_event_ids


def mark_event_seen(event_id: Optional[str]) -> None:
    """Record an event id as processed. FIFO eviction once the cap is hit."""
    if not event_id:
        return
    eid = str(event_id)
    if eid in _seen_event_ids:
        return
    _seen_event_ids.add(eid)
    if len(_seen_event_ids) > _seen_event_max:
        # Drop an arbitrary id (sets don't preserve order; this is only
        # to bound memory). New ids will still get tracked.
        try:
            _seen_event_ids.pop()
        except KeyError:  # pragma: no cover (defensive)
            pass


# ---------------------------------------------------------------------------
# C3 — durable webhook audit + idempotency (Firestore-backed)
# ---------------------------------------------------------------------------
# The in-process _seen_event_ids set above is per-instance and lost on restart;
# on Cloud Run (multi-instance / cold starts) that is not a sufficient
# idempotency guarantee. When CLARITYOS_BACKEND=firestore we persist one doc
# per Stripe event id under the _audit collection: existence == "already seen",
# and a ``processed`` flag records whether the handler ran to completion.
# Memory / mock backends transparently fall back to the in-process seen-set so
# the test suite (and local synthetic-event flows) are unchanged.
_AUDIT_COLLECTION = "_audit"
_audit_firestore_client = None  # lazy init


def _audit_backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


def _audit_fs():
    global _audit_firestore_client
    if _audit_firestore_client is not None:
        return _audit_firestore_client
    from google.cloud import firestore  # type: ignore
    _audit_firestore_client = firestore.Client()
    return _audit_firestore_client


def _audit_doc(event_id):
    return _audit_fs().collection(_AUDIT_COLLECTION).document(str(event_id))


def audit_seen(event_id: Optional[str]) -> bool:
    """Durable duplicate check. Firestore ``_audit/<event_id>`` existence when
    backend=firestore; the in-process seen-set otherwise. Fails OPEN to the
    in-process set on a Firestore error so a transient blip never silently
    drops a real event."""
    if not event_id:
        return False
    if _audit_backend() == "firestore":
        try:
            return _audit_doc(event_id).get().exists
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning("audit_seen firestore read failed eid=%s err=%s", event_id, e)
            return seen_event(event_id)
    return seen_event(event_id)


def audit_begin(event: Optional[dict]) -> None:
    """Record receipt of an event (``processed=False``). Always updates the
    in-process seen-set; additionally writes the durable ``_audit`` doc when
    backend=firestore."""
    if not isinstance(event, dict):
        return
    eid = event.get("id")
    if not eid:
        return
    mark_event_seen(eid)
    if _audit_backend() != "firestore":
        return
    try:
        _audit_doc(eid).set({
            "event_id": str(eid),
            "type": event.get("type"),
            "livemode": bool(event.get("livemode", False)),
            "api_version": event.get("api_version"),
            "received_at": time.time(),
            "processed": False,
        })
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("audit_begin firestore write failed eid=%s err=%s", eid, e)


def audit_complete(event_id: Optional[str]) -> None:
    """Flag the durable ``_audit`` doc ``processed=True`` once the handler
    succeeds. No-op for memory / mock backends."""
    if not event_id or _audit_backend() != "firestore":
        return
    try:
        _audit_doc(event_id).set(
            {"processed": True, "processed_at": time.time()}, merge=True
        )
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("audit_complete firestore write failed eid=%s err=%s", event_id, e)


def audit_fail(event_id: Optional[str], err: object) -> None:
    """Record a handler failure on the durable ``_audit`` doc (``processed``
    stays False so Stripe's retry can re-drive the event). No-op for memory /
    mock backends."""
    if not event_id or _audit_backend() != "firestore":
        return
    try:
        _audit_doc(event_id).set(
            {"processed": False, "error": str(err)[:500], "errored_at": time.time()},
            merge=True,
        )
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("audit_fail firestore write failed eid=%s err=%s", event_id, e)


# ---------------------------------------------------------------------------
# Module 18 — webhook failure triage signal (queryable, content-free)
# ---------------------------------------------------------------------------
def record_webhook_failure(reason: str, now_ts: Optional[float] = None) -> None:
    """Record a rejected Stripe webhook for the founder alerts surface. Stores
    ONLY a short reason code + timestamp — never the secret or the payload."""
    _webhook_failures.appendleft({
        "ts": float(now_ts if now_ts is not None else time.time()),
        "reason": str(reason or "unknown"),
    })


def webhook_failure_stats(
    window_s: float = 86400.0, now_ts: Optional[float] = None,
) -> dict:
    """Aggregate webhook failures within ``window_s``: total + by_reason + the
    most-recent failure ts. Counts / reason-codes only."""
    now = float(now_ts if now_ts is not None else time.time())
    cutoff = now - float(window_s)
    in_window = [
        f for f in _webhook_failures if float(f.get("ts") or 0.0) >= cutoff
    ]
    by_reason: dict = {}
    for f in in_window:
        r = str(f.get("reason") or "unknown")
        by_reason[r] = by_reason.get(r, 0) + 1
    return {
        "total": len(in_window),
        "by_reason": by_reason,
        "last_ts": (_webhook_failures[0]["ts"] if _webhook_failures else None),
    }


# ---------------------------------------------------------------------------
# Recent events (founder console surface)
# ---------------------------------------------------------------------------
def record_billing_event(
    event_type: str,
    *,
    user_id: Optional[str] = None,
    payload_meta: Optional[dict] = None,
    event_id: Optional[str] = None,
    mode: Optional[str] = None,
) -> dict:
    """Append a metadata-only billing event to the recent-events ring.

    The ``payload_meta`` dict is sanitised to keep raw card / customer
    objects out of the log. Callers should pre-extract just the fields
    they want surfaced.
    """
    record = {
        "ts": time.time(),
        "event_type": str(event_type or ""),
        "user_id": str(user_id) if user_id else None,
        "event_id": str(event_id) if event_id else None,
        "mode": mode or get_stripe_mode(),
        "payload_meta": _sanitise_meta(payload_meta or {}),
    }
    _recent_events.appendleft(record)
    return record


def list_recent_events(*, limit: int = 50) -> list[dict]:
    n = max(1, min(int(limit), _RECENT_EVENTS_MAX))
    return [dict(r) for r in list(_recent_events)[:n]]


def last_event_ts() -> Optional[float]:
    if not _recent_events:
        return None
    return float(_recent_events[0].get("ts") or 0.0) or None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SAFE_META_MAX_STR: int = 200
_FORBIDDEN_META_KEYS: frozenset = frozenset({
    "card", "payment_method", "customer", "client_secret", "raw",
    "email", "phone",  # keep PII out of the event log surface
})


def _sanitise_meta(meta: dict) -> dict:
    """Strip PII / large blobs from the payload metadata before it's
    logged or surfaced via /founder/billing/status."""
    if not isinstance(meta, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            continue
        if k in _FORBIDDEN_META_KEYS:
            continue
        out[k] = _coerce_meta_value(v)
    return out


def _coerce_meta_value(v: Any) -> Any:
    if isinstance(v, str):
        return v if len(v) <= _SAFE_META_MAX_STR else v[:_SAFE_META_MAX_STR]
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_coerce_meta_value(x) for x in v][:20]
    if isinstance(v, dict):
        return {
            k: _coerce_meta_value(vv) for k, vv in v.items()
            if isinstance(k, str) and k not in _FORBIDDEN_META_KEYS
        }
    s = str(v)
    return s if len(s) <= _SAFE_META_MAX_STR else s[:_SAFE_META_MAX_STR]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    _recent_events.clear()
    _seen_event_ids.clear()
    _webhook_failures.clear()
