"""
#145 -- two rails, one flag: /founder is admin only.

CT-1 RULED 09-04: a non-controller session on any /founder/* route is
refused 403 {"error": "admin_only"}; the controller is admitted; no cohort
string opens or closes the gate (the flag does -- users_store.is_controller,
the ONE predicate #124 named). The sweep below reads the route table, so a
new /founder/* handler mounted without the gate fails here, not on the
live console.
"""
from __future__ import annotations

import secrets
import time

import pytest

from conftest import TestClient

import sessions_store
import users_store

import app as _app


@pytest.fixture
def client(reset_stores):
    return TestClient(_app.app)


def _session(username: str, *, controller: bool = False, cohort: str = "terrace_1"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    # "terrace_1": a member string, NOT a controller string under the #124
    # shim ("founder" / "founder_exception" / "admin" are).
    patch = {"cohort": cohort, "membership_status": "active", "membership_tier": "founding_500"}
    if controller:
        patch["controller"] = True
    users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# --------------------------------------------------------------------------
# the sweep -- every /founder/* route refuses a member with admin_only
# --------------------------------------------------------------------------
def _founder_routes():
    return [r for r in _app.app.routes if getattr(r, "path", "").startswith("/founder")]


def _concrete(path: str) -> str:
    """/founder/vault/{user_id}/item/{key:path} -> /founder/vault/x/item/x.
    The gate runs before any path or body validation, so a dummy is enough."""
    import re
    return re.sub(r"\{[^}]+\}", "x", path)


def test_every_founder_route_refuses_a_member_with_admin_only(client):
    """Behavioural, not structural: 31 handlers in app.py depend on
    _require_founder directly; 20 more (acceptance_dashboard's routers)
    compose it inside _founder_gate at request time, which a Depends-tree
    walk cannot see. Calling each one is the witness. 51 at #145; a smaller
    count means a route was unmounted."""
    h = _session("sweep145@example.com")
    routes = _founder_routes()
    assert len(routes) >= 51, sorted(r.path for r in routes)
    open_doors = []
    for r in routes:
        for method in sorted(r.methods):
            url = _concrete(r.path)
            if method == "GET":
                resp = client.get(url, headers=h)
            elif method == "POST":
                resp = client.post(url, json={}, headers=h)
            else:
                # conftest's AppClient wraps GET and POST only (its _do refuses
                # other verbs). No /founder route uses another verb today; one
                # that does must be swept, not skipped -- fail loud here.
                pytest.fail(f"unswept verb {method} {r.path}: teach the sweep")
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            if resp.status_code != 403 or body.get("error") != "admin_only":
                open_doors.append(f"{method} {r.path} -> {resp.status_code} {body.get('error')}")
    assert open_doors == []


def test_the_gate_names_no_cohort_string():
    """The refusal is the flag's, not a string's: nothing in _require_founder
    compares a cohort value. (The one-deploy shim lives in users_store and
    is #157's to delete.)"""
    import inspect
    src = inspect.getsource(_app._require_founder)
    assert "is_controller" in src
    for s in ('"founder"', '"founder_exception"', '"admin"', "FOUNDER_LIKE"):
        assert s not in src, s


# --------------------------------------------------------------------------
# the refusal and the admission
# --------------------------------------------------------------------------
def test_a_member_is_refused_admin_only_on_founder_members(client):
    h = _session("cit145@example.com")
    r = client.get("/founder/members", headers=h)
    assert r.status_code == 403
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "admin_only"
    # the refusal names the rule, not a cohort, and carries no address
    assert "cohort" not in body["message"].lower()
    assert "@" not in r.text


def test_a_member_is_refused_on_a_write_too(client):
    h = _session("cit145b@example.com")
    r = client.post(
        "/founder/membership/credits",
        json={"user": "someone@example.com", "delta": 1_000_000},
        headers=h,
    )
    assert r.status_code == 403
    assert r.json()["error"] == "admin_only"


def test_no_session_is_401_not_admin_only(client):
    r = client.get("/founder/members")
    assert r.status_code == 401


def test_the_controller_is_admitted(client):
    h = _session("ctrl145@example.com", controller=True)
    assert client.get("/founder/members", headers=h).status_code == 200


def test_the_flag_admits_whatever_the_string_says(client):
    """controller=True on a doc whose cohort string is a member string: the
    flag is what the gate reads."""
    h = _session("flag145@example.com", controller=True, cohort="terrace_1")
    assert client.get("/founder/members", headers=h).status_code == 200


def test_a_derived_citizen_label_does_not_open_the_gate(client):
    """"founding" is the derived label of a paying citizen (#124). It is
    not a controller string and the flag is off: refused."""
    h = _session("founding145@example.com", cohort="founding")
    r = client.get("/founder/members", headers=h)
    assert r.status_code == 403
    assert r.json()["error"] == "admin_only"
