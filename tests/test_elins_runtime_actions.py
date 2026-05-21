"""
Tests for ELINS13 Unit 34 — ELINS runtime actions.

Layered coverage (>= 70 tests, target ~80):
    A. Top-level shape / locked keys
    B. Context passthrough
    C. Decision mapping (base path)
    D. Strict-mode adjustment
    E. Diagnostic mode (pass-through)
    F. Override application
    G. Override + strict interaction
    H. Runtime event vocabulary + order
    I. Escalation rules
    J. Long-arc-specific events
    K. Audit block correctness
    L. Validation — runtime_context
    M. Validation — elins_output
    N. Validation — override
    O. Determinism
    P. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_runtime_actions as rt_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _elins_output(decision: str = "allow",
                   long_arc_assessment: str = "benign",
                   whipsaw: bool = False,
                   tags=None) -> dict:
    """Minimal Unit 33 output shape — only what Unit 34 reads."""
    return {
        "session_id":  "sess_001",
        "operator_id": "op_alice",
        "timestamp":   "2026-05-12T10:00:00+00:00",
        "elins": {
            "structural": {},
            "regime":     {},
            "fusion": {
                "long_arc_assessment": long_arc_assessment,
                "oscillation": {"whipsaw": whipsaw},
            },
            "long_arc": {"decision": decision, "tags": [], "fusion": {}},
        },
        "decision":     decision,
        "tags":         list(tags or []),
        "vault_update": {},
    }


def _runtime_context(session_id: str = "sess_001",
                      operator_id: str = "op_alice",
                      timestamp: str = "2026-05-12T10:00:00+00:00",
                      runtime_mode: str = "normal",
                      previous_actions=None,
                      override=None) -> dict:
    ctx = {
        "session_id":       session_id,
        "operator_id":      operator_id,
        "timestamp":        timestamp,
        "runtime_mode":     runtime_mode,
        "previous_actions": previous_actions or [],
    }
    if override is not None:
        ctx["override"] = override
    return ctx


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp",
            "decision", "runtime_events", "overrides", "audit",
        }

    def test_audit_keys_locked(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        assert set(out["audit"].keys()) == {
            "elins_decision", "runtime_mode", "tags",
            "long_arc_assessment",
        }

    def test_runtime_events_is_list(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        assert isinstance(out["runtime_events"], list)


# ===========================================================================
# B. Context passthrough
# ===========================================================================
class TestContextPassthrough:
    def test_session_id_echoed(self):
        ctx = _runtime_context(session_id="custom_id")
        out = rt_mod.apply_elins_runtime_actions(ctx, _elins_output())
        assert out["session_id"] == "custom_id"

    def test_operator_id_echoed(self):
        ctx = _runtime_context(operator_id="op_charlie")
        out = rt_mod.apply_elins_runtime_actions(ctx, _elins_output())
        assert out["operator_id"] == "op_charlie"

    def test_timestamp_echoed(self):
        ctx = _runtime_context(timestamp="2030-01-01T00:00:00Z")
        out = rt_mod.apply_elins_runtime_actions(ctx, _elins_output())
        assert out["timestamp"] == "2030-01-01T00:00:00Z"


# ===========================================================================
# C. Decision mapping (base path)
# ===========================================================================
class TestDecisionMapping:
    def test_allow_maps_to_runtime_allow(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(decision="allow"),
        )
        assert out["decision"] == "allow"
        assert "runtime_allow" in out["runtime_events"]

    def test_warn_maps_to_runtime_warn(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(decision="warn"),
        )
        assert out["decision"] == "warn"
        assert "runtime_warn" in out["runtime_events"]

    def test_block_maps_to_runtime_block(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(decision="block"),
        )
        assert out["decision"] == "block"
        assert "runtime_block" in out["runtime_events"]

    def test_decision_event_is_first(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(decision="warn"),
        )
        # Decision event is always the first entry in runtime_events.
        assert out["runtime_events"][0] == "runtime_warn"


# ===========================================================================
# D. Strict-mode adjustment
# ===========================================================================
class TestStrictMode:
    def test_strict_allow_becomes_warn(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="strict"),
            _elins_output(decision="allow"),
        )
        assert out["decision"] == "warn"

    def test_strict_warn_becomes_block(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="strict"),
            _elins_output(decision="warn"),
        )
        assert out["decision"] == "block"

    def test_strict_block_stays_block(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="strict"),
            _elins_output(decision="block"),
        )
        assert out["decision"] == "block"

    def test_strict_does_not_mutate_elins_decision_in_audit(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="strict"),
            _elins_output(decision="allow"),
        )
        # The audit always carries the ORIGINAL ELINS decision.
        assert out["audit"]["elins_decision"] == "allow"


# ===========================================================================
# E. Diagnostic mode (pass-through)
# ===========================================================================
class TestDiagnosticMode:
    def test_diagnostic_does_not_adjust_allow(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="diagnostic"),
            _elins_output(decision="allow"),
        )
        assert out["decision"] == "allow"

    def test_diagnostic_does_not_adjust_warn(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="diagnostic"),
            _elins_output(decision="warn"),
        )
        assert out["decision"] == "warn"

    def test_diagnostic_does_not_adjust_block(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="diagnostic"),
            _elins_output(decision="block"),
        )
        assert out["decision"] == "block"

    def test_diagnostic_recorded_in_audit(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="diagnostic"),
            _elins_output(),
        )
        assert out["audit"]["runtime_mode"] == "diagnostic"


# ===========================================================================
# F. Override application
# ===========================================================================
class TestOverride:
    def test_override_decision_replaces_decision(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={"override_decision": "block"}),
            _elins_output(decision="allow"),
        )
        assert out["decision"] == "block"

    def test_override_event_present(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={"override_decision": "warn"}),
            _elins_output(decision="allow"),
        )
        assert "runtime_override" in out["runtime_events"]

    def test_no_override_no_override_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        assert "runtime_override" not in out["runtime_events"]

    def test_override_echoed_in_overrides(self):
        ov = {
            "override_decision": "block",
            "escalate":          True,
            "audit_note":        "Manual operator override.",
        }
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override=ov),
            _elins_output(decision="allow"),
        )
        assert out["overrides"] == ov

    def test_override_escalate_adds_escalate_event(self):
        ov = {"override_decision": "warn", "escalate": True}
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override=ov),
            _elins_output(decision="allow"),
        )
        assert "runtime_escalate" in out["runtime_events"]

    def test_override_escalate_false_no_escalate(self):
        ov = {"override_decision": "warn", "escalate": False}
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override=ov),
            _elins_output(decision="allow"),
        )
        # No other escalation trigger present → no runtime_escalate.
        assert "runtime_escalate" not in out["runtime_events"]

    def test_override_minimal_only_decision_field(self):
        # escalate + audit_note optional.
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={"override_decision": "block"}),
            _elins_output(decision="allow"),
        )
        assert out["decision"] == "block"
        assert out["overrides"] == {"override_decision": "block"}

    def test_empty_overrides_when_no_override(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        assert out["overrides"] == {}


# ===========================================================================
# G. Override + strict interaction
# ===========================================================================
class TestOverrideStrictInteraction:
    def test_override_wins_over_strict_in_allow_direction(self):
        # Strict would adjust allow→warn, but operator overrides to allow.
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(
                runtime_mode="strict",
                override={"override_decision": "allow"},
            ),
            _elins_output(decision="allow"),
        )
        # Override is final → allow wins over the strict adjustment.
        assert out["decision"] == "allow"

    def test_override_wins_over_strict_in_block_direction(self):
        # Strict would adjust allow→warn, operator overrides to block.
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(
                runtime_mode="strict",
                override={"override_decision": "block"},
            ),
            _elins_output(decision="allow"),
        )
        assert out["decision"] == "block"

    def test_audit_still_records_original_elins_decision(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(
                runtime_mode="strict",
                override={"override_decision": "allow"},
            ),
            _elins_output(decision="warn"),
        )
        assert out["audit"]["elins_decision"] == "warn"


# ===========================================================================
# H. Runtime event vocabulary + order
# ===========================================================================
class TestEventVocabulary:
    def test_decision_event_only_when_clean(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(),
        )
        # Benign + non-whipsaw → only the decision event.
        assert out["runtime_events"] == ["runtime_allow"]

    def test_only_locked_events_appear(self):
        valid = {
            "runtime_allow", "runtime_warn", "runtime_block",
            "runtime_escalate", "runtime_override",
            "runtime_long_arc_whipsaw",
            "runtime_long_arc_persistent_risk",
            "runtime_long_arc_persistent_degradation",
        }
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={
                "override_decision": "block", "escalate": True,
            }),
            _elins_output(
                decision="warn",
                long_arc_assessment="persistent_degradation",
                whipsaw=True,
            ),
        )
        for ev in out["runtime_events"]:
            assert ev in valid

    def test_event_order_decision_first(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={
                "override_decision": "block", "escalate": True,
            }),
            _elins_output(
                decision="warn",
                long_arc_assessment="persistent_risk",
                whipsaw=True,
            ),
        )
        assert out["runtime_events"][0] == "runtime_block"

    def test_event_order_override_before_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={
                "override_decision": "block", "escalate": True,
            }),
            _elins_output(decision="warn"),
        )
        idx_override = out["runtime_events"].index("runtime_override")
        idx_escalate = out["runtime_events"].index("runtime_escalate")
        assert idx_override < idx_escalate

    def test_event_order_escalate_before_long_arc(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(
                decision="block",
                long_arc_assessment="persistent_degradation",
                whipsaw=True,
            ),
        )
        idx_escalate = out["runtime_events"].index("runtime_escalate")
        idx_la = out["runtime_events"].index(
            "runtime_long_arc_persistent_degradation",
        )
        assert idx_escalate < idx_la

    def test_each_event_appears_at_most_once(self):
        # Both long_arc escalation AND override escalation could fire.
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(override={
                "override_decision": "block", "escalate": True,
            }),
            _elins_output(
                decision="warn",
                long_arc_assessment="persistent_risk",
                whipsaw=True,
            ),
        )
        # Each event id appears once.
        seen = {}
        for ev in out["runtime_events"]:
            seen[ev] = seen.get(ev, 0) + 1
        for ev, count in seen.items():
            assert count == 1, f"{ev} duplicated"


# ===========================================================================
# I. Escalation rules
# ===========================================================================
class TestEscalation:
    def test_persistent_risk_triggers_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="persistent_risk"),
        )
        assert "runtime_escalate" in out["runtime_events"]

    def test_persistent_degradation_triggers_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="persistent_degradation"),
        )
        assert "runtime_escalate" in out["runtime_events"]

    def test_oscillating_regime_plus_whipsaw_triggers_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(
                long_arc_assessment="oscillating_regime",
                whipsaw=True,
            ),
        )
        assert "runtime_escalate" in out["runtime_events"]

    def test_oscillating_regime_without_whipsaw_no_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(
                long_arc_assessment="oscillating_regime",
                whipsaw=False,
            ),
        )
        assert "runtime_escalate" not in out["runtime_events"]

    def test_benign_no_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="benign"),
        )
        assert "runtime_escalate" not in out["runtime_events"]

    def test_stabilizing_no_escalate(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="stabilizing"),
        )
        assert "runtime_escalate" not in out["runtime_events"]


# ===========================================================================
# J. Long-arc-specific events
# ===========================================================================
class TestLongArcEvents:
    def test_whipsaw_emits_la_whipsaw_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(whipsaw=True),
        )
        assert "runtime_long_arc_whipsaw" in out["runtime_events"]

    def test_no_whipsaw_no_la_whipsaw_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(whipsaw=False),
        )
        assert "runtime_long_arc_whipsaw" not in out["runtime_events"]

    def test_persistent_risk_emits_la_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="persistent_risk"),
        )
        assert "runtime_long_arc_persistent_risk" in out["runtime_events"]

    def test_persistent_degradation_emits_la_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="persistent_degradation"),
        )
        assert "runtime_long_arc_persistent_degradation" in \
               out["runtime_events"]

    def test_benign_emits_no_la_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="benign"),
        )
        la_events = [
            e for e in out["runtime_events"] if e.startswith(
                "runtime_long_arc_",
            )
        ]
        assert la_events == []

    def test_stabilizing_emits_no_la_event(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="stabilizing"),
        )
        la_events = [
            e for e in out["runtime_events"] if e.startswith(
                "runtime_long_arc_",
            )
        ]
        assert la_events == []


# ===========================================================================
# K. Audit block correctness
# ===========================================================================
class TestAudit:
    def test_elins_decision_recorded(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(), _elins_output(decision="warn"),
        )
        assert out["audit"]["elins_decision"] == "warn"

    def test_runtime_mode_recorded(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(runtime_mode="strict"),
            _elins_output(),
        )
        assert out["audit"]["runtime_mode"] == "strict"

    def test_tags_recorded(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(tags=["long_arc_persistent_risk", "risk_high"]),
        )
        assert "long_arc_persistent_risk" in out["audit"]["tags"]
        assert "risk_high" in out["audit"]["tags"]

    def test_long_arc_assessment_recorded(self):
        out = rt_mod.apply_elins_runtime_actions(
            _runtime_context(),
            _elins_output(long_arc_assessment="persistent_degradation"),
        )
        assert out["audit"]["long_arc_assessment"] == \
               "persistent_degradation"


# ===========================================================================
# L. Validation — runtime_context
# ===========================================================================
class TestRuntimeContextValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="runtime_context"):
            rt_mod.apply_elins_runtime_actions("nope", _elins_output())

    def test_missing_session_id_raises(self):
        bad = _runtime_context()
        del bad["session_id"]
        with pytest.raises(ValueError, match="session_id"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_missing_runtime_mode_raises(self):
        bad = _runtime_context()
        del bad["runtime_mode"]
        with pytest.raises(ValueError, match="runtime_mode"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_invalid_runtime_mode_raises(self):
        bad = _runtime_context(runtime_mode="superstrict")
        with pytest.raises(ValueError, match="runtime_mode"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_empty_session_id_raises(self):
        bad = _runtime_context(session_id="")
        with pytest.raises(ValueError, match="session_id"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_non_string_timestamp_raises(self):
        bad = _runtime_context()
        bad["timestamp"] = 123456789
        with pytest.raises(ValueError, match="timestamp"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_non_list_previous_actions_raises(self):
        bad = _runtime_context()
        bad["previous_actions"] = "nope"
        with pytest.raises(ValueError, match="previous_actions"):
            rt_mod.apply_elins_runtime_actions(bad, _elins_output())

    def test_none_previous_actions_ok(self):
        bad = _runtime_context()
        bad["previous_actions"] = None
        out = rt_mod.apply_elins_runtime_actions(bad, _elins_output())
        assert "decision" in out


# ===========================================================================
# M. Validation — elins_output
# ===========================================================================
class TestElinsOutputValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="elins_output"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), "nope")

    def test_missing_decision_raises(self):
        bad = _elins_output()
        del bad["decision"]
        with pytest.raises(ValueError, match="decision"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)

    def test_invalid_decision_raises(self):
        bad = _elins_output()
        bad["decision"] = "maybe"
        with pytest.raises(ValueError, match="decision"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)

    def test_missing_elins_block_raises(self):
        bad = _elins_output()
        del bad["elins"]
        with pytest.raises(ValueError, match="elins"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)

    def test_missing_fusion_raises(self):
        bad = _elins_output()
        del bad["elins"]["fusion"]
        with pytest.raises(ValueError, match="fusion"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)

    def test_missing_long_arc_assessment_raises(self):
        bad = _elins_output()
        del bad["elins"]["fusion"]["long_arc_assessment"]
        with pytest.raises(ValueError, match="long_arc_assessment"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)

    def test_missing_whipsaw_raises(self):
        bad = _elins_output()
        del bad["elins"]["fusion"]["oscillation"]
        with pytest.raises(ValueError, match="whipsaw"):
            rt_mod.apply_elins_runtime_actions(_runtime_context(), bad)


# ===========================================================================
# N. Validation — override
# ===========================================================================
class TestOverrideValidation:
    def test_non_dict_override_raises(self):
        ctx = _runtime_context()
        ctx["override"] = "nope"
        with pytest.raises(ValueError, match="override"):
            rt_mod.apply_elins_runtime_actions(ctx, _elins_output())

    def test_missing_override_decision_raises(self):
        ctx = _runtime_context(override={"escalate": True})
        with pytest.raises(ValueError, match="override_decision"):
            rt_mod.apply_elins_runtime_actions(ctx, _elins_output())

    def test_invalid_override_decision_raises(self):
        ctx = _runtime_context(override={"override_decision": "maybe"})
        with pytest.raises(ValueError, match="override_decision"):
            rt_mod.apply_elins_runtime_actions(ctx, _elins_output())

    def test_non_bool_escalate_raises(self):
        ctx = _runtime_context(override={
            "override_decision": "warn", "escalate": "yes",
        })
        with pytest.raises(ValueError, match="escalate"):
            rt_mod.apply_elins_runtime_actions(ctx, _elins_output())

    def test_non_string_audit_note_raises(self):
        ctx = _runtime_context(override={
            "override_decision": "warn", "audit_note": 42,
        })
        with pytest.raises(ValueError, match="audit_note"):
            rt_mod.apply_elins_runtime_actions(ctx, _elins_output())


# ===========================================================================
# O. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        ctx = _runtime_context()
        eo = _elins_output()
        a = rt_mod.apply_elins_runtime_actions(ctx, eo)
        b = rt_mod.apply_elins_runtime_actions(ctx, eo)
        assert a == b

    def test_byte_equal_with_overrides_and_escalation(self):
        ctx = _runtime_context(override={
            "override_decision": "block", "escalate": True,
            "audit_note": "manual escalation",
        })
        eo = _elins_output(
            decision="warn",
            long_arc_assessment="persistent_risk",
            whipsaw=True,
        )
        a = rt_mod.apply_elins_runtime_actions(ctx, eo)
        b = rt_mod.apply_elins_runtime_actions(ctx, eo)
        assert a == b

    def test_input_dicts_not_mutated(self):
        ctx = _runtime_context()
        eo = _elins_output()
        ctx_snapshot = dict(ctx)
        eo_snapshot = dict(eo)
        rt_mod.apply_elins_runtime_actions(ctx, eo)
        assert ctx == ctx_snapshot
        assert eo == eo_snapshot


# ===========================================================================
# P. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(rt_mod.apply_elins_runtime_actions)

    def test_event_vocabulary_locked(self):
        assert rt_mod.EVENT_RUNTIME_ALLOW    == "runtime_allow"
        assert rt_mod.EVENT_RUNTIME_WARN     == "runtime_warn"
        assert rt_mod.EVENT_RUNTIME_BLOCK    == "runtime_block"
        assert rt_mod.EVENT_RUNTIME_ESCALATE == "runtime_escalate"
        assert rt_mod.EVENT_RUNTIME_OVERRIDE == "runtime_override"
        assert rt_mod.EVENT_RUNTIME_LA_WHIPSAW == \
               "runtime_long_arc_whipsaw"
        assert rt_mod.EVENT_RUNTIME_LA_PERSISTENT_RISK == \
               "runtime_long_arc_persistent_risk"
        assert rt_mod.EVENT_RUNTIME_LA_PERSISTENT_DEGRADATION == \
               "runtime_long_arc_persistent_degradation"

    def test_runtime_modes_locked(self):
        assert rt_mod._VALID_RUNTIME_MODES == (
            "normal", "strict", "diagnostic",
        )

    def test_strict_adjustment_locked(self):
        assert rt_mod._STRICT_ADJUSTMENT == {
            "allow": "warn", "warn": "block", "block": "block",
        }


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(rt_mod)

    def _code_only(self) -> str:
        import re as _re
        src = self._src()
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_persistence_imports(self):
        # Unit 34 is the final bridge — must not touch persistence
        # or vault storage. RuntimeKernel owns those.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result", "vault_store", "memory_vault",
        ):
            assert forbidden not in src
