"""
Test configuration — adds the repo root to sys.path so ``import app``,
``import v29_hardening`` work when pytest is invoked from inside ``tests/``.

Tests force ``CLARITYOS_BACKEND=memory`` before importing app modules so the
in-memory stores (``users_store._MEMORY_USERS`` etc.) are used. Each store
exposes a ``_reset_memory_for_tests()`` hook the fixtures call between tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_ADMIN_USER", "admin")
os.environ.setdefault("CLARITYOS_ADMIN_PASSWORD", "test_admin_password_123")
# v31 — billing test defaults. Mock mode + auto-confirm keeps the v30
# tests passing as-is; v31 tests that exercise the async flow override
# the auto-confirm flag explicitly.
os.environ.setdefault("CLARITYOS_BILLING_MODE", "mock")
os.environ.setdefault("CLARITYOS_MOCK_AUTO_CONFIRM", "1")
# Don't burn random tokens through dewey on every test — mock the embedder
# in individual tests when it matters.
os.environ.setdefault("CLARITYOS_LOG_LEVEL", "WARNING")
# v36 — disable the macro scheduler boot so tests don't spawn the
# daemon thread on every import. Tests drive _run_macro_elins_once
# directly when they need to exercise the pipeline.
os.environ.setdefault("CLARITYOS_DISABLE_MACRO_SCHEDULER", "1")
# memory_vault no longer has a built-in default secret — _secret() raises
# if CLARITYOS_VAULT_SECRET is unset. Production mounts it from Google
# Secret Manager; the test harness pins a fixed throwaway value so every
# vault round-trip in the suite derives a stable per-user key. Tests that
# exercise secret rotation override this with monkeypatch.setenv.
os.environ.setdefault(
    "CLARITYOS_VAULT_SECRET",
    "clarityos-test-vault-secret-fixed-DO-NOT-USE-IN-PROD",
)

import pytest


class AppClient:
    """Tiny sync test client compatible with httpx >=0.28 when starlette's
    bundled TestClient is from a version that still passes ``app=`` to httpx.

    Wraps ``httpx.AsyncClient(transport=httpx.ASGITransport(app=...))`` and
    drives it via ``asyncio.run`` so tests can stay synchronous. Pulled into
    conftest so tests don't need a starlette/httpx version pin in the
    project."""

    __test__ = False  # never collected as a pytest test class

    def __init__(self, app):
        import httpx
        self._app = app
        self._httpx = httpx
        self._transport = httpx.ASGITransport(app=app)

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    async def _do(self, method: str, url: str, *, json=None, headers=None):
        async with self._httpx.AsyncClient(
            transport=self._transport, base_url="http://testserver",
        ) as ac:
            if method == "GET":
                return await ac.get(url, headers=headers)
            if method == "POST":
                return await ac.post(url, json=json, headers=headers)
            # PASS — Task Card 7: PUT/PATCH/DELETE added so the
            # web_surface catchall multi-method test (which exercises
            # every verb the router declares) can run through the
            # same httpx wrapper.
            if method == "PUT":
                return await ac.put(url, json=json, headers=headers)
            if method == "PATCH":
                return await ac.patch(url, json=json, headers=headers)
            if method == "DELETE":
                return await ac.delete(url, headers=headers)
            raise ValueError(f"unsupported method {method}")

    def get(self, url, headers=None):
        return self._run(self._do("GET", url, headers=headers))

    def post(self, url, json=None, headers=None):
        return self._run(self._do("POST", url, json=json, headers=headers))

    def put(self, url, json=None, headers=None):
        return self._run(self._do("PUT", url, json=json, headers=headers))

    def patch(self, url, json=None, headers=None):
        return self._run(self._do("PATCH", url, json=json, headers=headers))

    def delete(self, url, headers=None):
        return self._run(self._do("DELETE", url, headers=headers))


# Backward-compatible alias used by tests.
TestClient = AppClient


@pytest.fixture(autouse=True)
def _allow_temp_evidence_dirs(monkeypatch):
    """Unit 24: extend the evidence-directory allowlist with the system
    tmpdir so any test that uses pytest's ``tmp_path`` (or any other
    path under ``tempfile.gettempdir()``) passes
    ``validate_evidence_dir`` automatically.

    This is autouse for the whole suite — Unit 24 tests that need to
    exercise the rejection path either use absolute paths NOT under
    tmpdir (e.g. ``C:\\Windows`` / ``/etc``) or re-monkeypatch
    ``ALLOWED_EVIDENCE_DIRS`` themselves to a known-empty tuple.
    """
    import tempfile
    try:
        import elins_evidence_allowlist as _al
    except ImportError:
        return
    monkeypatch.setattr(
        _al, "ALLOWED_EVIDENCE_DIRS",
        tuple(_al.ALLOWED_EVIDENCE_DIRS) + (tempfile.gettempdir(),),
    )


@pytest.fixture
def reset_stores():
    """Wipe all in-memory stores. Yield a no-op marker so test bodies can
    just ``def test_x(reset_stores): ...`` and rely on a clean slate."""
    import users_store
    import sessions_store
    import vault_store
    import library_store
    import timeline_store
    import usage_store
    import elins_distribution_store
    import mesh_metadata_store
    import envelopes_store
    import markov_states_store
    import dewey_neighborhoods_store
    import dewey_memberships_store
    import membership_store
    import waitlist_store
    import dm_store
    from ELINS import elins_project
    import v29_hardening
    import elins_scheduler_config
    import elins_scheduler
    import operator_state

    # v54 — ingestion bus has its own per-user feed registry; reset
    # alongside the rest of the in-memory stores so tests don't leak
    # feeds between cases.
    from ELINS import ingestion_bus as _ib
    for mod in (
        users_store, sessions_store, vault_store, library_store, timeline_store,
        usage_store, elins_distribution_store, mesh_metadata_store,
        envelopes_store, markov_states_store, dewey_neighborhoods_store,
        dewey_memberships_store, membership_store, waitlist_store,
        dm_store, elins_project, elins_scheduler_config, operator_state, _ib,
    ):
        if hasattr(mod, "_reset_memory_for_tests"):
            mod._reset_memory_for_tests()
    if hasattr(elins_scheduler, "_reset_for_tests"):
        elins_scheduler._reset_for_tests()
    import intelligence_kernel
    if hasattr(intelligence_kernel, "_reset_for_tests"):
        intelligence_kernel._reset_for_tests()
    import perplexity_oracle as _po
    if hasattr(_po, "_reset_for_tests"):
        _po._reset_for_tests()
    import billing_config as _bc
    if hasattr(_bc, "_reset_for_tests"):
        _bc._reset_for_tests()
    import model_router as _mr
    if hasattr(_mr, "_reset_for_tests"):
        _mr._reset_for_tests()
    import local_model_runtime as _lmr
    if hasattr(_lmr, "_reset_for_tests"):
        _lmr._reset_for_tests()
    import memory_vault as _mv
    if hasattr(_mv, "_reset_for_tests"):
        _mv._reset_for_tests()
    # v76/v77 — problem_solver kernel (default in-memory store). The
    # v77 vault-backed store rides on top of memory_vault, which is
    # already reset above — no separate owner index in v77.
    import problem_solver as _ps
    if hasattr(_ps, "_reset_for_tests"):
        _ps._reset_for_tests()
    # v78 — Regression-First timeline events live in el_ins/timeline.
    # The existing el_ins reset hook clears every operator bucket.
    import el_ins as _ei
    if hasattr(_ei, "_reset_all_for_tests"):
        _ei._reset_all_for_tests()
    v29_hardening._reset_rate_limits_for_tests()
    v29_hardening._reset_flags_for_tests()
    # Mirror app.py's startup flag bootstrap so cohort-based defaults match
    # what production sees post-deploy.
    for _coh in ("founder", "founder_exception", "terrace_1"):
        v29_hardening.set_flag("v28_surfaces", True, cohort=_coh)
        v29_hardening.set_flag("onboarding_v1", True, cohort=_coh)
        v29_hardening.set_flag("whats_new_v28", True, cohort=_coh)
    # v30 flags + cohort defaults.
    v29_hardening._DEFAULT_FLAGS.setdefault("founder_tier_enabled", False)
    v29_hardening._DEFAULT_FLAGS.setdefault("g_credits_enabled", False)
    v29_hardening._DEFAULT_FLAGS.setdefault("membership_ui_enabled", False)
    for _coh in ("founder", "founder_exception"):
        v29_hardening.set_flag("founder_tier_enabled", True, cohort=_coh)
        v29_hardening.set_flag("g_credits_enabled", True, cohort=_coh)
        v29_hardening.set_flag("membership_ui_enabled", True, cohort=_coh)
    v29_hardening.set_flag("g_credits_enabled", True, cohort="terrace_1")
    v29_hardening.set_flag("membership_ui_enabled", True, cohort="terrace_1")
    yield None


@pytest.fixture
def flags_clean():
    """Like ``reset_stores`` but resets ONLY rate limits + feature flags
    (without re-applying the prod startup defaults). Use in unit tests of
    v29_hardening that assert default-off behavior."""
    import v29_hardening
    v29_hardening._reset_rate_limits_for_tests()
    v29_hardening._reset_flags_for_tests()
    yield None


@pytest.fixture
def manual_confirm(monkeypatch):
    """Disable mock-mode auto-confirm so PaymentIntents stay pending until
    the test explicitly fires the success/failure webhook. Used by v31
    tests that exercise the real async flow."""
    monkeypatch.setenv("CLARITYOS_MOCK_AUTO_CONFIRM", "0")
    yield None


# ===========================================================================
# PASS-6 Phase A — Automatic marker assignment for the three CI gates.
#
# Marker semantics (also documented in pytest.ini):
#   * runtime_spine       — BD1-BD5 cross-module stabilization tests.
#   * privacy_surface     — logging redaction, billing-surface redaction,
#                           forbidden-field stripping, plaintext guardrails.
#   * determinism_surface — router selection, founder-default vault
#                           consistency, operator_state seq, macro run-id,
#                           key-cache PBKDF2 determinism.
#
# Tagging is path-based so existing tests don't need per-function
# decorators. A test file may carry more than one marker — the union
# of every matching entry is applied. New PASS-6 invariant tests
# (test_runtime_inv_*.py) and module-load guards
# (test_module_load_guards.py) are tagged here so they participate in
# the same CI gates from the start.
# ===========================================================================
_FILE_MARKERS: dict[str, set[str]] = {
    # ---- Locked PASS-4 fix tests (existing) ----
    "test_founder_default_vault_persistence.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_fix_h6_provider_http_timeout_contextvar.py": {
        "runtime_spine",
    },
    "test_fix_h7_key_cache_ttl.py": {
        "runtime_spine", "privacy_surface", "determinism_surface",
    },
    "test_fix_p1_billing_surface_hardening.py": {
        "runtime_spine", "privacy_surface",
    },
    "test_fix_p2_migrate_strip_forbidden.py": {
        "runtime_spine", "privacy_surface", "determinism_surface",
    },
    "test_fix_p3_plaintext_vault_guardrails.py": {
        "runtime_spine", "privacy_surface",
    },
    "test_fix_p5_runtime_privacy.py": {
        "runtime_spine", "privacy_surface",
    },
    "test_b2_macro_seq_lock_preallocated.py": {
        "runtime_spine", "determinism_surface",
    },
    # ---- PASS-5 Phase D — concurrency + multi-instance ----
    "test_model_router_runtime.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_intelligence_kernel_runtime.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_operator_state_runtime.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_memory_vault_runtime.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_app_runtime_e2e.py": {
        "runtime_spine", "privacy_surface",
    },
    # ---- Pre-existing PASS-2/3 spine coverage (foundations) ----
    "test_v40_intelligence_kernel.py": {
        "runtime_spine",
    },
    "test_v44_model_router.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_v46_memory_vault.py": {
        "runtime_spine",
    },
    "test_v39_operator_state.py": {
        "runtime_spine",
    },
    "test_runtime_http_config.py": {
        "runtime_spine",
    },
    # ---- PASS-6 Phase A — explicit invariant tests ----
    "test_runtime_inv_http.py": {
        "runtime_spine", "privacy_surface",
    },
    "test_runtime_inv_kernel.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_runtime_inv_router.py": {
        "runtime_spine", "determinism_surface",
    },
    "test_runtime_inv_state.py": {
        "runtime_spine", "privacy_surface", "determinism_surface",
    },
    "test_runtime_inv_vault.py": {
        "runtime_spine", "privacy_surface", "determinism_surface",
    },
    # ---- PASS-6 Phase A — module-load guards ----
    "test_module_load_guards.py": {
        "runtime_spine", "determinism_surface",
    },
    # ---- PASS-6 Phase B — deployment-mode validation ----
    "test_deployment_runtime.py": {
        "runtime_spine", "privacy_surface", "determinism_surface",
    },
    # ---- PASS-6 Phase D — release engineering integrity ----
    # Release-integrity tests gate the version manifest, CHANGELOG,
    # release workflow, and release-notes source. They belong in the
    # runtime_spine gate because a release that misshapes any of these
    # surfaces should fail the same merge protection that a runtime
    # regression would.
    "test_release_integrity.py": {
        "runtime_spine",
    },
    # ---- PASS-7 — optional load + stress envelope ----
    # Tagged ONLY with ``load_envelope`` (deliberately not in the
    # default CI gate). Opt-in via ``pytest -m load_envelope``.
    "test_load_envelope.py": {
        "load_envelope",
    },
    # ---- PASS-6 Phase F — repository hygiene checks ----
    # Repository-shape gates (stray files, dependency freeze,
    # scaffolding presence). Belong in runtime_spine because a broken
    # repo shape blocks the same merges a runtime regression would.
    "test_repo_hygiene.py": {
        "runtime_spine",
    },
}


def pytest_collection_modifyitems(config, items):
    """PASS-6 Phase A — tag each collected test with the CI markers
    that correspond to its source file.

    Tagging is intentionally path-based (not per-function) so the
    existing tests don't need decorator churn. A test file can carry
    multiple markers; the union of all matching entries is applied.
    Files not in ``_FILE_MARKERS`` are left untouched so they don't
    accidentally drift into a gate they shouldn't be in.
    """
    for item in items:
        # ``item.path`` is a pathlib.Path on modern pytest; fall back
        # to ``fspath`` on older versions for safety.
        try:
            filename = item.path.name
        except AttributeError:  # pragma: no cover (legacy pytest)
            filename = os.path.basename(str(item.fspath))
        markers = _FILE_MARKERS.get(filename)
        if not markers:
            continue
        for marker_name in markers:
            item.add_marker(getattr(pytest.mark, marker_name))
