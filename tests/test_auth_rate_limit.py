"""
Tests for the /login + /register brute-force throttle (``app._throttle_auth``).

The throttle is IP-keyed (X-Forwarded-For first hop) on top of
``v29_hardening``'s token bucket. It's enforced in production but disabled
for the suite by default (conftest sets ``CLARITYOS_DISABLE_AUTH_RATE_LIMIT=1``)
so cumulative auth calls across tests don't drain a shared bucket. These
tests opt back in with ``monkeypatch.setenv`` and pin a distinct client IP
per case via ``X-Forwarded-For`` so each token bucket is isolated.

Capacities (see app.py): /login = 5 / 15 min per IP, /register = 3 / hr per IP.
"""
from __future__ import annotations

import pytest

import app as app_mod
from conftest import TestClient


def _xff(ip: str) -> dict[str, str]:
    """Force ``_client_ip`` to a known value so the per-IP bucket is
    deterministic and isolated from other tests."""
    return {"X-Forwarded-For": ip}


@pytest.fixture
def client(reset_stores, monkeypatch):
    # reset_stores clears the token buckets; re-enable enforcement (suite
    # default is "1" = off) so these tests exercise the real 429 path.
    monkeypatch.setenv("CLARITYOS_DISABLE_AUTH_RATE_LIMIT", "0")
    return TestClient(app_mod.app)


class TestLoginThrottle:
    def test_sixth_attempt_from_same_ip_is_429(self, client):
        ip = _xff("203.0.113.10")
        # capacity=5: the first 5 attempts clear the throttle and fail on
        # credentials (401, user does not exist); the 6th is rejected by the
        # throttle itself → 429.
        for _ in range(5):
            r = client.post(
                "/login", json={"username": "nope", "password": "bad"}, headers=ip
            )
            assert r.status_code == 401, r.text
        r = client.post(
            "/login", json={"username": "nope", "password": "bad"}, headers=ip
        )
        assert r.status_code == 429
        assert r.json()["error"] == "rate_limited"

    def test_other_ip_is_not_throttled(self, client):
        # Drain one IP's bucket completely.
        for _ in range(6):
            client.post(
                "/login",
                json={"username": "nope", "password": "bad"},
                headers=_xff("203.0.113.20"),
            )
        # A different IP starts with a full bucket → reaches the cred check (401),
        # not the throttle (429).
        r = client.post(
            "/login",
            json={"username": "nope", "password": "bad"},
            headers=_xff("203.0.113.21"),
        )
        assert r.status_code == 401


class TestRegisterThrottle:
    def test_fourth_signup_from_same_ip_is_429(self, client):
        ip = _xff("198.51.100.5")
        # capacity=3. The first 3 clear the throttle (whatever the downstream
        # outcome — created / invite-only / dup); the 4th is throttled.
        for i in range(3):
            r = client.post(
                "/register",
                json={"username": f"newuser{i}", "password": "password123"},
                headers=ip,
            )
            assert r.status_code != 429, r.text
        r = client.post(
            "/register",
            json={"username": "newuser_over", "password": "password123"},
            headers=ip,
        )
        assert r.status_code == 429
        assert r.json()["error"] == "rate_limited"


class TestThrottleDisabledByDefault:
    def test_suite_default_does_not_throttle(self, reset_stores, monkeypatch):
        # Mirror the suite default: gate OFF. Many rapid logins must never
        # 429 — this is the invariant that keeps the rest of the suite safe.
        monkeypatch.setenv("CLARITYOS_DISABLE_AUTH_RATE_LIMIT", "1")
        c = TestClient(app_mod.app)
        for _ in range(12):
            r = c.post(
                "/login",
                json={"username": "nope", "password": "bad"},
                headers=_xff("203.0.113.30"),
            )
            assert r.status_code == 401
