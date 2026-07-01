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
