"""
Tests for Unit 38 — route_model_request integration layer.

Layered coverage (target ~35 tests):
    A. Top-level shape / locked keys
    B. Engine routing — soft-mapped (select_model wins)
    C. Engine routing — hard-pin (OS policy wins over preference)
    D. Prompt shaping
    E. Response passthrough
    F. Validation — operator_intent
    G. Validation — model_route
    H. Validation — engine vocabulary
    I. Non-replacement of v44/v45 surface
    J. Determinism + JSON safety
    K. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import model_router as mr


# ===========================================================================
# Fixtures
# ===========================================================================
def _operator_intent(
    session_id: str = "sess_001",
    operator_id: str = "op_alice",
    intent_type: str = "query",
    runtime_mode: str = "normal",
    override=None,
) -> dict:
    payload = {
        "runtime_mode": runtime_mode,
        "elins_inputs": {"structural": {}, "regime_comparison": {}},
    }
    if override is not None:
        payload["override"] = override
    return {
        "session_id":  session_id,
        "operator_id": operator_id,
        "timestamp":   "2026-05-12T10:00:00+00:00",
        "intent_type": intent_type,
        "payload":     payload,
    }


def _route(engine: str) -> dict:
    return {"engine": engine, "reason": f"test routing to {engine}"}


@pytest.fixture(autouse=True)
def _reset_router():
    """Clear the founder default + local handle cache between tests
    so engine-resolution precedence is deterministic."""
    mr._reset_for_tests()
    yield
    mr._reset_for_tests()


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert set(out.keys()) == {"engine", "request", "response", "metadata"}

    def test_request_keys_locked(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert set(out["request"].keys()) == {
            "model_id", "task", "prompt_preview",
        }

    def test_metadata_keys_locked(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert set(out["metadata"].keys()) == {"provider", "mock", "ts"}

    def test_response_passthrough_has_route_request_keys(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        # route_request normalised contract.
        for key in ("ok", "model_id", "provider", "text", "mock", "ts"):
            assert key in out["response"]


# ===========================================================================
# B. Engine routing — soft-mapped engines go through select_model
# ===========================================================================
class TestSoftMappedRouting:
    def test_claude_engine_routes_via_G_task(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert out["request"]["model_id"] == "openai:gpt-5.4"
        assert out["request"]["task"] == "G"

    def test_copilot_engine_routes_via_c_task(self):
        out = mr.route_model_request(_operator_intent(), _route("copilot"))
        assert out["request"]["model_id"] == "openai:gpt-5.4-mini"
        assert out["request"]["task"] == "c"

    def test_gemini_engine_routes_via_ELINS_task(self):
        # TASK_DEFAULTS["ELINS"] is openai:gpt-5.4.
        out = mr.route_model_request(_operator_intent(), _route("gemini"))
        assert out["request"]["model_id"] == "openai:gpt-5.4"
        assert out["request"]["task"] == "ELINS"

    def test_grok_engine_routes_via_c_task(self):
        out = mr.route_model_request(_operator_intent(), _route("grok"))
        assert out["request"]["model_id"] == "openai:gpt-5.4-mini"
        assert out["request"]["task"] == "c"

    def test_founder_default_overrides_soft_mapped(self):
        mr.set_founder_default_model("google:gemini-2.5-flash")
        try:
            out = mr.route_model_request(_operator_intent(), _route("claude"))
            assert out["request"]["model_id"] == "google:gemini-2.5-flash"
        finally:
            mr.set_founder_default_model(None)


# ===========================================================================
# C. Engine routing — hard-pinned engines bypass select_model
# ===========================================================================
class TestHardPinnedRouting:
    def test_local_routes_to_local_llama(self):
        out = mr.route_model_request(_operator_intent(), _route("local"))
        assert out["request"]["model_id"] == mr.LOCAL_MODEL_ID  # "local:llama3.1"

    def test_local_task_marked_pinned(self):
        out = mr.route_model_request(_operator_intent(), _route("local"))
        assert out["request"]["task"] == "(pinned)"

    def test_local_overrides_founder_default(self):
        mr.set_founder_default_model("anthropic:claude-haiku-4-5-20251001")
        try:
            out = mr.route_model_request(_operator_intent(), _route("local"))
            # Hard-pin wins — diagnostic intents stay on-device regardless
            # of the founder's global default.
            assert out["request"]["model_id"] == mr.LOCAL_MODEL_ID
        finally:
            mr.set_founder_default_model(None)


# ===========================================================================
# D. Prompt shaping
# ===========================================================================
class TestPromptShaping:
    """#147 -- the model reads the operator's text."""
    FRAME = "[ClarityOS operator step] intent=query"

    def _captured(self, monkeypatch, intent, engine="claude"):
        seen: dict = {}
        real = mr.route_request

        def spy(model_id, prompt, **kw):
            seen["prompt"] = prompt
            return real(model_id, prompt, **kw)

        monkeypatch.setattr(mr, "route_request", spy)
        out = mr.route_model_request(intent, _route(engine))
        return out, seen["prompt"]

    def test_prompt_preview_capped_at_60_chars(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert len(out["request"]["prompt_preview"]) <= 60

    def test_prompt_carries_intent_type(self):
        out = mr.route_model_request(
            _operator_intent(intent_type="plan"), _route("claude"),
        )
        assert "intent=plan" in out["request"]["prompt_preview"]

    def test_prompt_is_the_frame_then_the_operator_text(self, monkeypatch):
        intent = _operator_intent(session_id="sess_0123456789abcdef", operator_id="op_alice_long_id")
        intent["payload"]["text"] = "MARKER-7f3a what should the operator do next?"
        _, prompt = self._captured(monkeypatch, intent)
        assert prompt == self.FRAME + "\n\nMARKER-7f3a what should the operator do next?"
        # the envelope never reaches the model
        for envelope in ("sess_0123456789abcdef", "op_alice_long_id", "runtime_mode",
                         "override", "elins_inputs_keys", "session=", "operator="):
            assert envelope not in prompt

    def test_prompt_preview_is_the_frame_only(self, monkeypatch):
        intent = _operator_intent()
        intent["payload"]["text"] = "MARKER-7f3a what should the operator do next?"
        out, _ = self._captured(monkeypatch, intent)
        assert out["request"]["prompt_preview"] == self.FRAME

    def test_text_is_capped_by_the_module_constant(self, monkeypatch):
        intent = _operator_intent()
        intent["payload"]["text"] = "x" * (mr.OPERATOR_TEXT_MAX_CHARS + 500)
        _, prompt = self._captured(monkeypatch, intent)
        assert prompt == self.FRAME + "\n\n" + "x" * mr.OPERATOR_TEXT_MAX_CHARS

    def test_missing_text_gives_the_frame_and_an_empty_body(self, monkeypatch):
        _, prompt = self._captured(monkeypatch, _operator_intent())
        assert prompt == self.FRAME + "\n\n"

    def test_the_envelope_goes_to_the_log_line_not_the_prompt(self, monkeypatch, caplog):
        caplog.set_level("INFO", logger="clarityos.model_router")
        intent = _operator_intent(session_id="sess_0123456789abcdef", runtime_mode="strict")
        intent["payload"]["text"] = "MARKER-7f3a"
        _, prompt = self._captured(monkeypatch, intent)
        lines = [r.getMessage() for r in caplog.records
                 if r.getMessage().startswith("route_model_request ")]
        assert len(lines) == 1
        line = lines[0]
        assert "runtime_mode=strict" in line and "elins_inputs_keys=2" in line
        assert "session_ref=sess_012..." in line          # a redacted ref
        assert "sess_0123456789abcdef" not in line
        assert "MARKER" not in line and "text_chars=11" in line  # never the text
        assert "runtime_mode" not in prompt

    def test_the_mock_reply_carries_no_member_text(self):
        # the suite sets no provider key, so route_request answers with the
        # mock; its 60-char preview used to be of the WHOLE prompt
        intent = _operator_intent()
        intent["payload"]["text"] = "MARKER-7f3a what should the operator do next?"
        out = mr.route_model_request(intent, _route("claude"))
        assert out["response"]["mock"] is True
        assert out["response"]["text"] == f"[mock {out['request']['model_id']}] {self.FRAME}"

    def test_a_non_string_intent_type_frames_as_unknown(self, monkeypatch):
        intent = _operator_intent()
        intent["intent_type"] = {"x": "MEMBER"}
        _, prompt = self._captured(monkeypatch, intent)
        assert prompt.startswith("[ClarityOS operator step] intent=unknown\n\n")
        assert "MEMBER" not in prompt

    def test_prompt_handles_malformed_payload_gracefully(self, monkeypatch):
        intent = _operator_intent()
        intent["payload"] = "not a dict"
        out, prompt = self._captured(monkeypatch, intent)
        assert prompt == self.FRAME + "\n\n"
        assert isinstance(out["request"]["prompt_preview"], str)

    def test_the_vault_preferred_model_names_the_answerer(self):
        intent = _operator_intent()
        intent["payload"]["preferred_model_id"] = "google:gemini-2.5-flash"
        out = mr.route_model_request(intent, _route("claude"))
        assert out["engine"] == "claude"  # the label, chosen before the call
        assert out["request"]["model_id"] == "google:gemini-2.5-flash"
        assert out["request"]["model_id"] != mr.TASK_DEFAULTS[mr._ENGINE_TO_TASK["claude"]]
        assert out["request"]["task"] == "(vault-preferred)"


# ===========================================================================
# E. Response passthrough
# ===========================================================================
class TestResponsePassthrough:
    def test_metadata_provider_matches_response(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert out["metadata"]["provider"] == out["response"]["provider"]

    def test_metadata_mock_matches_response(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert out["metadata"]["mock"] == out["response"]["mock"]

    def test_metadata_ts_is_float(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        assert isinstance(out["metadata"]["ts"], float)

    def test_engine_echoed(self):
        for engine in ("local", "claude", "copilot", "gemini", "grok"):
            out = mr.route_model_request(_operator_intent(), _route(engine))
            assert out["engine"] == engine


# ===========================================================================
# F. operator_intent validation
# ===========================================================================
class TestOperatorIntentValidation:
    def test_none_rejected(self):
        with pytest.raises(ValueError, match="operator_intent"):
            mr.route_model_request(None, _route("claude"))

    def test_list_rejected(self):
        with pytest.raises(ValueError, match="operator_intent"):
            mr.route_model_request([1, 2, 3], _route("claude"))

    def test_string_rejected(self):
        with pytest.raises(ValueError, match="operator_intent"):
            mr.route_model_request("not a dict", _route("claude"))


# ===========================================================================
# G. model_route validation
# ===========================================================================
class TestModelRouteValidation:
    def test_none_rejected(self):
        with pytest.raises(ValueError, match="model_route"):
            mr.route_model_request(_operator_intent(), None)

    def test_list_rejected(self):
        with pytest.raises(ValueError, match="model_route"):
            mr.route_model_request(_operator_intent(), ["claude"])

    def test_missing_engine_rejected(self):
        with pytest.raises(ValueError, match="engine"):
            mr.route_model_request(_operator_intent(), {"reason": "x"})

    def test_empty_engine_rejected(self):
        with pytest.raises(ValueError, match="engine"):
            mr.route_model_request(_operator_intent(), {"engine": ""})

    def test_non_string_engine_rejected(self):
        with pytest.raises(ValueError, match="engine"):
            mr.route_model_request(_operator_intent(), {"engine": 42})


# ===========================================================================
# H. Engine vocabulary validation
# ===========================================================================
class TestEngineVocabulary:
    def test_unknown_engine_rejected(self):
        with pytest.raises(ValueError, match="engine"):
            mr.route_model_request(
                _operator_intent(), _route("perplexity"),
            )

    def test_openai_engine_rejected(self):
        # openai is a model_router provider but NOT a dispatcher engine
        # — Unit 36's vocabulary is the source of truth here.
        with pytest.raises(ValueError, match="engine"):
            mr.route_model_request(_operator_intent(), _route("openai"))

    def test_valid_engines_match_dispatcher_vocabulary(self):
        # Unit 36's locked engine vocab is {copilot, claude, gemini, grok, local}.
        assert set(mr._VALID_ENGINES) == {
            "copilot", "claude", "gemini", "grok", "local",
        }


# ===========================================================================
# I. Non-replacement of v44/v45 surface
# ===========================================================================
class TestNoSurfaceReplacement:
    def test_select_model_still_callable(self):
        # v44 entrypoint must continue to work after Unit 38 lands.
        model_id = mr.select_model(None, task="G")
        assert model_id == "openai:gpt-5.4"

    def test_route_request_still_callable(self):
        # v44 entrypoint must continue to work after Unit 38 lands.
        out = mr.route_request("anthropic:claude-haiku-4-5-20251001", "hello")
        assert out["ok"] is True
        assert out["model_id"] == "anthropic:claude-haiku-4-5-20251001"

    def test_task_defaults_untouched(self):
        # v44/v45 task buckets must be preserved exactly.
        for bucket in ("c", "G", "ELINS", "thread", "thread_summary"):
            assert bucket in mr.TASK_DEFAULTS

    def test_supported_models_untouched(self):
        # v44/v45 model catalogue must be preserved.
        for model_id in (
            "openai:gpt-5.4", "anthropic:claude-haiku-4-5-20251001",
            "google:gemini-2.5-flash", "xai:groq-llama", "local:llama3.1",
        ):
            assert model_id in mr.SUPPORTED_MODELS

    def test_provider_handlers_untouched(self):
        # All v44/v45 provider handlers stay registered.
        assert set(mr._PROVIDER_HANDLERS.keys()) == {
            "openai", "anthropic", "gemini", "xai", "local",
            "ollama", "deepseek", "mistral",
        }

    def test_router_version_bumped(self):
        # v80 — bumped for FRAGO 12.B.08 (deepseek + mistral wiring).
        assert mr.ROUTER_VERSION == "model_router.v80"


# ===========================================================================
# J. Determinism + JSON safety
# ===========================================================================
class TestDeterminism:
    def test_same_input_same_routing(self):
        a = mr.route_model_request(_operator_intent(), _route("claude"))
        b = mr.route_model_request(_operator_intent(), _route("claude"))
        # ts will differ (route_request stamps time.time()), so compare
        # everything else.
        assert a["engine"] == b["engine"]
        assert a["request"] == b["request"]
        assert a["response"]["model_id"] == b["response"]["model_id"]
        assert a["response"]["provider"] == b["response"]["provider"]
        assert a["response"]["mock"] == b["response"]["mock"]

    def test_output_is_json_safe(self):
        out = mr.route_model_request(_operator_intent(), _route("claude"))
        s = json.dumps(out)
        assert json.loads(s) == out

    def test_intent_not_mutated(self):
        intent = _operator_intent()
        snap = json.dumps(intent, sort_keys=True)
        mr.route_model_request(intent, _route("claude"))
        assert json.dumps(intent, sort_keys=True) == snap

    def test_model_route_not_mutated(self):
        route = _route("claude")
        snap = json.dumps(route, sort_keys=True)
        mr.route_model_request(_operator_intent(), route)
        assert json.dumps(route, sort_keys=True) == snap


# ===========================================================================
# K. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_route_model_request_exported(self):
        assert hasattr(mr, "route_model_request")
        assert callable(mr.route_model_request)

    def test_engine_maps_exported(self):
        assert hasattr(mr, "_ENGINE_HARD_PIN")
        assert hasattr(mr, "_ENGINE_TO_TASK")
        assert hasattr(mr, "_VALID_ENGINES")

    def test_route_model_request_signature(self):
        sig = inspect.signature(mr.route_model_request)
        assert list(sig.parameters.keys()) == ["operator_intent", "model_route"]

    def test_no_new_network_imports(self):
        src = inspect.getsource(mr.route_model_request)
        # Unit 38 must not add direct I/O — it delegates to route_request.
        for forbidden in (
            "requests.", "httpx.", "urllib.request",
            "asyncio.open_connection", "open(",
        ):
            assert forbidden not in src, (
                f"route_model_request must not use {forbidden!r}"
            )
