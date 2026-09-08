"""
#124 -- citizens are numbered, cohort is a range, the founder is a controller.

★ WHAT THESE PIN. One global counter; a number minted at FIRST LOGIN only
(never on create); a second login changes nothing; existing docs numbered
once in created_at order with the Outlook doc first; the founder is
doc.controller and both gates read ONE predicate (drift guard); a
founder-granted walker is not a citizen; the derived labels for 1 / 500 /
501 / controller; the display suffix rule; /me and the founder rows carry
the identity. #157: the string shim is DELETED -- a legacy string on a doc
opens nothing on either gate and is never flipped into the flag; the two
gates share ONE refusal (#181); `paid` replaces `citizen` on the wire (#174);
an invite never mints a controller (#173).
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
    assert client.get("/org/timeline/24h", headers=h_ctrl).status_code == 200
    a = client.get("/founder/members", headers=h_cit)
    b = client.get("/org/timeline/24h", headers=h_cit)
    # #181 -- ONE refusal: same status, same body, on both gates
    assert a.status_code == b.status_code == 403
    assert a.json() == b.json() == rh.ADMIN_ONLY_REFUSAL
    assert "Founder cohort required" not in b.text


def test_a_legacy_string_opens_nothing_on_either_gate(client):
    """#157 -- the #124 shim is deleted. "founder" is a role and confers
    nothing (#173); "admin" and the invite kind are strings on a doc and
    open neither gate. The refusal is the one refusal."""
    for old in ("founder", "founder_exception", "admin", "member"):
        h = _session_for(f"legacy_{old}@example.com", cohort=old)
        a = client.get("/founder/members", headers=h)
        b = client.get("/org/timeline/24h", headers=h)
        assert a.status_code == b.status_code == 403, old
        assert a.json() == b.json() == rh.ADMIN_ONLY_REFUSAL, old
        assert users_store.derive_cohort(users_store.get_user(f"legacy_{old}@example.com")) == "all", old


def test_drift_guard_the_one_refusal_is_error_response_shaped(app_module):
    """#181 -- runtime_http owns the dict (the lower module); it must be
    exactly what app.error_response would build, so a reader of either gate
    sees {ok, error, message} and nothing else."""
    assert rh.ADMIN_ONLY_REFUSAL == app_module.error_response(
        "admin_only", "Admin only: this console is the controller's")
    assert set(rh.ADMIN_ONLY_REFUSAL) == {"ok", "error", "message"}
    assert "@" not in rh.ADMIN_ONLY_REFUSAL["message"] and "cohort" not in rh.ADMIN_ONLY_REFUSAL["message"].lower()


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
    assert users_store.is_paid(doc) is False
    # a paid founding membership IS paid (#174: citizen is the number; paid is a state)
    paid = _session_for("paid@example.com", membership_status="active", membership_tier="founding_500",
                        membership_price=50.0)
    assert users_store.is_paid(users_store.get_user("paid@example.com")) is True
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
    """#157 -- the flags read a label's OWN key (the alias shim is deleted);
    reset_stores arms the three labels the way app.py does. Arm them again
    here so these tests say what they rely on."""
    import v29_hardening as h
    for label in ("founding", "all"):
        h.set_flag("v28_surfaces", True, cohort=label)
        h.set_flag("membership_ui_enabled", True, cohort=label)


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
    assert w["member_number"] == 2 and w["paid"] is False and w["controller"] is False
    assert "citizen" not in w  # #174 -- paid is the state; citizen is the number
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
    assert ident["paid"] is False and ident["controller"] is False
    assert "citizen" not in ident


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
    assert by_email["r1@example.com"]["paid"] is False
    assert "citizen" not in by_email["r1@example.com"]
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


def test_the_pass_flags_named_controllers_and_never_flips_a_string(reset_stores, caplog):
    """#157 / #156 RULED B -- the boot pass flags the CONFIGURED names and
    logs (a hashed ref, never the address) a doc whose only claim is the old
    role / admin string; it never flips that string into the flag. The
    invite kind "founder_exception" is what a redeemed invite writes and is
    NOT logged -- an invite never minted a controller (#173)."""
    import bcrypt
    caplog.set_level("WARNING")
    for u, coh in (("old.founder@example.com", "founder"), ("fe@example.com", "founder_exception"),
                   ("adm@example.com", "admin"), ("m@example.com", "member")):
        users_store.create_user(username=u, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                                salt="", tier="free", created_at=100.0)
        users_store.update_user(u, {"cohort": coh})
    users_store.number_existing_users(controllers=("ghost@example.com", "adm@example.com"))  # a missing controller is logged, not fatal
    assert not users_store.get_user("old.founder@example.com").get("controller")  # the string stays a string
    assert not users_store.get_user("fe@example.com").get("controller")
    assert users_store.get_user("adm@example.com")["controller"] is True          # named -> flagged
    assert not users_store.get_user("m@example.com").get("controller")
    msgs = [r.getMessage() for r in caplog.records if "controller.string_only" in r.getMessage()]
    assert len(msgs) == 1 and users_store._uref("old.founder@example.com") in msgs[0]
    assert users_store._uref("fe@example.com") not in msgs[0]  # the invite kind is not a claim
    assert "old.founder" not in msgs[0] and "example.com" not in msgs[0]


def test_comp_override_and_malformed_numbers_are_handled(reset_stores):
    assert users_store.is_paid({"membership_status": "active", "membership_tier": "founding_500",
                                "comp_override": True}) is False
    assert users_store.citz_id({"username": "x@e.com", "member_number": "not-a-number"}) is None
    assert users_store.identity_view({"username": "x@e.com", "member_number": "junk"})["member_number"] is None


def test_the_grant_backfill_marks_manual_only_ledgers_and_logs_no_address(app_module, caplog):
    """A pre-#124 founder grant: an active founding doc whose ledger holds
    only manual activations. The backfill marks it granted and logs a HASH
    reference -- never the address, never a prefix of it (the tag-boot log
    of 37a4a67 carried eight characters of an email; this pins the fix)."""
    import bcrypt
    caplog.set_level("INFO")
    for u, txs in (
        ("granted.walker@example.com", [{"type": "membership_activation", "metadata": {"manual": True}}]),
        ("paid.member@example.com", [{"type": "membership_activation", "metadata": {"manual": True}},
                                     {"type": "checkout_session_completed", "metadata": {}}]),
    ):
        users_store.create_user(username=u, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                                salt="", tier="free", created_at=100.0)
        users_store.set_membership(u, tier="founding_500", price=50.0, status="active")
        for t in txs:
            membership_store.record_transaction(u, type=t["type"], amount=50.0, credits_delta=0,
                                                metadata=t["metadata"])
    marked = app_module._backfill_membership_granted()
    assert marked == 1
    assert users_store.get_user("granted.walker@example.com")["membership_granted"] is True
    assert not users_store.get_user("paid.member@example.com").get("membership_granted")
    assert users_store.is_paid(users_store.get_user("paid.member@example.com")) is True
    msgs = [r.getMessage() for r in caplog.records if "membership_granted.backfilled" in r.getMessage()]
    assert len(msgs) == 1
    assert "granted.walker" not in msgs[0] and "granted.w" not in msgs[0]
    assert users_store._uref("granted.walker@example.com") in msgs[0]


def test_a_session_with_no_doc_derives_nothing(app_module, monkeypatch):
    """The old entitlement-from-absence guard stands: a live session whose doc
    is gone derives NO label (not "all"). The harness auto-provisions a doc for
    every session user (conftest, v87), so the absence is staged on the read."""
    sid = "sess_" + secrets.token_urlsafe(12)
    sessions_store.create_session(sid, "vanished@example.com", expires_at=time.time() + 3600)
    monkeypatch.setattr(users_store, "get_user", lambda username: None)
    sess = app_module.require_session(x_session_id=sid)
    assert sess["cohort"] is None


# ===========================================================================
# #173 -- an invite never mints a controller
# ===========================================================================
def test_a_redeemed_invite_never_mints_a_controller(client, app_module, monkeypatch):
    """/invite/create (the bootstrap admin) -> /invite/{token}/redeem writes
    the invite KIND on the new doc and nothing that opens a gate: no
    controller flag, label "all", both gates refuse with the one refusal."""
    monkeypatch.setenv("INVITE_HMAC_SECRET", "test-invite-secret-" + "x" * 32)  # tokens._secret reads it per call
    h_admin = _session_for(app_module.ADMIN_USER)
    r = client.post("/invite/create", json={"cohort": "founder_exception"}, headers=h_admin)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = client.post(f"/invite/{token}/redeem", json={"username": "invited@example.com", "password": "a-password-1"})
    assert r.status_code == 200, r.text
    doc = users_store.get_user("invited@example.com")
    assert doc is not None and doc.get("cohort") == "founder_exception"
    assert not doc.get("controller")
    assert users_store.is_controller(doc) is False and users_store.derive_cohort(doc) == "all"
    h = {"X-Session-ID": r.json()["session_id"]}
    a = client.get("/founder/members", headers=h)
    b = client.get("/org/timeline/24h", headers=h)
    assert a.status_code == b.status_code == 403
    assert a.json() == b.json() == rh.ADMIN_ONLY_REFUSAL
