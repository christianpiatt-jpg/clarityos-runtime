"""
#124 -- citizens are numbered, cohort is a range, the founder is a controller.

★ WHAT THESE PIN. One global counter; a number minted at FIRST LOGIN only
(never on create); a second login changes nothing; existing docs numbered
once in created_at order with the Outlook doc first; the founder is
doc.controller and both gates read ONE predicate (drift guard); a
founder-granted walker is not a citizen; the derived labels for 1 / 500 /
501 / controller; the display suffix rule; /me and the founder rows carry
the identity; the one-deploy string shim still opens the gates.
"""
from __future__ import annotations

import secrets
import time

import pytest

from conftest import TestClient

import auth_magiclink as am
import membership_store
import runtime_http as rh
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
    box: dict = {"links": []}
    monkeypatch.setattr(am, "EMAIL_SENDER", lambda email, link, ctx: box["links"].append(link) or True)
    return box


def _login_via_link(sender, email: str, now=None) -> dict:
    """The real first-login path: request -> click."""
    now = now or time.time()
    am.request_magic_link(email, "test", "app", f"ip-{email}", "ua", now=now)
    token = sender["links"][-1].split("token=", 1)[1]
    r = am.verify_magic_link(token, f"ip-{email}", "ua", now=now)
    assert r["status"] == "ok", r
    return r


def _session_for(username: str, **doc) -> dict:
    import bcrypt
    if not users_store.get_user(username):
        users_store.create_user(username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                                salt="", tier="free", created_at=doc.pop("created_at", time.time()))
    if doc:
        users_store.update_user(username, doc)
    sid = "sess_" + secrets.token_urlsafe(12)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# rule 1 -- mint at first login, idempotent
# ===========================================================================
def test_number_is_minted_on_first_verify_only_and_a_second_login_changes_nothing(reset_stores, sender):
    a = _login_via_link(sender, "first@example.com")
    assert a["created"] is True and a["member_number"] == 1
    doc1 = dict(users_store.get_user("first@example.com"))
    b = _login_via_link(sender, "first@example.com")
    assert b["created"] is False and b["member_number"] == 1
    doc2 = users_store.get_user("first@example.com")
    assert doc2["member_number"] == 1
    assert doc2["operator_id"] == doc1["operator_id"]
    # the counter moved exactly once
    c = _login_via_link(sender, "second@example.com")
    assert c["member_number"] == 2


def test_console_create_gets_no_number_until_the_owner_clicks(client, sender):
    h = _session_for("founder_x", controller=True)
    r = client.post("/founder/members/create", json={"email": "ruy@example.com"}, headers=h)
    assert r.status_code == 200, r.text
    doc = users_store.get_user("ruy@example.com")
    assert "member_number" not in doc or not doc.get("member_number")
    # the owner clicks the link the console sent -> the NEXT number is minted
    # (relative: the first test to import app also numbers the bootstrap admin)
    n0 = users_store._MEMORY_COUNTER["next"]
    token = sender["links"][-1].split("token=", 1)[1]
    v = am.verify_magic_link(token, "ip", "ua")
    assert v["status"] == "ok" and v["member_number"] == n0
    assert users_store.get_user("ruy@example.com")["member_number"] == n0


def test_ensure_user_writes_no_cohort_string(reset_stores):
    am.ensure_user("clean@example.com", time.time())
    doc = users_store.get_user("clean@example.com")
    assert "cohort" not in doc


# ===========================================================================
# rule 6 -- existing docs numbered once, created_at order, Outlook first
# ===========================================================================
def test_existing_docs_are_numbered_once_in_created_at_order_with_the_controller_first(reset_stores):
    import bcrypt
    def mk(u, t):
        users_store.create_user(username=u, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                                salt="", tier="free", created_at=t)
    mk("old@example.com", 1000.0)
    mk("mid@example.com", 2000.0)
    mk("christian.piatt@outlook.com", 3000.0)   # newest, but the controller
    mk("new@example.com", 4000.0)
    got = users_store.number_existing_users(
        first=("christian.piatt@outlook.com",),
        controllers=("christian.piatt@outlook.com", "admin"),
    )
    assert got == [("christian.piatt@outlook.com", 1), ("old@example.com", 2),
                   ("mid@example.com", 3), ("new@example.com", 4)]
    assert users_store.get_user("christian.piatt@outlook.com")["controller"] is True
    assert users_store.citz_id(users_store.get_user("christian.piatt@outlook.com")) == "citz-000001chr"
    # idempotent: a second pass assigns nothing and moves nothing
    assert users_store.number_existing_users(first=("christian.piatt@outlook.com",)) == []
    assert users_store.get_user("old@example.com")["member_number"] == 2


def test_app_startup_numbered_the_docs_it_found(app_module):
    """The startup pass ran at import (idempotent). The bootstrap admin doc
    exists and is a controller; a doc created after boot is NOT numbered
    until its owner clicks."""
    # reset_stores wipes the admin doc the import-time pass numbered; run the
    # bootstrap again the way a boot would and check what it writes.
    app_module._bootstrap_admin()
    admin = users_store.get_user(app_module.ADMIN_USER)
    assert admin is not None and admin.get("controller") is True
    assert users_store.derive_cohort(admin) == "controller"
    got = users_store.number_existing_users(first=(), controllers=(app_module.ADMIN_USER,))
    assert (app_module.ADMIN_USER, users_store.get_user(app_module.ADMIN_USER)["member_number"]) in got


# ===========================================================================
# rule 5 -- the founder is a controller; both gates read ONE predicate
# ===========================================================================
def test_gates_admit_a_controller_and_refuse_a_citizen(client):
    h_ctrl = _session_for("ctrl@example.com", controller=True)
    h_cit = _session_for("cit@example.com", member_number=7, membership_status="active",
                         membership_tier="founding_500", membership_price=50.0)
    assert client.get("/founder/members", headers=h_ctrl).status_code == 200
    assert client.get("/founder/members", headers=h_cit).status_code == 403
    assert client.get("/org/timeline/24h", headers=h_ctrl).status_code == 200
    r = client.get("/org/timeline/24h", headers=h_cit)
    assert r.status_code == 403 and "Founder cohort required" in r.text


def test_the_one_deploy_shim_still_opens_the_gates_for_the_old_strings(client):
    for old in ("founder", "founder_exception", "admin"):
        h = _session_for(f"legacy_{old}@example.com", cohort=old)
        assert client.get("/founder/members", headers=h).status_code == 200, old
        assert client.get("/org/timeline/24h", headers=h).status_code == 200, old
    h = _session_for("legacy_member@example.com", cohort="member")
    assert client.get("/founder/members", headers=h).status_code == 403


def test_drift_guard_both_gates_read_users_store_is_controller(client, monkeypatch):
    """Flip the ONE predicate and both gates flip with it."""
    h = _session_for("nobody@example.com")
    assert client.get("/founder/members", headers=h).status_code == 403
    assert client.get("/org/timeline/24h", headers=h).status_code == 403
    monkeypatch.setattr(users_store, "is_controller", lambda doc: True)
    assert client.get("/founder/members", headers=h).status_code == 200
    assert client.get("/org/timeline/24h", headers=h).status_code == 200
    assert rh.require_founder is not None  # the runtime_http gate is the one under test above


# ===========================================================================
# rule 7 -- a founder grant does not confer citizenship
# ===========================================================================
def test_founder_activated_walker_is_not_a_citizen(client, sender):
    h = _session_for("founder_x", controller=True)
    r = client.post("/founder/members/create",
                    json={"email": "walker@example.com", "activate": True, "send_link": False}, headers=h)
    assert r.status_code == 200 and r.json()["activated"] is True
    doc = users_store.get_user("walker@example.com")
    assert doc["membership_status"] == "active" and doc["membership_tier"] == "founding_500"
    assert doc["membership_granted"] is True
    assert users_store.is_citizen(doc) is False
    # a paid founding membership IS citizenship
    paid = _session_for("paid@example.com", membership_status="active", membership_tier="founding_500",
                        membership_price=50.0)
    assert users_store.is_citizen(users_store.get_user("paid@example.com")) is True
    _ = paid


# ===========================================================================
# rules 2/3 -- labels and the display id
# ===========================================================================
def test_labels_for_1_500_501_and_controller():
    assert users_store.derive_cohort({"member_number": 1}) == "founding"
    assert users_store.derive_cohort({"member_number": 500}) == "founding"
    assert users_store.derive_cohort({"member_number": 501}) == "all"
    assert users_store.derive_cohort({}) == "all"
    assert users_store.derive_cohort({"member_number": 3, "controller": True}) == "controller"


def test_suffix_rule():
    assert users_store.citz_suffix("christian.piatt@outlook.com") == "chr"
    assert users_store.citz_suffix("ch.x@example.com") == "ch0"
    assert users_store.citz_suffix("-a-@example.com") == "0a0"
    assert users_store.citz_suffix("A.B@example.com") == "a0b"
    assert users_store.citz_suffix("ab@example.com") == "ab0"
    assert users_store.citz_id({"username": "christian.piatt@outlook.com", "member_number": 1}) == "citz-000001chr"
    assert users_store.citz_id({"username": "ch.x@e.com", "member_number": 7}) == "citz-000007ch0"
    assert users_store.citz_id({"username": "x@e.com"}) is None


# ===========================================================================
# rule 4 -- /me and the founder rows carry the identity; cohort is derived
# ===========================================================================
def _arm_member_flags():
    """reset_stores re-arms v28 for the three legacy invite cohorts only. Arm
    the LEGACY "member" string and expect the derived labels to light through
    the alias shim -- the same path a legacy operator override takes in prod."""
    import v29_hardening as h
    h.set_flag("v28_surfaces", True, cohort="member")
    h.set_flag("membership_ui_enabled", True, cohort="member")


def test_me_carries_number_citizen_controller_and_citz_id(client, sender):
    _arm_member_flags()
    _login_via_link(sender, "christian.piatt@outlook.com")
    users_store.update_user("christian.piatt@outlook.com", {"controller": True})
    h = _session_for("christian.piatt@outlook.com")
    body = client.get("/me", headers=h).json()
    assert body["member_number"] == 1
    assert body["controller"] is True
    assert body["citz_id"] == "citz-000001chr"
    assert body["cohort"] == "controller"
    assert body["operator"] is True
    # a walker
    _login_via_link(sender, "walker2@example.com")
    w = client.get("/me", headers=_session_for("walker2@example.com")).json()
    assert w["member_number"] == 2 and w["citizen"] is False and w["controller"] is False
    assert w["citz_id"] == "citz-000002wal" and w["cohort"] == "founding"
    assert w["features"]["v28_surfaces"] is True  # the cockpit works


def test_membership_state_shows_the_id(client, sender):
    _arm_member_flags()
    _login_via_link(sender, "shown@example.com")
    h = _session_for("shown@example.com")
    r = client.get("/membership/state", headers=h)
    assert r.status_code == 200, r.text
    ident = r.json()["state"]["identity"]
    assert ident["member_number"] == 1 and ident["citz_id"] == "citz-000001sho"
    assert ident["citizen"] is False and ident["controller"] is False


def test_founder_members_rows_carry_numbers_in_created_at_order(client, sender):
    h = _session_for("founder_x", controller=True)
    for i, e in enumerate(("r1@example.com", "r2@example.com", "r3@example.com")):
        client.post("/founder/members/create", json={"email": e, "send_link": False}, headers=h)
        users_store.update_user(e, {"created_at": 5000.0 + i})
    users_store.number_existing_users()
    rows = client.get("/founder/members?limit=10", headers=h).json()["members"]
    by_email = {r["email"]: r for r in rows}
    assert by_email["r1@example.com"]["member_number"] < by_email["r2@example.com"]["member_number"] < by_email["r3@example.com"]["member_number"]
    assert by_email["r1@example.com"]["citz_id"].startswith("citz-")
    assert by_email["r1@example.com"]["cohort"] in ("founding", "all")
    assert by_email["r1@example.com"]["citizen"] is False
    assert by_email["founder_x"]["controller"] is True
    for r in rows:
        for secret in ("password_hash", "salt", "operator_id"):
            assert secret not in r


# ===========================================================================
# hardenings from the adversarial pass
# ===========================================================================
def test_a_mint_failure_never_burns_the_click(reset_stores, sender, monkeypatch):
    def boom(username):
        raise RuntimeError("counter down")
    monkeypatch.setattr(users_store, "assign_member_number", boom)
    r = _login_via_link(sender, "unlucky@example.com")
    assert r["status"] == "ok" and r["member_number"] is None
    assert users_store.get_user("unlucky@example.com") is not None


def test_two_concurrent_first_logins_for_one_address_mint_one_number(reset_stores):
    import threading
    am.ensure_user("race@example.com", time.time())
    out: list = []
    def go():
        out.append(users_store.assign_member_number("race@example.com"))
    ts = [threading.Thread(target=go) for _ in range(8)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert set(out) == {1}
    assert users_store.get_user("race@example.com")["member_number"] == 1
    assert users_store._MEMORY_COUNTER["next"] == 2  # exactly one number taken


def test_the_boot_pass_is_one_time_a_doc_born_after_it_waits_for_the_click(reset_stores, sender):
    import bcrypt
    users_store.create_user(username="before@example.com", password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                            salt="", tier="free", created_at=1000.0)
    first = users_store.number_existing_users(now=5000.0)
    assert first == [("before@example.com", 1)]
    # born after the migration (a console create, say)
    am.ensure_user("after@example.com", 6000.0)
    users_store.update_user("after@example.com", {"created_at": 6000.0})
    assert users_store.number_existing_users(now=7000.0) == []          # a later boot numbers nothing new
    assert not users_store.get_user("after@example.com").get("member_number")
    assert _login_via_link(sender, "after@example.com")["member_number"] == 2  # the click mints


def test_the_pass_flags_controllers_first_and_migrates_legacy_strings(reset_stores):
    import bcrypt
    for u, coh in (("fe@example.com", "founder_exception"), ("adm@example.com", "admin"), ("m@example.com", "member")):
        users_store.create_user(username=u, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                                salt="", tier="free", created_at=100.0)
        users_store.update_user(u, {"cohort": coh})
    users_store.number_existing_users(controllers=("ghost@example.com",))  # a missing controller is logged, not fatal
    assert users_store.get_user("fe@example.com")["controller"] is True
    assert users_store.get_user("adm@example.com")["controller"] is True
    assert not users_store.get_user("m@example.com").get("controller")


def test_comp_override_and_malformed_numbers_are_handled(reset_stores):
    assert users_store.is_citizen({"membership_status": "active", "membership_tier": "founding_500",
                                   "comp_override": True}) is False
    assert users_store.citz_id({"username": "x@e.com", "member_number": "not-a-number"}) is None
    assert users_store.identity_view({"username": "x@e.com", "member_number": "junk"})["member_number"] is None


def test_a_session_with_no_doc_derives_nothing(app_module, monkeypatch):
    """The old entitlement-from-absence guard stands: a live session whose doc
    is gone derives NO label (not "all"). The harness auto-provisions a doc for
    every session user (conftest, v87), so the absence is staged on the read."""
    sid = "sess_" + secrets.token_urlsafe(12)
    sessions_store.create_session(sid, "vanished@example.com", expires_at=time.time() + 3600)
    monkeypatch.setattr(users_store, "get_user", lambda username: None)
    sess = app_module.require_session(x_session_id=sid)
    assert sess["cohort"] is None
