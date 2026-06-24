"""DeepSeek V4 handler tests (v80.1 / FRAGO 12.B.08).

Unit-level: monkeypatch the module-level ``_http_post_json`` so no real
network call happens; assert ``_call_deepseek`` hits the correct endpoint,
strips the ``deepseek:`` prefix for the wire model, sends Bearer auth, and
returns the canonical envelope. Also covers mock-on-unset and the
``route_request`` dispatch path. Mirrors the existing urllib-handler
pattern (``_call_openai``); no ``openai`` SDK import.
"""
import model_router as mr


def test_deepseek_mock_on_unset(monkeypatch):
    monkeypatch.delenv("CLARITYOS_DEEPSEEK_KEY", raising=False)
    out = mr._call_deepseek("deepseek:deepseek-v4-flash", "hi",
                            temperature=0.2, max_tokens=16)
    assert out["mock"] is True
    assert out["provider"] == "deepseek"
    assert out["model_id"] == "deepseek:deepseek-v4-flash"


def test_deepseek_real_path(monkeypatch):
    monkeypatch.setenv("CLARITYOS_DEEPSEEK_KEY", "sk-test-deepseek")
    captured = {}

    def fake_post(url, *, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": "deepseek v4 reply"}}]}

    monkeypatch.setattr(mr, "_http_post_json", fake_post)
    out = mr._call_deepseek("deepseek:deepseek-v4-pro", "hello",
                            temperature=0.2, max_tokens=32)
    assert out["mock"] is False
    assert out["provider"] == "deepseek"
    assert out["text"] == "deepseek v4 reply"
    assert out["model_id"] == "deepseek:deepseek-v4-pro"
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek-v4-pro"      # prefix stripped
    assert captured["headers"]["Authorization"] == "Bearer sk-test-deepseek"


def test_deepseek_via_route_request(monkeypatch):
    """End-to-end through route_request -> _PROVIDER_HANDLERS dispatch."""
    monkeypatch.setenv("CLARITYOS_DEEPSEEK_KEY", "sk-test-deepseek")
    monkeypatch.setattr(
        mr, "_http_post_json",
        lambda url, *, headers, body: {"choices": [{"message": {"content": "ok"}}]},
    )
    out = mr.route_request("deepseek:deepseek-v4-flash", "hello")
    assert out["provider"] == "deepseek"
    assert out["mock"] is False
    assert out["model_id"] == "deepseek:deepseek-v4-flash"
    assert out["text"] == "ok"
