"""W1_HUB-B — Regression floor for Module B alignment hook in intelligence_kernel.

Locks the wiring installed in W1_HUB-A (commit f485e69) against silent-no-op
regression permanently. Four contract locks across ten tests:

  1. Positive case (4 tests) — externalization-intent text produces a dict
     advisory at result["meta"]["module_b_alignment"] with the 5-key
     IntegratedAlignmentResult shape; json.dumps round-trips clean; a
     recursive walk finds no forbidden fields.

  2. Negative case (2 tests) — non-triggering text produces exactly None at
     result["meta"]["module_b_alignment"]; the key MUST be present (locks
     the silent-missing-key regression).

  3. Non-blocking guarantee (1 test) — monkeypatching
     azimuth_transition.compute_aligned_expression to raise, using positive
     text so detect_externalization_intent fires and the except branch is
     genuinely exercised, still lets the turn complete with an
     "assistant_message" in the result and role=="assistant".

  4. Import-surface guard (3 tests) — intelligence_kernel.azimuth_transition
     is the azimuth_transition module; azimuth_transition.EnvelopeState is
     present as an attribute; intelligence_kernel.asdict is
     dataclasses.asdict.

Fixture pattern mirrors tests/test_cite_integration.py (kernel-path
precedent):
  - bare user_id string (no users_store.create_user call)
  - create_thread(user_id, title)["thread_id"]
  - reset_stores fixture parameter for isolation
  - FakeRouter monkeypatched onto model_router.route_request

Isolation caveat: reset_stores does not wipe threads_vault or memory_vault
(conftest:123, ~20 stores + intelligence_kernel._reset_for_tests only).
Isolation across tests is achieved via unique thread ids returned by
create_thread, matching the cite_integration precedent.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict, List, Optional

import pytest


# --- Test-input constants ---------------------------------------------------

_POSITIVE_TEXT = "should i send this message to my colleague"
_NEGATIVE_TEXT = "what is the capital of france"

_EXPECTED_KEYS = {
    "aligned_expression",
    "halt_level",
    "trust_state_delta",
    "momentum_preserved",
    "surface_directives",
}

_FORBIDDEN_FIELDS = {
    "raw_prompt",
    "system_prompt",
    "api_key",
    "authorization",
    "bearer",
}


# --- Router stub (mirrors test_cite_integration.FakeRouter) -----------------


class FakeRouter:
    """Records calls and returns scripted mock model outputs in order."""

    def __init__(self, outputs: List[str]) -> None:
        self._outputs = list(outputs)
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"args": args, "kwargs": kwargs})
        text = self._outputs.pop(0) if self._outputs else "ok"
        return {
            "ok": True,
            "model_id": "fake-model",
            "provider": "fake",
            "text": text,
            "mock": True,
            "ts": 0,
        }


def _install_router(monkeypatch: pytest.MonkeyPatch, outputs: List[str]) -> FakeRouter:
    import model_router
    fake = FakeRouter(outputs)
    monkeypatch.setattr(model_router, "route_request", fake)
    return fake


def _new_thread(user: str = "alice", title: str = "w1hub-b") -> str:
    """Bare-user-id + create_thread precedent (test_cite_integration.py:59-61)."""
    import threads_vault as tv
    return tv.create_thread(user, title)["thread_id"]


# --- Recursive walker for forbidden-field guard -----------------------------


def _walk_for_forbidden(obj: Any) -> Optional[str]:
    """Return the first forbidden key found in a nested dict/list, or None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _FORBIDDEN_FIELDS:
                return k
            hit = _walk_for_forbidden(v)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for item in obj:
            hit = _walk_for_forbidden(item)
            if hit is not None:
                return hit
    return None


# ============================================================================
# CONTRACT LOCK 1 — Positive case (4 tests)
# ============================================================================


def test_positive_advisory_present_and_is_dict(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive text → meta['module_b_alignment'] is a dict."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-a"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _POSITIVE_TEXT)

    meta = result.get("meta") or {}
    assert "module_b_alignment" in meta, "positive path must attach module_b_alignment key"
    advisory = meta["module_b_alignment"]
    assert isinstance(advisory, dict), f"advisory must be dict, got {type(advisory).__name__}"


def test_positive_advisory_has_five_key_shape(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advisory dict matches IntegratedAlignmentResult 5-key shape exactly."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-b"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _POSITIVE_TEXT)
    advisory = result["meta"]["module_b_alignment"]

    assert set(advisory.keys()) == _EXPECTED_KEYS, (
        f"expected keys {_EXPECTED_KEYS}, got {set(advisory.keys())}"
    )


def test_positive_advisory_json_round_trip(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advisory serializes cleanly via json.dumps (no unserializable objects)."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-c"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _POSITIVE_TEXT)
    advisory = result["meta"]["module_b_alignment"]

    encoded = json.dumps(advisory)
    decoded = json.loads(encoded)
    assert decoded == advisory, "json round-trip must preserve advisory content"


def test_positive_advisory_no_forbidden_fields(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recursive walk finds no forbidden field names anywhere in the advisory."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-d"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _POSITIVE_TEXT)
    advisory = result["meta"]["module_b_alignment"]

    hit = _walk_for_forbidden(advisory)
    assert hit is None, f"forbidden field surfaced in advisory: {hit!r}"


# ============================================================================
# CONTRACT LOCK 2 — Negative case (2 tests)
# ============================================================================


def test_negative_advisory_key_present_and_none(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-triggering text → key PRESENT, value exactly None."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-e"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _NEGATIVE_TEXT)

    meta = result.get("meta") or {}
    assert "module_b_alignment" in meta, (
        "negative path MUST still expose the key — locks silent-missing-key regression"
    )
    assert meta["module_b_alignment"] is None, (
        f"negative path must produce exactly None, got {meta['module_b_alignment']!r}"
    )


def test_negative_advisory_no_dict_leaks(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative path must never produce a dict-shaped advisory."""
    import intelligence_kernel as ik
    _install_router(monkeypatch, ["reply-f"])
    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _NEGATIVE_TEXT)
    advisory = result["meta"]["module_b_alignment"]

    assert not isinstance(advisory, dict), (
        f"negative path leaked a dict advisory: {advisory!r}"
    )


# ============================================================================
# CONTRACT LOCK 3 — Non-blocking guarantee (1 test)
# ============================================================================


def test_hook_exception_does_not_block_turn(
    reset_stores: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Raise from compute_aligned_expression under positive text; turn completes.

    Uses _POSITIVE_TEXT so detect_externalization_intent fires and the hook
    actually reaches compute_aligned_expression (exercising the except branch).
    Under negative text the hook short-circuits before that call and this test
    would pass vacuously — that would not lock the non-blocking guarantee.
    """
    import intelligence_kernel as ik
    import azimuth_transition as at
    _install_router(monkeypatch, ["reply-g"])

    def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("simulated Module B failure")

    monkeypatch.setattr(at, "compute_aligned_expression", _boom)

    user = "alice"
    tid = _new_thread(user)

    result = ik.run_thread_message(user, tid, _POSITIVE_TEXT)

    assert "assistant_message" in result, (
        "turn must complete with assistant_message even when hook raises"
    )
    msg = result["assistant_message"]
    role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
    assert role == "assistant", f"assistant_message must have role='assistant', got {role!r}"


# ============================================================================
# CONTRACT LOCK 4 — Import-surface guard (3 tests)
# ============================================================================


def test_import_surface_azimuth_transition_bound() -> None:
    """intelligence_kernel.azimuth_transition IS the azimuth_transition module."""
    import intelligence_kernel as ik
    import azimuth_transition as at
    assert ik.azimuth_transition is at, (
        "intelligence_kernel must bind azimuth_transition module at import"
    )


def test_import_surface_envelope_state_present() -> None:
    """azimuth_transition.EnvelopeState is present as an attribute."""
    import azimuth_transition as at
    assert hasattr(at, "EnvelopeState"), (
        "azimuth_transition must re-export EnvelopeState for hook consumers"
    )


def test_import_surface_asdict_is_dataclasses_asdict() -> None:
    """intelligence_kernel.asdict IS dataclasses.asdict (no local shadow)."""
    import intelligence_kernel as ik
    assert ik.asdict is dataclasses.asdict, (
        "intelligence_kernel.asdict must be the stdlib dataclasses.asdict"
    )
