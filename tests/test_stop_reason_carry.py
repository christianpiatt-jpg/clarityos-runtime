"""
#128 -- the provider's stop reason is carried, not dropped.

★ WHAT THESE PIN. Every vendor returns a stop signal (anthropic
``stop_reason``, openai ``choices[0].finish_reason``, gemini
``candidates[0].finishReason``); the router read none of them, so the
kernel's refusal detection had only phrase shapes to go on. Now each adapter
carries the RAW vendor value as ``result["stop_reason"]`` (None on mock --
a mock stopped for no vendor reason), and run_emotional_physics copies it
to ``_meta["stop_reason"]``. No normalisation in the router: the value sets
are disjoint in meaning and ``provider`` sits in the same dict. All seven
adapters carry the key (ollama done_reason; deepseek / mistral
finish_reason; local whatever the runtime says, else None).

★ THE CASE THE FIELD IS FOR. A vendor-classified refusal often comes with an
EMPTY body (anthropic stop_reason "refusal", openai finish_reason
"content_filter" with null content, gemini finishReason "SAFETY" with no
parts). The adapters raise on the empty body and degrade to mock -- and
before this the signal died with the raise. It is captured the moment the
body arrives and rides the degraded result, so the kernel sees it.

Stubs ``model_router._http_post_json`` (the one chokepoint) -- no network.
"""
from __future__ import annotations

import pytest

import model_router as mr


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in ("CLARITYOS_ANTHROPIC_KEY", "CLARITYOS_OPENAI_KEY", "CLARITYOS_GEMINI_KEY"):
        monkeypatch.delenv(k, raising=False)
    mr._reset_for_tests()
    yield
    mr._reset_for_tests()


def _anthropic_reply(text: str, stop: str = "end_turn") -> dict:
    return {"content": [{"type": "text", "text": text}], "stop_reason": stop,
            "usage": {"input_tokens": 3, "output_tokens": 2}}


class TestAdaptersCarryTheRawValue:
    def test_anthropic_stop_reason(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setattr(mr, "_http_post_json",
                            lambda url, *, headers, body: _anthropic_reply("ok", "end_turn"))
        out = mr._call_anthropic("anthropic:claude-haiku-4-5-20251001", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is False
        assert out["stop_reason"] == "end_turn"

    def test_anthropic_max_tokens_is_carried_verbatim(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setattr(mr, "_http_post_json",
                            lambda url, *, headers, body: _anthropic_reply("truncat", "max_tokens"))
        out = mr._call_anthropic("anthropic:claude-haiku-4-5-20251001", "hi", temperature=0.2, max_tokens=16)
        assert out["stop_reason"] == "max_tokens"

    def test_openai_finish_reason(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        })
        out = mr._call_openai("openai:gpt-5.4", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is False
        assert out["stop_reason"] == "stop"

    def test_openai_content_filter_is_carried_verbatim(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "choices": [{"message": {"content": "x"}, "finish_reason": "content_filter"}],
        })
        out = mr._call_openai("openai:gpt-5.4", "hi", temperature=0.2, max_tokens=16)
        assert out["stop_reason"] == "content_filter"

    def test_gemini_finish_reason(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-g")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}],
        })
        out = mr._call_gemini("google:gemini-2.5-flash", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is False
        assert out["stop_reason"] == "STOP"

    def test_a_vendor_that_omits_the_field_yields_none_not_a_guess(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "choices": [{"message": {"content": "ok"}}],
        })
        out = mr._call_openai("openai:gpt-5.4", "hi", temperature=0.2, max_tokens=16)
        assert out["stop_reason"] is None


class TestMockCarriesNone:
    def test_mock_result_has_the_key_and_it_is_none(self):
        out = mr._mock_result("anthropic:claude-haiku-4-5-20251001", "anthropic", "hi", 0.0)
        assert "stop_reason" in out
        assert out["stop_reason"] is None

    def test_no_key_path_is_mock_with_none(self):
        out = mr._call_anthropic("anthropic:claude-haiku-4-5-20251001", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is True
        assert out["stop_reason"] is None


class TestKernelCopiesItIntoMeta:
    def test_run_emotional_physics_meta_stop_reason_end_turn(self, monkeypatch, reset_stores):
        """The brief's acceptance line: _meta.stop_reason == "end_turn" on a
        mocked anthropic reply. The reply text is deliberately not the JSON
        the kernel wants, so the skeleton path is exercised too: the stop
        reason is copied REGARDLESS of whether the body parsed."""
        import intelligence_kernel as ik
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        seen = {}
        def fake_post(url, *, headers, body):
            seen["url"] = url
            return _anthropic_reply("not json at all", "end_turn")
        monkeypatch.setattr(mr, "_http_post_json", fake_post)
        # route the physics task to anthropic explicitly, whatever the
        # task default says today
        monkeypatch.setattr(ik, "_resolve_model",
                            lambda *a, **k: "anthropic:claude-haiku-4-5-20251001")
        out = ik.run_emotional_physics("alice", "The board met. Nobody named it. Everyone left.")
        assert "anthropic.com" in seen.get("url", ""), "the stubbed anthropic call was not reached"
        assert out["_meta"]["stop_reason"] == "end_turn"

    def test_run_emotional_physics_meta_stop_reason_none_on_mock(self, reset_stores):
        import intelligence_kernel as ik
        out = ik.run_emotional_physics("alice", "The board met.")
        assert "stop_reason" in out["_meta"]
        assert out["_meta"]["stop_reason"] is None


class TestEmptyBodyRefusalStillCarriesTheSignal:
    """The degraded (mock) result carries the vendor's reason."""

    def test_anthropic_refusal_with_no_text_blocks(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "content": [], "stop_reason": "refusal",
        })
        out = mr._call_anthropic("anthropic:claude-haiku-4-5-20251001", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is True
        assert "fallback_error" in out
        assert out["stop_reason"] == "refusal"

    def test_openai_content_filter_with_null_content(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "choices": [{"message": {"content": None}, "finish_reason": "content_filter"}],
        })
        out = mr._call_openai("openai:gpt-5.4", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is True
        assert out["stop_reason"] == "content_filter"

    def test_gemini_safety_with_no_parts(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-g")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}],
        })
        out = mr._call_gemini("google:gemini-2.5-flash", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is True
        assert out["stop_reason"] == "SAFETY"

    def test_transport_failure_before_any_body_carries_none(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        def boom(url, *, headers, body):
            raise ConnectionError("down")
        monkeypatch.setattr(mr, "_http_post_json", boom)
        out = mr._call_anthropic("anthropic:claude-haiku-4-5-20251001", "hi", temperature=0.2, max_tokens=16)
        assert out["mock"] is True
        assert out["stop_reason"] is None

    def test_kernel_sees_the_refusal_even_though_the_body_degraded(self, monkeypatch, reset_stores):
        import intelligence_kernel as ik
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "content": [], "stop_reason": "refusal",
        })
        monkeypatch.setattr(ik, "_resolve_model", lambda *a, **k: "anthropic:claude-haiku-4-5-20251001")
        out = ik.run_emotional_physics("alice", "The board met.")
        assert out["_meta"]["stop_reason"] == "refusal"


class TestTheOtherFourAdapters:
    def test_deepseek_and_mistral_carry_finish_reason(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_DEEPSEEK_KEY", "sk-d")
        monkeypatch.setenv("CLARITYOS_MISTRAL_KEY", "sk-m")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "length"}],
        })
        assert mr._call_deepseek("deepseek:deepseek-v4-flash", "hi", temperature=0.2, max_tokens=16)["stop_reason"] == "length"
        assert mr._call_mistral("mistral:mistral-large-2512", "hi", temperature=0.2, max_tokens=16)["stop_reason"] == "length"

    def test_ollama_carries_done_reason(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OLLAMA_URL", "http://localhost:11434")
        monkeypatch.setattr(mr, "_http_post_json", lambda url, *, headers, body: {
            "model": "llama3.1", "response": "ok", "done": True, "done_reason": "stop",
        })
        assert mr._call_ollama("ollama:llama3.1", "hi", temperature=0.2, max_tokens=16)["stop_reason"] == "stop"

    def test_every_adapter_result_has_the_key(self, monkeypatch):
        """No key configured -> every adapter degrades to mock, and the mock
        carries stop_reason None. The key is never ABSENT."""
        for k in ("CLARITYOS_DEEPSEEK_KEY", "CLARITYOS_MISTRAL_KEY", "CLARITYOS_OLLAMA_URL"):
            monkeypatch.delenv(k, raising=False)
        for fn, mid in (
            (mr._call_openai, "openai:gpt-5.4"), (mr._call_anthropic, "anthropic:claude-haiku-4-5-20251001"),
            (mr._call_gemini, "google:gemini-2.5-flash"), (mr._call_deepseek, "deepseek:deepseek-v4-flash"),
            (mr._call_mistral, "mistral:mistral-large-2512"), (mr._call_ollama, "ollama:llama3.1"),
        ):
            out = fn(mid, "hi", temperature=0.2, max_tokens=16)
            assert "stop_reason" in out, fn.__name__
            assert out["stop_reason"] is None, fn.__name__
