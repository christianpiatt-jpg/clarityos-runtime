"""
entitlement_view.py — V83 / Entitlement projection.

A read-only PROJECTION over the existing ClarityOS membership +
billing stores. It introduces NO billing core, NO state machine, and
NO second source of truth — the authoritative state already lives in:

    * users_store      — membership_tier / membership_status /
                         billing_state / renewal_ts /
                         membership_confirmed   (v30 / v31 / v42 / v74)
    * membership_store — Founding 500 cohort roster   (v30)
    * billing_config   — Stripe mode               (v42)

``compute_entitlement_view(user)`` reads those, derives a normalised
entitlement dict, and returns it. WordPress / the operator portal
consume this single shape to gate access. This is the "adapter" half
of the V83 entitlement work — option (b) from the design call:
project from the existing state, never fork it.

Pure-ish + defensive: never raises. Unknown users return a fully
shaped dict with ``exists: False`` so callers render unconditionally.

Public surface
--------------
    compute_entitlement_view(user) -> dict
    SOURCE_TAG = "clarityos.entitlement_view.v83.1"
"""
from __future__ import annotations

import logging
import time
from typing import Any

import billing_config
import membership_store
import users_store

logger = logging.getLogger("clarityos.entitlement_view")

SOURCE_TAG = "clarityos.entitlement_view.v83.1"

# Billing states that still grant access. ``past_due`` + ``grace_period``
# are *inside the v31 retry / grace window* — access is retained on
# purpose; that is what the grace window is for.
_ACCESS_BILLING_STATES = ("active", "past_due", "grace_period")

# Billing states that revoke access outright.
_REVOKED_BILLING_STATES = ("cancelled", "failed")


# ---------------------------------------------------------------------------
# Defensive store reads
# ---------------------------------------------------------------------------
def _is_founding_member(user: str) -> bool:
    """Authoritative Founding 500 roster check. A cohort-store hiccup
    degrades to ``False`` rather than raising — the projection must
    never bubble an exception."""
    try:
        return bool(
            membership_store.is_member(user, membership_store.FOUNDING_COHORT)
        )
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning(
            "entitlement_view: is_member failed user=%s err=%s", user, e,
        )
        return False


def _billing_mode() -> str:
    """Stripe mode label (mock / live / disabled / ...). Never raises."""
    try:
        return str(billing_config.get_billing_status().get("mode") or "unknown")
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning("entitlement_view: billing_status failed err=%s", e)
        return "unknown"


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
def _empty_view(user: str) -> dict:
    """Shape returned for an unknown / invalid user. Every field is
    present so callers never branch on missing keys."""
    return {
        "exists":                  False,
        "user":                    user,
        "tier":                    None,
        "active":                  False,
        "billing_state":           None,
        "cancel_at_period_end":    False,
        "current_period_end":      None,
        "lifetime":                False,
        "founding_500_badge":      False,
        "membership_confirmed":    False,
        "membership_confirmed_ts": None,
        "features": {
            "portal_access":      False,
            "founding_500_badge": False,
            "priority_support":   False,
            "downloads":          False,
            "community_access":   False,
            "billing_portal":     False,
        },
        "billing_mode": _billing_mode(),
        "source":       SOURCE_TAG,
        "computed_at":  time.time(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compute_entitlement_view(user: str) -> dict:
    """Compute the entitlement projection for ``user``.

    Returns a fully-shaped dict — never ``None``, never raises.
    Unknown / invalid users get ``exists: False`` with every feature
    flag ``False``.

    ``active`` semantics — the user is entitled when:
        * ``membership_status`` is not ``"cancelled"``, AND
        * ``billing_state`` is None        → access tracks
                                              ``membership_status``,
        * ``billing_state`` ∈ (active, past_due, grace_period)
                                           → access retained,
        * ``billing_state`` ∈ (cancelled, failed)
                                           → access revoked.

      ``past_due`` + ``grace_period`` keep access on purpose — that's
      the v31 retry / grace window.

    Fields with no source in the current v30/v31 model
    (``cancel_at_period_end``, ``lifetime``) are surfaced honestly as
    ``False`` — see the inline notes. When the v42 Stripe subscription
    webhook starts recording scheduled cancellations,
    ``cancel_at_period_end`` gets a real source; until then it is
    deterministically ``False``, not guessed.
    """
    if not isinstance(user, str) or not user.strip():
        return _empty_view(user if isinstance(user, str) else "")

    doc = None
    try:
        doc = users_store.get_user(user)
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning(
            "entitlement_view: get_user failed user=%s err=%s", user, e,
        )
    if not doc:
        return _empty_view(user)

    try:
        view = users_store.get_membership_view(user) or {}
    except Exception as e:   # pragma: no cover (defensive)
        logger.warning(
            "entitlement_view: membership_view failed user=%s err=%s", user, e,
        )
        view = {}

    tier              = view.get("tier")
    membership_status = view.get("status")
    billing_state     = view.get("billing_state")
    renewal_ts        = view.get("renewal_ts")

    # --- access derivation (mirrors /me/billing's normalisation) ---
    if membership_status == "cancelled":
        active = False
    elif billing_state in _REVOKED_BILLING_STATES:
        active = False
    elif billing_state in _ACCESS_BILLING_STATES:
        active = True
    elif billing_state is None:
        active = (membership_status == "active")
    else:
        active = False

    founding = _is_founding_member(user)
    membership_confirmed = bool(doc.get("membership_confirmed", False))
    membership_confirmed_ts = doc.get("membership_confirmed_ts")

    return {
        "exists":                  True,
        "user":                    user,
        "tier":                    tier,
        "active":                  active,
        "billing_state":           billing_state,
        # ``cancel_at_period_end`` + ``lifetime`` have no field in the
        # v30/v31 model. Surfaced ``False`` honestly — not guessed.
        "cancel_at_period_end":    False,
        "current_period_end":      renewal_ts,
        "lifetime":                False,
        "founding_500_badge":      founding,
        "membership_confirmed":    membership_confirmed,
        "membership_confirmed_ts": membership_confirmed_ts,
        # Features are a pure function of the fields above — no new
        # state. Access-gated perks key off ``active``; the founding
        # badge is permanent (cohort roster), independent of billing.
        "features": {
            "portal_access":      active,
            "founding_500_badge": founding,
            "priority_support":   active and founding,
            "downloads":          active,
            "community_access":   active,
            "billing_portal":     tier is not None,
        },
        "billing_mode": _billing_mode(),
        "source":       SOURCE_TAG,
        "computed_at":  time.time(),
    }
