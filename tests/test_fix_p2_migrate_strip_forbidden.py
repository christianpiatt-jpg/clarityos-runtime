"""
PASS-4 FIX-P2 — ``migrate_operator_state_to_vault`` reapplies
``_strip_forbidden`` and respects ``HISTORY_MAX``.

The pre-fix migration path persisted legacy ELINS / #G history entries
verbatim, meaning a snapshot that carried prompt-bearing fields
(``text``, ``scenario_text``, ``input_text``, ``raw_text``) would seed
the vault with those bodies even though identical fields would be
stripped on every live write via ``record_elins_interaction`` /
``record_g_run``. The pre-fix code also didn't enforce
``HISTORY_MAX``, so a snapshot with thousands of legacy entries could
inflate the vault beyond what the runtime read path will ever surface.

The fix runs every legacy history entry through ``_strip_forbidden``
and caps each bucket at ``HISTORY_MAX`` (newest kept) before writing.

These tests focus narrowly on the V2 mitigation; the existing v39 /
v46 / v51 tests cover the rest of the operator_state surface and
continue to pass unchanged.
"""
from __future__ import annotations

import time

import pytest

import memory_vault
import operator_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _vault_history(user_id: str, prefix: str) -> list[dict]:
    """Return every vault entry under ``prefix`` for ``user_id``,
    sorted oldest→newest. Used to assert what actually landed in the
    vault after migration."""
    all_entries = memory_vault.vault_list(user_id)
    out = [
        v for k, v in all_entries.items()
        if k.startswith(prefix) and isinstance(v, dict)
    ]
    out.sort(key=lambda x: float(x.get("ts") or 0.0))
    return out


# ---------------------------------------------------------------------------
# Test A — Forbidden fields stripped on migration
# ---------------------------------------------------------------------------
class TestForbiddenStripping:
    def test_text_bearing_fields_stripped_from_elins_history(self, reset_stores):
        """The four documented forbidden keys (``text``,
        ``scenario_text``, ``input_text``, ``raw_text``) must NOT
        appear in any vault entry created from a legacy snapshot."""
        legacy = {
            "elins_history": [
                {
                    "ts": 1_700_000_000.0,
                    "elins_id": "elins_a",
                    "topic": "trust between partners",
                    "text": "FULL PROMPT BODY — SHOULD NOT LEAK",
                    "scenario_text": "scenario body — also leakable",
                    "input_text": "raw input from user",
                    "raw_text": "anything ending in _text",
                    "kind": "global",
                },
                {
                    "ts": 1_700_000_100.0,
                    "elins_id": "elins_b",
                    "topic": "later entry",
                    "text": "another body",
                    "region": "US",
                    "kind": "regional",
                },
            ],
            "g_history": [
                {
                    "ts": 1_700_000_050.0,
                    "g_id": "g_a",
                    "mode": "G",
                    "topic": "g run",
                    "text": "G prompt body",
                    "input_text": "operator question",
                },
            ],
        }
        operator_state.migrate_operator_state_to_vault("alice", legacy)

        # Walk every persisted history entry directly via vault_list
        # so we see exactly what landed at rest — not what the
        # operator_state read path filters back out.
        elins_persisted = _vault_history("alice", "elins.")
        g_persisted = _vault_history("alice", "g_runs.")

        assert len(elins_persisted) == 2
        assert len(g_persisted) == 1

        for entry in elins_persisted + g_persisted:
            for forbidden in ("text", "scenario_text", "input_text", "raw_text"):
                assert forbidden not in entry, (
                    f"{forbidden!r} survived migration: {entry!r}"
                )

    def test_non_forbidden_fields_survive_unchanged(self, reset_stores):
        """``_strip_forbidden`` only removes the four documented keys.
        Topic, region, kind, elins_id, ts must all survive."""
        legacy = {
            "elins_history": [
                {
                    "ts": 1_700_000_000.0,
                    "elins_id": "elins_a",
                    "topic": "trust between partners",
                    "region": "US",
                    "kind": "regional",
                    "text": "should be stripped",
                },
            ],
        }
        operator_state.migrate_operator_state_to_vault("bob", legacy)
        [entry] = _vault_history("bob", "elins.")
        assert entry["elins_id"] == "elins_a"
        assert entry["topic"] == "trust between partners"
        assert entry["region"] == "US"
        assert entry["kind"] == "regional"
        assert entry["ts"] == 1_700_000_000.0
        assert "text" not in entry

    def test_state_read_after_migration_has_no_forbidden_fields(self, reset_stores):
        """End-to-end check: the canonical view of state returned by
        ``get_operator_state`` after a migration must also be free of
        the forbidden keys (defence-in-depth — this is what every
        kernel/operator_state consumer actually reads)."""
        legacy = {
            "elins_history": [
                {
                    "ts": 1_700_000_000.0,
                    "elins_id": "elins_a",
                    "topic": "x",
                    "text": "leakable body",
                    "raw_text": "another leakable body",
                },
            ],
        }
        state = operator_state.migrate_operator_state_to_vault("carol", legacy)
        for entry in state.get("elins_history") or []:
            for forbidden in ("text", "scenario_text", "input_text", "raw_text"):
                assert forbidden not in entry


# ---------------------------------------------------------------------------
# Test B — HISTORY_MAX respected
# ---------------------------------------------------------------------------
class TestHistoryMaxCap:
    def test_elins_history_capped_at_history_max(self, reset_stores):
        """A legacy snapshot with more than ``HISTORY_MAX`` entries must
        be trimmed to that cap before persistence — keeping the newest
        rows, dropping the oldest. Matches ``_list_history`` /
        ``_prune_history`` semantics so the read path always sees the
        same number of rows that ever landed."""
        cap = operator_state.HISTORY_MAX
        overage = cap + 50
        # ts increases monotonically — entry 0 is the oldest.
        legacy = {
            "elins_history": [
                {
                    "ts": 1_700_000_000.0 + i,
                    "elins_id": f"elins_{i:04d}",
                    "topic": f"topic_{i:04d}",
                    "kind": "global",
                }
                for i in range(overage)
            ],
        }
        operator_state.migrate_operator_state_to_vault("dave", legacy)

        persisted = _vault_history("dave", "elins.")
        assert len(persisted) == cap, (
            f"expected exactly HISTORY_MAX={cap} entries, got {len(persisted)}"
        )
        # The newest entries are kept; the oldest are dropped.
        # Oldest surviving id corresponds to index = overage - cap.
        oldest = persisted[0]
        newest = persisted[-1]
        assert oldest["elins_id"] == f"elins_{overage - cap:04d}"
        assert newest["elins_id"] == f"elins_{overage - 1:04d}"

    def test_g_history_capped_independently(self, reset_stores):
        """The cap applies per bucket — large g_history doesn't shrink
        elins_history and vice versa."""
        cap = operator_state.HISTORY_MAX
        legacy = {
            "elins_history": [
                {"ts": 1_700_000_000.0 + i, "elins_id": f"e_{i}", "topic": f"t_{i}"}
                for i in range(5)
            ],
            "g_history": [
                {"ts": 1_700_000_500.0 + i, "g_id": f"g_{i}", "mode": "G",
                 "topic": f"gt_{i}"}
                for i in range(cap + 20)
            ],
        }
        operator_state.migrate_operator_state_to_vault("emma", legacy)

        elins_persisted = _vault_history("emma", "elins.")
        g_persisted = _vault_history("emma", "g_runs.")
        assert len(elins_persisted) == 5
        assert len(g_persisted) == cap

    def test_under_cap_persists_all_entries(self, reset_stores):
        """A snapshot smaller than HISTORY_MAX is migrated in full."""
        legacy = {
            "elins_history": [
                {"ts": 1_700_000_000.0 + i, "elins_id": f"e_{i}", "topic": f"t_{i}"}
                for i in range(7)
            ],
        }
        operator_state.migrate_operator_state_to_vault("frank", legacy)
        assert len(_vault_history("frank", "elins.")) == 7


# ---------------------------------------------------------------------------
# Test C — No regression for already-clean data
# ---------------------------------------------------------------------------
class TestNoRegressionForCleanData:
    def test_clean_entries_pass_through_unchanged(self, reset_stores):
        """A legacy snapshot that already conforms (no forbidden keys,
        under the cap) is migrated byte-for-byte. The migration does
        not invent fields, drop legal fields, or mangle values."""
        legacy = {
            "elins_history": [
                {
                    "ts": 1_700_000_001.0,
                    "elins_id": "ok_1",
                    "topic": "clean entry",
                    "region": "EU",
                    "kind": "regional",
                },
                {
                    "ts": 1_700_000_002.0,
                    "elins_id": "ok_2",
                    "topic": "second clean entry",
                    "kind": "global",
                },
            ],
            "g_history": [
                {
                    "ts": 1_700_000_003.0,
                    "g_id": "g_clean",
                    "mode": "G",
                    "topic": "clean g",
                },
            ],
        }
        operator_state.migrate_operator_state_to_vault("grace", legacy)
        elins_persisted = _vault_history("grace", "elins.")
        g_persisted = _vault_history("grace", "g_runs.")

        assert elins_persisted == legacy["elins_history"]
        assert g_persisted == legacy["g_history"]

    def test_scalar_fields_migrated_unchanged(self, reset_stores):
        """The non-history scalar/dict fields keep their pre-FIX-P2
        migration behaviour: external_signal_mode, preferred_*, etc.,
        all land in the vault and surface via ``get_operator_state``."""
        legacy = {
            "external_signal_mode": "cloud_perplexity",
            "preferred_domains": {"trust": 1.0, "supply": 0.5},
            "preferred_regions": {"US": 1.0},
            "preferred_model":   "openai:gpt-5.4",
            "last_model_used":   "anthropic:claude-haiku-4-5-20251001",
            "local_model_usage_count": 12,
            "created_ts":      1_699_000_000.0,
            "last_active_ts":  1_700_000_000.0,
            "elins_history":   [],
            "g_history":       [],
        }
        state = operator_state.migrate_operator_state_to_vault(
            "henry", legacy,
        )
        assert state["external_signal_mode"] == "cloud_perplexity"
        assert state["preferred_domains"]    == {"trust": 1.0, "supply": 0.5}
        assert state["preferred_regions"]    == {"US": 1.0}
        assert state["preferred_model"]      == "openai:gpt-5.4"
        assert state["last_model_used"]      == "anthropic:claude-haiku-4-5-20251001"
        assert state["local_model_usage_count"] == 12
        assert state["created_ts"]      == 1_699_000_000.0
        assert state["last_active_ts"]  == 1_700_000_000.0

    def test_migration_is_deterministic_for_same_input(self, reset_stores):
        """Two users given the same legacy snapshot produce identical
        per-entry content in the vault. The vault keys differ (the
        history sequence counter is a process-global monotonic int by
        v46 design — that pre-existed FIX-P2), but the dict payload
        landing under each key is identical."""
        legacy = {
            "elins_history": [
                {"ts": 1_700_000_000.0 + i, "elins_id": f"e_{i}",
                 "topic": f"t_{i}", "text": "should be stripped"}
                for i in range(5)
            ],
        }
        operator_state.migrate_operator_state_to_vault("ida_1", legacy)
        operator_state.migrate_operator_state_to_vault("ida_2", legacy)
        h1 = _vault_history("ida_1", "elins.")
        h2 = _vault_history("ida_2", "elins.")
        # Same number of rows, same per-entry contents, in the same order.
        assert h1 == h2
        # And the forbidden field is gone from both.
        for entry in h1 + h2:
            assert "text" not in entry
