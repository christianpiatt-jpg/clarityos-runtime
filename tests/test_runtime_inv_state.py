"""
PASS-6 Phase A — BD4 (operator_state) architectural invariants.

Locked invariants covered:
    INV-S1 — _next_seq is strictly monotonic per prefix under _SEQ_LOCK
    INV-S2 — HISTORY_MAX = 200 enforced on every persist path
             (live record_* via _prune_history; migration via the
             FIX-P2 sort + slice in migrate_operator_state_to_vault)
    INV-S3 — _strip_forbidden removes exactly the four documented keys
             {text, scenario_text, input_text, raw_text} and leaves
             every other key untouched
    INV-S4 — _trim_topic delegates to runtime_privacy.topic_trim
    INV-S5 — operator_state has no persistence dep outside memory_vault
"""
from __future__ import annotations

from pathlib import Path

import pytest

import memory_vault
import operator_state
import runtime_privacy


# ---------------------------------------------------------------------------
# INV-S1 — Monotonic _next_seq under _SEQ_LOCK
# ---------------------------------------------------------------------------
class TestINV_S1_NextSeqMonotonic:
    def test_inv_s1_returns_strictly_increasing_per_prefix(self, reset_stores):
        seen = [operator_state._next_seq("inv_s1") for _ in range(10)]
        assert seen == list(range(1, 11)), (
            f"INV-S1 violated — _next_seq not strictly monotonic: {seen}"
        )

    def test_inv_s1_distinct_prefixes_have_independent_counters(
        self, reset_stores,
    ):
        a = [operator_state._next_seq("inv_s1_a") for _ in range(5)]
        b = [operator_state._next_seq("inv_s1_b") for _ in range(3)]
        assert a == [1, 2, 3, 4, 5]
        assert b == [1, 2, 3]


# ---------------------------------------------------------------------------
# INV-S2 — HISTORY_MAX enforced on live + migration paths
# ---------------------------------------------------------------------------
class TestINV_S2_HistoryMaxCap:
    def test_inv_s2_constant_is_200(self):
        assert operator_state.HISTORY_MAX == 200

    def test_inv_s2_migration_caps_oversize_history(self, reset_stores):
        """The FIX-P2 mitigation: a migration that would persist more
        than HISTORY_MAX rows must trim to the newest HISTORY_MAX
        before writing. This is the architectural guarantee, asserted
        directly against the migration helper."""
        cap = operator_state.HISTORY_MAX
        overage = cap + 50
        legacy = {
            "elins_history": [
                {"ts": 1_700_000_000.0 + i,
                 "elins_id": f"e_{i:04d}", "topic": f"t_{i:04d}"}
                for i in range(overage)
            ],
        }
        operator_state.migrate_operator_state_to_vault("inv_s2", legacy)

        # Count persisted entries under the elins.* prefix.
        all_entries = memory_vault.vault_list("inv_s2")
        elins_count = sum(1 for k in all_entries if k.startswith("elins."))
        assert elins_count == cap, (
            f"INV-S2 violated — migration persisted {elins_count} rows; "
            f"HISTORY_MAX={cap}"
        )

    def test_inv_s2_live_writes_cap_at_history_max(self, reset_stores):
        """Live ``record_elins_interaction`` calls trigger
        ``_prune_history`` after each write — so the persisted count
        never exceeds HISTORY_MAX even under sustained writes."""
        cap = operator_state.HISTORY_MAX
        for i in range(cap + 25):
            operator_state.record_elins_interaction(
                "inv_s2_live", f"elins_{i}",
                context={"topic": f"t_{i}", "kind": "global"},
            )
        all_entries = memory_vault.vault_list("inv_s2_live")
        elins_count = sum(1 for k in all_entries if k.startswith("elins."))
        assert elins_count <= cap, (
            f"INV-S2 violated — live writes persisted {elins_count} > {cap}"
        )


# ---------------------------------------------------------------------------
# INV-S3 — _strip_forbidden behaviour pinned
# ---------------------------------------------------------------------------
class TestINV_S3_StripForbidden:
    _FORBIDDEN: frozenset[str] = frozenset({
        "text", "scenario_text", "input_text", "raw_text",
    })

    def test_inv_s3_removes_exactly_the_documented_keys(self):
        legacy = {
            "ts": 1.0,
            "elins_id": "e",
            "topic": "t",
            "kind": "global",
            "text": "PROMPT BODY",
            "scenario_text": "SCENARIO BODY",
            "input_text": "INPUT BODY",
            "raw_text": "RAW BODY",
        }
        clean = operator_state._strip_forbidden(legacy)
        for k in self._FORBIDDEN:
            assert k not in clean, (
                f"INV-S3 violated — {k!r} survived _strip_forbidden"
            )
        # Every other key survives byte-for-byte.
        for k, v in legacy.items():
            if k in self._FORBIDDEN:
                continue
            assert clean.get(k) == v, (
                f"INV-S3 violated — non-forbidden key {k!r} was altered"
            )

    def test_inv_s3_returns_independent_dict(self):
        """The helper must return a copy; mutating the original after
        the call must not leak through."""
        legacy = {"topic": "t", "text": "x"}
        clean = operator_state._strip_forbidden(legacy)
        legacy["topic"] = "MUTATED"
        assert clean["topic"] == "t"

    def test_inv_s3_handles_none_and_empty(self):
        assert operator_state._strip_forbidden(None) == {}
        assert operator_state._strip_forbidden({}) == {}


# ---------------------------------------------------------------------------
# INV-S4 — _trim_topic delegates to runtime_privacy.topic_trim
# ---------------------------------------------------------------------------
class TestINV_S4_TrimTopicDelegation:
    @pytest.mark.parametrize("raw", [
        None, "", "  hello  ", "x" * 300, "topic with    inner whitespace",
    ])
    def test_inv_s4_byte_for_byte_equivalence(self, raw):
        assert operator_state._trim_topic(raw) == runtime_privacy.topic_trim(raw)


# ---------------------------------------------------------------------------
# INV-S5 — operator_state depends only on memory_vault for persistence
# ---------------------------------------------------------------------------
class TestINV_S5_PersistenceDependency:
    _DISALLOWED_PERSISTENCE_MODULES: frozenset[str] = frozenset({
        "users_store",
        "sessions_store",
        "library_store",
        "timeline_store",
        "envelopes_store",
        "trajectories_store",
        "markov_states_store",
        "incident_store",
        "vault_store",   # legacy v1 module — operator_state must use memory_vault, not vault_store
        "membership_store",
        "elins_distribution_store",
        "mesh_metadata_store",
        "dewey_neighborhoods_store",
        "dewey_memberships_store",
        "dm_store",
        "waitlist_store",
        "invites_store",
        "embeddings_cache_store",
        "usage_store",
    })

    def test_inv_s5_no_other_persistence_imports(self):
        """``operator_state.py`` must not import any persistence
        module other than ``memory_vault``. Lock this with a grep-style
        source scan — any new persistence dep here is an architectural
        decision that needs review."""
        src = Path("operator_state.py").read_text(encoding="utf-8")
        offenders: list[str] = []
        for mod in self._DISALLOWED_PERSISTENCE_MODULES:
            # Match ``import mod`` / ``from mod import`` patterns —
            # word-boundary so ``import memory_vault`` doesn't match
            # ``import vault_store``.
            if (
                f"import {mod}" in src
                or f"from {mod} " in src
                or f"from {mod}\n" in src
            ):
                offenders.append(mod)
        assert offenders == [], (
            "INV-S5 violated — operator_state.py imports forbidden "
            f"persistence modules: {offenders!r}"
        )

    def test_inv_s5_memory_vault_is_imported(self):
        """And the one sanctioned dep IS present."""
        src = Path("operator_state.py").read_text(encoding="utf-8")
        assert "import memory_vault" in src
