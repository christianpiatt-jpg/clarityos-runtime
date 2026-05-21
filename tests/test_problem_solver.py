"""
Tests for V76 / ProblemSolver.REGRESSION_FIRST kernel (rewritten from
V75 in the kernel-realignment pass).

Covers:
    A. start_chain — happy path + envelope + uuid + ms timestamps
    B. record_finding — auto-grow layers + overwrite + sort + validation
    C. close_chain — irreversibility + notes override
    D. tag_chain — merge semantics + validation + caps
    E. get_chain / list_chains — newest-first + reset hook
    F. analyze_packet — packet parsing + chain build via start_chain
    G. Auto-trigger detection (auto_trigger.py)
    H. Skills bundle alignment + no-import boundary
    I. Canonical example from system_prompt.md
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Optional

import pytest

import problem_solver as ps
from problem_solver.regression_first import (
    CLASSIFICATIONS,
    LAYER_STATUSES,
    LAYER_NOTES_MAX,
    NOTES_MAX,
    PROTOCOL_NAME,
    SYSTEM_PROMPT_PATH,
    TAGS_PER_CHAIN_MAX,
    TAG_KEY_MAX,
    TAG_VALUE_MAX,
    TITLE_MAX,
    _extract_packet_dict,
    _make_chain_id,
    _reset_for_tests,
    _reset_prompt_cache,
    analyze_packet,
)
from problem_solver.auto_trigger import (
    CUE_PHRASES,
    CUE_WORDS,
    _has_cue,
    extract_problem,
    should_auto_trigger,
)


@pytest.fixture(autouse=True)
def _clean_state():
    _reset_for_tests()
    yield
    _reset_for_tests()


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ===========================================================================
# A. start_chain
# ===========================================================================
class TestStartChain:
    def test_happy_path_envelope(self):
        c = ps.start_chain("Production deploy stalled")
        assert set(c.keys()) == {
            "chain_id", "created_at", "closed_at",
            "title", "notes", "layers", "tags",
            "archived",   # v81 — visibility flag, defaults to False
        }
        assert c["title"] == "Production deploy stalled"
        assert c["notes"] is None
        assert c["layers"] == []
        assert c["tags"] == {}
        assert c["closed_at"] is None
        assert c["archived"] is False
        assert _UUID_RE.match(c["chain_id"])
        assert isinstance(c["created_at"], int) and c["created_at"] > 0

    def test_notes_optional(self):
        c = ps.start_chain(
            "Deploy stalled", notes="auth handshake hanging at step 3",
        )
        assert c["notes"] == "auth handshake hanging at step 3"

    def test_whitespace_notes_normalises_to_none(self):
        c = ps.start_chain("Deploy stalled", notes="   \n  ")
        assert c["notes"] is None

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            ps.start_chain("")
        with pytest.raises(ValueError):
            ps.start_chain("   ")

    def test_oversized_title_rejected(self):
        with pytest.raises(ValueError):
            ps.start_chain("x" * (TITLE_MAX + 1))

    def test_oversized_notes_rejected(self):
        with pytest.raises(ValueError):
            ps.start_chain("ok", notes="x" * (NOTES_MAX + 1))

    def test_non_string_notes_rejected(self):
        with pytest.raises(ValueError):
            ps.start_chain("ok", notes=42)  # type: ignore[arg-type]

    def test_chain_ids_are_unique(self):
        ids = {ps.start_chain(f"chain {i}")["chain_id"] for i in range(10)}
        assert len(ids) == 10

    def test_chain_persisted_in_store(self):
        c = ps.start_chain("x")
        assert ps.get_chain(c["chain_id"]) is c


# ===========================================================================
# B. record_finding
# ===========================================================================
class TestRecordFinding:
    def test_layer_auto_appends(self):
        c = ps.start_chain("x")
        out = ps.record_finding(c["chain_id"], 0, "ok", "looks good")
        assert len(out["layers"]) == 1
        layer = out["layers"][0]
        assert layer["layer_index"] == 0
        assert layer["status"] == "ok"
        assert layer["notes"] == "looks good"
        assert isinstance(layer["updated_at"], int)
        assert layer["updated_at"] > 0

    def test_status_overwrite_updates_in_place(self):
        c = ps.start_chain("x")
        ps.record_finding(c["chain_id"], 0, "unknown", "haven't checked")
        out = ps.record_finding(c["chain_id"], 0, "issue", "found the bug")
        assert len(out["layers"]) == 1
        assert out["layers"][0]["status"] == "issue"
        assert out["layers"][0]["notes"] == "found the bug"

    def test_layers_sorted_by_index(self):
        c = ps.start_chain("x")
        ps.record_finding(c["chain_id"], 3, "ok", "three")
        ps.record_finding(c["chain_id"], 0, "ok", "zero")
        ps.record_finding(c["chain_id"], 2, "issue", "two")
        out = ps.record_finding(c["chain_id"], 1, "blocked", "one")
        assert [L["layer_index"] for L in out["layers"]] == [0, 1, 2, 3]

    def test_all_four_statuses_valid(self):
        c = ps.start_chain("x")
        for i, s in enumerate(LAYER_STATUSES):
            out = ps.record_finding(c["chain_id"], i, s, f"layer {i}")
            assert out["layers"][i]["status"] == s

    def test_notes_optional(self):
        c = ps.start_chain("x")
        out = ps.record_finding(c["chain_id"], 0, "ok")
        assert out["layers"][0]["notes"] is None
        out = ps.record_finding(c["chain_id"], 1, "ok", None)
        assert out["layers"][1]["notes"] is None

    def test_whitespace_notes_normalises_to_none(self):
        c = ps.start_chain("x")
        out = ps.record_finding(c["chain_id"], 0, "ok", "   ")
        assert out["layers"][0]["notes"] is None

    def test_invalid_status_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.record_finding(c["chain_id"], 0, "verified", "x")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            ps.record_finding(c["chain_id"], 0, "GREEN", "x")  # type: ignore[arg-type]

    def test_negative_layer_index_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.record_finding(c["chain_id"], -1, "ok", "x")

    def test_non_int_layer_index_rejected(self):
        c = ps.start_chain("x")
        for bad in (1.5, "0", None, True):
            with pytest.raises(ValueError):
                ps.record_finding(c["chain_id"], bad, "ok", "x")  # type: ignore[arg-type]

    def test_unknown_chain_raises_keyerror(self):
        with pytest.raises(KeyError):
            ps.record_finding("does-not-exist", 0, "ok", "x")

    def test_closed_chain_rejects_findings(self):
        c = ps.start_chain("x")
        ps.record_finding(c["chain_id"], 0, "ok", "first")
        ps.close_chain(c["chain_id"])
        with pytest.raises(ValueError) as exc:
            ps.record_finding(c["chain_id"], 1, "ok", "after close")
        assert "closed" in str(exc.value)

    def test_oversized_notes_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.record_finding(
                c["chain_id"], 0, "ok", "x" * (LAYER_NOTES_MAX + 1),
            )


# ===========================================================================
# C. close_chain
# ===========================================================================
class TestCloseChain:
    def test_close_sets_closed_at(self):
        c = ps.start_chain("x")
        assert c["closed_at"] is None
        out = ps.close_chain(c["chain_id"])
        assert isinstance(out["closed_at"], int)
        assert out["closed_at"] >= c["created_at"]

    def test_close_optional_notes_overwrites_top_level(self):
        c = ps.start_chain("x", notes="initial")
        out = ps.close_chain(c["chain_id"], notes="final summary")
        assert out["notes"] == "final summary"

    def test_close_without_notes_preserves_initial(self):
        c = ps.start_chain("x", notes="initial")
        out = ps.close_chain(c["chain_id"])
        assert out["notes"] == "initial"

    def test_close_whitespace_notes_normalises_to_none(self):
        c = ps.start_chain("x", notes="initial")
        out = ps.close_chain(c["chain_id"], notes="   ")
        assert out["notes"] is None

    def test_close_oversized_notes_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.close_chain(c["chain_id"], notes="x" * (NOTES_MAX + 1))

    def test_close_idempotency_blocked(self):
        c = ps.start_chain("x")
        ps.close_chain(c["chain_id"])
        with pytest.raises(ValueError) as exc:
            ps.close_chain(c["chain_id"])
        assert "already closed" in str(exc.value)

    def test_unknown_chain_raises_keyerror(self):
        with pytest.raises(KeyError):
            ps.close_chain("does-not-exist")


# ===========================================================================
# D. tag_chain
# ===========================================================================
class TestTagChain:
    def test_merge_into_empty_tags(self):
        c = ps.start_chain("x")
        out = ps.tag_chain(c["chain_id"], {
            "area": "wordpress", "severity": "high",
        })
        assert out["tags"] == {"area": "wordpress", "severity": "high"}

    def test_overwrite_existing_key(self):
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"severity": "low"})
        out = ps.tag_chain(c["chain_id"], {"severity": "high"})
        assert out["tags"]["severity"] == "high"

    def test_preserves_keys_not_in_request(self):
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp", "severity": "high"})
        out = ps.tag_chain(c["chain_id"], {"severity": "low"})
        assert out["tags"] == {"area": "wp", "severity": "low"}

    def test_empty_dict_is_noop(self):
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp"})
        out = ps.tag_chain(c["chain_id"], {})
        assert out["tags"] == {"area": "wp"}

    def test_non_dict_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], [("k", "v")])  # type: ignore[arg-type]

    def test_non_string_key_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {42: "v"})  # type: ignore[dict-item]

    def test_non_string_value_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {"k": 42})  # type: ignore[dict-item]

    def test_empty_key_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {"   ": "v"})

    def test_oversized_key_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {"x" * (TAG_KEY_MAX + 1): "v"})

    def test_oversized_value_rejected(self):
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {"k": "x" * (TAG_VALUE_MAX + 1)})

    def test_too_many_tags_rejected(self):
        c = ps.start_chain("x")
        ok_tags = {f"k{i}": "v" for i in range(TAGS_PER_CHAIN_MAX)}
        ps.tag_chain(c["chain_id"], ok_tags)
        with pytest.raises(ValueError) as exc:
            ps.tag_chain(c["chain_id"], {"overflow": "v"})
        assert "exceed" in str(exc.value)

    def test_failed_tag_leaves_state_intact(self):
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp"})
        # Mixed valid + invalid in one batch — should fail atomically.
        with pytest.raises(ValueError):
            ps.tag_chain(c["chain_id"], {
                "severity": "high",
                "x" * (TAG_KEY_MAX + 1): "bad",
            })
        # severity was NOT added because validation aborted before
        # mutation.
        assert ps.get_chain(c["chain_id"])["tags"] == {"area": "wp"}

    def test_closed_chain_rejects_tags(self):
        c = ps.start_chain("x")
        ps.close_chain(c["chain_id"])
        with pytest.raises(ValueError) as exc:
            ps.tag_chain(c["chain_id"], {"area": "wp"})
        assert "closed" in str(exc.value)

    def test_unknown_chain_raises_keyerror(self):
        with pytest.raises(KeyError):
            ps.tag_chain("does-not-exist", {"area": "wp"})


# ===========================================================================
# E. get_chain / list_chains / store
# ===========================================================================
class TestStore:
    def test_get_unknown_raises_keyerror(self):
        with pytest.raises(KeyError):
            ps.get_chain("does-not-exist")

    def test_list_empty(self):
        assert ps.list_chains() == []

    def test_list_newest_first(self):
        a = ps.start_chain("first")
        b = ps.start_chain("second")
        c = ps.start_chain("third")
        ids = [x["chain_id"] for x in ps.list_chains()]
        assert ids == [c["chain_id"], b["chain_id"], a["chain_id"]]

    def test_list_includes_closed_chains(self):
        a = ps.start_chain("open")
        b = ps.start_chain("closed")
        ps.close_chain(b["chain_id"])
        ids = [x["chain_id"] for x in ps.list_chains()]
        assert set(ids) == {a["chain_id"], b["chain_id"]}

    def test_reset_for_tests_clears_state(self):
        ps.start_chain("x")
        assert len(ps.list_chains()) == 1
        _reset_for_tests()
        assert ps.list_chains() == []

    def test_layer_statuses_constant_matches(self):
        assert set(LAYER_STATUSES) == {"ok", "issue", "blocked", "unknown"}

    def test_classifications_constant_matches(self):
        assert set(CLASSIFICATIONS) == {
            "emotion-dominant", "balanced", "structure-dominant",
        }

    def test_protocol_name_locked(self):
        assert PROTOCOL_NAME == "ProblemSolver.REGRESSION_FIRST"

    def test_make_chain_id_is_canonical_uuid(self):
        for _ in range(5):
            cid = _make_chain_id()
            # Parses as a UUID, and is the canonical str form.
            assert str(uuid.UUID(cid)) == cid


# ===========================================================================
# F. analyze_packet
# ===========================================================================
def _canonical_packet(
    *,
    regression_required: bool = True,
    layers: Optional[list[dict]] = None,
    operator_intent: str = "Identify root cause of rendering failure.",
) -> dict:
    """Build a canonical unified packet (matches schema.json + the
    example block in system_prompt.md). Layers carry 'location' (this
    is the bundle's emitted shape, separate from the kernel's stored
    layers which are operator-driven)."""
    if layers is None:
        layers = [
            {
                "layer": 1, "name": "Domain & Routing",
                "question": "Which page is set as homepage?",
                "location": "Settings → Reading → Homepage",
                "goal": "Correct page selected",
            },
            {
                "layer": 2, "name": "Template Layer",
                "question": "Which template renders this page?",
                "location": "WP theme template hierarchy",
                "goal": "Expected template is bound",
            },
        ]
    return {
        "EL": 2,
        "INS": 3,
        "ratio": "0.67",
        "el_signals": ["something is wrong"],
        "ins_signals": ["page", "scaffold"],
        "classification": "structure-dominant",
        "operator_intent": operator_intent,
        "regression_required": regression_required,
        "regression_chain": layers if regression_required else [],
        "recommended_system_action": (
            "Pause and request operator verification."
            if regression_required else "Proceed normally."
        ),
    }


class TestExtractPacketDict:
    def test_passthrough(self):
        assert _extract_packet_dict({"x": 1}) == {"x": 1}

    def test_strips_fence(self):
        s = "```json\n" + json.dumps({"x": 1}) + "\n```"
        assert _extract_packet_dict(s) == {"x": 1}

    def test_invalid_returns_none(self):
        assert _extract_packet_dict("not-json") is None
        assert _extract_packet_dict(42) is None  # type: ignore[arg-type]


class TestAnalyzePacket:
    def test_happy_path_returns_packet_and_chain(self):
        p = analyze_packet(_canonical_packet(), title="WP scaffold issue")
        assert p is not None
        assert p["EL"] == 2
        assert p["INS"] == 3
        assert p["ratio"] == "0.67"
        assert p["classification"] == "structure-dominant"
        assert p["regression_required"] is True
        assert p["chain"] is not None
        assert p["chain"]["title"] == "WP scaffold issue"
        # Chain is empty by design — operator drives layer creation
        # via /step. Skeleton from packet is informational only.
        assert p["chain"]["layers"] == []
        # Persisted in the store.
        assert ps.get_chain(p["chain"]["chain_id"]) is p["chain"]

    def test_no_problem_no_chain(self):
        p = analyze_packet(_canonical_packet(regression_required=False))
        assert p is not None
        assert p["regression_required"] is False
        assert p["chain"] is None
        assert ps.list_chains() == []

    def test_build_chain_false_skips_persistence(self):
        p = analyze_packet(
            _canonical_packet(), title="x", build_chain=False,
        )
        assert p is not None
        assert p["chain"] is None
        assert ps.list_chains() == []

    def test_title_defaults_to_operator_intent(self):
        p = analyze_packet(_canonical_packet())
        assert p is not None
        assert p["chain"] is not None
        assert p["chain"]["title"] == (
            "Identify root cause of rendering failure."
        )

    def test_oversized_intent_title_is_truncated(self):
        long_intent = "x" * (TITLE_MAX + 50)
        p = analyze_packet(_canonical_packet(operator_intent=long_intent))
        assert p is not None
        assert p["chain"] is not None
        assert len(p["chain"]["title"]) <= TITLE_MAX

    def test_invalid_scores_returns_none(self):
        for bad in (-1, 6, 99, "two"):
            packet = _canonical_packet()
            packet["EL"] = bad  # type: ignore[assignment]
            assert analyze_packet(packet) is None

    def test_invalid_classification_returns_none(self):
        packet = _canonical_packet()
        packet["classification"] = "high_el"  # wrong vocabulary
        assert analyze_packet(packet) is None

    def test_missing_required_field_returns_none(self):
        required = (
            "EL", "INS", "ratio", "classification",
            "operator_intent", "regression_required",
            "regression_chain", "recommended_system_action",
        )
        for missing in required:
            packet = _canonical_packet()
            del packet[missing]
            assert analyze_packet(packet) is None, (
                f"analyze_packet should fail when {missing!r} missing"
            )

    def test_fenced_json_parses(self):
        fenced = "```json\n" + json.dumps(_canonical_packet()) + "\n```"
        p = analyze_packet(fenced, title="x")
        assert p is not None
        assert p["chain"] is not None

    def test_signals_coerced_to_strings(self):
        packet = _canonical_packet()
        packet["el_signals"] = ["a", "b", 3]
        p = analyze_packet(packet, title="x", build_chain=False)
        assert p is not None
        assert p["el_signals"] == ["a", "b", "3"]

    def test_regression_chain_must_be_list(self):
        packet = _canonical_packet()
        packet["regression_chain"] = "not a list"  # type: ignore[assignment]
        assert analyze_packet(packet) is None


# ===========================================================================
# G. Auto-trigger
# ===========================================================================
class TestAutoTrigger:
    def test_obvious_problem_triggers(self):
        assert should_auto_trigger("the cockpit is broken")

    def test_cue_phrase_triggers(self):
        assert should_auto_trigger("the export doesn't work today")

    def test_calm_text_does_not_trigger(self):
        assert not should_auto_trigger("good morning, how is the weather")

    def test_empty_text_does_not_trigger(self):
        assert not should_auto_trigger("")
        assert not should_auto_trigger("   ")

    def test_with_el_ins_high_el_and_cue_triggers(self):
        result = {"analysis": {"ratio_classification": "high_el"}}
        assert should_auto_trigger(
            "absolutely broken catastrophic disaster",
            el_ins_result=result,
        )

    def test_with_el_ins_balanced_does_not_trigger_even_with_cue(self):
        result = {"analysis": {"ratio_classification": "balanced"}}
        assert not should_auto_trigger(
            "the export is broken", el_ins_result=result,
        )

    def test_with_el_ins_high_el_but_no_cue_does_not_trigger(self):
        result = {"analysis": {"ratio_classification": "high_el"}}
        assert not should_auto_trigger(
            "absolutely catastrophic stunning unprecedented",
            el_ins_result=result,
        )

    def test_has_cue_words(self):
        for w in ("bug", "broken", "error", "crash", "failure"):
            assert _has_cue(f"there is a {w} here")

    def test_has_cue_phrases(self):
        for p in CUE_PHRASES:
            assert _has_cue(f"the thing {p} for sure")

    def test_cue_words_constant_lowercased(self):
        for w in CUE_WORDS:
            assert w == w.lower()
            assert " " not in w

    def test_extract_problem_collapses_whitespace(self):
        assert extract_problem(
            "   the   thing\nis\tbroken   ",
        ) == "the thing is broken"

    def test_extract_problem_empty_yields_empty(self):
        assert extract_problem("") == ""
        assert extract_problem("   ") == ""


# ===========================================================================
# H. Skills bundle alignment
# ===========================================================================
class TestSkillsBundleAlignment:
    def test_system_prompt_path_exists(self):
        assert SYSTEM_PROMPT_PATH.exists(), (
            f"system prompt missing at {SYSTEM_PROMPT_PATH}"
        )

    def test_schema_json_exists_alongside_prompt(self):
        schema_path = SYSTEM_PROMPT_PATH.parent / "schema.json"
        assert schema_path.exists()
        json.loads(schema_path.read_text(encoding="utf-8"))

    def test_readme_exists(self):
        assert (SYSTEM_PROMPT_PATH.parent / "README.md").exists()

    def test_no_skills_export_python_import(self):
        # ARCHITECTURE.md no-skills-import boundary: problem_solver
        # reads the prompt as plain text. Verify the module doesn't
        # perform a python-level import of anything under skills_export.
        for mod_path in (
            "problem_solver/regression_first.py",
            "problem_solver/auto_trigger.py",
            "problem_solver/__init__.py",
        ):
            src = (
                SYSTEM_PROMPT_PATH.parent.parent.parent / mod_path
            ).read_text(encoding="utf-8")
            assert "from skills_export" not in src, (
                f"{mod_path} must not python-import from skills_export"
            )
            assert "import skills_export" not in src, (
                f"{mod_path} must not python-import from skills_export"
            )

    def test_schema_describes_unified_packet(self):
        """The bundle schema is the EMITTED packet shape (EL/INS +
        regression_chain skeleton). The kernel's stored chain has a
        different shape (chain_id / created_at / closed_at / title /
        layers / tags). Locked here."""
        schema_path = SYSTEM_PROMPT_PATH.parent / "schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # Packet-required keys live on the emitted shape.
        for key in (
            "EL", "INS", "ratio", "classification",
            "operator_intent", "regression_required",
            "regression_chain", "recommended_system_action",
        ):
            assert key in schema["properties"], (
                f"emitted-packet schema missing {key!r}"
            )
        # The stored chain DOES NOT use those keys.
        c = ps.start_chain("x")
        for key in ("EL", "INS", "regression_required"):
            assert key not in c

    def test_packet_layer_schema_uses_location(self):
        schema_path = SYSTEM_PROMPT_PATH.parent / "schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        layer_schema = schema["properties"]["regression_chain"]["items"]
        assert "location" in layer_schema["properties"]
        # Stored chain layers use 'layer_index' instead.
        ps.record_finding(ps.start_chain("x")["chain_id"], 0, "ok", "y")
        chain = ps.list_chains()[0]
        assert "layer_index" in chain["layers"][0]
        assert "location" not in chain["layers"][0]


# ===========================================================================
# I. Canonical example from system_prompt.md
# ===========================================================================
class TestCanonicalExample:
    def test_prompt_example_block_parses(self):
        """Lock the canonical example from system_prompt.md against
        the kernel — proves the documented example is ingestable."""
        prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        fence = "```json"
        blocks: list[str] = []
        idx = 0
        while True:
            start = prompt.find(fence, idx)
            if start < 0:
                break
            body_start = start + len(fence)
            end = prompt.find("```", body_start)
            if end < 0:
                break
            blocks.append(prompt[body_start:end].strip())
            idx = end + 3
        assert len(blocks) >= 2, (
            f"system_prompt.md must contain >=2 ```json blocks; "
            f"found {len(blocks)}"
        )
        # The second block is the EXAMPLE (the first is the format
        # template with placeholders).
        example = json.loads(blocks[1])
        p = analyze_packet(example)
        assert p is not None
        assert p["regression_required"] is True
        assert p["chain"] is not None
        assert p["chain"]["title"].startswith("Identify")
