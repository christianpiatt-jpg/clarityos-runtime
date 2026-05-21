"""
Tests for v74 / Unit 84 — Founding 500 Subscription Gate confirmation.

Covers POST /membership/confirm:
* Happy path: active subscription + accept_terms=true -> 200 with confirmed=true
* Subscription inactive -> 409 subscription_inactive
* Idempotency: second confirm returns 200, state unchanged
* Cohort full race-condition guard: not-a-member + cap full -> 409 cohort_full
* Anonymous request rejected with 401
* accept_terms=false rejected
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def stub_embedder(monkeypatch):
    import dewey_pipeline

    def fake_embed(text):
        if not text or not str(text).strip():
            return None
        h = abs(hash(str(text)))
        return [((h >> (i * 4)) & 0xFF) / 255.0 for i in range(8)]

    monkeypatch.setattr(dewey_pipeline, "embed_text_cached", fake_embed)
    monkeypatch.setattr(dewey_pipeline, "embed_text", lambda t: fake_embed(t) or [])
    monkeypatch.setattr(dewey_pipeline, "embed_object", lambda o: fake_embed(str(o)) or [0.0] * 8)
    yield


@pytest.fixture
def app_module(reset_stores, stub_embedder):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
    import secrets, time as _t
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=_t.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=_t.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _activate(client, sid):
    """Drive the user through /membership/activate so they're in the
    active cohort. v31 mock auto-confirm lands the membership
    synchronously, mirroring what the WordPress + Stripe Checkout
    webhook would do in production."""
    return client.post(
        "/membership/activate",
        headers=_auth(sid),
        json={"accept_terms": True},
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_confirm_membership_success(app_module, client):
    user, sid = _make_user(app_module, "felix", cohort="founder")
    # Pre-condition: user has paid and is active in the cohort.
    r0 = _activate(client, sid)
    assert r0.status_code == 200, r0.json()
    assert r0.json()["state"]["membership"]["status"] == "active"
    assert r0.json()["state"]["membership"]["confirmed"] is False

    # The confirmation endpoint.
    r = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": True},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    state = body["state"]
    assert state["membership"]["tier"] == "founding_500"
    assert state["membership"]["confirmed"] is True
    assert state["membership"]["confirmed_ts"] is not None


# ---------------------------------------------------------------------------
# Subscription inactive
# ---------------------------------------------------------------------------
def test_confirm_membership_subscription_inactive(app_module, client):
    user, sid = _make_user(app_module, "gina", cohort="founder")
    # Skip /activate — the user has not paid yet.
    r = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": True},
    )
    assert r.status_code == 409, r.json()
    assert r.json()["error"] == "subscription_inactive"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------
def test_confirm_membership_idempotent(app_module, client):
    user, sid = _make_user(app_module, "hank", cohort="founder")
    _activate(client, sid)

    r1 = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": True},
    )
    assert r1.status_code == 200
    confirmed_ts_1 = r1.json()["state"]["membership"]["confirmed_ts"]
    assert confirmed_ts_1 is not None

    # Second call should be a no-op success — state unchanged, same ts.
    r2 = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": True},
    )
    assert r2.status_code == 200, r2.json()
    confirmed_ts_2 = r2.json()["state"]["membership"]["confirmed_ts"]
    assert confirmed_ts_2 == confirmed_ts_1


# ---------------------------------------------------------------------------
# Cohort full race-condition guard
# ---------------------------------------------------------------------------
def test_confirm_membership_cohort_full(app_module, client, monkeypatch):
    """Edge case: user.membership_status=='active' but they're not a
    counted cohort member AND the cohort is at cap. This shouldn't
    happen in production (Stripe webhook adds to cohort atomically
    with status flip) but the contract requires 409 cohort_full."""
    import users_store, membership_store

    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 1)
    # Pre-fill the cohort directly (skipping /activate so we don't
    # trip the v29 flag gate on a no-cohort user).
    _make_user(app_module, "filler", cohort="founder")
    membership_store.add_member("filler")

    user, sid = _make_user(app_module, "ivy", cohort="founder")
    # Mark ivy active in users_store WITHOUT adding to membership_store —
    # simulates the race where the webhook flipped status before
    # cohort assignment landed.
    users_store.update_user("ivy", {
        "membership_tier": membership_store.FOUNDING_COHORT,
        "membership_status": "active",
        "membership_price": 50.0,
        "membership_started_ts": time.time(),
    })

    r = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": True},
    )
    assert r.status_code == 409, r.json()
    assert r.json()["error"] == "cohort_full"


# ---------------------------------------------------------------------------
# Auth + payload guards
# ---------------------------------------------------------------------------
def test_confirm_membership_anonymous_rejected(app_module, client):
    r = client.post(
        "/membership/confirm",
        json={"accept_terms": True},
    )
    assert r.status_code == 401


def test_confirm_membership_terms_required(app_module, client):
    user, sid = _make_user(app_module, "jay", cohort="founder")
    _activate(client, sid)

    r = client.post(
        "/membership/confirm",
        headers=_auth(sid),
        json={"accept_terms": False},
    )
    assert r.status_code == 400, r.json()
    assert r.json()["error"] == "terms_required"
