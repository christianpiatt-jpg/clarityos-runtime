"""
Tests for Unit 37 — runtime continuity reentry.

Layered coverage (target ~40 tests):
    A. Top-level shape / locked keys
    B. Cold-start handling (None / empty / no elins)
    C. ELINS continuity extraction (last_fusion / last_long_arc / fusion_history)
    D. Runtime mode resolution + default
    E. Timestamp resolution precedence
    F. Validation — session_id
    G. Validation — operator_id
    H. Validation — vault_state
    I. Determinism + immutability
    J. JSON-safety
    K. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest

import runtime_continuity as rc_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _last_fusion(timestamp: str = "2026-05-12T10:00:00+00:00") -> dict:
    return {
        "timestamp":            timestamp,
        "long_arc_assessment":  "benign",
        "cumulative_risk":      {"risk_level": "low"},
        "trajectory":           {"start_regime": "stable", "end_regime": "stable"},
    }


def _last_long_arc(timestamp: str = "2026-05-12T09:00:00+00:00") -> dict:
    return {
        "timestamp":            timestamp,
        "long_arc_assessment":  "benign",
        "consecutive":          {"persistent_risk": 0, "persistent_degradation": 0},
        "whipsaw":              False,
    }


def _vault_state(
    last_fusion=None,
    last_long_arc=None,
    fusion_history=None,
    runtime_mode=None,
) -> dict:
    elins = {}
    if last_fusion is not None:
        elins["last_fusion"] = last_fusion
    if last_long_arc is not None:
        elins["last_long_arc"] = last_long_arc
    if fusion_history is not None:
        elins["fusion_history"] = fusion_history
    out = {"elins": elins}
    if runtime_mode is not None:
        out["runtime_mode"] = runtime_mode
    return out


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked_cold_start(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp", "continuity",
        }

    def test_keys_locked_warm(self):
        vs = _vault_state(last_fusion=_last_fusion())
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert set(out.keys()) == {
            "session_id", "operator_id", "timestamp", "continuity",
        }

    def test_continuity_keys_locked(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert set(out["continuity"].keys()) == {"elins", "runtime_mode"}

    def test_continuity_elins_keys_locked(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert set(out["continuity"]["elins"].keys()) == {
            "last_fusion", "last_long_arc", "fusion_history",
        }


# ===========================================================================
# B. Cold-start handling
# ===========================================================================
class TestColdStart:
    def test_none_vault_state(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert out["continuity"]["elins"]["last_fusion"] is None
        assert out["continuity"]["elins"]["last_long_arc"] is None
        assert out["continuity"]["elins"]["fusion_history"] == []

    def test_empty_dict_vault_state(self):
        out = rc_mod.resume_runtime_session("s1", "op1", {})
        assert out["continuity"]["elins"]["last_fusion"] is None
        assert out["continuity"]["elins"]["last_long_arc"] is None
        assert out["continuity"]["elins"]["fusion_history"] == []

    def test_vault_state_without_elins(self):
        out = rc_mod.resume_runtime_session("s1", "op1", {"other": 1})
        assert out["continuity"]["elins"]["last_fusion"] is None
        assert out["continuity"]["elins"]["fusion_history"] == []

    def test_elins_is_not_a_dict(self):
        out = rc_mod.resume_runtime_session(
            "s1", "op1", {"elins": "not a dict"},
        )
        assert out["continuity"]["elins"]["last_fusion"] is None
        assert out["continuity"]["elins"]["fusion_history"] == []

    def test_cold_start_timestamp_empty(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert out["timestamp"] == ""

    def test_cold_start_runtime_mode_normal(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        assert out["continuity"]["runtime_mode"] == "normal"


# ===========================================================================
# C. ELINS continuity extraction
# ===========================================================================
class TestElinsContinuity:
    def test_last_fusion_passthrough(self):
        lf = _last_fusion()
        vs = _vault_state(last_fusion=lf)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["last_fusion"] == lf

    def test_last_long_arc_passthrough(self):
        lla = _last_long_arc()
        vs = _vault_state(last_long_arc=lla)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["last_long_arc"] == lla

    def test_fusion_history_passthrough(self):
        hist = [{"a": 1}, {"a": 2}, {"a": 3}]
        vs = _vault_state(fusion_history=hist)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["fusion_history"] == hist

    def test_fusion_history_is_copied(self):
        hist = [{"a": 1}]
        vs = _vault_state(fusion_history=hist)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        out["continuity"]["elins"]["fusion_history"].append({"a": 2})
        # Original list untouched.
        assert hist == [{"a": 1}]

    def test_malformed_last_fusion_treated_as_none(self):
        vs = {"elins": {"last_fusion": "not a dict"}}
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["last_fusion"] is None

    def test_malformed_last_long_arc_treated_as_none(self):
        vs = {"elins": {"last_long_arc": [1, 2, 3]}}
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["last_long_arc"] is None

    def test_malformed_fusion_history_treated_as_empty(self):
        vs = {"elins": {"fusion_history": "not a list"}}
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["fusion_history"] == []

    def test_full_continuity_roundtrip(self):
        lf = _last_fusion()
        lla = _last_long_arc()
        hist = [{"x": 1}, {"x": 2}]
        vs = _vault_state(
            last_fusion=lf, last_long_arc=lla, fusion_history=hist,
        )
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["elins"]["last_fusion"] == lf
        assert out["continuity"]["elins"]["last_long_arc"] == lla
        assert out["continuity"]["elins"]["fusion_history"] == hist


# ===========================================================================
# D. Runtime mode resolution
# ===========================================================================
class TestRuntimeMode:
    def test_normal_mode(self):
        vs = _vault_state(runtime_mode="normal")
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["runtime_mode"] == "normal"

    def test_strict_mode(self):
        vs = _vault_state(runtime_mode="strict")
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["runtime_mode"] == "strict"

    def test_diagnostic_mode(self):
        vs = _vault_state(runtime_mode="diagnostic")
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["runtime_mode"] == "diagnostic"

    def test_absent_mode_defaults_to_normal(self):
        out = rc_mod.resume_runtime_session("s1", "op1", _vault_state())
        assert out["continuity"]["runtime_mode"] == "normal"

    def test_unknown_mode_falls_back_to_normal(self):
        vs = _vault_state(runtime_mode="reckless")
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["runtime_mode"] == "normal"

    def test_non_string_mode_falls_back_to_normal(self):
        vs = {"runtime_mode": 42}
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["continuity"]["runtime_mode"] == "normal"


# ===========================================================================
# E. Timestamp resolution precedence
# ===========================================================================
class TestTimestamp:
    def test_last_fusion_wins(self):
        lf = _last_fusion(timestamp="2026-05-12T10:00:00+00:00")
        lla = _last_long_arc(timestamp="2026-05-12T09:00:00+00:00")
        vs = _vault_state(last_fusion=lf, last_long_arc=lla)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["timestamp"] == "2026-05-12T10:00:00+00:00"

    def test_last_long_arc_used_when_no_fusion(self):
        lla = _last_long_arc(timestamp="2026-05-12T09:00:00+00:00")
        vs = _vault_state(last_long_arc=lla)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["timestamp"] == "2026-05-12T09:00:00+00:00"

    def test_no_timestamps_yields_empty_string(self):
        vs = _vault_state(last_fusion={"long_arc_assessment": "benign"})
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["timestamp"] == ""

    def test_non_string_timestamp_falls_through(self):
        lf = {"timestamp": 12345}
        lla = _last_long_arc(timestamp="2026-05-12T09:00:00+00:00")
        vs = _vault_state(last_fusion=lf, last_long_arc=lla)
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert out["timestamp"] == "2026-05-12T09:00:00+00:00"


# ===========================================================================
# F. session_id validation
# ===========================================================================
class TestSessionIdValidation:
    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            rc_mod.resume_runtime_session("", "op1", None)

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            rc_mod.resume_runtime_session(42, "op1", None)

    def test_none_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            rc_mod.resume_runtime_session(None, "op1", None)


# ===========================================================================
# G. operator_id validation
# ===========================================================================
class TestOperatorIdValidation:
    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="operator_id"):
            rc_mod.resume_runtime_session("s1", "", None)

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="operator_id"):
            rc_mod.resume_runtime_session("s1", 42, None)

    def test_none_rejected(self):
        with pytest.raises(ValueError, match="operator_id"):
            rc_mod.resume_runtime_session("s1", None, None)


# ===========================================================================
# H. vault_state validation
# ===========================================================================
class TestVaultStateValidation:
    def test_none_accepted(self):
        rc_mod.resume_runtime_session("s1", "op1", None)  # no raise

    def test_dict_accepted(self):
        rc_mod.resume_runtime_session("s1", "op1", {})  # no raise

    def test_list_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            rc_mod.resume_runtime_session("s1", "op1", [1, 2, 3])

    def test_string_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            rc_mod.resume_runtime_session("s1", "op1", "not a dict")

    def test_int_rejected(self):
        with pytest.raises(ValueError, match="vault_state"):
            rc_mod.resume_runtime_session("s1", "op1", 42)


# ===========================================================================
# I. Determinism + immutability
# ===========================================================================
class TestDeterminism:
    def test_same_input_same_output(self):
        vs = _vault_state(last_fusion=_last_fusion())
        a = rc_mod.resume_runtime_session("s1", "op1", vs)
        b = rc_mod.resume_runtime_session("s1", "op1", vs)
        assert a == b

    def test_input_vault_state_not_mutated(self):
        lf = _last_fusion()
        hist = [{"a": 1}]
        vs = _vault_state(last_fusion=lf, fusion_history=hist)
        snapshot = json.dumps(vs, sort_keys=True)
        rc_mod.resume_runtime_session("s1", "op1", vs)
        assert json.dumps(vs, sort_keys=True) == snapshot

    def test_session_id_echoed(self):
        out = rc_mod.resume_runtime_session("custom_session", "op1", None)
        assert out["session_id"] == "custom_session"

    def test_operator_id_echoed(self):
        out = rc_mod.resume_runtime_session("s1", "custom_operator", None)
        assert out["operator_id"] == "custom_operator"


# ===========================================================================
# J. JSON-safety
# ===========================================================================
class TestJsonSafety:
    def test_cold_start_json_roundtrip(self):
        out = rc_mod.resume_runtime_session("s1", "op1", None)
        s = json.dumps(out)
        assert json.loads(s) == out

    def test_warm_json_roundtrip(self):
        vs = _vault_state(
            last_fusion=_last_fusion(),
            last_long_arc=_last_long_arc(),
            fusion_history=[{"x": 1}],
            runtime_mode="strict",
        )
        out = rc_mod.resume_runtime_session("s1", "op1", vs)
        s = json.dumps(out)
        assert json.loads(s) == out


# ===========================================================================
# K. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_api_exposed(self):
        assert hasattr(rc_mod, "resume_runtime_session")
        assert callable(rc_mod.resume_runtime_session)

    def test_resume_signature(self):
        sig = inspect.signature(rc_mod.resume_runtime_session)
        assert list(sig.parameters.keys()) == [
            "session_id", "operator_id", "vault_state",
        ]

    def test_no_io_imports(self):
        src = inspect.getsource(rc_mod)
        # The continuity layer must not pull in I/O modules. The
        # storage layer above handles that.
        for forbidden in (
            "import requests", "import httpx",
            "open(", "subprocess",
            "asyncio.open_connection",
        ):
            assert forbidden not in src, (
                f"runtime_continuity must not use {forbidden!r}"
            )
