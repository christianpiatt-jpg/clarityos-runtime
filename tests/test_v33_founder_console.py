"""
Tests for v33 — Founder Console + ELINS Standardization + #cmt.

Covers:
* elins/standard_elins.generate_ELINS — 10-layer pipeline shape +
  determinism + primitive extraction + domain mapping.
* elins/standard_elins.generate_S_ELINS — pass/fail + alignment scoring +
  edited-object detection.
* elins/elins_project — save_daily_run / load_previous_run / primitive
  index / domain history / EP baseline.
* comment_generator — 3-layer MRCG output shape, attractor detection,
  domain templates, low-emotion + noun-density activation metadata.
* dm_store — add/list/notes round-trip + idempotency invariants.
* /elins/preview, /elins/global, /elins/qc endpoints.
* /cmt/generate + /c/run mode='comment' endpoints.
* /founder/dm/{add,list,notes} endpoints (founder gate).
* /founder/membership/{activate,cancel,credits} endpoints.
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder", *, password=b"x"):
    import secrets
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(password, bcrypt.gensalt())
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


# ===========================================================================
# elins/standard_elins
# ===========================================================================
def test_generate_ELINS_returns_all_layers(reset_stores):
    from ELINS import standard_elins as se
    out = se.generate_ELINS(
        "tariffs are creating pressure, the courts are showing drift, "
        "trust in the agency is eroding."
    )
    for layer in se.LAYER_NAMES:
        assert layer in out, f"missing layer {layer}"
    assert out["output_object"]["scenario_id"].startswith("sc_")
    assert out["output_object"]["version"].startswith("elins.v34")


def test_generate_ELINS_primitive_extraction(reset_stores):
    from ELINS import standard_elins as se
    out = se.generate_ELINS(
        "There is enormous pressure on the courts and growing tension "
        "between the agencies, but trust between partners remains high."
    )
    p = out["primitives"]["intensities"]
    # Pressure + tension + trust should all light up; alignment lower.
    assert p["pressure"] > 0
    assert p["tension"] > 0
    assert p["trust"] > 0


def test_generate_ELINS_domain_mapping(reset_stores):
    from ELINS import standard_elins as se
    out = se.generate_ELINS(
        "The Supreme Court ruling and the constitutional question create "
        "pressure on the institution.",
    )
    # Either legal or institutional should be the top domain.
    top = out["domain_mapping"]["effective_top"]
    assert top in ("legal", "institutional")


def test_generate_ELINS_is_deterministic(reset_stores):
    from ELINS import standard_elins as se
    text = "the trust between partners is eroding under economic pressure."
    a = se.generate_ELINS(text)
    b = se.generate_ELINS(text)
    # Drop the time field which differs by microseconds.
    a["input_phase"].pop("ts", None)
    b["input_phase"].pop("ts", None)
    a["output_object"].pop("ts", None)
    b["output_object"].pop("ts", None)
    assert a["primitives"] == b["primitives"]
    assert a["synthesis"] == b["synthesis"]


def test_generate_ELINS_rejects_empty(reset_stores):
    from ELINS import standard_elins as se
    with pytest.raises(ValueError):
        se.generate_ELINS("")
    with pytest.raises(ValueError):
        se.generate_ELINS("   ")


def test_generate_ELINS_rejects_bad_domain_hint(reset_stores):
    from ELINS import standard_elins as se
    with pytest.raises(ValueError):
        se.generate_ELINS("text", domain_hint="not_a_real_domain")


def test_generate_S_ELINS_passes_for_clean_object(reset_stores):
    from ELINS import standard_elins as se
    elins_obj = se.generate_ELINS(
        "trust is collapsing under institutional pressure and legal contradiction."
    )
    s = se.generate_S_ELINS(elins_obj)
    assert s["passed"] is True
    assert s["alignment_score"] > 0.99
    assert s["max_delta"] < 1e-6


def test_generate_S_ELINS_detects_edited_intensities(reset_stores):
    from ELINS import standard_elins as se
    elins_obj = se.generate_ELINS(
        "trust is collapsing under institutional pressure."
    )
    # Tamper with the recorded intensities to simulate a stale / edited
    # ELINS object.
    elins_obj["primitives"]["intensities"]["trust"] = 0.0
    elins_obj["primitives"]["intensities"]["pressure"] = 0.0
    s = se.generate_S_ELINS(elins_obj)
    assert s["passed"] is False
    assert s["max_delta"] >= se.S_ELINS_PASS_THRESHOLD


# ===========================================================================
# elins/elins_project — persistence helpers
# ===========================================================================
def test_save_daily_run_and_load_previous(reset_stores):
    from ELINS import standard_elins as se
    from ELINS import elins_project as ep
    text = "the institution is drifting under sustained pressure."
    run = se.generate_ELINS(text, user="alice")
    ep.save_daily_run("alice", run, day="2026-05-04")
    new_run = se.generate_ELINS("trust between partners is eroding.", user="alice")
    ep.save_daily_run("alice", new_run, day="2026-05-05")
    prev = ep.load_previous_run("alice", day="2026-05-05")
    assert prev is not None
    assert prev["day"] == "2026-05-04"


def test_save_daily_run_idempotent_on_same_day(reset_stores):
    from ELINS import standard_elins as se
    from ELINS import elins_project as ep
    a = se.generate_ELINS("first text about pressure", user="bob")
    b = se.generate_ELINS("second text about trust", user="bob")
    id1 = ep.save_daily_run("bob", a, day="2026-05-05")
    id2 = ep.save_daily_run("bob", b, day="2026-05-05")
    assert id1 == id2  # same key
    runs = ep.list_runs_for_user("bob")
    assert len(runs) == 1  # second save overwrote


def test_update_global_primitive_index(reset_stores):
    from ELINS import standard_elins as se
    from ELINS import elins_project as ep
    run = se.generate_ELINS("pressure drift contradiction", user="carol")
    ep.update_global_primitive_index(run)
    rows = ep.list_primitive_index()
    assert len(rows) == 1
    assert "pressure" in rows[0]["intensities"]


def test_update_domain_history(reset_stores):
    from ELINS import standard_elins as se
    from ELINS import elins_project as ep
    run = se.generate_ELINS("court ruling on constitutional pressure", user="dan")
    ep.update_domain_history("dan", run)
    rows = ep.list_domain_history("dan")
    assert len(rows) == 1
    assert rows[0]["domain"] in ("legal", "institutional")


def test_update_ep_baseline_smooths_over_runs(reset_stores):
    from ELINS import standard_elins as se
    from ELINS import elins_project as ep
    a = se.generate_ELINS("immense pressure on the institution", user="eve")
    ep.update_ep_baseline("eve", a)
    base1 = ep.get_baseline("eve")
    b = se.generate_ELINS("trust and alignment between partners", user="eve")
    ep.update_ep_baseline("eve", b)
    base2 = ep.get_baseline("eve")
    assert base2["sample_count"] == 2
    # The smoothed baseline should not equal either single observation.
    assert base2["net"] != base1["net"]


# ===========================================================================
# comment_generator — MRCG v1.0
# ===========================================================================
def test_generate_comment_shape(reset_stores):
    import comment_generator as cg
    out = cg.generate_comment("This institution is drifting under enormous pressure.")
    assert out["ok"] is True
    assert isinstance(out["comment"], str) and len(out["comment"]) > 0
    for k in ("structural_reframe", "domain_alignment", "identity_move", "stabilizing_close"):
        assert k in out["construction"]
    for k in ("attractor", "domain", "tone", "primitive_intensities"):
        assert k in out["detection"]
    assert out["activation"]["low_emotion"] in (True, False)
    assert 0.0 <= out["activation"]["noun_density"] <= 1.0


def test_generate_comment_attractor_detection(reset_stores):
    import comment_generator as cg
    out = cg.generate_comment(
        "The agency is drifting from its mandate and the regulator is showing signs of decline."
    )
    assert out["detection"]["attractor"] in ("institutional_drift", "consensus_drift")


def test_generate_comment_domain_alignment(reset_stores):
    import comment_generator as cg
    out = cg.generate_comment(
        "Court ruling on constitutional pressure",
        domain_hint="legal",
    )
    assert "legal" in out["construction"]["domain_alignment"].lower()


def test_generate_comment_low_emotion_holds(reset_stores):
    import comment_generator as cg
    out = cg.generate_comment(
        "There is sustained pressure on the institution.",
    )
    # Constructed comment should hit low-emotion check.
    assert out["activation"]["low_emotion"] is True


def test_generate_comment_deterministic(reset_stores):
    import comment_generator as cg
    text = "Trust between the partners is eroding."
    a = cg.generate_comment(text)
    b = cg.generate_comment(text)
    assert a["comment"] == b["comment"]
    assert a["construction"] == b["construction"]


def test_generate_comment_rejects_empty(reset_stores):
    import comment_generator as cg
    with pytest.raises(ValueError):
        cg.generate_comment("")


def test_generate_comment_rejects_bad_domain_hint(reset_stores):
    import comment_generator as cg
    with pytest.raises(ValueError):
        cg.generate_comment("text", domain_hint="invalid_domain")


# ===========================================================================
# dm_store
# ===========================================================================
def test_dm_store_add_and_list(reset_stores):
    import dm_store
    a = dm_store.add_dm(
        founder="root", channel="linkedin", subject="hi", snippet="initial outreach",
    )
    b = dm_store.add_dm(
        founder="root", channel="email", user="alice", subject="follow-up",
    )
    rows = dm_store.list_dms()
    assert len(rows) == 2
    # Filter by channel.
    only_linked = dm_store.list_dms(channel="linkedin")
    assert len(only_linked) == 1
    assert only_linked[0]["id"] == a["id"]
    # Filter by user.
    for_alice = dm_store.list_dms_for_user("alice")
    assert len(for_alice) == 1
    assert for_alice[0]["id"] == b["id"]


def test_dm_store_notes_roundtrip(reset_stores):
    import dm_store
    dm = dm_store.add_dm(founder="root", channel="manual")
    n1 = dm_store.add_dm_note(dm["id"], "first contact summary", founder="root")
    n2 = dm_store.add_dm_note(dm["id"], "follow-up call summary", founder="root")
    notes = dm_store.get_dm_notes(dm["id"])
    assert len(notes) == 2
    # Newest first.
    assert notes[0]["id"] == n2["id"]
    assert notes[1]["id"] == n1["id"]


def test_dm_store_note_unknown_dm_returns_none(reset_stores):
    import dm_store
    assert dm_store.add_dm_note("dm_does_not_exist", "x", founder="root") is None


# ===========================================================================
# Endpoints — /elins/{preview, global, qc}
# ===========================================================================
def test_elins_preview_returns_all_layers(app_module, client):
    user, sid = _make_user(app_module, "evan", cohort="founder")
    r = client.post(
        "/elins/preview", headers=_auth(sid),
        json={"text": "institutional drift under sustained pressure"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "output_object" in body["elins"]
    assert "primitives" in body["elins"]


def test_elins_preview_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "lurker", cohort=None)
    r = client.post(
        "/elins/preview", headers=_auth(sid), json={"text": "x x x x"},
    )
    assert r.status_code == 403


def test_elins_global_persists_run(app_module, client):
    from ELINS import elins_project as ep
    user, sid = _make_user(app_module, "frank", cohort="founder")
    r = client.post(
        "/elins/global", headers=_auth(sid),
        json={"text": "Court ruling on constitutional pressure"},
    )
    assert r.status_code == 200, r.json()
    run_id = r.json()["run_id"]
    runs = ep.list_runs_for_user("frank")
    assert any(row["id"] == run_id for row in runs)


def test_elins_global_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "guest", cohort=None)
    r = client.post(
        "/elins/global", headers=_auth(sid),
        json={"text": "x x x x"},
    )
    assert r.status_code == 403


def test_elins_qc_returns_pass_for_clean_object(app_module, client):
    from ELINS import standard_elins as se
    user, sid = _make_user(app_module, "harry", cohort="founder")
    elins_obj = se.generate_ELINS("trust collapse under pressure")
    r = client.post(
        "/elins/qc", headers=_auth(sid), json={"elins_object": elins_obj},
    )
    assert r.status_code == 200, r.json()
    s = r.json()["s_elins"]
    assert s["passed"] is True


def test_elins_qc_rejects_non_dict(app_module, client):
    user, sid = _make_user(app_module, "izzy", cohort="founder")
    r = client.post(
        "/elins/qc", headers=_auth(sid), json={"elins_object": {}},
    )
    assert r.status_code == 400


# ===========================================================================
# Endpoints — /cmt/generate + /c/run
# ===========================================================================
def test_cmt_generate_endpoint(app_module, client):
    user, sid = _make_user(app_module, "jane", cohort="founder")
    r = client.post(
        "/cmt/generate", headers=_auth(sid),
        json={"text": "the agency is drifting from its mandate"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert isinstance(body["comment"], str) and body["comment"]


def test_c_run_mode_comment(app_module, client):
    user, sid = _make_user(app_module, "kim", cohort="founder")
    r = client.post(
        "/c/run", headers=_auth(sid),
        json={"text": "trust between the parties is eroding", "mode": "comment"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["mode"] == "comment"
    assert "result" in body
    assert "comment" in body["result"]


def test_c_run_rejects_unknown_mode(app_module, client):
    user, sid = _make_user(app_module, "lou", cohort="founder")
    r = client.post(
        "/c/run", headers=_auth(sid),
        json={"text": "anything", "mode": "totally_made_up"},
    )
    assert r.status_code == 400


def test_me_advertises_capabilities(app_module, client):
    user, sid = _make_user(app_module, "max", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    body = r.json()
    ids = [c["id"] for c in body.get("capabilities") or []]
    assert "cmt" in ids
    assert "elins_qc" in ids


# ===========================================================================
# Endpoints — /founder/dm/{add,list,notes}
# ===========================================================================
def test_founder_dm_add_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "nan", cohort=None)
    r = client.post("/founder/dm/add", headers=_auth(sid), json={})
    assert r.status_code == 403


def test_founder_dm_add_and_list(app_module, client):
    user, sid = _make_user(app_module, "olive", cohort="founder")
    r = client.post(
        "/founder/dm/add", headers=_auth(sid),
        json={"channel": "linkedin", "subject": "hello", "snippet": "first contact"},
    )
    assert r.status_code == 200, r.json()
    dm_id = r.json()["dm"]["id"]

    listed = client.get("/founder/dm/list", headers=_auth(sid)).json()
    assert listed["count"] == 1
    assert listed["dms"][0]["id"] == dm_id


def test_founder_dm_notes_roundtrip(app_module, client):
    user, sid = _make_user(app_module, "pat", cohort="founder")
    r = client.post(
        "/founder/dm/add", headers=_auth(sid), json={"channel": "manual"},
    )
    dm_id = r.json()["dm"]["id"]
    note_r = client.post(
        "/founder/dm/notes", headers=_auth(sid),
        json={"dm_id": dm_id, "body": "first note"},
    )
    assert note_r.status_code == 200
    body = note_r.json()
    assert body["note"]["body"] == "first note"
    assert len(body["notes"]) == 1


def test_founder_dm_notes_unknown_dm_returns_404(app_module, client):
    user, sid = _make_user(app_module, "quinn", cohort="founder")
    r = client.post(
        "/founder/dm/notes", headers=_auth(sid),
        json={"dm_id": "dm_nope", "body": "x"},
    )
    assert r.status_code == 404


# ===========================================================================
# Endpoints — /founder/membership/{activate,cancel,credits}
# ===========================================================================
def test_founder_membership_activate(app_module, client):
    """Founder manually activates a target user without going through
    the PaymentIntent flow."""
    f, sid_f = _make_user(app_module, "founderA", cohort="founder")
    target, _sid_t = _make_user(app_module, "targetA", cohort="founder")
    r = client.post(
        "/founder/membership/activate", headers=_auth(sid_f),
        json={"user": target, "note": "comp"},
    )
    assert r.status_code == 200, r.json()
    state = r.json()["membership"]
    assert state["status"] == "active"
    assert state["billing_state"] == "active"
    assert state["price"] == 50.00


def test_founder_membership_activate_unknown_user_404(app_module, client):
    f, sid_f = _make_user(app_module, "founderB", cohort="founder")
    r = client.post(
        "/founder/membership/activate", headers=_auth(sid_f),
        json={"user": "no_such_user"},
    )
    assert r.status_code == 404


def test_founder_membership_cancel(app_module, client):
    f, sid_f = _make_user(app_module, "founderC", cohort="founder")
    target, _ = _make_user(app_module, "targetC", cohort="founder")
    client.post(
        "/founder/membership/activate", headers=_auth(sid_f),
        json={"user": target},
    )
    r = client.post(
        "/founder/membership/cancel", headers=_auth(sid_f),
        json={"user": target, "note": "manual cancel"},
    )
    assert r.status_code == 200, r.json()
    state = r.json()["membership"]
    assert state["status"] == "cancelled"
    assert state["billing_state"] == "cancelled"


def test_founder_membership_credits_grant_and_revoke(app_module, client):
    import users_store
    f, sid_f = _make_user(app_module, "founderD", cohort="founder")
    target, _ = _make_user(app_module, "targetD", cohort="founder")

    grant = client.post(
        "/founder/membership/credits", headers=_auth(sid_f),
        json={"user": target, "delta": 10, "reason": "welcome bonus"},
    )
    assert grant.status_code == 200
    assert grant.json()["balance"] == 10
    assert users_store.get_g_credit_balance(target) == 10

    revoke = client.post(
        "/founder/membership/credits", headers=_auth(sid_f),
        json={"user": target, "delta": -3, "reason": "refund"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["balance"] == 7


def test_founder_membership_credits_blocks_negative_balance(app_module, client):
    f, sid_f = _make_user(app_module, "founderE", cohort="founder")
    target, _ = _make_user(app_module, "targetE", cohort="founder")
    r = client.post(
        "/founder/membership/credits", headers=_auth(sid_f),
        json={"user": target, "delta": -5, "reason": "noop"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "would_go_negative"


def test_founder_membership_credits_zero_delta_rejected(app_module, client):
    f, sid_f = _make_user(app_module, "founderF", cohort="founder")
    target, _ = _make_user(app_module, "targetF", cohort="founder")
    r = client.post(
        "/founder/membership/credits", headers=_auth(sid_f),
        json={"user": target, "delta": 0},
    )
    assert r.status_code == 400


# ===========================================================================
# Auth contract — every founder endpoint requires a session
# ===========================================================================
@pytest.mark.parametrize("path,method,body", [
    ("/elins/preview", "POST", {"text": "x"}),
    ("/elins/global", "POST", {"text": "x"}),
    ("/elins/qc", "POST", {"elins_object": {}}),
    ("/cmt/generate", "POST", {"text": "x"}),
    ("/c/run", "POST", {"text": "x", "mode": "comment"}),
    ("/founder/dm/add", "POST", {"channel": "manual"}),
    ("/founder/dm/list", "GET", None),
    ("/founder/dm/notes", "POST", {"dm_id": "x", "body": "x"}),
    ("/founder/membership/activate", "POST", {"user": "x"}),
    ("/founder/membership/cancel", "POST", {"user": "x"}),
    ("/founder/membership/credits", "POST", {"user": "x", "delta": 1}),
])
def test_v33_endpoints_require_session(app_module, client, path, method, body):
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body)
    assert r.status_code == 401, f"{path} returned {r.status_code}"
