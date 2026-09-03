"""Every /founder/* route in acceptance_dashboard.py is founder-gated.

Eight routers there shipped with no ``dependencies=``. Five returned 200 to an
UNAUTHENTICATED browser (console/summary, launch/readiness, surfaces/unified,
operator/state, acceptance/runs/recent), and POST
/founder/acceptance/incidents/{id}/resolve was an ungated WRITE.

The gate is applied at the ROUTER level, so pinning console/summary pins every
handler under every prefix -- including future ones and the resolve write. The
last test hits that write directly to prove the WRITE path is closed, not just
the reads.
"""
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


def _make_user(app_module, username, cohort="founder"):
    import secrets
    import bcrypt
    import users_store
    import sessions_store
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def test_console_summary_401_without_session(client):
    r = client.get("/founder/console/summary")
    assert r.status_code == 401, (r.status_code, r.text[:200])
    assert r.json()["error"] == "missing_session"


def test_console_summary_403_for_non_founder(app_module, client):
    _, sid = _make_user(app_module, "cg_outsider", cohort=None)
    r = client.get("/founder/console/summary", headers={"X-Session-ID": sid})
    assert r.status_code == 403, (r.status_code, r.text[:200])


def test_console_summary_200_for_founder(app_module, client):
    _, sid = _make_user(app_module, "cg_founder", cohort="founder")
    r = client.get("/founder/console/summary", headers={"X-Session-ID": sid})
    assert r.status_code == 200, (r.status_code, r.text[:200])


def test_resolve_write_is_gated_without_a_session(client):
    # The ungated WRITE this fix targets. Without a session it must 401 BEFORE
    # the handler runs -- not 200, and not a 4xx/5xx from inside the handler
    # that would mean it executed against a missing incident.
    r = client.post(
        "/founder/acceptance/incidents/does-not-exist/resolve", json={},
    )
    assert r.status_code == 401, (r.status_code, r.text[:200])
    assert r.json()["error"] == "missing_session"
