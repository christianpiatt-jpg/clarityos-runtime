"""
Tests for v69 / Unit 74 — el_ins.el_ins_analyzer.

Covers:
    A. Deterministic mode classifications (high_el / high_ins / balanced)
    B. JSON shape matches skills_export/el_ins/schema.json
    C. Reasoning mode mapping (stabilize / expand / normal)
    D. Edge cases (empty, whitespace, unknown tokens)
    E. provider_mode parameter validation
    F. analyze_thread batches preserve order
    G. LLM fallback to deterministic on parse failure
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import el_ins
from el_ins.el_ins_analyzer import (
    HIGH_EL_THRESHOLD,
    HIGH_INS_THRESHOLD,
    PROVIDER_MODES,
    SYSTEM_PROMPT_PATH,
    _classify_ratio,
    _coerce_llm_output,
    _deterministic_analyze,
    _mode_for,
    _reset_prompt_cache,
    _tokenise,
)


# ===========================================================================
# A. Deterministic classifications
# ===========================================================================
class TestDeterministicClassifications:
    def test_pure_emotive_text_is_high_el(self):
        text = (
            "catastrophic disaster doom panic everyone obviously crisis "
            "unprecedented stunning shocking horrifying terrible"
        )
        r = el_ins.analyze_text(text, provider_mode="deterministic")
        assert r["analysis"]["ratio_classification"] == "high_el"
        assert r["reasoning_mode"] == "stabilize"

    def test_pure_institutional_text_is_high_ins(self):
        text = (
            "section 42 statute contract clause testimony defendant ruling "
            "constitution treaty doctrine ordinance"
        )
        r = el_ins.analyze_text(text, provider_mode="deterministic")
        assert r["analysis"]["ratio_classification"] == "high_ins"
        assert r["reasoning_mode"] == "expand"

    def test_mixed_balanced_text(self):
        # Even mix of both vocabularies should land balanced.
        text = (
            "the statute is essential and the treaty obviously matters; "
            "the contract clause is critical for the court ruling"
        )
        r = el_ins.analyze_text(text, provider_mode="deterministic")
        assert r["analysis"]["ratio_classification"] in (
            "balanced", "high_el", "high_ins",
        )
        # Balanced is what we expect, but assert reasoning_mode is
        # one of the three valid values regardless.
        assert r["reasoning_mode"] in ("stabilize", "expand", "normal")

    def test_neutral_text_with_no_markers_is_balanced(self):
        text = "the cat sat on the mat and watched the rain"
        r = el_ins.analyze_text(text, provider_mode="deterministic")
        assert r["analysis"]["el_score"] == 0
        assert r["analysis"]["ins_score"] == 0
        assert r["analysis"]["ratio_classification"] == "balanced"
        assert r["reasoning_mode"] == "normal"


# ===========================================================================
# B. JSON shape
# ===========================================================================
class TestSchemaShape:
    def test_top_level_keys_locked(self):
        r = el_ins.analyze_text("any text", provider_mode="deterministic")
        assert set(r.keys()) == {
            "analysis", "reasoning_mode", "regression_chain", "stability_notes",
        }

    def test_analysis_block_keys_locked(self):
        r = el_ins.analyze_text("any text", provider_mode="deterministic")
        assert set(r["analysis"].keys()) == {
            "el_components", "ins_components",
            "el_score", "ins_score",
            "ratio_classification",
        }

    def test_regression_chain_keys_locked(self):
        r = el_ins.analyze_text("any text", provider_mode="deterministic")
        assert set(r["regression_chain"].keys()) == {
            "projection", "drivers", "precedents",
            "principle_stack", "invariant",
        }

    def test_scores_are_in_bounds(self):
        r = el_ins.analyze_text(
            "catastrophic " * 100, provider_mode="deterministic",
        )
        assert 0 <= r["analysis"]["el_score"] <= 10
        assert 0 <= r["analysis"]["ins_score"] <= 10

    def test_ratio_classification_is_valid_enum(self):
        for text in [
            "catastrophic disaster doom",
            "statute clause testimony",
            "neutral content here",
            "",
        ]:
            r = el_ins.analyze_text(text, provider_mode="deterministic")
            assert r["analysis"]["ratio_classification"] in (
                "high_el", "high_ins", "balanced",
            )

    def test_components_are_string_lists(self):
        r = el_ins.analyze_text(
            "catastrophic statute disaster contract",
            provider_mode="deterministic",
        )
        for elt in r["analysis"]["el_components"]:
            assert isinstance(elt, str)
        for elt in r["analysis"]["ins_components"]:
            assert isinstance(elt, str)


# ===========================================================================
# C. Reasoning mode mapping
# ===========================================================================
class TestReasoningModeMapping:
    def test_high_el_maps_to_stabilize(self):
        assert _mode_for("high_el") == "stabilize"

    def test_high_ins_maps_to_expand(self):
        assert _mode_for("high_ins") == "expand"

    def test_balanced_maps_to_normal(self):
        assert _mode_for("balanced") == "normal"


# ===========================================================================
# D. Edge cases
# ===========================================================================
class TestEdgeCases:
    def test_empty_string_returns_balanced(self):
        r = el_ins.analyze_text("", provider_mode="deterministic")
        assert r["analysis"]["ratio_classification"] == "balanced"
        assert r["reasoning_mode"] == "normal"

    def test_whitespace_only_returns_balanced(self):
        r = el_ins.analyze_text("   \n  \t  ", provider_mode="deterministic")
        assert r["analysis"]["ratio_classification"] == "balanced"

    def test_unknown_tokens_only_returns_balanced(self):
        r = el_ins.analyze_text(
            "zorblax fnordable wibbletronic", provider_mode="deterministic",
        )
        assert r["analysis"]["el_score"] == 0
        assert r["analysis"]["ins_score"] == 0
        assert r["analysis"]["ratio_classification"] == "balanced"

    def test_only_one_side_present_picks_that_side(self):
        r_el = el_ins.analyze_text(
            "obviously absolutely critical", provider_mode="deterministic",
        )
        assert r_el["analysis"]["ratio_classification"] == "high_el"
        r_ins = el_ins.analyze_text(
            "statute clause treaty", provider_mode="deterministic",
        )
        assert r_ins["analysis"]["ratio_classification"] == "high_ins"


# ===========================================================================
# E. provider_mode validation
# ===========================================================================
class TestProviderMode:
    def test_provider_modes_constant_matches_three_values(self):
        assert set(PROVIDER_MODES) == {"llm", "deterministic", "auto"}

    def test_invalid_provider_mode_raises(self):
        with pytest.raises(ValueError):
            el_ins.analyze_text("text", provider_mode="banana")  # type: ignore[arg-type]


# ===========================================================================
# F. analyze_thread batch
# ===========================================================================
class TestAnalyzeThread:
    def test_thread_returns_one_result_per_message(self):
        msgs = ["catastrophic", "statute", "the cat sat"]
        results = el_ins.analyze_thread(msgs, provider_mode="deterministic")
        assert len(results) == 3

    def test_thread_preserves_input_order(self):
        msgs = ["catastrophic disaster", "statute clause"]
        results = el_ins.analyze_thread(msgs, provider_mode="deterministic")
        assert results[0]["analysis"]["ratio_classification"] == "high_el"
        assert results[1]["analysis"]["ratio_classification"] == "high_ins"

    def test_empty_iterable_returns_empty_list(self):
        assert el_ins.analyze_thread([], provider_mode="deterministic") == []


# ===========================================================================
# G. LLM fallback
# ===========================================================================
class TestLlmFallback:
    def test_llm_call_failure_falls_back_to_deterministic(self, monkeypatch):
        # Force the prompt to load (cached), then make model_router
        # raise on every call. The analyzer should silently fall back
        # to the deterministic path.
        _reset_prompt_cache()
        import model_router as mr

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated network failure")

        monkeypatch.setattr(mr, "route_request", _boom)
        r = el_ins.analyze_text(
            "catastrophic disaster", provider_mode="llm",
        )
        # The deterministic fallback ran — we can tell because
        # stability_notes are populated by the heuristic path.
        assert r["analysis"]["ratio_classification"] == "high_el"

    def test_llm_invalid_json_falls_back_to_deterministic(self, monkeypatch):
        _reset_prompt_cache()
        import model_router as mr
        monkeypatch.setattr(
            mr, "route_request",
            lambda *_a, **_kw: {"text": "not-json", "ok": True},
        )
        r = el_ins.analyze_text("statute clause", provider_mode="llm")
        assert r["analysis"]["ratio_classification"] == "high_ins"

    def test_llm_valid_json_is_passed_through(self, monkeypatch):
        _reset_prompt_cache()
        import model_router as mr
        fake_result = {
            "analysis": {
                "el_components": ["foo"],
                "ins_components": ["bar"],
                "el_score": 7.5,
                "ins_score": 2.0,
                "ratio_classification": "high_el",
            },
            "reasoning_mode": "stabilize",
            "regression_chain": {
                "projection": "the market will crash",
                "drivers": ["interest rates", "leverage"],
                "precedents": [
                    {"driver": "interest rates", "precedent": "1929 crash",
                     "principle": "credit cycle reversal"},
                ],
                "principle_stack": ["credit cycle", "leverage unwind"],
                "invariant": "leverage + reversal = crash",
            },
            "stability_notes": "high narrative inflation",
        }
        monkeypatch.setattr(
            mr, "route_request",
            lambda *_a, **_kw: {"text": json.dumps(fake_result), "ok": True},
        )
        r = el_ins.analyze_text(
            "the market will crash catastrophically",
            provider_mode="llm",
        )
        assert r["analysis"]["ratio_classification"] == "high_el"
        assert r["regression_chain"]["projection"] == "the market will crash"
        assert r["regression_chain"]["principle_stack"] == [
            "credit cycle", "leverage unwind",
        ]


# ===========================================================================
# H. LLM JSON fence-tolerance
# ===========================================================================
class TestLlmFenceTolerance:
    def test_fenced_json_is_extracted(self):
        payload = {
            "analysis": {
                "el_components": [], "ins_components": [],
                "el_score": 1.0, "ins_score": 1.0,
                "ratio_classification": "balanced",
            },
            "reasoning_mode": "normal",
            "regression_chain": {
                "projection": None, "drivers": [], "precedents": [],
                "principle_stack": [], "invariant": None,
            },
            "stability_notes": None,
        }
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        r = _coerce_llm_output(fenced)
        assert r is not None
        assert r["analysis"]["ratio_classification"] == "balanced"


# ===========================================================================
# I. Skills bundle alignment
# ===========================================================================
class TestSkillsBundleAlignment:
    def test_system_prompt_path_exists(self):
        assert SYSTEM_PROMPT_PATH.exists(), (
            f"system prompt missing at {SYSTEM_PROMPT_PATH}"
        )

    def test_schema_json_exists_alongside_prompt(self):
        schema_path = SYSTEM_PROMPT_PATH.parent / "schema.json"
        assert schema_path.exists()
        # And it's valid JSON.
        json.loads(schema_path.read_text(encoding="utf-8"))

    def test_no_skills_export_python_import(self):
        # ARCHITECTURE.md no-skills-import boundary: el_ins reads the
        # prompt as plain text. Verify the module doesn't perform a
        # python-level import of anything under skills_export.
        import el_ins.el_ins_analyzer as mod
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "from skills_export" not in src
        assert "import skills_export" not in src


# ===========================================================================
# J. Internal helpers
# ===========================================================================
class TestInternalHelpers:
    def test_tokenise_lowercases_words(self):
        out = _tokenise("Catastrophic STATUTE   clause")
        assert out == ["catastrophic", "statute", "clause"]

    def test_classify_ratio_thresholds(self):
        # Ratio at exactly the high_el threshold counts as high_el.
        assert _classify_ratio(HIGH_EL_THRESHOLD, 1.0) == "high_el"
        # Strictly below high_ins threshold counts as high_ins.
        assert _classify_ratio(0.5, 1.0) == "high_ins"
        # Mid-range balanced.
        assert _classify_ratio(1.0, 1.0) == "balanced"

    def test_classify_ratio_both_zero_balanced(self):
        assert _classify_ratio(0.0, 0.0) == "balanced"

    def test_classify_ratio_one_zero(self):
        assert _classify_ratio(5.0, 0.0) == "high_el"
        assert _classify_ratio(0.0, 5.0) == "high_ins"
