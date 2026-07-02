"""v81 — /markov recast adapter shape + routing tests.

Covers ``markov_adapter``'s v80-envelope preservation plus the new P-series
fields, ``select_model`` routing to the anthropic task default (post-flip),
``meta["model"]`` override handling, mock-flag propagation, and the
``_build_recast_prompt`` composition (system-prompt inclusion + 2000-char
grounding cap). Adapter is exercised directly (no HTTP) so the shape contract
is asserted independently of the endpoint's metered_compute wrapper.

Provider calls fall back to a deterministic mock without a configured key, so
these run offline and assert ``mock is True``.
"""
from __future__ import annotations

import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import pytest

pytestmark = [pytest.mark.runtime_spine]

_P_KEYS = {"P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"}


@pytest.fixture
def appmod(reset_stores):
    import app as appmod
    return appmod


def test_adapter_returns_v80_fields_plus_primitives(appmod):
    out = appmod.markov_adapter(
        "The board pressured the founder to resign amid falling revenue.", None, "u1",
    )
    # v80 envelope preserved (backward-compat surface).
    for k in ("model", "provider", "output", "mock", "user"):
        assert k in out, f"missing v80 field {k!r}"
    assert out["user"] == "u1"
    # v81 additive fields.
    for k in ("primitives", "primitives_formatted", "primitives_meta", "recast"):
        assert k in out, f"missing v81 field {k!r}"
    assert isinstance(out["primitives"], dict)
    assert _P_KEYS <= set(out["primitives"])
    assert out["primitives_formatted"].startswith("# Primitives")
    assert out["primitives_meta"]["status"] == "extracted"
    assert "counts" in out["primitives_meta"]
    # output mirrors the recast body (single cleaned recast).
    assert out["output"] == out["recast"]
    assert isinstance(out["recast"], str)


def test_default_routes_to_anthropic_and_mocks_without_key(appmod, monkeypatch):
    monkeypatch.delenv("CLARITYOS_ANTHROPIC_KEY", raising=False)
    out = appmod.markov_adapter("x", None, "u2")
    assert out["model"].startswith("anthropic:"), out["model"]
    assert out["mock"] is True


def test_valid_meta_override_is_honored(appmod):
    out = appmod.markov_adapter("x", {"model": "openai:gpt-5.4"}, "u3")
    assert out["model"].startswith("openai:"), out["model"]


def test_invalid_meta_override_falls_through_to_default(appmod):
    # An unknown id is dropped to None → precedence falls to the task default
    # (anthropic post-flip) rather than raising.
    out = appmod.markov_adapter("x", {"model": "bogus:not-a-model"}, "u4")
    assert out["model"].startswith("anthropic:"), out["model"]


def test_build_recast_prompt_includes_system_and_caps_original(appmod):
    formatted = "# Primitives\n## P1 — Entities\n- acme"
    prompt = appmod._build_recast_prompt(formatted, "hello world")
    assert appmod._RECAST_SYSTEM_PROMPT in prompt
    assert "EXTRACTED PRIMITIVES:" in prompt
    assert formatted in prompt
    assert prompt.rstrip().endswith("RECAST:")


def test_build_recast_prompt_truncates_over_2000_chars(appmod):
    formatted = "# Primitives"
    long_text = "a" * 2500
    capped = appmod._build_recast_prompt(formatted, long_text)
    assert " [...truncated]" in capped
    assert "a" * 2500 not in capped
    # Grounding preview keeps the 2000-char head.
    assert "a" * 2000 in capped


# ---------------------------------------------------------------------------
# v82 — mock/credit fix: raise 502 only on a CONFIGURED-handler error
# (scenario 3, fallback_error stamped) so metered_compute refunds the credit.
# Scenarios 1 & 2 (unconfigured provider / no handler → mock, no
# fallback_error) must still return normally.
# ---------------------------------------------------------------------------
def test_markov_adapter_raises_502_when_handler_errors(reset_stores, monkeypatch):
    """Scenario 3: handler configured, provider call raises → adapter raises 502.

    Verifies the mock/credit fix: a mock:true response with fallback_error
    causes the adapter to raise HTTPException(502) instead of returning
    a stub. This lets metered_compute's exception teardown refund the credit.
    """
    from fastapi import HTTPException
    import app as appmod
    import model_router

    def _raising_handler(model_id, prompt, *, temperature, max_tokens):
        raise RuntimeError("simulated anthropic outage")

    monkeypatch.setitem(model_router._PROVIDER_HANDLERS, "anthropic", _raising_handler)
    monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "test-key-for-scenario-3")

    with pytest.raises(HTTPException) as excinfo:
        appmod.markov_adapter(
            "test input", {"model": "anthropic:claude-haiku-4-5-20251001"}, "test_user",
        )

    assert excinfo.value.status_code == 502
    assert excinfo.value.detail["ok"] is False
    assert excinfo.value.detail["error"] == "provider_error"
    assert "anthropic" in excinfo.value.detail["message"]
    assert "simulated anthropic outage" in excinfo.value.detail["message"]


def test_markov_adapter_returns_mock_when_provider_unconfigured(reset_stores, monkeypatch):
    """Scenario 1 (regression): no provider key → mock:true, no fallback_error
    → adapter returns normally with mock envelope. Should NOT raise.
    """
    import app as appmod

    monkeypatch.delenv("CLARITYOS_ANTHROPIC_KEY", raising=False)

    out = appmod.markov_adapter(
        "test input", {"model": "anthropic:claude-haiku-4-5-20251001"}, "test_user",
    )

    assert out["mock"] is True
    assert "fallback_error" not in out  # scenario 1 has no fallback_error
    assert out["output"].startswith("[mock ")  # deterministic stub


def test_markov_adapter_returns_normally_on_real_result(reset_stores, monkeypatch):
    """Regression: real (mock:false) response from handler → adapter returns
    normally, does NOT raise. Guards against the fix over-triggering.
    """
    import app as appmod
    import model_router

    def _real_handler(model_id, prompt, *, temperature, max_tokens):
        return {
            "ok": True,
            "model_id": model_id,
            "provider": "anthropic",
            "text": "real response text",
            "mock": False,
            "ts": 0.0,
        }

    monkeypatch.setitem(model_router._PROVIDER_HANDLERS, "anthropic", _real_handler)
    monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "test-key")

    out = appmod.markov_adapter(
        "test input", {"model": "anthropic:claude-haiku-4-5-20251001"}, "test_user",
    )

    assert out["mock"] is False
    assert out["output"] == "real response text"
    assert out["recast"] == "real response text"
