"""
GET /timeline/list must not be shadowed by the timeline router's catch-all.

★ WHY THIS TEST IS THE FIX, AND THE REORDERING IS JUST HOW IT PASSES

FastAPI matches routes in REGISTRATION order, first match wins.
``timeline_router`` carries a catch-all at ``runtime_http.py:1326``::

    @timeline_router.get("/{event_id}")

Included near the top of ``app.py``, that catch-all registered ~2,500 lines
before ``@app.get("/timeline/list")`` and swallowed it. The request resolved
to ``timeline_get(event_id="list")``, ``el_ins.get_event(user, "list")``
returned None, and the client got::

    404  {"ok": false, "error": "http_error",
          "message": "timeline event not found"}

A real endpoint, reporting that a fabricated event id does not exist. It
reads exactly like "the client calls a path that does not exist" -- and it
is not. The path exists and is shadowed. Different defect, different fix,
and the 404 text points at the wrong one.

★★ Route order is invisible in code review. Nothing about moving an
``include_router`` call, adding a route, or reordering a decorator looks
dangerous, and none of it shows up in a diff as a behaviour change. A future
refactor re-breaks this silently and the only symptom is a 404 on a live
endpoint. That is why the guard is a test.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import secrets  # noqa: E402
import time  # noqa: E402

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.routing import Match  # noqa: E402

import app as app_module  # noqa: E402
import sessions_store  # noqa: E402
import users_store  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app_module.app)


@pytest.fixture(scope="module")
def auth(client):
    user = "tl_shadow_probe"
    if not users_store.user_exists(user):
        users_store.create_user(
            username=user, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
            salt="", tier="free", created_at=time.time(),
        )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _resolve(path, method="GET"):
    """Which route object actually wins for ``path``? This is the property
    under test -- a status code alone would not distinguish 'the right
    handler returned empty' from 'the catch-all happened to 200'."""
    scope = {"type": "http", "method": method, "path": path, "path_params": {},
             "headers": [], "query_string": b"", "root_path": "",
             "app": app_module.app}
    for rt in app_module.app.routes:
        try:
            match, _ = rt.matches(scope)
        except Exception:            # pragma: no cover - non-http routes
            continue
        if match == Match.FULL:
            return getattr(rt, "path", None), getattr(rt, "name", None)
    return None, None


def test_timeline_list_resolves_to_its_own_handler():
    """The structural assertion: /timeline/list must bind to timeline_list,
    NOT to the /{event_id} catch-all."""
    path, name = _resolve("/timeline/list")
    assert path == "/timeline/list", (
        f"/timeline/list is shadowed by {path!r} (handler {name!r}) -- the "
        f"catch-all is registered first again"
    )
    assert name == "timeline_list"


def test_timeline_list_returns_the_list_shape_not_a_404(client, auth):
    """The behavioural assertion, as the client experiences it."""
    r = client.get("/timeline/list", headers=auth)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body.get("ok") is True
    # The list shape -- an events collection and a count. The catch-all
    # returned neither; it returned {"ok": false, "error": "http_error"}.
    assert "events" in body, f"not the list shape: {sorted(body)}"
    assert isinstance(body["events"], list)
    assert "count" in body


def test_the_catch_all_still_works_for_a_real_event_id():
    """Guards the guard. The fix must not have disabled /{event_id} -- if it
    had, this test file would pass while breaking the route it moved."""
    path, name = _resolve("/timeline/some-real-event-id")
    assert path == "/timeline/{event_id}", (
        f"the catch-all stopped matching; got {path!r}"
    )
    assert name == "timeline_get"


@pytest.mark.parametrize("path,expected", [
    # The sibling routes on the same router must be unaffected.
    ("/timeline", "/timeline"),
    ("/timeline/since/123", "/timeline/since/{timestamp_ms}"),
    # POST /timeline/write was never at risk (the catch-all is GET-only),
    # but pin it so a future edit cannot quietly capture it either.
    ("/timeline/write", "/timeline/write"),
])
def test_sibling_timeline_routes_unchanged(path, expected):
    resolved, _ = _resolve(path, method="POST" if path.endswith("/write") else "GET")
    assert resolved == expected, f"{path} now resolves to {resolved!r}"
