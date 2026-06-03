"""
Tests for the ClarityOS magic-link auth backend (auth_magiclink + the
/auth/enter and /auth/verify routes).

Coverage:
    A. /auth/enter token issuance, single-link-per-user, enumeration-safe
       rate limiting, malformed-email rejection.
    B. /auth/verify happy path (new user -> /onboarding, active member ->
       allowlisted next), one-time use, expiry, garbage tokens, session
       creation.
    C. Redirect allowlist / open-redirect rejection.
    D. HTTP routes: form-encoded enter, generic 200 / 400, verify 303 +
       HttpOnly session cookie, generic invalid-link page.

The module functions are exercised directly for the deterministic token
lifecycle (passing an explicit ``now``); the routes are exercised over a
small form-capable httpx client (the shared TestClient is JSON-only and
follows no redirects).
"""
from __future__ import annotations

import asyncio
import time

import pytest

import auth_magiclink
import sessions_store
import users_store


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


def _capturing_sender():
    """Replace auth_magiclink.EMAIL_SENDER with a capture; return the dict it
    fills so tests can read the emitted magic link (and thus the raw token)."""
    box: dict = {}

    def sender(email, link, ctx):
        box["email"] = email
        box["link"] = link
        box["ctx"] = ctx
        return True

    auth_magiclink.EMAIL_SENDER = sender
    return box


def _raw_token(link: str) -> str:
    return link.split("token=", 1)[1]


def _records_for(email: str):
    return [r for r in auth_magiclink._MEM_TOKENS.values() if r["email"] == email]


def _make_active_member(email: str, now: float) -> None:
    import bcrypt
    users_store.create_user(
        username=email, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="paid", created_at=now,
    )


# Form-capable ASGI helpers (TestClient is JSON-only + auto-follows nothing).
def _post_form(app, url, data):
    import httpx

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            return await ac.post(url, data=data)

    return asyncio.run(go())


def _get_noredirect(app, url):
    import httpx

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", follow_redirects=False
        ) as ac:
            return await ac.get(url)

    return asyncio.run(go())


# ===========================================================================
# A. /auth/enter — issuance + rate limiting (module level)
# ===========================================================================
class TestEnter:
    def test_malformed_email_rejected(self, reset_stores):
        r = auth_magiclink.request_magic_link("not-an-email", "wp-shell", "/app", "1.1.1.1", "ua")
        assert r["status"] == "invalid_email"
        assert _records_for("not-an-email") == []

    def test_valid_email_issues_one_token_and_emails_link(self, reset_stores):
        box = _capturing_sender()
        r = auth_magiclink.request_magic_link("a@b.com", "wp-shell", "/app", "ip", "ua")
        assert r["status"] == "ok"
        assert "/auth/verify?token=" in box["link"]
        recs = _records_for("a@b.com")
        assert len(recs) == 1
        assert recs[0]["purpose"] == "login"
        assert recs[0]["source"] == "wp-shell"
        # only a symbolic key is persisted, never a client-supplied path
        assert recs[0]["next_key"] == "app"
        assert "next" not in recs[0]
        assert recs[0]["used_at"] is None
        # only the hash is stored — never the raw secret
        assert "token" not in recs[0]
        assert recs[0]["token_hash"] == auth_magiclink._hash_token(_raw_token(box["link"]))

    def test_new_link_invalidates_prior_unused(self, reset_stores):
        now = 1000.0
        auth_magiclink.request_magic_link("dup@x.com", "wp", "/app", "ipA", "ua", now=now)
        auth_magiclink.request_magic_link("dup@x.com", "wp", "/app", "ipA", "ua", now=now)
        recs = _records_for("dup@x.com")
        assert len(recs) == 2
        assert sum(1 for r in recs if r["used_at"] is None) == 1  # only the newest is live

    def test_rate_limit_is_enumeration_safe(self, reset_stores):
        now = 2000.0
        for _ in range(3):  # per-email limit is 3 / window
            r = auth_magiclink.request_magic_link("rl@x.com", "wp", "/app", "ipB", "ua", now=now)
            assert r["status"] == "ok" and not r.get("rate_limited")
        blocked = auth_magiclink.request_magic_link("rl@x.com", "wp", "/app", "ipB", "ua", now=now)
        # Client still sees generic success; no new token was minted.
        assert blocked["status"] == "ok"
        assert blocked.get("rate_limited") is True
        assert len(_records_for("rl@x.com")) == 3


# ===========================================================================
# B. /auth/verify — token validation + session creation (module level)
# ===========================================================================
class TestVerify:
    def test_new_user_created_and_routed_to_onboarding(self, reset_stores):
        box = _capturing_sender()
        auth_magiclink.request_magic_link("new@x.com", "wp", "/app", "ip", "ua")
        raw = _raw_token(box["link"])
        r = auth_magiclink.verify_magic_link(raw, "ip", "ua")
        assert r["status"] == "ok"
        assert r["created"] is True
        assert r["active"] is False
        assert r["redirect_path"] == "/onboarding"     # inactive -> onboarding
        assert r["redirect"] == "https://clarity.pro-mediations.com/onboarding"
        # session really exists and is bound to the email
        sess = sessions_store.get_session(r["session_id"])
        assert sess is not None and sess["user"] == "new@x.com"
        # token is single-use — used_at is now set
        h = auth_magiclink._hash_token(raw)
        assert auth_magiclink._MEM_TOKENS[h]["used_at"] is not None
        # the auto-created account exists and cannot password-login
        assert users_store.user_exists("new@x.com")

    def test_active_member_routes_to_allowlisted_next(self, reset_stores):
        _make_active_member("paid@x.com", time.time())
        box = _capturing_sender()
        auth_magiclink.request_magic_link("paid@x.com", "wp", "/app", "ip", "ua")
        r = auth_magiclink.verify_magic_link(_raw_token(box["link"]), "ip", "ua")
        assert r["status"] == "ok"
        assert r["active"] is True
        assert r["created"] is False
        assert r["redirect"] == "https://clarity.pro-mediations.com/app"

    def test_active_member_allowlisted_subpath_preserved(self, reset_stores):
        _make_active_member("paid2@x.com", time.time())
        box = _capturing_sender()
        auth_magiclink.request_magic_link("paid2@x.com", "wp", "/app/transformation", "ip", "ua")
        r = auth_magiclink.verify_magic_link(_raw_token(box["link"]), "ip", "ua")
        assert r["redirect"] == "https://clarity.pro-mediations.com/app/transformation"

    def test_non_allowlisted_subpath_falls_back(self, reset_stores):
        _make_active_member("paid2b@x.com", time.time())
        box = _capturing_sender()
        auth_magiclink.request_magic_link("paid2b@x.com", "wp", "/app/workspace", "ip", "ua")
        r = auth_magiclink.verify_magic_link(_raw_token(box["link"]), "ip", "ua")
        assert r["redirect"] == "https://clarity.pro-mediations.com/app"

    def test_open_redirect_next_is_rejected(self, reset_stores):
        _make_active_member("paid3@x.com", time.time())
        box = _capturing_sender()
        auth_magiclink.request_magic_link("paid3@x.com", "wp", "https://evil.example/x", "ip", "ua")
        r = auth_magiclink.verify_magic_link(_raw_token(box["link"]), "ip", "ua")
        assert r["redirect"] == "https://clarity.pro-mediations.com/app"   # external next ignored

    def test_token_is_single_use(self, reset_stores):
        box = _capturing_sender()
        auth_magiclink.request_magic_link("once@x.com", "wp", "/app", "ip", "ua")
        raw = _raw_token(box["link"])
        assert auth_magiclink.verify_magic_link(raw, "ip", "ua")["status"] == "ok"
        assert auth_magiclink.verify_magic_link(raw, "ip", "ua")["status"] == "invalid"

    def test_expired_token_is_invalid(self, reset_stores):
        now = 5000.0
        box = _capturing_sender()
        auth_magiclink.request_magic_link("exp@x.com", "wp", "/app", "ip", "ua", now=now)
        raw = _raw_token(box["link"])
        later = now + auth_magiclink._token_ttl() + 1
        assert auth_magiclink.verify_magic_link(raw, "ip", "ua", now=later)["status"] == "invalid"

    def test_garbage_and_empty_tokens_are_invalid(self, reset_stores):
        assert auth_magiclink.verify_magic_link("totally-made-up", "ip", "ua")["status"] == "invalid"
        assert auth_magiclink.verify_magic_link("", "ip", "ua")["status"] == "invalid"
        assert auth_magiclink.verify_magic_link(None, "ip", "ua")["status"] == "invalid"


# ===========================================================================
# C. Redirect / next hardening (untrusted input)
# ===========================================================================
class TestNextHardening:
    @pytest.mark.parametrize("raw,expected_key", [
        ("/app", "app"),
        ("/app/", "app"),                       # trailing slash tolerated
        ("/app/transformation", "transformation"),
        ("/account", "account"),
        ("transformation", "transformation"),   # bare symbolic key
        ("app", "app"),
        ("/app/workspace", ""),                 # not on the allowlist
        ("//evil.com", ""),
        ("https://example.com", ""),
        ("http://evil.example", ""),
        ("/\\evil", ""),
        ("/app%2f..%2f..%2fexternal", ""),
        ("/app/../../external", ""),
        ("/etc/passwd", ""),
        ("app-evil", ""),
        ("", ""),
        ("   ", ""),
        (None, ""),
        (123, ""),
    ])
    def test_normalize_next_maps_to_key_or_empty(self, raw, expected_key):
        assert auth_magiclink.normalize_next(raw) == expected_key

    @pytest.mark.parametrize("malicious", [
        "https://example.com",
        "//evil.com",
        "/\\evil",
        "/app%2f..%2f..%2fexternal",
        "/app/../../external",
        "/etc/passwd",
    ])
    def test_malicious_next_redirects_to_safe_default(self, reset_stores, malicious):
        # End-to-end: even an active member who somehow submits a hostile next
        # lands on the safe default, and the redirect is always same-origin.
        _make_active_member("vec@x.com", time.time())
        box = _capturing_sender()
        auth_magiclink.request_magic_link("vec@x.com", "wp", malicious, "ip", "ua")
        r = auth_magiclink.verify_magic_link(_raw_token(box["link"]), "ip", "ua")
        assert r["redirect"] == "https://clarity.pro-mediations.com/app"
        assert r["redirect"].startswith("https://clarity.pro-mediations.com/")

    def test_resolve_next_path_rules(self, reset_stores):
        # Inactive members always go to onboarding, even for an allowlisted key.
        assert auth_magiclink.resolve_next_path("transformation", active=False) == "/onboarding"
        assert auth_magiclink.resolve_next_path("transformation", active=True) == "/app/transformation"
        assert auth_magiclink.resolve_next_path("", active=True) == "/app"
        assert auth_magiclink.resolve_next_path("bogus", active=True) == "/app"


# ===========================================================================
# D. HTTP routes
# ===========================================================================
class TestRoutes:
    def test_enter_returns_generic_ok(self, app_module):
        r = _post_form(app_module.app, "/auth/enter",
                       {"email": "route@x.com", "source": "wp-shell", "next": "/app"})
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_enter_malformed_email_is_400(self, app_module):
        r = _post_form(app_module.app, "/auth/enter", {"email": "nope", "source": "wp-shell"})
        assert r.status_code == 400
        assert r.json()["status"] == "error"

    def test_verify_redirects_and_sets_session_cookie(self, app_module):
        box = _capturing_sender()
        _post_form(app_module.app, "/auth/enter",
                   {"email": "rt2@x.com", "source": "wp-shell", "next": "/app"})
        raw = _raw_token(box["link"])
        r = _get_noredirect(app_module.app, f"/auth/verify?token={raw}")
        assert r.status_code == 303
        assert r.headers["location"] == "https://clarity.pro-mediations.com/onboarding"  # new user -> onboarding
        set_cookie = r.headers.get("set-cookie", "")
        assert "clarityos_session=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_verify_invalid_token_shows_generic_page(self, app_module):
        r = _get_noredirect(app_module.app, "/auth/verify?token=made-up")
        assert r.status_code == 400
        assert "no longer valid" in r.text.lower()
