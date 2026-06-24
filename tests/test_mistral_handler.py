"""Mistral Large 3 handler tests (v80.1 / FRAGO 12.B.08).

Mirror of test_deepseek_handler — monkeypatch ``_http_post_json``, assert
``_call_mistral`` hits api.mistral.ai, strips the ``mistral:`` prefix,
sends Bearer auth, returns the canonical envelope. Exact model id is
``mistral-large-2512`` per ET-2 console catalog read 2026-06-24. No SDK import.
"""
import io
import urllib.error

import pytest

import model_router as mr


def test_mistral_mock_on_unset(monkeypatch):
    monkeypatch.delenv("CLARITYOS_MISTRAL_KEY", raising=False)
    out = mr._call_mistral("mistral:mistral-large-2512", "hi",
                           temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert out["provider"] == "mistral"
    assert out["model_id"] == "mistral:mistral-large-2512"


def test_mistral_real_path(monkeypatch):
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    captured = {}

    def fake_post(url, *, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": "mistral large reply"}}]}

    monkeypatch.setattr(mr, "_http_post_json", fake_post)
    out = mr._call_mistral("mistral:mistral-large-2512", "hello",
                           temperature=0.2, max_tokens=32)
    assert out["mock"] is False
    assert out["provider"] == "mistral"
    assert out["text"] == "mistral large reply"
    assert out["model_id"] == "mistral:mistral-large-2512"
    assert captured["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert captured["body"]["model"] == "mistral-large-2512"   # prefix stripped
    assert captured["headers"]["Authorization"] == "Bearer sk-test-mistral"


def test_mistral_via_route_request(monkeypatch):
    """End-to-end through route_request -> _PROVIDER_HANDLERS dispatch."""
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    monkeypatch.setattr(
        mr, "_http_post_json",
        lambda url, *, headers, body: {"choices": [{"message": {"content": "ok"}}]},
    )
    out = mr.route_request("mistral:mistral-large-2512", "hello")
    assert out["provider"] == "mistral"
    assert out["mock"] is False
    assert out["model_id"] == "mistral:mistral-large-2512"
    assert out["text"] == "ok"


# ---------------------------------------------------------------------------
# FRAGO 12.B.08 Amendment 5+6 — capture-hardening tests.
# Verify the guarded HTTPError-body capture in _call_mistral behaves correctly
# BEFORE the live verify-c10 probe. Test #3 is the load-bearing regression
# guard: the non-HTTPError paths must still mock-fall-back cleanly (an
# unguarded e.read() there would AttributeError and break the fallback).
# ---------------------------------------------------------------------------
def _raise(exc):
    def _post(url, *, headers, body):
        raise exc
    return _post


def test_mistral_http_error_body_captured_in_log(monkeypatch, caplog):
    """HTTPError -> guarded branch logs status= and body= (capture-hardening)."""
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    err = urllib.error.HTTPError(
        "https://api.mistral.ai/v1/chat/completions", 400, "Bad Request", {},
        io.BytesIO(b'{"message":"invalid model id"}'),
    )
    monkeypatch.setattr(mr, "_http_post_json", _raise(err))
    with caplog.at_level("WARNING"):
        out = mr._call_mistral("mistral:mistral-large-2512", "hi",
                               temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert out["provider"] == "mistral"
    assert "status=400" in caplog.text
    assert "body=" in caplog.text


def test_mistral_http_error_body_decoded_verbatim(monkeypatch, caplog):
    """The captured body equals the upstream payload, read once, UTF-8."""
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    payload = '{"message":"model not found: mistral-large-2512"}'
    err = urllib.error.HTTPError(
        "https://api.mistral.ai/v1/chat/completions", 422, "Unprocessable", {},
        io.BytesIO(payload.encode("utf-8")),
    )
    monkeypatch.setattr(mr, "_http_post_json", _raise(err))
    with caplog.at_level("WARNING"):
        out = mr._call_mistral("mistral:mistral-large-2512", "hi",
                               temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert payload in caplog.text


@pytest.mark.parametrize("exc", [
    ValueError("missing choices[0].message.content"),
    urllib.error.URLError("connection refused"),
    TimeoutError("read timed out"),
])
def test_mistral_non_http_error_falls_back_clean(monkeypatch, caplog, exc):
    """LOAD-BEARING: non-HTTPError paths must mock-fall-back without crashing
    (the DeepSeek regression-guard analog). An unguarded .read() here would
    AttributeError and break the fallback."""
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    monkeypatch.setattr(mr, "_http_post_json", _raise(exc))
    with caplog.at_level("WARNING"):
        out = mr._call_mistral("mistral:mistral-large-2512", "hi",
                               temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert out["provider"] == "mistral"
    assert "non-http error" in caplog.text


def test_model_router_imports_urllib_error():
    """Guards the module-scope ``import urllib.error`` against refactor drops;
    the guarded except in _call_mistral/_call_anthropic/_call_gemini needs it."""
    assert hasattr(mr, "urllib")
    assert mr.urllib.error.HTTPError is not None
