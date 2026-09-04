"""
The money leg (#142 #153 #155) -- dollars on the surface, Adjust in
dollars, admin unlimited.

WHAT THESE PIN. CT-1 RULED 09-03/09-04: display dollars at $0.01
(sub-cent -> $0.00); deduct in micro unchanged; Adjust in DOLLARS with a
±$1,000 cap; the controller's balance is UNLIMITED (no gate, no debit,
Adjust refused with a reason); one #G run costs $1.00.
"""
from __future__ import annotations

import secrets
import time

import pytest

from conftest import TestClient

import compute_meter
import sessions_store
import usage_billing
import users_store

import app as _app


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


@pytest.fixture
def client(reset_stores):
    users_store._MEMORY_DEBITS.clear()
    return TestClient(_app.app)


def _session(username: str, *, controller: bool = False, micro: int = 0):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    # "terrace_1": v28_surfaces + g_credits_enabled + membership_ui_enabled
    # armed at app import, and NOT a controller string under the #124 shim
    # ("founder" / "founder_exception" / "admin" are -- and a controller is
    # unlimited, which is exactly what these tests must not be by accident).
    patch = {"cohort": "terrace_1", "membership_status": "active", "membership_tier": "founding_500"}
    if controller:
        patch.update({"controller": True, "cohort": "founder"})
    users_store.update_user(username, patch)
    if micro:
        users_store.add_g_credits(username, micro)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


# --------------------------------------------------------------------------
# dollars at $0.01
# --------------------------------------------------------------------------
def test_micro_to_dollars_floors_to_the_cent():
    assert usage_billing.micro_to_dollars(661054) == "$0.66"
    assert usage_billing.micro_to_dollars(900) == "$0.00"
    assert usage_billing.micro_to_dollars(1_000_000) == "$1.00"
    assert usage_billing.micro_to_dollars(-1_000_000) == "-$1.00"
    assert usage_billing.micro_to_dollars(-900) == "$0.00"     # no sign on nothing
    assert usage_billing.micro_to_dollars(15_000_000) == "$15.00"


def test_membership_state_shows_dollars_and_the_raw_figure(client):
    user, h = _session("walker_a", micro=661054)
    g = client.get("/membership/state", headers=h).json()["state"]["g_credits"]
    assert g["balance_display"] == "$0.66"
    assert g["balance_micro"] == 661054 and g["balance"] == 661054
    assert g["unlimited"] is False


# --------------------------------------------------------------------------
# Adjust in dollars (micro on the wire), the cap, both units echoed
# --------------------------------------------------------------------------
def test_adjust_15_dollars_lands_15_million_micro_and_a_dollar_history_row(client):
    founder, hf = _session("founder_m", controller=True)
    target, ht = _session("ava_m")
    r = client.post("/founder/membership/credits", headers=hf,
                    json={"user": target, "delta": 15_000_000, "reason": "pre-walk"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance_micro"] == 15_000_000 and body["balance_display"] == "$15.00"
    assert body["delta_micro"] == 15_000_000 and body["delta_display"] == "+$15.00"
    g = client.get("/membership/state", headers=ht).json()["state"]["g_credits"]
    assert g["balance_display"] == "$15.00"
    row = g["history_tail"][-1]
    assert row["type"] == "adjust" and row["credits_delta"] == 15_000_000


def test_adjust_cap_is_one_thousand_dollars(client):
    founder, hf = _session("founder_c", controller=True)
    target, _ = _session("cap_target")
    ok = client.post("/founder/membership/credits", headers=hf,
                     json={"user": target, "delta": _app.FOUNDER_ADJUST_CAP_MICRO})
    assert ok.status_code == 200
    over = client.post("/founder/membership/credits", headers=hf,
                       json={"user": target, "delta": 1_500_000_000})   # $1,500.00
    assert over.status_code == 400
    assert over.json()["error"] == "out_of_range"
    assert _app.FOUNDER_ADJUST_CAP_MICRO == 1_000_000_000


def test_adjust_on_a_controller_doc_is_refused_with_a_reason(client):
    founder, hf = _session("founder_r", controller=True)
    other, _ = _session("second_controller", controller=True)
    r = client.post("/founder/membership/credits", headers=hf,
                    json={"user": other, "delta": 1_000_000})
    assert r.status_code == 400
    assert r.json()["error"] == "controller_unlimited"
    assert "unlimited" in r.json()["message"]


def test_adjust_log_carries_the_dollar_amount_and_never_the_target_address(client, caplog):
    caplog.set_level("INFO")
    founder, hf = _session("founder_l", controller=True)
    target, _ = _session("quiet.target@example.com")
    client.post("/founder/membership/credits", headers=hf,
                json={"user": target, "delta": 2_500_000})
    lines = [r.getMessage() for r in caplog.records if "founder_membership_credits" in r.getMessage()]
    assert lines and all("quiet.target" not in m for m in lines)
    assert any("+$2.50" in m for m in lines)


# --------------------------------------------------------------------------
# admin unlimited
# --------------------------------------------------------------------------
def test_a_controller_reads_unlimited_on_membership_and_in_the_founder_rows(client):
    founder, hf = _session("founder_u", controller=True)
    g = client.get("/membership/state", headers=hf).json()["state"]["g_credits"]
    assert g["balance_display"] == "unlimited" and g["unlimited"] is True
    rows = client.get(f"/founder/members?email={founder}", headers=hf).json()["members"]
    assert rows[0]["balance_display"] == "unlimited"


def test_an_unlimited_meter_measures_and_never_moves_money(reset_stores):
    users_store._MEMORY_DEBITS.clear()
    _session("meter_admin", controller=True, micro=5_000_000)
    m = compute_meter.ComputeMeter(user="meter_admin", request_id="req-u1",
                                   endpoint="/markov", unlimited=True)
    assert m.reserve("openai:gpt-5.4", "x" * 4000) == 0
    assert m.reserved_micro == 0
    m.add_vendor_usage({"usage": {"prompt_tokens": 1200, "completion_tokens": 900},
                        "model_id": "openai:gpt-5.4", "provider": "openai"})
    breakdown = m.settle()
    assert breakdown is not None and breakdown["total_cost_micro"] > 0   # measured
    assert users_store.get_g_credit_balance("meter_admin") == 5_000_000  # never charged
    assert "req-u1" not in users_store._MEMORY_DEBITS


def test_a_limited_meter_still_debits(reset_stores):
    users_store._MEMORY_DEBITS.clear()
    _session("meter_member", micro=5_000_000)
    m = compute_meter.ComputeMeter(user="meter_member", request_id="req-l1", endpoint="/markov")
    assert m.reserve("openai:gpt-5.4", "x" * 4000) > 0
    assert users_store.get_g_credit_balance("meter_member") < 5_000_000


def test_a_controller_runs_a_metered_route_at_zero_balance_and_pays_nothing(client):
    admin, h = _session("route_admin", controller=True, micro=0)
    h2 = {**h, "Idempotency-Key": "idem-" + secrets.token_urlsafe(8)}
    r = client.post("/markov", json={"text": "the ridge holds"}, headers=h2)
    assert r.status_code == 200, r.text
    assert users_store.get_g_credit_balance(admin) == 0


def test_a_member_at_zero_balance_is_still_gated_on_a_metered_route(client):
    member, h = _session("route_member", micro=0)
    h2 = {**h, "Idempotency-Key": "idem-" + secrets.token_urlsafe(8)}
    assert client.post("/markov", json={"text": "x"}, headers=h2).status_code == 402


# --------------------------------------------------------------------------
# #153 -- one #G run costs $1.00; a controller is never debited
# --------------------------------------------------------------------------
def test_g_run_debits_one_dollar_and_a_controller_is_not_debited(client, monkeypatch):
    monkeypatch.setattr(_app, "_run_g_elins", lambda *a, **k: {"ok": True, "analysis": {}})
    member, hm = _session("g_member", micro=2_500_000)
    r = client.post("/elins/g/run", json={"scenario_text": "a scenario"}, headers=hm)
    assert r.status_code == 200, r.text
    assert r.json()["g_credits_remaining"] == 1_500_000
    # under $1.00 left: the next run is refused, the balance untouched
    r2 = client.post("/elins/g/run", json={"scenario_text": "a scenario"}, headers=hm)
    assert r2.status_code == 200
    r3 = client.post("/elins/g/run", json={"scenario_text": "a scenario"}, headers=hm)
    assert r3.status_code == 402 and r3.json()["error"] == "no_credits"
    assert users_store.get_g_credit_balance(member) == 500_000
    admin, ha = _session("g_admin", controller=True, micro=0)
    ra = client.post("/elins/g/run", json={"scenario_text": "a scenario"}, headers=ha)
    assert ra.status_code == 200, ra.text
    assert "g_credits_remaining" not in ra.json()
    assert users_store.get_g_credit_balance(admin) == 0


def test_consume_g_credit_default_cost_is_unchanged():
    users_store._reset_memory_for_tests()
    users_store.create_user("c1", b"x", "", "free", time.time())
    users_store.add_g_credits("c1", 3)
    assert users_store.consume_g_credit("c1") == 2          # the pre-#153 unit, kept
    assert users_store.consume_g_credit("c1", cost=2) == 0
    with pytest.raises(ValueError):
        users_store.consume_g_credit("c1", cost=1)
