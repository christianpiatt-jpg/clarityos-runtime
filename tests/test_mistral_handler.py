"""Mistral Large 3 handler tests (v80.1 / FRAGO 12.B.08).

Mirror of test_deepseek_handler — monkeypatch ``_http_post_json``, assert
``_call_mistral`` hits api.mistral.ai, strips the ``mistral:`` prefix,
sends Bearer auth, returns the canonical envelope. Exact model id is
``mistral-large-3-25-12`` per C1 live-docs verification. No SDK import.
"""
import model_router as mr


def test_mistral_mock_on_unset(monkeypatch):
    monkeypatch.delenv("CLARITYOS_MISTRAL_KEY", raising=False)
    out = mr._call_mistral("mistral:mistral-large-3-25-12", "hi",
                           temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert out["provider"] == "mistral"
    assert out["model_id"] == "mistral:mistral-large-3-25-12"


def test_mistral_real_path(monkeypatch):
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    captured = {}

    def fake_post(url, *, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": "mistral large reply"}}]}

    monkeypatch.setattr(mr, "_http_post_json", fake_post)
    out = mr._call_mistral("mistral:mistral-large-3-25-12", "hello",
                           temperature=0.2, max_tokens=32)
    assert out["mock"] is False
    assert out["provider"] == "mistral"
    assert out["text"] == "mistral large reply"
    assert out["model_id"] == "mistral:mistral-large-3-25-12"
    assert captured["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert captured["body"]["model"] == "mistral-large-3-25-12"   # prefix stripped
    assert captured["headers"]["Authorization"] == "Bearer sk-test-mistral"


def test_mistral_via_route_request(monkeypatch):
    """End-to-end through route_request -> _PROVIDER_HANDLERS dispatch."""
    monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-test-mistral")
    monkeypatch.setattr(
        mr, "_http_post_json",
        lambda url, *, headers, body: {"choices": [{"message": {"content": "ok"}}]},
    )
    out = mr.route_request("mistral:mistral-large-3-25-12", "hello")
    assert out["provider"] == "mistral"
    assert out["mock"] is False
    assert out["model_id"] == "mistral:mistral-large-3-25-12"
    assert out["text"] == "ok"
