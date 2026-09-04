"""
Tests for v30 — Founding Cohort membership + #G credit system.

Covers:
* /membership/state shape + flag gate
* /membership/activate happy path + waitlist when cap is full
* /membership/cancel + price-lock forfeit semantics
* /membership/g/buy_single + buy_pack_20 increment balance
* /elins/g/run consumes one credit per call; 402 on empty balance
* membership_store cap + waitlist invariants
* users_store add/consume_g_credit + balance never negative
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def stub_embedder(monkeypatch):
    """Same fake embedder used by v28 tests so #G runs don't hit Vertex."""
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


@pytest.fixture(autouse=True)
def _arm_member_flags(reset_stores):
    """A non-controller's session cohort is a DERIVED label ("all" /
    "founding"); the flags resolve through the label's alias "member",
    never through the doc's stored string. Arm what production arms for
    members (app.py flag bootstrap) so a member here is a member there."""
    import v29_hardening
    for flag in ("g_credits_enabled", "membership_ui_enabled", "v28_surfaces"):
        v29_hardening.set_flag(flag, True, cohort="member")
    yield


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


# ---------------------------------------------------------------------------
# users_store helpers
# ---------------------------------------------------------------------------
def test_g_credit_balance_default_zero(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    assert users_store.get_g_credit_balance("u1") == 0


def test_add_g_credits_increments_and_appends_history(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    bal = users_store.add_g_credits(
        "u1", 20, history_entry={"type": "g_buy_pack_20", "credits_delta": 20},
    )
    assert bal == 20
    doc = users_store.get_user("u1")
    # the ledger is balance_micro; the retired ``g_credits`` field is never written
    assert doc["balance_micro"] == 20
    assert "g_credits" not in doc
    assert len(doc["g_credit_history"]) == 1


def test_consume_g_credit_blocks_when_zero(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    with pytest.raises(ValueError):
        users_store.consume_g_credit("u1")


def test_consume_g_credit_decrements(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    users_store.add_g_credits("u1", 3)
    assert users_store.consume_g_credit("u1") == 2
    assert users_store.consume_g_credit("u1") == 1
    assert users_store.consume_g_credit("u1") == 0
    with pytest.raises(ValueError):
        users_store.consume_g_credit("u1")


# ---------------------------------------------------------------------------
# membership_store
# ---------------------------------------------------------------------------
def test_cohort_state_default(reset_stores):
    import membership_store
    s = membership_store.get_cohort_state()
    assert s["cohort"] == "founding_500"
    assert s["active_count"] == 0
    assert s["cap"] == 500
    assert s["remaining"] == 500
    assert s["is_full"] is False


def test_add_member_idempotent_via_value_error(reset_stores):
    import membership_store
    membership_store.add_member("u1")
    with pytest.raises(ValueError) as exc:
        membership_store.add_member("u1")
    assert str(exc.value) == "already_member"


def test_cohort_full_pushes_to_waitlist(reset_stores, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 2)
    membership_store.add_member("u1")
    membership_store.add_member("u2")
    with pytest.raises(ValueError) as exc:
        membership_store.add_member("u3")
    assert str(exc.value) == "cohort_full"
    membership_store.add_to_waitlist("u3")
    pos = membership_store.waitlist_position("u3")
    assert pos == 1


def test_remove_member_idempotent(reset_stores):
    import membership_store
    membership_store.add_member("u1")
    membership_store.remove_member("u1")
    membership_store.remove_member("u1")  # second call: no-op
    assert membership_store.is_member("u1") is False


def test_record_transaction_caps_at_max(reset_stores, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "MAX_TX_PER_USER", 5)
    for i in range(10):
        membership_store.record_transaction(
            "u1", type="g_consume", amount=0.0, credits_delta=-1,
            metadata={"i": i},
        )
    txs = membership_store.list_transactions("u1", limit=100)
    assert len(txs) == 5
    # The newest five (i=5..9) should remain.
    metadata_indices = sorted(int(t["metadata"]["i"]) for t in txs)
    assert metadata_indices == [5, 6, 7, 8, 9]


# ---------------------------------------------------------------------------
# /membership/state
# ---------------------------------------------------------------------------
def test_membership_state_default_for_founder(app_module, client):
    user, sid = _make_user(app_module, "minnie", cohort="founder")
    r = client.get("/membership/state", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    assert state["membership"]["status"] is None
    assert state["membership"]["next_price"] == 50.00
    assert state["g_credits"]["balance"] == 0
    assert state["cohort"]["active_count"] == 0


def test_membership_state_blocked_when_flag_off(app_module, client):
    user, sid = _make_user(app_module, "ghost", cohort=None)
    # the flag is OFF for this user (a user override outranks the cohort)
    import v29_hardening
    v29_hardening.set_flag("membership_ui_enabled", False, user=user)
    r = client.get("/membership/state", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /membership/activate
# ---------------------------------------------------------------------------
def test_activate_requires_terms(app_module, client):
    user, sid = _make_user(app_module, "abby", cohort="founder")
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": False})
    assert r.status_code == 400
    assert r.json()["error"] == "terms_required"


def test_activate_happy_path(app_module, client):
    user, sid = _make_user(app_module, "alex", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    state = body["state"]
    # v31 — auto-confirm mock mode lands the membership immediately.
    assert state["membership"]["status"] == "active"
    assert state["membership"]["price_locked"] == 50.00
    assert state["cohort"]["active_count"] == 1
    # Intent metadata is part of the new contract.
    assert body["intent"]["mode"] == "mock"
    assert body["intent"]["intent_id"].startswith("pi_")


def test_activate_idempotent_when_already_active(app_module, client):
    user, sid = _make_user(app_module, "ari", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    assert r.status_code == 200
    assert r.json().get("already_active") is True


def test_activate_when_cap_full_returns_waitlist(app_module, client, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 2)
    u1, sid1 = _make_user(app_module, "first", cohort="founder")
    u2, sid2 = _make_user(app_module, "second", cohort="founder")
    u3, sid3 = _make_user(app_module, "third", cohort="founder")

    assert client.post("/membership/activate", headers=_auth(sid1), json={"accept_terms": True}).status_code == 200
    assert client.post("/membership/activate", headers=_auth(sid2), json={"accept_terms": True}).status_code == 200
    r = client.post("/membership/activate", headers=_auth(sid3), json={"accept_terms": True})
    assert r.status_code == 200
    body = r.json()
    assert body["waitlisted"] is True
    assert body["state"]["waitlist_position"] == 1
    # Cohort active_count never exceeded the cap.
    assert body["state"]["cohort"]["active_count"] == 2


# ---------------------------------------------------------------------------
# /membership/cancel — price-lock forfeit
# ---------------------------------------------------------------------------
def test_cancel_then_state_shows_full_price(app_module, client):
    user, sid = _make_user(app_module, "casey", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    r = client.post("/membership/cancel", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    assert state["membership"]["status"] == "cancelled"
    # next_price is full price after cancel.
    assert state["membership"]["next_price"] == 150.00
    assert state["membership"]["price_lock_forfeit"] is True
    assert state["cohort"]["active_count"] == 0


def test_reactivate_after_cancel_pays_full_price(app_module, client):
    user, sid = _make_user(app_module, "carla", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    client.post("/membership/cancel", headers=_auth(sid))
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    # The lock recorded at reactivation reflects the full price now.
    assert state["membership"]["price_locked"] == 150.00
    assert state["membership"]["status"] == "active"


def test_cancel_when_not_active_rejected(app_module, client):
    user, sid = _make_user(app_module, "noah", cohort="founder")
    r = client.post("/membership/cancel", headers=_auth(sid))
    assert r.status_code == 400
    assert r.json()["error"] == "not_active"


# ---------------------------------------------------------------------------
# #G credit purchases + history
# ---------------------------------------------------------------------------
# * The credit-path users below are "terrace_1", not "founder": under the
#   #124 one-deploy shim "founder" is a CONTROLLER, and a controller's
#   balance is UNLIMITED (#142) -- never gated, never debited, "unlimited".
def test_buy_single_is_retired(app_module, client):
    # billing_intents.RETIRED_KINDS: the $1 single was retired under the
    # micro-dollar ledger; the route answers 402 bad_kind and lands nothing.
    user, sid = _make_user(app_module, "barry", cohort="terrace_1")
    r = client.post("/membership/g/buy_single", headers=_auth(sid))
    assert r.status_code == 402, r.json()
    assert r.json()["error"] == "bad_kind"
    import users_store
    assert users_store.get_g_credit_balance(user) == 0


def test_buy_pack_20_increments_balance(app_module, client):
    user, sid = _make_user(app_module, "bea", cohort="terrace_1")
    r = client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    # #142 -- the "20-pack ($20.00)" lands $20.00 = 20_000_000 micro-dollars
    import billing_intents
    assert billing_intents.G_CREDIT_PACK_MICRO == 20_000_000
    assert body["balance"] == 20_000_000
    assert body["purchase"]["units"] == 20
    assert body["purchase"]["amount"] == 20.00


def test_buy_blocked_when_g_credits_disabled(app_module, client):
    user, sid = _make_user(app_module, "guest2", cohort=None)
    # the flag is OFF for this user (a user override outranks the cohort)
    import v29_hardening
    v29_hardening.set_flag("g_credits_enabled", False, user=user)
    r = client.post("/membership/g/buy_single", headers=_auth(sid))
    assert r.status_code == 403


def test_history_returns_recent_first(app_module, client):
    user, sid = _make_user(app_module, "henri", cohort="terrace_1")
    client.post("/membership/g/buy_single", headers=_auth(sid))
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.get("/membership/g/history", headers=_auth(sid))
    assert r.status_code == 200
    txs = r.json()["transactions"]
    types = [t["type"] for t in txs]
    # v31 — transaction types reflect PaymentIntent kinds, newest first.
    assert types[0] == "g_credit_pack"
    assert "g_credit_pack" in types


# ---------------------------------------------------------------------------
# /elins/g/run + credit consumption
# ---------------------------------------------------------------------------
def test_g_run_blocks_with_402_when_no_credits(app_module, client):
    user, sid = _make_user(app_module, "rhea", cohort="terrace_1")
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "scenario"},
    )
    assert r.status_code == 402
    assert r.json()["error"] == "no_credits"


def test_g_run_consumes_one_credit_on_success(app_module, client):
    user, sid = _make_user(app_module, "rin", cohort="terrace_1")
    # Buy a pack first.
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "scenario"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    # #153 -- "$1.00 buys one #G run": 20_000_000 - 1_000_000
    assert body["g_credits_remaining"] == 19_000_000


def test_g_run_does_not_consume_credit_on_failure(app_module, client):
    user, sid = _make_user(app_module, "ria", cohort="terrace_1")
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": ""},  # empty fails validation pre-credit check
    )
    assert r.status_code == 400
    # Balance unchanged (micro-dollars).
    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["g_credits"]["balance"] == 20_000_000
    assert state["g_credits"]["balance_display"] == "$20.00"


# ---------------------------------------------------------------------------
# Auth contract — every membership endpoint requires a session
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,method,body", [
    ("/membership/state", "GET", None),
    ("/membership/activate", "POST", {"accept_terms": True}),
    ("/membership/cancel", "POST", {}),
    ("/membership/g/buy_single", "POST", {}),
    ("/membership/g/buy_pack_20", "POST", {}),
    ("/membership/g/history", "GET", None),
])
def test_membership_endpoints_require_session(app_module, client, path, method, body):
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body)
    assert r.status_code == 401, f"{path} returned {r.status_code}"


# ---------------------------------------------------------------------------
# #107 #84 #65 -- the cohort hop in require_session
# ---------------------------------------------------------------------------
# WHAT THESE PIN. Three stores, one read. A paid member carries
# membership_tier on the doc AND a cohort-blob entry AND, if the doc predates
# v43 (2026-08-27), cohort=None. Every flag gate reads session["cohort"] and
# nothing else, so a pre-v43 paying member 403'd on their own surfaces
# (26 x 403 on the founder's own session). The hop derives cohort from the two real fields when the
# doc says None -- and ONLY then. Nothing here defaults; an unpaid doc stays
# None and its 403 stays TRUE.
#
# These call require_session directly. TestClient does not run in this
# environment (#89), and the hop is a plain function of a session id.


def _arm_v43_flags():
    """Mirror app.py:527-531 EXACTLY. conftest.reset_stores re-arms v28 for
    founder / founder_exception / terrace_1 only -- its comment says it
    mirrors app startup, but it predates v43 and omits member, admin and
    founding_500. Without this, (a) would fail for a stale-harness reason
    rather than a real one."""
    import v29_hardening as h
    import membership_store
    for coh in ("founder", "founder_exception", "terrace_1",
                "member", "admin", membership_store.FOUNDING_COHORT):
        h.set_flag("v28_surfaces", True, cohort=coh)


def _seat(user, status="active"):
    """The production grant, in production order: add_member (the seat),
    then set_membership (the doc). app.py webhook path :2099 -> :2111."""
    import users_store, membership_store
    membership_store.add_member(user)
    users_store.set_membership(
        user, tier=membership_store.FOUNDING_COHORT, price=50.0, status=status,
    )


def test_hop_a_paid_doc_with_null_cohort_opens(app_module):
    """D1, direction one. the founder's own doc shape (from the HAR's GET /me): tier founding_500, seat held,
    cohort None. The session derives founding_500 and the v28 gate opens."""
    import v29_hardening as h, membership_store, users_store
    _arm_v43_flags()
    user, sid = _make_user(app_module, "ava", cohort=None)
    _seat(user)
    sess = app_module.require_session(x_session_id=sid)
    # #124 -- the hop is retired: cohort is the DERIVED label. An unnumbered
    # doc is "all" (v43's "member"); the v28 gate opens for it.
    assert sess["cohort"] == "all"
    assert h.feature_enabled("v28_surfaces", user=user, cohort=sess["cohort"]) is True
    # Read path ONLY. Nothing is written to the doc.
    assert "cohort" not in (users_store.get_user(user) or {})


def test_hop_b_unpaid_doc_stays_closed(app_module):
    """D1, direction two. Neither field says paid -> cohort stays None and
    the 403 is TRUE. This is the assertion that forbids `or "member"`."""
    import v29_hardening as h
    import users_store
    _arm_v43_flags()
    user, sid = _make_user(app_module, "lurker", cohort=None)
    sess = app_module.require_session(x_session_id=sid)
    # #124 rule 2 -- default label "all": every account gets the member
    # surfaces (v43's ruling), and NOTHING founder-like is derived.
    assert sess["cohort"] == "all"
    assert app_module.users_store.is_controller(users_store.get_user(user)) is False
    assert h.feature_enabled("founder_tier_enabled", user=user, cohort=sess["cohort"]) is False


def test_hop_c_present_cohort_is_never_touched(app_module):
    """A doc that already carries a cohort is left alone -- the hop only
    fills None. founder_exception stays founder-like and passes
    _require_founder, which reads the doc directly."""
    user, sid = _make_user(app_module, "chris", cohort="founder_exception")
    sess = app_module.require_session(x_session_id=sid)
    # #124 -- the legacy string is honoured by the one-deploy shim: the
    # derived label is "controller" and the founder gate opens.
    assert sess["cohort"] == "controller"
    assert app_module._require_founder(session=sess) is sess


def test_hop_d_cancelled_member_derives_no_cohort(app_module):
    """CT-1, 2026-09-02: "if you cancel your membership, it's gone."
    Cancel keeps tier on the doc and drops the blob seat; the hop reads
    membership_status and only "active" derives. Nothing is deleted --
    the doc still says founding_500/cancelled -- but no cohort is
    derived from it and the v28 gate stays shut."""
    import v29_hardening as h, membership_store, users_store
    _arm_v43_flags()
    user, sid = _make_user(app_module, "cxl", cohort=None)
    _seat(user, status="cancelled")
    membership_store.remove_member(user)
    assert membership_store.is_member(user) is False
    sess = app_module.require_session(x_session_id=sid)
    # #124 -- cancelled: not a citizen; the label is the default "all".
    assert sess["cohort"] == "all"
    assert users_store.is_citizen(users_store.get_user(user)) is False


def test_hop_e_blob_seat_with_active_status(app_module):
    """A seat in the blob with membership_status active but no tier on the
    doc: status says active, the blob says seated, the hop derives."""
    import users_store, membership_store
    user, sid = _make_user(app_module, "blobonly", cohort=None)
    membership_store.add_member(user)
    users_store.set_membership(user, tier=None, price=None, status="active")
    sess = app_module.require_session(x_session_id=sid)
    assert sess["cohort"] == "all"  # #124 -- no number yet; the label does not read the seat


def test_hop_e2_blob_seat_with_no_status_stays_closed(app_module):
    """(e'). The webhook seats (add_member, :2099) before it writes the doc
    (:2111). A crash in that window leaves a seat and a doc with no status.
    None is not active: the hop derives nothing. The seat is not deleted;
    it is simply not enough on its own."""
    import membership_store
    user, sid = _make_user(app_module, "blobonly2", cohort=None)
    membership_store.add_member(user)
    sess = app_module.require_session(x_session_id=sid)
    assert sess["cohort"] == "all"  # #124


def test_hop_f_explicit_member_cohort_untouched(app_module):
    """A v43-born account (cohort="member") is not upgraded by a seat the
    hop never consults -- the hop fills None and nothing else."""
    user, sid = _make_user(app_module, "mem", cohort="member")
    _seat(user)
    sess = app_module.require_session(x_session_id=sid)
    assert sess["cohort"] == "all"  # #124 -- "member" was always "all"


def test_hop_g_get_me_echoes_the_derived_cohort(app_module, client):
    """GET /me echoes the DERIVED cohort. Before this, me() re-read the doc
    and reported cohort None for a paid pre-v43 member while every gate
    opened -- the footer read "COHORT --" on an account whose surfaces were
    all live. me() now reads the session cohort the hop produced."""
    _arm_v43_flags()
    user, sid = _make_user(app_module, "ava_me", cohort=None)
    _seat(user)
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["cohort"] == "all"  # #124 -- derived; unnumbered until first click
    assert body["features"]["v28_surfaces"] is True
    # Not a controller: operator stays False, exactly as before.
    assert body["operator"] is False
    assert body["citizen"] is True and body["member_number"] is None


# ===========================================================================
# #123 -- set_membership honours its own docstring
# ===========================================================================
# ★ WHAT THESE PIN. The docstring said "pass None to clear a field" while the
# code guarded on `is not None`, so None was never written and a
# re-activation left membership_cancelled_ts standing. Now: omit = leave
# alone; None = clear (written as null); float = set. And the activation
# writers pass cancelled_ts=None.
def _seed_user(username):
    import bcrypt
    import users_store
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )


def test_activate_after_cancel_clears_cancelled_ts(reset_stores):
    import users_store
    _seed_user("re_activated")
    users_store.set_membership(
        "re_activated", tier="founding_500", price=50.0, status="cancelled",
        cancelled_ts=1783420269.0,
    )
    assert users_store.get_user("re_activated")["membership_cancelled_ts"] == 1783420269.0

    users_store.set_membership(
        "re_activated", tier="founding_500", price=50.0, status="active",
        started_ts=1783500000.0, cancelled_ts=None,
    )
    doc = users_store.get_user("re_activated")
    assert doc["membership_status"] == "active"
    assert doc.get("membership_cancelled_ts") is None
    assert users_store.get_membership_view("re_activated")["cancelled_ts"] is None
    assert doc["membership_started_ts"] == 1783500000.0


def test_omitting_a_ts_leaves_it_untouched_and_none_clears_started_too(reset_stores):
    """Backward compatibility for every existing caller (none passes None
    today): omit = untouched. And the clear works for started_ts as well."""
    import users_store
    _seed_user("untouched")
    users_store.set_membership(
        "untouched", tier="founding_500", price=50.0, status="active",
        started_ts=1783500000.0, cancelled_ts=1783420269.0,
    )
    # omit both -> both survive a status-only rewrite
    users_store.set_membership("untouched", tier="founding_500", price=50.0, status="cancelled")
    doc = users_store.get_user("untouched")
    assert doc["membership_started_ts"] == 1783500000.0
    assert doc["membership_cancelled_ts"] == 1783420269.0
    # explicit None clears started_ts as well
    users_store.set_membership("untouched", tier="founding_500", price=50.0, status="cancelled", started_ts=None)
    assert users_store.get_user("untouched").get("membership_started_ts") is None


def test_founder_activate_route_clears_a_prior_cancellation(app_module, client):
    """The named writer, through its route: a cancelled member the founder
    re-activates carries no cancelled_ts afterwards."""
    import users_store
    founder, fsid = _make_user(app_module, "founder_123", cohort="founder")
    _seed_user("comeback")
    users_store.set_membership(
        "comeback", tier="founding_500", price=50.0, status="cancelled",
        cancelled_ts=1783420269.0,
    )
    r = client.post(
        "/founder/membership/activate",
        json={"user": "comeback", "price": 0},
        headers={"X-Session-ID": fsid},
    )
    assert r.status_code == 200, r.text
    doc = users_store.get_user("comeback")
    assert doc["membership_status"] == "active"
    assert doc.get("membership_cancelled_ts") is None
