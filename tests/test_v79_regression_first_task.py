"""
Tests for V79 — wire regression_first into intelligence_kernel and
model_router.

Coverage:
    A. TASK_DEFAULTS["regression_first"] is registered and stable
    B. select_model resolves regression_first via TASK_DEFAULTS by default
    C. select_model honours explicit override for regression_first
    D. select_model honours founder default for regression_first
    E. select_model honours user preferred_model for regression_first
    F. intelligence_kernel.run_regression_first dispatches analyze_packet
    G. run_regression_first persists chain through injected store
    H. run_regression_first defaults to InMemory store when store=None
    I. run_regression_first records model on operator_state.last_model_used
    J. run_regression_first graceful degrades on malformed packet
    K. run_regression_first emits a kernel_run log line
    L. model_router.call_regression_first resolves model_id + calls kernel
    M. call_regression_first allows explicit model_id override
    N. HTTP surface — v76 routes still present (v80 /packet locked separately)
"""
from __future__ import annotations

import json
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _canonical_packet(
    *,
    regression_required: bool = True,
    operator_intent: str = "Identify root cause of rendering failure.",
) -> dict:
    layers: list[dict] = [
        {
            "layer": 1, "name": "Domain & Routing",
            "question": "Which page is set as homepage?",
            "location": "Settings → Reading → Homepage",
            "goal": "Correct page selected",
        },
    ] if regression_required else []
    return {
        "EL": 2, "INS": 3, "ratio": "0.67",
        "el_signals": ["something is wrong"],
        "ins_signals": ["page", "scaffold"],
        "classification": "structure-dominant",
        "operator_intent": operator_intent,
        "regression_required": regression_required,
        "regression_chain": layers,
        "recommended_system_action": (
            "Pause and request operator verification."
            if regression_required else "Proceed normally."
        ),
    }


# ===========================================================================
# A–E. model_router — TASK_DEFAULTS + select_model precedence
# ===========================================================================
class TestTaskDefaults:
    def test_regression_first_registered(self):
        import model_router as mr
        assert "regression_first" in mr.TASK_DEFAULTS
        assert mr.TASK_DEFAULTS["regression_first"] == "openai:gpt-4o"

    def test_select_model_falls_to_task_default(self, reset_stores):
        import model_router as mr
        assert mr.select_model(None, task="regression_first") == (
            mr.TASK_DEFAULTS["regression_first"]
        )

    def test_select_model_explicit_override(self, reset_stores):
        import model_router as mr
        chosen = mr.select_model(
            None, task="regression_first", override="openai:gpt-4o",
        )
        assert chosen == "openai:gpt-4o"

    def test_select_model_unknown_override_raises(self, reset_stores):
        import model_router as mr
        with pytest.raises(ValueError):
            mr.select_model(
                None, task="regression_first", override="not_a_model",
            )

    def test_select_model_founder_default_overrides(self, reset_stores):
        import model_router as mr
        mr.set_founder_default_model("openai:gpt-4o")
        try:
            assert mr.select_model(None, task="regression_first") == (
                "openai:gpt-4o"
            )
        finally:
            mr.set_founder_default_model(None)

    def test_select_model_user_preferred(self, reset_stores):
        import model_router as mr
        import operator_state
        operator_state.set_preferred_model("alice", "google:gemini-2.0-flash")
        assert mr.select_model("alice", task="regression_first") == (
            "google:gemini-2.0-flash"
        )


# ===========================================================================
# F–K. intelligence_kernel.run_regression_first
# ===========================================================================
class TestRunRegressionFirst:
    def test_dispatches_analyze_packet_happy_path(self, reset_stores):
        import intelligence_kernel as ik
        result = ik.run_regression_first(_canonical_packet())
        assert result["ok"] is True
        assert result["packet"] is not None
        assert result["packet"]["classification"] == "structure-dominant"
        assert result["chain"] is not None
        assert result["chain"]["title"].startswith("Identify")

    def test_persists_chain_through_injected_store(self, reset_stores):
        import intelligence_kernel as ik
        import problem_solver
        store = problem_solver.VaultBackedRegressionChainStore("alice")
        result = ik.run_regression_first(
            _canonical_packet(), user_id="alice", store=store,
        )
        chain_id = result["chain"]["chain_id"]
        # The store should be able to fetch it back.
        fetched = store.get(chain_id)
        assert fetched is not None
        assert fetched["chain_id"] == chain_id

    def test_defaults_to_in_memory_store_when_none(self, reset_stores):
        import intelligence_kernel as ik
        import problem_solver
        result = ik.run_regression_first(_canonical_packet())
        # Default store is DEFAULT_STORE (in-memory). The chain
        # should be in DEFAULT_STORE's list_all().
        chain_id = result["chain"]["chain_id"]
        in_memory = problem_solver.DEFAULT_STORE.list_all()
        assert any(c["chain_id"] == chain_id for c in in_memory)

    def test_records_model_on_operator_state_last_model_used(
        self, reset_stores,
    ):
        import intelligence_kernel as ik
        import operator_state
        ik.run_regression_first(
            _canonical_packet(), user_id="alice",
        )
        state = operator_state.get_operator_state("alice") or {}
        # last_model_used should reflect the task default.
        assert state.get("last_model_used") == "openai:gpt-4o"

    def test_explicit_model_id_threaded_through(self, reset_stores):
        import intelligence_kernel as ik
        result = ik.run_regression_first(
            _canonical_packet(),
            user_id="alice",
            model_id="openai:gpt-4o",
        )
        assert result["model_id"] == "openai:gpt-4o"

    def test_graceful_degrade_on_malformed_packet(self, reset_stores):
        import intelligence_kernel as ik
        result = ik.run_regression_first({"not": "a valid packet"})
        assert result["ok"] is False
        assert result["packet"] is None
        assert result["chain"] is None
        # Even on degrade, the model_id is still resolved.
        assert result["model_id"] == "openai:gpt-4o"

    def test_graceful_degrade_on_non_dict_input(self, reset_stores):
        import intelligence_kernel as ik
        result = ik.run_regression_first("not-json")
        assert result["ok"] is False
        assert result["packet"] is None
        assert result["chain"] is None

    def test_regression_not_required_no_chain(self, reset_stores):
        import intelligence_kernel as ik
        result = ik.run_regression_first(
            _canonical_packet(regression_required=False),
        )
        assert result["ok"] is True
        assert result["packet"] is not None
        assert result["packet"]["regression_required"] is False
        # No chain when regression_required is False.
        assert result["chain"] is None

    def test_emits_kernel_run_log(self, reset_stores, monkeypatch):
        import intelligence_kernel as ik
        import kernel_logging
        captured: list[dict] = []
        real_log = kernel_logging.log_kernel_run

        def _capture(*args, **kwargs):
            captured.append(dict(kwargs))
            return real_log(*args, **kwargs)

        monkeypatch.setattr(kernel_logging, "log_kernel_run", _capture)
        ik.run_regression_first(
            _canonical_packet(), user_id="alice",
        )
        # At least one run_regression_first log line.
        rf = [c for c in captured if c.get("kind") == "run_regression_first"]
        assert len(rf) == 1
        meta = rf[0].get("meta") or {}
        assert meta.get("model_id") == "openai:gpt-4o"
        assert meta.get("regression_required") is True
        assert isinstance(meta.get("chain_id"), str)


# ===========================================================================
# L–M. model_router.call_regression_first
# ===========================================================================
class TestCallRegressionFirst:
    def test_resolves_model_id_via_task_defaults(self, reset_stores):
        import model_router as mr
        result = mr.call_regression_first(_canonical_packet())
        assert result["ok"] is True
        assert result["model_id"] == "openai:gpt-4o"

    def test_explicit_model_id_override(self, reset_stores):
        import model_router as mr
        result = mr.call_regression_first(
            _canonical_packet(), model_id="openai:gpt-4o",
        )
        assert result["model_id"] == "openai:gpt-4o"

    def test_unknown_override_raises(self, reset_stores):
        import model_router as mr
        with pytest.raises(ValueError):
            mr.call_regression_first(
                _canonical_packet(), model_id="not_a_model",
            )

    def test_user_preferred_model_wins_over_task_default(self, reset_stores):
        import model_router as mr
        import operator_state
        operator_state.set_preferred_model("alice", "google:gemini-2.0-flash")
        result = mr.call_regression_first(
            _canonical_packet(), user="alice",
        )
        assert result["model_id"] == "google:gemini-2.0-flash"

    def test_pass_through_store(self, reset_stores):
        import model_router as mr
        import problem_solver
        store = problem_solver.VaultBackedRegressionChainStore("alice")
        result = mr.call_regression_first(
            _canonical_packet(), user="alice", store=store,
        )
        chain_id = result["chain"]["chain_id"]
        assert store.get(chain_id) is not None

    def test_router_helper_proxies_to_kernel(self, reset_stores, monkeypatch):
        import intelligence_kernel as ik
        import model_router as mr
        seen: dict = {}

        def _spy(packet, *, user_id=None, model_id=None, store=None):
            seen["packet"]   = packet
            seen["user_id"]  = user_id
            seen["model_id"] = model_id
            seen["store"]    = store
            return {
                "packet": None, "chain": None,
                "model_id": model_id, "ok": False,
            }

        monkeypatch.setattr(ik, "run_regression_first", _spy)
        mr.call_regression_first(
            _canonical_packet(), user="alice", model_id="openai:gpt-4o",
        )
        assert seen["user_id"]  == "alice"
        assert seen["model_id"] == "openai:gpt-4o"


# ===========================================================================
# N. HTTP surface (V79 was kernel-only; V80 added /packet)
# ===========================================================================
class TestHttpSurface:
    def test_v76_routes_present(self, reset_stores):
        """V79's plumbing must not have removed the v76 manual routes.
        (V80's /packet endpoint is locked by
        test_v80_regression_first_packet::TestRouteAndManifest.)"""
        import app
        routes = {getattr(r, "path", None) for r in app.app.routes}
        assert "/me/regression_first/start" in routes
        assert "/me/regression_first/step" in routes
        assert "/me/regression_first/{chain_id}" in routes
        assert "/me/regression_first" in routes
        assert "/me/regression_first/{chain_id}/close" in routes
        assert "/me/regression_first/{chain_id}/tag" in routes
