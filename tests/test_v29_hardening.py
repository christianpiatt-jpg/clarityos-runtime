"""
Unit tests for v29_hardening primitives — validators, rate limiter, flags,
structured logging redaction. These are pure-Python tests that don't need
FastAPI to run.
"""
from __future__ import annotations

import logging

import pytest

import v29_hardening as h


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
def test_require_str_happy(reset_stores):
    assert h.require_str("hello", "field") == "hello"
    assert h.require_str("  trimmed  ", "field") == "trimmed"


def test_require_str_missing_required(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_str(None, "field")
    assert exc.value.code == "missing_field"


def test_require_str_wrong_type(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_str(42, "field")
    assert exc.value.code == "bad_type"


def test_require_str_empty_disallowed(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_str("   ", "field")
    assert exc.value.code == "empty_field"


def test_require_str_empty_allowed(reset_stores):
    assert h.require_str("", "field", allow_empty=True) == ""


def test_require_str_max_len(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_str("a" * 100, "field", max_len=10)
    assert exc.value.code == "field_too_long"


def test_require_int_default(reset_stores):
    assert h.require_int(None, "x", min_value=0, max_value=23, default=5) == 5


def test_require_int_range(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_int(99, "hour", min_value=0, max_value=23)
    assert exc.value.code == "out_of_range"


def test_require_int_bad_type(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.require_int("not-a-number", "x")
    assert exc.value.code == "bad_type"


def test_require_dict_max_keys(reset_stores):
    big = {f"k{i}": i for i in range(257)}
    with pytest.raises(h.ValidationError) as exc:
        h.require_dict(big, "metadata", max_keys=256)
    assert exc.value.code == "too_many_keys"


def test_require_bool_pass_through(reset_stores):
    assert h.require_bool(True, "x") is True
    assert h.require_bool(False, "x") is False
    assert h.require_bool(None, "x", default=True) is True
    with pytest.raises(h.ValidationError):
        h.require_bool("yes", "x")


def test_require_one_of(reset_stores):
    assert h.require_one_of("apple", "fruit", ["apple", "pear"]) == "apple"
    with pytest.raises(h.ValidationError) as exc:
        h.require_one_of("banana", "fruit", ["apple", "pear"])
    assert exc.value.code == "invalid_value"


# ---------------------------------------------------------------------------
# Mesh payload validator
# ---------------------------------------------------------------------------
def test_validate_mesh_payload_ok(reset_stores):
    did, md = h.validate_mesh_payload("device-1", {"a": 1})
    assert did == "device-1"
    assert md == {"a": 1}


def test_validate_mesh_payload_oversize(reset_stores):
    big_meta = {"blob": "x" * (16 * 1024 + 1)}
    with pytest.raises(h.ValidationError) as exc:
        h.validate_mesh_payload("d", big_meta)
    assert exc.value.code == "mesh_payload"


def test_validate_mesh_payload_missing_device(reset_stores):
    with pytest.raises(h.ValidationError) as exc:
        h.validate_mesh_payload("", {})
    assert exc.value.code == "empty_field"


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
def test_rate_limit_under_capacity(reset_stores):
    for _ in range(5):
        assert h.check_rate_limit("u1", "/foo", capacity=10, window_s=60) is True


def test_rate_limit_overflow_blocks_then_refills(reset_stores):
    capacity = 3
    for _ in range(capacity):
        assert h.check_rate_limit("u2", "/foo", capacity=capacity, window_s=60) is True
    # bucket empty
    assert h.check_rate_limit("u2", "/foo", capacity=capacity, window_s=60) is False
    # Force a manual refill by bumping the bucket's last_refill_ts back in time.
    bucket = h._bucket("u2", "/foo")
    bucket["last_refill_ts"] -= 60.0
    assert h.check_rate_limit("u2", "/foo", capacity=capacity, window_s=60) is True


def test_rate_limit_independent_users(reset_stores):
    cap = 1
    assert h.check_rate_limit("u3", "/foo", capacity=cap, window_s=60) is True
    assert h.check_rate_limit("u3", "/foo", capacity=cap, window_s=60) is False
    # different user has its own bucket
    assert h.check_rate_limit("u4", "/foo", capacity=cap, window_s=60) is True


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
def test_feature_default_off(flags_clean):
    assert h.feature_enabled("v28_surfaces") is False


def test_feature_user_override_wins(flags_clean):
    h.set_flag("v28_surfaces", True, user="alice")
    assert h.feature_enabled("v28_surfaces", user="alice") is True
    assert h.feature_enabled("v28_surfaces", user="bob") is False


def test_feature_cohort_override(flags_clean):
    h.set_flag("v28_surfaces", True, cohort="founder")
    assert h.feature_enabled("v28_surfaces", user="charlie", cohort="founder") is True
    assert h.feature_enabled("v28_surfaces", user="charlie", cohort="terrace_1") is False


def test_feature_user_override_beats_cohort(flags_clean):
    h.set_flag("v28_surfaces", True, cohort="founder")
    h.set_flag("v28_surfaces", False, user="dan")
    assert h.feature_enabled("v28_surfaces", user="dan", cohort="founder") is False


def test_list_flags_includes_defaults(flags_clean):
    flags = h.list_flags()
    assert "v28_surfaces" in flags
    assert flags["v28_surfaces"]["default"] is False


# ---------------------------------------------------------------------------
# Structured logging — never emits user content
# ---------------------------------------------------------------------------
def test_log_event_redacts_user(caplog, reset_stores):
    with caplog.at_level(logging.INFO, logger="clarityos.v29"):
        h.log_event("test_event", user="alice123longusername", route="/x", success=True)
    msg = caplog.records[-1].getMessage()
    assert "alice123long" in msg  # truncated prefix kept
    assert "longusername" not in msg.replace("alice123long", "")


def test_log_event_collapses_collections(caplog, reset_stores):
    with caplog.at_level(logging.INFO, logger="clarityos.v29"):
        h.log_event(
            "test_event", user="bob", payload={"secret": "DO_NOT_LEAK"},
            items=["a", "b", "c"],
        )
    msg = caplog.records[-1].getMessage()
    assert "DO_NOT_LEAK" not in msg
    assert "payload_count=1" in msg
    assert "items_count=3" in msg


def test_timed_block_emits_duration(caplog, reset_stores):
    with caplog.at_level(logging.INFO, logger="clarityos.v29"):
        with h.TimedBlock("op", user="u", route="/y") as tb:
            tb.set(neighborhoods=5)
    msg = caplog.records[-1].getMessage()
    assert "duration_ms=" in msg
    assert "neighborhoods=5" in msg
    assert "success=1" in msg


def test_timed_block_marks_failure_on_exception(caplog, reset_stores):
    with caplog.at_level(logging.INFO, logger="clarityos.v29"):
        with pytest.raises(RuntimeError):
            with h.TimedBlock("op2", user="u"):
                raise RuntimeError("boom")
    msg = caplog.records[-1].getMessage()
    assert "success=0" in msg
