"""
PASS-6 Phase A — BD3 (model_router) architectural invariants.

Locked invariants covered:
    INV-R1 — select_model precedence: explicit override > founder
             default > operator_state.preferred_model > task default.
             "auto" sentinel falls through.
    INV-R2 — Founder default is vault-backed (cache cleared → next
             read pulls from vault, byte-for-byte same value)
    INV-R3 — Provider HTTP timeout is per-context via ContextVar;
             default = runtime_http_config.DEFAULT_CALL_TIMEOUT
    INV-R4 — _mock_result uses runtime_privacy.prompt_preview (byte-
             stable mock contract)
    INV-R5 — resolve_model_alias case rules + unknown returns None
    INV-R6 — _PROVIDER_HTTP_TIMEOUT readable via module __getattr__
"""
from __future__ import annotations

import pytest

import memory_vault
import model_router as mr
import runtime_http_config as rhc
import runtime_privacy


# ---------------------------------------------------------------------------
# INV-R1 — select_model precedence as a direct 16-cell matrix
# ---------------------------------------------------------------------------
class TestINV_R1_SelectModelPrecedence:
    """Enumerate every combination of (override, founder, preferred,
    task) and assert the documented winner. Failure indicates the
    precedence chain has drifted."""

    _OVERRIDE = "anthropic:claude-3.7"
    _FOUNDER  = "google:gemini-2.0-flash"
    _PREF     = "openai:gpt-4o"
    _TASK     = "c"  # → openai:gpt-4o-mini per TASK_DEFAULTS

    def _setup(
        self,
        *,
        override: bool,
        founder: bool,
        preferred: bool,
    ) -> tuple[str | None, str]:
        if founder:
            mr.set_founder_default_model(self._FOUNDER)
        if preferred:
            import operator_state
            operator_state.set_preferred_model("inv_r1_user", self._PREF)
        return (self._OVERRIDE if override else None), self._TASK

    @pytest.mark.parametrize("override,founder,preferred,expected", [
        # Override always wins, no matter what else is set.
        (True,  True,  True,  _OVERRIDE),
        (True,  True,  False, _OVERRIDE),
        (True,  False, True,  _OVERRIDE),
        (True,  False, False, _OVERRIDE),
        # No override → founder wins.
        (False, True,  True,  _FOUNDER),
        (False, True,  False, _FOUNDER),
        # No override, no founder → preferred_model wins.
        (False, False, True,  _PREF),
        # No override, no founder, no pref → task default.
        (False, False, False, "openai:gpt-4o-mini"),
    ])
    def test_inv_r1_precedence_matrix(
        self, reset_stores, override, founder, preferred, expected,
    ):
        override_id, task = self._setup(
            override=override, founder=founder, preferred=preferred,
        )
        chosen = mr.select_model(
            "inv_r1_user", task=task, override=override_id,
        )
        assert chosen == expected, (
            f"INV-R1 violated — (override={override}, founder={founder}, "
            f"preferred={preferred}) selected {chosen!r}, expected {expected!r}"
        )

    def test_inv_r1_auto_sentinel_falls_through(self, reset_stores):
        chosen = mr.select_model(None, task="c", override="auto")
        assert chosen == mr.TASK_DEFAULTS["c"]
        assert chosen != "auto"

    def test_inv_r1_unknown_override_raises(self, reset_stores):
        with pytest.raises(ValueError):
            mr.select_model(None, task="ELINS", override="not_a_model")


# ---------------------------------------------------------------------------
# INV-R2 — Founder default is vault-backed
# ---------------------------------------------------------------------------
class TestINV_R2_FounderDefaultVaultBacked:
    def test_inv_r2_set_writes_to_vault(self, reset_stores):
        mr.set_founder_default_model("openai:gpt-4o")
        stored = memory_vault.vault_get(
            mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
        )
        assert stored == "openai:gpt-4o", (
            "INV-R2 violated — set_founder_default_model did not "
            "persist to the vault"
        )

    def test_inv_r2_fresh_process_reads_from_vault(self, reset_stores):
        mr.set_founder_default_model("anthropic:claude-3.7")

        # Simulate fresh process — clear cache only, leave vault alone.
        mr._founder_default_model = None
        mr._founder_default_loaded = False

        assert mr.get_founder_default_model() == "anthropic:claude-3.7", (
            "INV-R2 violated — cache reload did not consult the vault"
        )

    def test_inv_r2_clear_removes_vault_entry(self, reset_stores):
        mr.set_founder_default_model("openai:gpt-4o")
        mr.set_founder_default_model(None)
        assert memory_vault.vault_get(
            mr._FOUNDER_GLOBAL_USER_ID, mr._FOUNDER_DEFAULT_KEY,
        ) is None, (
            "INV-R2 violated — clearing did not remove the vault entry"
        )


# ---------------------------------------------------------------------------
# INV-R3 — Provider HTTP timeout is per-context via ContextVar
# ---------------------------------------------------------------------------
class TestINV_R3_ContextVarTimeout:
    def test_inv_r3_default_equals_runtime_http_config(self, reset_stores):
        assert mr._PROVIDER_HTTP_TIMEOUT_DEFAULT == rhc.DEFAULT_CALL_TIMEOUT
        assert mr._PROVIDER_HTTP_TIMEOUT_VAR.get() == rhc.DEFAULT_CALL_TIMEOUT

    def test_inv_r3_request_timeout_scopes_override(self, reset_stores):
        prior = mr._PROVIDER_HTTP_TIMEOUT
        with mr._request_timeout(11.0):
            assert mr._PROVIDER_HTTP_TIMEOUT == 11.0
        assert mr._PROVIDER_HTTP_TIMEOUT == prior

    def test_inv_r3_nested_overrides_restore_lifo(self, reset_stores):
        with mr._request_timeout(10.0):
            with mr._request_timeout(20.0):
                assert mr._PROVIDER_HTTP_TIMEOUT == 20.0
            assert mr._PROVIDER_HTTP_TIMEOUT == 10.0
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT


# ---------------------------------------------------------------------------
# INV-R4 — _mock_result uses runtime_privacy.prompt_preview
# ---------------------------------------------------------------------------
class TestINV_R4_MockResultUsesPromptPreview:
    def test_inv_r4_preview_matches_runtime_privacy(self, reset_stores):
        long_prompt = ("x" * 30) + ("y" * 200)
        out = mr._mock_result(
            "anthropic:claude-3.7", "anthropic", long_prompt, 0.0,
        )
        text = out["text"]
        lead = "[mock anthropic:claude-3.7] "
        assert text.startswith(lead)
        embedded = text[len(lead):]
        expected = runtime_privacy.prompt_preview(long_prompt).rstrip()
        assert embedded == expected
        assert len(embedded) == runtime_privacy.MOCK_PROMPT_PREVIEW_LEN


# ---------------------------------------------------------------------------
# INV-R5 — resolve_model_alias contract
# ---------------------------------------------------------------------------
class TestINV_R5_ResolveModelAlias:
    @pytest.mark.parametrize("alias,canonical", [
        ("claude",       "anthropic:claude-3.7"),
        ("CLAUDE",       "anthropic:claude-3.7"),
        ("Claude",       "anthropic:claude-3.7"),
        ("gpt",          "openai:gpt-4o"),
        ("gemini",       "google:gemini-2.0-flash"),
        ("groq",         "xai:groq-llama"),
        ("local",        "local:llama3.1"),
    ])
    def test_inv_r5_aliases_case_insensitive(self, alias, canonical):
        assert mr.resolve_model_alias(alias) == canonical

    def test_inv_r5_canonical_ids_case_sensitive(self):
        # Canonical id matches exactly.
        assert mr.resolve_model_alias("openai:gpt-4o") == "openai:gpt-4o"
        # Case-mangled canonical id falls through to alias map (None
        # for unknown alias).
        assert mr.resolve_model_alias("OPENAI:gpt-4o") is None

    def test_inv_r5_unknown_returns_none(self):
        assert mr.resolve_model_alias(None) is None
        assert mr.resolve_model_alias("") is None
        assert mr.resolve_model_alias("   ") is None
        assert mr.resolve_model_alias("totally_made_up") is None


# ---------------------------------------------------------------------------
# INV-R6 — _PROVIDER_HTTP_TIMEOUT readable via module __getattr__
# ---------------------------------------------------------------------------
class TestINV_R6_LegacyAttributeShim:
    def test_inv_r6_legacy_attribute_returns_contextvar_get(self, reset_stores):
        v = mr._PROVIDER_HTTP_TIMEOUT
        assert isinstance(v, float)
        assert v == mr._PROVIDER_HTTP_TIMEOUT_VAR.get()

    def test_inv_r6_unknown_attribute_raises(self):
        with pytest.raises(AttributeError):
            _ = mr._does_not_exist_xyz   # type: ignore[attr-defined]
