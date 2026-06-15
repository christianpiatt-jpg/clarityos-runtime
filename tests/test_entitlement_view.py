"""
Tests for V83 — entitlement projection.

Covers:
    A. compute_entitlement_view — projection logic over the existing
       v30/v31/v42/v74 stores (no new state)
    B. active-state derivation across every billing_state
    C. founding badge from the cohort roster
    D. features block derives purely from the core fields
    E. GET /me/entitlement endpoint (auth + shape)
    F. GET /founder/entitlement/{user_id} endpoint (founder gate,
       bad-input 400, unknown-user 200 exists=False)
    G. never raises / always fully shaped
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(
        sid, username, expires_at=time.time() + 3600,
    )
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _make_founding_active(username):
    """Create a user who is an active Founding 500 member.
    Returns ``(username, session_id)`` — same shape as ``_make_user``."""
    import membership_store
    import users_store
    user, sid = _make_user(username)
    users_store.set_membership(
        username, tier="founding_500", price=50.0,
        status="active", started_ts=time.time(),
    )
    users_store.set_billing_state(username, billing_state="active")
    membership_store.add_member(username)
    return user, sid


# ===========================================================================
# A. Projection logic
# ===========================================================================
class TestProjectionShape:
    def test_unknown_user_exists_false(self, reset_stores):
        import entitlement_view
        v = entitlement_view.compute_entitlement_view("ghost")
        assert v["exists"] is False
        assert v["active"] is False
        assert v["tier"] is None
        assert v["founding_500_badge"] is False

    def test_unknown_user_fully_shaped(self, reset_stores):
        import entitlement_view
        v = entitlement_view.compute_entitlement_view("ghost")
        # Every key present so callers never branch on missing keys.
        for key in (
            "exists", "user", "tier", "active", "billing_state",
            "cancel_at_period_end", "current_period_end", "lifetime",
            "founding_500_badge", "membership_confirmed",
            "membership_confirmed_ts", "features", "billing_mode",
            "source", "computed_at",
        ):
            assert key in v, f"missing key {key!r}"
        for fkey in (
            "portal_access", "founding_500_badge", "priority_support",
            "downloads", "community_access", "billing_portal",
        ):
            assert fkey in v["features"]
            assert v["features"][fkey] is False

    def test_empty_user_string_handled(self, reset_stores):
        import entitlement_view
        v = entitlement_view.compute_entitlement_view("")
        assert v["exists"] is False

    def test_non_string_user_handled(self, reset_stores):
        import entitlement_view
        v = entitlement_view.compute_entitlement_view(None)  # type: ignore[arg-type]
        assert v["exists"] is False

    def test_source_tag_present(self, reset_stores):
        import entitlement_view
        v = entitlement_view.compute_entitlement_view("ghost")
        assert v["source"] == "clarityos.entitlement_view.v83.1"
        assert isinstance(v["computed_at"], float)

    def test_existing_user_no_membership(self, reset_stores):
        import entitlement_view
        _make_user("plainuser")
        v = entitlement_view.compute_entitlement_view("plainuser")
        # User exists but never bought a membership.
        assert v["exists"] is True
        assert v["tier"] is None
        assert v["active"] is False
        assert v["founding_500_badge"] is False


# ===========================================================================
# B. active-state derivation
# ===========================================================================
class TestActiveDerivation:
    def _user_with_billing(self, name, *, status, billing_state):
        import users_store
        _make_user(name)
        users_store.set_membership(
            name, tier="founding_500", price=50.0, status=status,
            started_ts=time.time(),
        )
        if billing_state is not None:
            users_store.set_billing_state(name, billing_state=billing_state)
        return name

    def test_active_billing_active(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u1", status="active", billing_state="active")
        assert entitlement_view.compute_entitlement_view("u1")["active"] is True

    def test_past_due_retains_access(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u2", status="active", billing_state="past_due")
        # past_due is inside the retry window — access retained.
        assert entitlement_view.compute_entitlement_view("u2")["active"] is True

    def test_grace_period_retains_access(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u3", status="active", billing_state="grace_period")
        assert entitlement_view.compute_entitlement_view("u3")["active"] is True

    def test_cancelled_billing_revokes(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u4", status="active", billing_state="cancelled")
        assert entitlement_view.compute_entitlement_view("u4")["active"] is False

    def test_failed_billing_revokes(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u5", status="active", billing_state="failed")
        assert entitlement_view.compute_entitlement_view("u5")["active"] is False

    def test_cancelled_membership_revokes(self, reset_stores):
        import entitlement_view
        # membership_status cancelled overrides even an active billing_state.
        self._user_with_billing("u6", status="cancelled", billing_state="active")
        assert entitlement_view.compute_entitlement_view("u6")["active"] is False

    def test_no_billing_machine_tracks_membership_status(self, reset_stores):
        import entitlement_view
        # billing_state None + membership active → active.
        self._user_with_billing("u7", status="active", billing_state=None)
        assert entitlement_view.compute_entitlement_view("u7")["active"] is True

    def test_no_billing_machine_inactive_membership(self, reset_stores):
        import entitlement_view
        self._user_with_billing("u8", status=None, billing_state=None)
        assert entitlement_view.compute_entitlement_view("u8")["active"] is False


# ===========================================================================
# C. Founding badge
# ===========================================================================
class TestFoundingBadge:
    def test_badge_true_for_cohort_member(self, reset_stores):
        import entitlement_view
        _make_founding_active("founder_alice")
        v = entitlement_view.compute_entitlement_view("founder_alice")
        assert v["founding_500_badge"] is True
        assert v["features"]["founding_500_badge"] is True

    def test_badge_false_for_non_cohort_user(self, reset_stores):
        import entitlement_view
        import users_store
        _make_user("regular")
        users_store.set_membership(
            "regular", tier="standard", price=0.0, status="active",
        )
        v = entitlement_view.compute_entitlement_view("regular")
        assert v["founding_500_badge"] is False

    def test_badge_survives_billing_lapse(self, reset_stores):
        """The founding badge is a permanent cohort fact — it stays
        True even when billing has lapsed (access is gone, badge isn't)."""
        import entitlement_view
        import membership_store
        import users_store
        _make_user("lapsed_founder")
        users_store.set_membership(
            "lapsed_founder", tier="founding_500", price=50.0,
            status="active", started_ts=time.time(),
        )
        membership_store.add_member("lapsed_founder")
        users_store.set_billing_state("lapsed_founder", billing_state="cancelled")
        v = entitlement_view.compute_entitlement_view("lapsed_founder")
        assert v["active"] is False            # access revoked
        assert v["founding_500_badge"] is True  # badge permanent


# ===========================================================================
# D. Features derivation
# ===========================================================================
class TestFeatures:
    def test_active_founding_features(self, reset_stores):
        import entitlement_view
        _make_founding_active("ff")
        f = entitlement_view.compute_entitlement_view("ff")["features"]
        assert f["portal_access"] is True
        assert f["founding_500_badge"] is True
        assert f["priority_support"] is True   # active AND founding
        assert f["downloads"] is True
        assert f["community_access"] is True
        assert f["billing_portal"] is True     # tier is not None

    def test_inactive_user_features_off(self, reset_stores):
        import entitlement_view
        import users_store
        _make_user("inact")
        users_store.set_membership(
            "inact", tier="founding_500", price=50.0, status="cancelled",
        )
        f = entitlement_view.compute_entitlement_view("inact")["features"]
        assert f["portal_access"] is False
        assert f["downloads"] is False
        assert f["community_access"] is False
        # billing_portal stays True — they have a tier, can reactivate.
        assert f["billing_portal"] is True

    def test_priority_support_needs_active_and_founding(self, reset_stores):
        import entitlement_view
        import membership_store
        import users_store
        # Founding member but billing cancelled → no priority support.
        _make_user("ps")
        users_store.set_membership(
            "ps", tier="founding_500", price=50.0, status="active",
            started_ts=time.time(),
        )
        membership_store.add_member("ps")
        users_store.set_billing_state("ps", billing_state="cancelled")
        f = entitlement_view.compute_entitlement_view("ps")["features"]
        assert f["priority_support"] is False  # founding but not active


# ===========================================================================
# E. v74 membership_confirmed surfacing
# ===========================================================================
class TestMembershipConfirmed:
    def test_confirmed_flag_surfaces(self, reset_stores):
        import entitlement_view
        import users_store
        _make_user("conf")
        users_store.update_user("conf", {
            "membership_confirmed": True,
            "membership_confirmed_ts": 1700000000.0,
        })
        v = entitlement_view.compute_entitlement_view("conf")
        assert v["membership_confirmed"] is True
        assert v["membership_confirmed_ts"] == 1700000000.0

    def test_unconfirmed_defaults_false(self, reset_stores):
        import entitlement_view
        _make_user("unconf")
        v = entitlement_view.compute_entitlement_view("unconf")
        assert v["membership_confirmed"] is False


# ===========================================================================
# F. Endpoints
# ===========================================================================
class TestMeEntitlementEndpoint:
    def test_returns_200_for_authed_user(self, client):
        _, sid = _make_founding_active("alice")
        r = client.get("/me/entitlement", headers=_auth(sid))
        assert r.status_code == 200
        body = r.json()
        assert body["exists"] is True
        assert body["user"] == "alice"
        assert body["active"] is True
        assert body["founding_500_badge"] is True

    def test_requires_session(self, client):
        r = client.get("/me/entitlement")
        assert r.status_code == 401

    def test_reflects_caller_not_arbitrary_user(self, client):
        # /me/entitlement is self-only — the projected user is the
        # session user, full stop.
        _make_founding_active("alice")
        _, bob_sid = _make_user("bob")
        r = client.get("/me/entitlement", headers=_auth(bob_sid))
        assert r.json()["user"] == "bob"
        assert r.json()["founding_500_badge"] is False


class TestFounderEntitlementEndpoint:
    def test_founder_reads_any_user(self, client):
        _make_founding_active("alice")
        _, founder_sid = _make_user("thefounder", cohort="founder")
        r = client.get(
            "/founder/entitlement/alice", headers=_auth(founder_sid),
        )
        assert r.status_code == 200
        assert r.json()["user"] == "alice"
        assert r.json()["active"] is True

    def test_non_founder_gets_403(self, client):
        _make_founding_active("alice")
        # cohort=None → not founder-like.
        _, plain_sid = _make_user("plain", cohort=None)
        r = client.get(
            "/founder/entitlement/alice", headers=_auth(plain_sid),
        )
        assert r.status_code == 403

    def test_requires_session(self, client):
        r = client.get("/founder/entitlement/alice")
        assert r.status_code == 401

    def test_unknown_user_returns_200_exists_false(self, client):
        # Projection never 404s — unknown user is 200 with exists:False.
        _, founder_sid = _make_user("thefounder", cohort="founder")
        r = client.get(
            "/founder/entitlement/ghost", headers=_auth(founder_sid),
        )
        assert r.status_code == 200
        assert r.json()["exists"] is False

    def test_slash_bearing_user_id_rejected(self, client):
        # A URL-encoded slash decodes to a path separator: Starlette's
        # router 404s `/founder/entitlement/bad/slash` (no matching
        # single-segment route) BEFORE the handler's `"/" in user_id`
        # 400 guard runs. Either way the request is rejected, never
        # processed into an entitlement view — that's the invariant.
        _, founder_sid = _make_user("thefounder", cohort="founder")
        r = client.get(
            "/founder/entitlement/bad%2Fslash", headers=_auth(founder_sid),
        )
        assert r.status_code in (400, 404)


# ===========================================================================
# G. Manifest + version
# ===========================================================================
class TestManifestAndVersion:
    def test_routes_in_manifest(self, client):
        endpoints = client.get("/").json()["endpoints"]
        assert "GET  /me/entitlement" in endpoints
        assert "GET  /founder/entitlement/{user_id}" in endpoints

    def test_health_version(self, client):
        assert client.get("/health").json()["version"] == __import__("_version").__version__
