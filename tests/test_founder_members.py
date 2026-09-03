"""
#150 -- the founder can create an account and see the accounts.

★ WHAT THESE PIN. A user doc was born only at verify_magic_link ->
ensure_user; the founder console could not create one, and "active 4"
had no list of who. Now:

  POST /founder/members/create  births the doc by the SAME fn a link click
                                uses (field set equality asserted), seats a
                                membership by the SAME body Activate uses,
                                sends the person's link through the SAME
                                request_magic_link (throttle intact), and
                                returns NEITHER a token NOR a session.
  GET  /founder/members         a projected page: no password hash, no salt,
                                no operator id; newest first; email= lookup.

Both founder-only (401 no session / 403 member). The email sender is
captured, never real.
"""
from __future__ import annotations

import secrets
import time

import pytest

from conftest import TestClient

import auth_magiclink as am
import membership_store
import sessions_store
import users_store


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


@pytest.fixture
def sender(monkeypatch):
    """Capture every emitted link; the raw token is readable from it."""
    box: dict = {"links": [], "emails": []}
    def _send(email, link, ctx):
        box["links"].append(link); box["emails"].append(email)
        return True
    monkeypatch.setattr(am, "EMAIL_SENDER", _send)
    # belt: reset_stores already resets these via am._reset_memory_for_tests
    for name in ("_MEM_TOKENS", "_RL_HITS"):
        store = getattr(am, name, None)
        if isinstance(store, dict):
            store.clear()
    return box


def _make_user(username, cohort="founder", *, active=False):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    patch = {"cohort": cohort}
    if active:
        patch.update({"membership_status": "active", "membership_tier": "founding_500"})
    users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _founder():
    return _make_user("founder_x", cohort="founder")


def _member():
    return _make_user("member_x", cohort="founding_500", active=True)


RESPONSE_KEYS = {"ok", "created", "activated", "activate_error", "sent", "link_throttled", "email_hash"}
ROW_KEYS = {"email", "cohort", "membership_status", "membership_tier",
            "created_at", "last_seen", "balance_display", "auth_method"}


# ===========================================================================
# create
# ===========================================================================
def test_create_births_the_same_doc_shape_as_a_magic_link_click(client, sender):
    """The link path and the founder path share ONE birth fn."""
    # (1) a magic-link birth, end to end through the module
    am.request_magic_link("walker.one@example.com", "test", "app", "ip-1", "ua", now=time.time())
    token = sender["links"][-1].split("token=", 1)[1]
    r = am.verify_magic_link(token, "ip-1", "ua")
    assert r["status"] == "ok" and r["created"] is True
    link_doc = users_store.get_user("walker.one@example.com")

    # (2) the founder path
    h = _founder()
    resp = client.post("/founder/members/create",
                       json={"email": "Walker.Two@Example.com", "send_link": False}, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == RESPONSE_KEYS
    assert body["created"] is True and body["activated"] is False and body["sent"] is False
    doc = users_store.get_user("walker.two@example.com")  # normalised lowercase
    assert doc is not None

    # identical field set; the values that must differ do
    assert set(doc.keys()) == set(link_doc.keys())
    assert doc["cohort"] == "member" == link_doc["cohort"]
    assert doc["auth_method"] == "magic_link"
    assert doc["tier"] == "free"
    assert str(doc["operator_id"]).startswith("op_") and doc["operator_id"] != link_doc["operator_id"]
    assert doc["password_hash"] != link_doc["password_hash"]


def test_create_is_idempotent_and_resends_the_link(client, sender):
    h = _founder()
    a = client.post("/founder/members/create", json={"email": "again@example.com"}, headers=h).json()
    op_before = users_store.get_user("again@example.com")["operator_id"]
    b = client.post("/founder/members/create", json={"email": "again@example.com"}, headers=h).json()
    assert a["created"] is True and a["sent"] is True
    assert b["created"] is False and b["sent"] is True
    assert users_store.get_user("again@example.com")["operator_id"] == op_before
    assert len(sender["links"]) == 2 and sender["emails"] == ["again@example.com"] * 2


def test_create_never_returns_the_token_link_or_a_session(client, sender):
    h = _founder()
    resp = client.post("/founder/members/create", json={"email": "secret@example.com"}, headers=h)
    body = resp.json()
    assert set(body.keys()) == RESPONSE_KEYS
    link = sender["links"][-1]
    token = link.split("token=", 1)[1]
    assert token not in resp.text and link not in resp.text
    assert "session" not in resp.text.lower()
    # the email itself is not echoed either -- only its hash
    assert "secret@example.com" not in resp.text
    assert body["email_hash"] == am._email_hash("secret@example.com")


def test_create_with_activate_seats_exactly_as_the_activate_route(client, sender):
    h = _founder()
    # via create
    a = client.post("/founder/members/create",
                    json={"email": "seated.a@example.com", "activate": True, "send_link": False},
                    headers=h).json()
    assert a["created"] is True and a["activated"] is True
    # via the route, on a doc born the founder way, same price (0 = grant)
    client.post("/founder/members/create",
                json={"email": "seated.b@example.com", "send_link": False}, headers=h)
    r = client.post("/founder/membership/activate",
                    json={"user": "seated.b@example.com", "price": 0}, headers=h)
    assert r.status_code == 200, r.text

    va = users_store.get_membership_view("seated.a@example.com")
    vb = users_store.get_membership_view("seated.b@example.com")
    for k in ("tier", "price", "status", "billing_state", "cancelled_ts"):
        assert va[k] == vb[k], k
    assert va["status"] == "active" and va["tier"] == membership_store.FOUNDING_COHORT
    assert va["price"] == 0.0 and va["cancelled_ts"] is None
    assert membership_store.is_member("seated.a@example.com")
    assert membership_store.is_member("seated.b@example.com")

    # activating again is a no-op, reported as such
    again = client.post("/founder/members/create",
                        json={"email": "seated.a@example.com", "activate": True, "send_link": False},
                        headers=h).json()
    assert again["created"] is False and again["activated"] is False


def test_create_honours_the_per_email_throttle(client, sender):
    h = _founder()
    results = [client.post("/founder/members/create", json={"email": "burst@example.com"}, headers=h).json()
               for _ in range(am._ENTER_EMAIL_MAX + 1)]
    assert all(r["sent"] for r in results[:am._ENTER_EMAIL_MAX])
    last = results[-1]
    assert last["sent"] is False and last["link_throttled"] is True
    assert len(sender["links"]) == am._ENTER_EMAIL_MAX


def test_create_rejects_a_malformed_email(client, sender):
    h = _founder()
    r = client.post("/founder/members/create", json={"email": "not-an-email"}, headers=h)
    assert r.status_code == 400
    assert users_store.get_user("not-an-email") is None


def test_create_is_founder_only(client, sender):
    assert client.post("/founder/members/create", json={"email": "x@example.com"}).status_code == 401
    m = _member()
    r = client.post("/founder/members/create", json={"email": "x@example.com"}, headers=m)
    assert r.status_code == 403
    assert users_store.get_user("x@example.com") is None
    assert sender["links"] == []


# ===========================================================================
# list
# ===========================================================================
def test_list_projects_rows_without_secrets_newest_first_and_pages(client, sender):
    h = _founder()  # the founder's own doc is a row too -- it lists everything
    base = time.time() + 1000  # newer than the founder's doc, so the order is defined
    for i, e in enumerate(("l1@example.com", "l2@example.com", "l3@example.com")):
        client.post("/founder/members/create", json={"email": e, "send_link": False}, headers=h)
        users_store.update_user(e, {"created_at": base + i})
    r = client.get("/founder/members?limit=2&offset=0", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2 and body["has_more"] is True
    for row in body["members"]:
        assert set(row.keys()) == ROW_KEYS
    dumped = r.text
    for secret in ("password_hash", "salt", "operator_id", "stripe_customer_id"):
        assert secret not in dumped
    emails = [m["email"] for m in body["members"]]
    assert emails == ["l3@example.com", "l2@example.com"]  # newest first
    assert body["members"][0]["cohort"] == "member"
    assert body["members"][0]["balance_display"] == "$0.00"  # a fresh doc, exactly

    r2 = client.get("/founder/members?limit=2&offset=2", headers=h).json()
    # the last page: l1, then the founder's own (older) doc; nothing after
    assert [m["email"] for m in r2["members"]] == ["l1@example.com", "founder_x"]
    assert r2["has_more"] is False


def test_list_email_lookup_finds_one_or_none(client, sender):
    h = _founder()
    client.post("/founder/members/create",
                json={"email": "find.me@example.com", "activate": True, "send_link": False}, headers=h)
    hit = client.get("/founder/members?email=Find.Me@Example.com", headers=h).json()
    assert hit["count"] == 1 and hit["members"][0]["email"] == "find.me@example.com"
    assert hit["members"][0]["membership_status"] == "active"
    miss = client.get("/founder/members?email=nobody@example.com", headers=h).json()
    assert miss["count"] == 0 and miss["members"] == []


def test_list_is_founder_only(client, sender):
    assert client.get("/founder/members").status_code == 401
    assert client.get("/founder/members", headers=_member()).status_code == 403


# ===========================================================================
# the birth fn itself
# ===========================================================================
def test_ensure_user_is_public_with_a_back_compat_alias(reset_stores):
    assert am._ensure_user is am.ensure_user
    assert am.ensure_user("born@example.com", time.time()) is True
    assert am.ensure_user("born@example.com", time.time()) is False


# ===========================================================================
# hardenings from the adversarial pass
# ===========================================================================
def test_create_sent_is_false_when_the_sender_fails(client, monkeypatch, reset_stores):
    """`sent` means the sender reported success, never merely attempted."""
    monkeypatch.setattr(am, "EMAIL_SENDER", lambda email, link, ctx: False)
    h = _founder()
    body = client.post("/founder/members/create", json={"email": "unsent@example.com"}, headers=h).json()
    assert body["created"] is True and body["sent"] is False and body["link_throttled"] is False


def test_create_with_activate_on_a_full_cohort_reports_it_and_still_sends_the_link(client, sender, monkeypatch):
    def full(user, name=membership_store.FOUNDING_COHORT):
        raise ValueError("cohort_full")
    monkeypatch.setattr(membership_store, "add_member", full)
    h = _founder()
    r = client.post("/founder/members/create", json={"email": "late@example.com", "activate": True}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True and body["activated"] is False
    assert body["activate_error"] == "cohort_error"
    assert body["sent"] is True and len(sender["links"]) == 1
    assert users_store.get_user("late@example.com") is not None  # the doc exists, and the founder was told


def test_create_never_logs_the_raw_email(client, sender, caplog):
    caplog.set_level("INFO")
    h = _founder()
    client.post("/founder/members/create", json={"email": "quiet.walker@example.com"}, headers=h).json()
    assert not any("quiet.walker@example.com" in rec.getMessage() for rec in caplog.records)
    # ... while the hash-scoped throttle bucket is what request_magic_link saw
    ehash = am._email_hash("quiet.walker@example.com")
    assert any(ehash in rec.getMessage() for rec in caplog.records)


def test_list_email_lookup_tries_the_exact_key_first(client, sender):
    """A legacy /login username is stored as typed; the lookup must find it
    before normalising, or the console would offer to create a duplicate."""
    h = _founder()
    import bcrypt
    users_store.create_user(username="Legacy.User", password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                            salt="", tier="free", created_at=time.time())
    hit = client.get("/founder/members?email=Legacy.User", headers=h).json()
    assert hit["count"] == 1 and hit["members"][0]["email"] == "Legacy.User"
    bad = client.get("/founder/members?email=a/b", headers=h).json()
    assert bad["count"] == 0
