"""
Tests for v65 / Unit 69 -- provider health dashboard, as rewritten for #120.

★ THE PROBE THAT LIED. The old probe POSTed a 1-token completion with a
PLACEHOLDER model and reported anthropic 404 / gemini 404 / openai 400 while
real calls succeeded. The probe is now the provider's models-list GET on the
same host and the same auth header the real call uses, and it reports THREE
STATES with the OBSERVED HTTP status carried:

    available    2xx JSON came back (http_status = the observed code)
    no_key       nothing probed -- no env key
    unreachable  probed and failed; http_status = the provider's code when
                 it answered (401 = key rejected), None when nothing did

Stubs ``runtime_http._http_get_json`` (ONE site; returns (status, body)).
No real network in tests: the fixture's belt is pytest.fail, which the
probe's catch-all cannot swallow (Failed derives from BaseException).

Layered coverage:
    A. Unauthed -> 401
    B. No env keys -> only "mock" available; everything else no_key
    C. One env key -> only that provider is probed, at the real host
    D. Stubbed success -> available, status OBSERVED (not a constant)
    E. Stubbed failures -> unreachable, status carried / None
    F. Response shape locked (additive keys)
    G. A key never appears in any URL or error text -- on EVERY branch
    H. The belt bites: an unstubbed probe fails the test, loudly
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
def _no_network(url, *, headers, timeout):
    # pytest.fail raises Failed (a BaseException), so the probe's
    # `except Exception` cannot turn a forgotten stub into a quiet
    # "unreachable" -- the test dies here, as the belt promises.
    pytest.fail(f"unstubbed probe reached the transport: {url}")


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.providers_router)

    # Clean env so each test sets exactly the keys it cares about.
    for k in (
        "CLARITYOS_ANTHROPIC_KEY",
        "CLARITYOS_OPENAI_KEY",
        "CLARITYOS_GEMINI_KEY",
        "CLARITYOS_XAI_KEY",
        "CLARITYOS_LOCAL_MODEL_PATH",
    ):
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setattr(rh_mod, "_http_get_json", _no_network)

    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield TestClient(app)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-ph-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _http_error(code: int, reason: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/", code, reason, {}, None)  # type: ignore[arg-type]


def _ok(status: int = 200):
    return lambda url, *, headers, timeout: (status, {"data": []})


LOCKED_KEYS = {"available", "error", "state", "http_status", "probe"}


# ===========================================================================
# A. Unauthed -> 401
# ===========================================================================
class TestAuth:
    def test_unauthed_health_check_returns_401(self, client):
        r = client.get("/runtime/providers/health")
        assert r.status_code == 401


# ===========================================================================
# B. No env keys -> only mock available; the rest are no_key
# ===========================================================================
class TestNoKeys:
    def test_no_keys_only_mock_available(self, client):
        r = client.get("/runtime/providers/health", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["mock"]["available"] is True
        assert body["mock"]["error"] is None
        assert body["mock"]["state"] == "available"
        for provider in ("anthropic", "openai", "gemini"):
            assert body[provider]["available"] is False
            assert body[provider]["state"] == "no_key"
            assert body[provider]["http_status"] is None
            assert "no api key" in body[provider]["error"]


# ===========================================================================
# C. One env key -> only that provider is probed, at the REAL host, with
#    the REAL auth header, via a models-list GET.
# ===========================================================================
class TestSingleKey:
    def test_only_anthropic_key_triggers_anthropic_probe(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")

        seen = []
        def fake_get(url, *, headers, timeout):
            seen.append((url, dict(headers), timeout))
            return 200, {"data": []}
        monkeypatch.setattr(rh_mod, "_http_get_json", fake_get)

        body = client.get("/runtime/providers/health", headers=_auth()).json()
        assert body["anthropic"]["state"] == "available"
        assert body["openai"]["state"] == "no_key"
        assert body["gemini"]["state"] == "no_key"
        assert len(seen) == 1
        url, headers, timeout = seen[0]
        assert url == "https://api.anthropic.com/v1/models"
        assert headers["x-api-key"] == "sk-test"
        assert headers["anthropic-version"] == "2023-06-01"
        assert timeout > 0
        assert body["anthropic"]["probe"] == "api.anthropic.com/v1/models"

    def test_openai_probe_uses_bearer_on_the_real_host(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        seen = []
        monkeypatch.setattr(rh_mod, "_http_get_json",
                            lambda url, *, headers, timeout: seen.append((url, dict(headers))) or (200, {"data": []}))
        body = client.get("/runtime/providers/health", headers=_auth()).json()
        assert seen[0][0] == "https://api.openai.com/v1/models"
        assert seen[0][1]["Authorization"] == "Bearer sk-o"
        assert body["openai"]["probe"] == "api.openai.com/v1/models"

    def test_gemini_probe_keeps_the_key_out_of_the_url(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-g")
        seen = []
        monkeypatch.setattr(rh_mod, "_http_get_json",
                            lambda url, *, headers, timeout: seen.append((url, dict(headers))) or (200, {"models": []}))
        body = client.get("/runtime/providers/health", headers=_auth()).json()
        url, headers = seen[0]
        assert url == "https://generativelanguage.googleapis.com/v1beta/models"
        assert "key=" not in url
        assert headers["x-goog-api-key"] == "sk-g"
        assert body["gemini"]["probe"] == "generativelanguage.googleapis.com/v1beta/models"


# ===========================================================================
# D. Stubbed success -> available; the status is the OBSERVED one
# ===========================================================================
class TestStubbedSuccess:
    @pytest.mark.parametrize("provider,env", [
        ("anthropic", "CLARITYOS_ANTHROPIC_KEY"),
        ("openai",    "CLARITYOS_OPENAI_KEY"),
        ("gemini",    "CLARITYOS_GEMINI_KEY"),
    ])
    def test_success_is_available_with_the_observed_status(self, client, monkeypatch, provider, env):
        monkeypatch.setenv(env, "sk-x")
        monkeypatch.setattr(rh_mod, "_http_get_json", _ok(200))
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r[provider]["available"] is True
        assert r[provider]["error"] is None
        assert r[provider]["state"] == "available"
        assert r[provider]["http_status"] == 200

    def test_status_is_observed_not_a_constant(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-x")
        monkeypatch.setattr(rh_mod, "_http_get_json", _ok(203))
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"]["state"] == "available"
        assert r["openai"]["http_status"] == 203


# ===========================================================================
# E. Stubbed failures -> unreachable; the HTTP status is CARRIED
# ===========================================================================
class TestStubbedFailure:
    def test_401_means_the_provider_answered_and_rejected_the_key(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise _http_error(401, "Unauthorized")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["anthropic"]["available"] is False
        assert r["anthropic"]["state"] == "unreachable"
        assert r["anthropic"]["http_status"] == 401
        assert r["anthropic"]["error"] == "HTTP 401 Unauthorized"

    def test_404_is_carried_not_swallowed(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise _http_error(404, "Not Found")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["gemini"]["state"] == "unreachable"
        assert r["gemini"]["http_status"] == 404

    def test_read_timeout_is_unreachable_with_no_status(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise socket.timeout("timed out")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"]["state"] == "unreachable"
        assert r["openai"]["http_status"] is None
        assert r["openai"]["error"].startswith("timeout after")

    def test_connect_timeout_wrapped_in_urlerror_reads_the_same(self, client, monkeypatch):
        """urllib wraps a connect-phase timeout as URLError(reason=TimeoutError);
        same deadline, same words."""
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise urllib.error.URLError(TimeoutError("timed out"))
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"]["state"] == "unreachable"
        assert r["openai"]["http_status"] is None
        assert r["openai"]["error"].startswith("timeout after")

    def test_dns_or_refused_is_unreachable_with_no_status(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise urllib.error.URLError(OSError("Name or service not known"))
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"]["state"] == "unreachable"
        assert r["openai"]["http_status"] is None
        assert "unreachable" in r["openai"]["error"]

    def test_parse_failure_is_unreachable(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-test")
        def boom(url, *, headers, timeout):
            raise ValueError("provider returned non-object JSON")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["gemini"]["available"] is False
        assert r["gemini"]["state"] == "unreachable"
        assert "non-object JSON" in r["gemini"]["error"]


# ===========================================================================
# F. Response shape locked (the two legacy keys plus three additive ones)
# ===========================================================================
class TestResponseShape:
    def test_keys_are_exactly_four_providers(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert set(r.keys()) == {"anthropic", "openai", "gemini", "mock"}

    def test_each_provider_carries_locked_inner_keys(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        for provider, entry in r.items():
            assert set(entry.keys()) == LOCKED_KEYS, (
                f"{provider!r} entry keys: {set(entry.keys())}"
            )
            assert isinstance(entry["available"], bool)
            assert entry["error"] is None or isinstance(entry["error"], str)
            assert entry["state"] in {"available", "no_key", "unreachable"}
            assert entry["http_status"] is None or isinstance(entry["http_status"], int)
            # available <=> state == available, always
            assert entry["available"] == (entry["state"] == "available")

    def test_mock_is_always_available(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["mock"]["available"] is True
        assert r["mock"]["error"] is None
        assert r["mock"]["state"] == "available"


# ===========================================================================
# G. A key never appears in a URL, a probe path, or an error text -- on
#    EVERY text-bearing branch (HTTPError, URLError, generic)
# ===========================================================================
SECRET = "sk-SECRET-9f3a1c-long-enough"


def _all_keys(monkeypatch):
    monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", SECRET)
    monkeypatch.setenv("CLARITYOS_OPENAI_KEY", SECRET)
    monkeypatch.setenv("CLARITYOS_GEMINI_KEY", SECRET)


class TestNeverLogAKey:
    def test_httperror_reason_that_quotes_the_headers_is_not_echoed(self, client, monkeypatch):
        _all_keys(monkeypatch)
        seen_urls = []
        def boom(url, *, headers, timeout):
            seen_urls.append(url)
            raise _http_error(403, f"forbidden for {url}?{headers}")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)

        body = client.get("/runtime/providers/health", headers=_auth()).json()
        assert all(SECRET not in u for u in seen_urls)
        dumped = json.dumps(body)
        assert SECRET not in dumped
        for p in ("anthropic", "openai", "gemini"):
            assert body[p]["http_status"] == 403
            assert body[p]["error"] == "HTTP 403 Forbidden"       # the standard phrase, nothing else
            assert "http" not in body[p]["probe"]                  # host+path only

    def test_urlerror_reason_that_quotes_the_headers_is_scrubbed(self, client, monkeypatch):
        _all_keys(monkeypatch)
        def boom(url, *, headers, timeout):
            raise urllib.error.URLError(OSError(f"connect failed for {url} with {headers}"))
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        body = client.get("/runtime/providers/health", headers=_auth()).json()
        dumped = json.dumps(body)
        assert SECRET not in dumped
        for p in ("anthropic", "openai", "gemini"):
            assert body[p]["state"] == "unreachable"
            assert "[redacted]" in body[p]["error"]
            assert "https://" not in body[p]["error"]              # URLs leave as [url]

    def test_generic_exception_text_that_quotes_the_headers_is_scrubbed(self, client, monkeypatch):
        _all_keys(monkeypatch)
        def boom(url, *, headers, timeout):
            raise RuntimeError(f"boom {url} {headers}")
        monkeypatch.setattr(rh_mod, "_http_get_json", boom)
        body = client.get("/runtime/providers/health", headers=_auth()).json()
        dumped = json.dumps(body)
        assert SECRET not in dumped
        for p in ("anthropic", "openai", "gemini"):
            assert body[p]["error"].startswith("RuntimeError:")
            assert "[redacted]" in body[p]["error"]
            assert "https://" not in body[p]["error"]

    def test_scrub_does_not_shred_a_message_on_a_tiny_key(self):
        # a 1-char "key" must not turn every 'e' into [redacted]
        assert rh_mod._scrub("Remote end closed connection", "e") == "Remote end closed connection"
        assert rh_mod._scrub("token sk-SECRET-9f3a1c-long-enough here", SECRET) == "token [redacted] here"
        assert rh_mod._scrub("see https://api.openai.com/v1/models?x=1 now", "") == "see [url] now"


# ===========================================================================
# H. The belt bites
# ===========================================================================
class TestBelt:
    def test_an_unstubbed_probe_fails_the_test_loudly(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        # the fixture's _no_network is in place; the probe must NOT turn it
        # into a quiet "unreachable"
        with pytest.raises(BaseException) as ei:
            client.get("/runtime/providers/health", headers=_auth())
        assert "unstubbed probe reached the transport" in str(ei.value)
