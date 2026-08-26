"""
CORS preflight must grant Idempotency-Key on metered routes.

★ WHY THIS IS A TEST AND NOT A CODE COMMENT

`metered_compute` REJECTS a metered call that arrives without an
`Idempotency-Key` header, and `web/src/lib/api.ts:127` duly sends one. But a
browser does not just send a non-simple header -- it asks permission first,
in the CORS preflight. If `allow_headers` does not name the header, the
OPTIONS is refused and **the POST is never sent at all**:

    DevTools Issues:  blocked - HTTP status of preflight request
                      didn't indicate success
    HAR:              status 0

That is not a 4xx you can read in a server log; from the backend's side the
request simply never happens. It presented as a live 404-class failure on
`POST /markov`, and it would have hit the metered chat path identically the
moment the meter went live -- with no deploy ordering or client change able
to work around it, because the browser stops before the wire.

The allow-list is one line, invisible in review, and a future edit that
trims it re-breaks every metered route silently. Hence a test.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

ORIGIN = "https://clarity.pro-mediations.com"


@pytest.fixture(scope="module")
def client():
    return TestClient(app_module.app)

# Every route behind metered_compute. Each one needs the header, so each one
# needs the preflight to grant it.
METERED_ROUTES = [
    "/markov",
    "/galileo",
    "/library",
    "/tizzy",
    "/model/complete",
    "/engine/v1/run",
    "/markov/chat",
    "/me/threads/any-thread-id/message",
]


def _preflight(client, path, request_headers):
    return client.options(path, headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": request_headers,
    })


@pytest.mark.parametrize("path", METERED_ROUTES)
def test_preflight_grants_idempotency_key(client, path):
    """The generation test: ask the way a browser asks, and check the answer."""
    r = _preflight(client, path, "content-type,x-session-id,idempotency-key")
    assert 200 <= r.status_code < 300, (
        f"preflight for {path} returned {r.status_code} -- the browser would "
        f"block the POST and it would never reach the server"
    )
    allowed = r.headers.get("access-control-allow-headers", "").lower()
    assert "idempotency-key" in allowed, (
        f"{path}: access-control-allow-headers omits Idempotency-Key: {allowed!r}"
    )


def test_preflight_actually_discriminates(client):
    """Guards the guard. If a preflight returned 2xx for ANY header, the test
    above would pass without proving anything. A header that was never
    granted must still be refused."""
    r = _preflight(client, "/markov", "content-type,x-header-never-granted")
    assert r.status_code == 400, (
        "preflight accepted an ungranted header -- the test above is vacuous"
    )


def test_session_and_content_type_still_granted(client):
    """The header was ADDED, not swapped in. The pre-existing three must
    survive, or auth breaks everywhere."""
    r = _preflight(client, "/markov", "content-type,x-session-id,authorization")
    assert 200 <= r.status_code < 300
    allowed = r.headers.get("access-control-allow-headers", "").lower()
    for h in ("content-type", "x-session-id", "authorization"):
        assert h in allowed, f"{h} lost from the allow-list"
