"""
Tests for v32 — Public website + Waitlist pipeline.

Covers:
* waitlist_store: email validation, normalization, idempotent add,
  status transitions, listing + filter + count.
* /waitlist/join (public): happy path, bad email → 400, IP rate-limit →
  429, idempotent on duplicate email.
* /public/cohort_status: shape contract.
* /founder/waitlist + /founder/waitlist/update: founder-only auth gate,
  status transitions including converted-with-user_id.
* Cohort-full behavior: /membership/activate returns waitlisted=true
  and the activation code path is short-circuited; public site can
  still drive /waitlist/join.
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
    import secrets
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# waitlist_store — pure-Python unit tests
# ---------------------------------------------------------------------------
def test_normalize_email_happy(reset_stores):
    import waitlist_store
    assert waitlist_store.normalize_email("Foo@BAR.com") == "foo@bar.com"
    assert waitlist_store.normalize_email("  user@example.org  ") == "user@example.org"


def test_normalize_email_rejects_invalid(reset_stores):
    import waitlist_store
    for bad in ["", "notanemail", "no@dot", "two@@dots.com", "x@.com"]:
        with pytest.raises(ValueError):
            waitlist_store.normalize_email(bad)


def test_normalize_email_rejects_too_long(reset_stores):
    import waitlist_store
    huge = "a" * 400 + "@example.com"
    with pytest.raises(ValueError):
        waitlist_store.normalize_email(huge)


def test_add_waitlist_entry_happy(reset_stores):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(
        email="alice@example.com", name="Alice", source="website",
    )
    assert rec["email"] == "alice@example.com"
    assert rec["name"] == "Alice"
    assert rec["source"] == "website"
    assert rec["status"] == "waiting"
    assert rec["id"].startswith("wl_")


def test_add_waitlist_entry_idempotent_on_duplicate(reset_stores):
    import waitlist_store
    a = waitlist_store.add_waitlist_entry(email="dup@example.com")
    b = waitlist_store.add_waitlist_entry(email="DUP@example.com", name="changed")
    # Same id; second call returns the existing record untouched.
    assert a["id"] == b["id"]
    assert b["name"] is None  # original record had no name


def test_add_waitlist_entry_after_dropped_creates_new(reset_stores):
    import waitlist_store
    a = waitlist_store.add_waitlist_entry(email="ghost@example.com")
    waitlist_store.update_status(a["id"], status="dropped")
    b = waitlist_store.add_waitlist_entry(email="ghost@example.com", name="Came back")
    assert a["id"] != b["id"]
    assert b["status"] == "waiting"


def test_status_transitions(reset_stores):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="x@example.com")
    rid = rec["id"]
    waitlist_store.mark_contacted(rid, note="emailed once")
    cur = waitlist_store.get_waitlist_entry(rid)
    assert cur["status"] == "contacted"
    assert cur["contacted_ts"] is not None
    waitlist_store.mark_converted(rid, user_id="alice")
    cur = waitlist_store.get_waitlist_entry(rid)
    assert cur["status"] == "converted"
    assert cur["user_id"] == "alice"
    assert cur["converted_ts"] is not None


def test_converted_requires_user_id(reset_stores):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="y@example.com")
    with pytest.raises(ValueError):
        waitlist_store.update_status(rec["id"], status="converted", user_id="")


def test_list_waitlist_filter_and_sort(reset_stores):
    import waitlist_store
    a = waitlist_store.add_waitlist_entry(email="a@example.com", ts=1000.0)
    b = waitlist_store.add_waitlist_entry(email="b@example.com", ts=2000.0)
    c = waitlist_store.add_waitlist_entry(email="c@example.com", ts=3000.0)
    waitlist_store.update_status(b["id"], status="contacted")

    rows = waitlist_store.list_waitlist()
    assert [r["email"] for r in rows] == ["c@example.com", "b@example.com", "a@example.com"]

    waiting = waitlist_store.list_waitlist(status="waiting")
    assert [r["email"] for r in waiting] == ["c@example.com", "a@example.com"]


def test_count_waitlist(reset_stores):
    import waitlist_store
    waitlist_store.add_waitlist_entry(email="x1@example.com")
    waitlist_store.add_waitlist_entry(email="x2@example.com")
    rec3 = waitlist_store.add_waitlist_entry(email="x3@example.com")
    waitlist_store.update_status(rec3["id"], status="contacted")
    assert waitlist_store.count_waitlist() == 3
    assert waitlist_store.count_waitlist(status="waiting") == 2
    assert waitlist_store.count_waitlist(status="contacted") == 1


def test_invalid_source_rejected(reset_stores):
    import waitlist_store
    with pytest.raises(ValueError):
        waitlist_store.add_waitlist_entry(email="z@example.com", source="not_a_source")


# ---------------------------------------------------------------------------
# /waitlist/join — public endpoint
# ---------------------------------------------------------------------------
def test_waitlist_join_happy(app_module, client):
    r = client.post(
        "/waitlist/join",
        json={"email": "first@example.com", "name": "First", "source": "website"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "waiting"
    assert body["id"].startswith("wl_")


def test_waitlist_join_does_not_require_auth(app_module, client):
    r = client.post("/waitlist/join", json={"email": "noauth@example.com"})
    assert r.status_code == 200


def test_waitlist_join_rejects_bad_email(app_module, client):
    r = client.post("/waitlist/join", json={"email": "not-an-email"})
    assert r.status_code == 400
    assert r.json()["error"] == "bad_email"


def test_waitlist_join_idempotent(app_module, client):
    r1 = client.post("/waitlist/join", json={"email": "twice@example.com"})
    r2 = client.post("/waitlist/join", json={"email": "twice@example.com", "name": "ignored"})
    # Both succeed and return the same entry id.
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_waitlist_join_rate_limit(app_module, client):
    """11th submission from the same IP within the window should 429.
    Capacity is 10 per 600s in app.py."""
    for i in range(10):
        r = client.post(
            "/waitlist/join",
            json={"email": f"bot{i}@example.com"},
        )
        assert r.status_code == 200, f"call {i}: {r.json()}"
    r11 = client.post(
        "/waitlist/join", json={"email": "overflow@example.com"},
    )
    assert r11.status_code == 429
    assert r11.json()["error"] == "rate_limited"


def test_waitlist_join_lowercases_email(app_module, client):
    import waitlist_store
    client.post("/waitlist/join", json={"email": "Mixed@Example.COM"})
    rec = waitlist_store.find_by_email("mixed@example.com")
    assert rec is not None
    assert rec["email"] == "mixed@example.com"


# ---------------------------------------------------------------------------
# /public/cohort_status
# ---------------------------------------------------------------------------
def test_public_cohort_status_no_auth(app_module, client):
    r = client.get("/public/cohort_status")
    assert r.status_code == 200
    body = r.json()
    assert body["cohort"] == "founding_500"
    assert body["cap"] == 500
    assert body["is_full"] is False
    assert body["active_count"] == 0


def test_public_cohort_status_reflects_full(app_module, client, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 1)
    membership_store.add_member("u1")
    r = client.get("/public/cohort_status")
    body = r.json()
    assert body["is_full"] is True
    assert body["active_count"] == 1


# ---------------------------------------------------------------------------
# /founder/waitlist + /founder/waitlist/update
# ---------------------------------------------------------------------------
def test_founder_list_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "lurker", cohort=None)
    r = client.get("/founder/waitlist", headers=_auth(sid))
    assert r.status_code == 403


def test_founder_list_returns_entries(app_module, client):
    import waitlist_store
    waitlist_store.add_waitlist_entry(email="a@example.com")
    waitlist_store.add_waitlist_entry(email="b@example.com")

    user, sid = _make_user(app_module, "founder1", cohort="founder")
    r = client.get("/founder/waitlist", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert len(body["entries"]) == 2
    assert body["counts"]["waiting"] == 2
    assert body["counts"]["total"] == 2


def test_founder_list_filter_by_status(app_module, client):
    import waitlist_store
    waitlist_store.add_waitlist_entry(email="a@example.com")
    rec = waitlist_store.add_waitlist_entry(email="b@example.com")
    waitlist_store.update_status(rec["id"], status="contacted")

    user, sid = _make_user(app_module, "founder2", cohort="founder")
    r = client.get("/founder/waitlist?status=contacted", headers=_auth(sid))
    body = r.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["email"] == "b@example.com"


def test_founder_list_rejects_bad_status(app_module, client):
    user, sid = _make_user(app_module, "founder3", cohort="founder")
    r = client.get("/founder/waitlist?status=garbage", headers=_auth(sid))
    assert r.status_code == 400


def test_founder_update_status_transition(app_module, client):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="t@example.com")

    user, sid = _make_user(app_module, "founder4", cohort="founder")
    r = client.post(
        "/founder/waitlist/update",
        headers=_auth(sid),
        json={"id": rec["id"], "status": "contacted", "note": "emailed"},
    )
    assert r.status_code == 200, r.json()
    entry = r.json()["entry"]
    assert entry["status"] == "contacted"
    assert entry["note"] == "emailed"


def test_founder_update_converted_requires_user_id(app_module, client):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="conv@example.com")

    user, sid = _make_user(app_module, "founder5", cohort="founder")
    r = client.post(
        "/founder/waitlist/update",
        headers=_auth(sid),
        json={"id": rec["id"], "status": "converted"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "user_id_required"


def test_founder_update_converted_with_user_id(app_module, client):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="ok@example.com")

    user, sid = _make_user(app_module, "founder6", cohort="founder")
    r = client.post(
        "/founder/waitlist/update",
        headers=_auth(sid),
        json={"id": rec["id"], "status": "converted", "user_id": "alice"},
    )
    assert r.status_code == 200
    entry = r.json()["entry"]
    assert entry["status"] == "converted"
    assert entry["user_id"] == "alice"


def test_founder_update_unknown_id(app_module, client):
    user, sid = _make_user(app_module, "founder7", cohort="founder")
    r = client.post(
        "/founder/waitlist/update",
        headers=_auth(sid),
        json={"id": "wl_does_not_exist", "status": "contacted"},
    )
    assert r.status_code == 404


def test_founder_update_requires_founder(app_module, client):
    import waitlist_store
    rec = waitlist_store.add_waitlist_entry(email="z@example.com")

    user, sid = _make_user(app_module, "stranger", cohort=None)
    r = client.post(
        "/founder/waitlist/update",
        headers=_auth(sid),
        json={"id": rec["id"], "status": "dropped"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Cohort-full integration with /membership/activate
# ---------------------------------------------------------------------------
def test_activate_when_cohort_full_returns_friendly_message(app_module, client, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 1)
    # First user fills the cohort.
    u1, sid1 = _make_user(app_module, "first", cohort="founder")
    r1 = client.post(
        "/membership/activate", headers=_auth(sid1), json={"accept_terms": True},
    )
    assert r1.status_code == 200

    # Second user gets the friendly waitlist message.
    u2, sid2 = _make_user(app_module, "second", cohort="founder")
    r2 = client.post(
        "/membership/activate", headers=_auth(sid2), json={"accept_terms": True},
    )
    body = r2.json()
    assert body["waitlisted"] is True
    assert "message" in body
    assert "full" in body["message"].lower()


def test_public_can_join_waitlist_when_cohort_full(app_module, client, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 0)
    # Cohort is "full" (cap=0); public form still works.
    r = client.post(
        "/waitlist/join", json={"email": "hopeful@example.com"},
    )
    assert r.status_code == 200
    cohort_r = client.get("/public/cohort_status")
    assert cohort_r.json()["is_full"] is True
