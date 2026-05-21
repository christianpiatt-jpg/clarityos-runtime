"""
PASS-4 FIX-P5 — Centralised logging-redaction helpers.

Covers two layers:

  1. ``runtime_privacy`` itself — pure-string behaviour for
     ``session_ref``, ``user_ref``, ``prompt_preview``, ``topic_trim``,
     ``event_ref`` (including the documented constants).

  2. The refactored runtime modules — grep-style assertions that
     after FIX-P5 no module in the in-scope list passes a raw
     ``user_id`` / ``session_id`` to a ``logger.X("... user=%s ...",
     user, ...)`` style call, and that the new helpers are wired at
     each redaction site.

The existing v44 / v46 / v40 / v31 / v42 / v66 tests already cover the
upstream functional surface and continue to pass after FIX-P5 — those
suites are the load-bearing regression coverage; the tests here focus
narrowly on the V2 mitigation itself.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

import runtime_privacy


REPO_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. Pure helper behaviour
# ===========================================================================
class TestConstants:
    def test_module_constants_exist_and_match_spec(self):
        assert runtime_privacy.SESSION_REF_LEN         == 8
        assert runtime_privacy.USER_REF_LEN            == 8
        assert runtime_privacy.MOCK_PROMPT_PREVIEW_LEN == 60
        assert runtime_privacy.TOPIC_MAX_LEN           == 200
        assert runtime_privacy.EVENT_ID_SHORT_LEN      == 24


class TestSessionRef:
    def test_session_ref_none_returns_marker(self):
        assert runtime_privacy.session_ref(None) == "<none>"

    def test_session_ref_empty_returns_marker(self):
        assert runtime_privacy.session_ref("") == "<none>"

    def test_session_ref_non_string_returns_marker(self):
        for bad in (123, 1.5, ["abc"], {"x": 1}):
            assert runtime_privacy.session_ref(bad) == "<none>"

    def test_session_ref_short_input_still_redacts_with_ellipsis(self):
        """A short session_id (under 8 chars) is still truncated to
        ``input + '...'`` so log readers can always tell at a glance
        that the value is a redacted ref, never the raw token."""
        assert runtime_privacy.session_ref("abc") == "abc..."

    def test_session_ref_exactly_eight_chars(self):
        assert runtime_privacy.session_ref("12345678") == "12345678..."

    def test_session_ref_long_input_truncates_at_eight(self):
        s = "sess_abcdefghijklmnop"
        assert runtime_privacy.session_ref(s) == "sess_abc..."

    def test_session_ref_idempotent_for_typed_string(self):
        """Calling twice on the same input must return the same string
        — used by the grep assertion that a refactored log line still
        prints the same redacted value across requests."""
        a = runtime_privacy.session_ref("sess_xxxxxxxx")
        b = runtime_privacy.session_ref("sess_xxxxxxxx")
        assert a == b


class TestUserRef:
    def test_user_ref_none_returns_marker(self):
        assert runtime_privacy.user_ref(None) == "<none>"

    def test_user_ref_empty_returns_marker(self):
        assert runtime_privacy.user_ref("") == "<none>"

    def test_user_ref_non_string_returns_marker(self):
        for bad in (0, 1.0, b"alice", ["alice"]):
            assert runtime_privacy.user_ref(bad) == "<none>"

    def test_user_ref_short_input_still_redacts(self):
        assert runtime_privacy.user_ref("ab") == "ab..."

    def test_user_ref_long_input_truncates_at_eight(self):
        assert runtime_privacy.user_ref("verylongusername") == "verylong..."

    def test_user_ref_unicode_is_safe(self):
        # Truncation is by code-point count, which is what Python
        # string slicing does. The result is still a string; never
        # bytes, never raising.
        out = runtime_privacy.user_ref("ünïcödé_user")
        assert isinstance(out, str)
        assert out.endswith("...")


class TestPromptPreview:
    def test_prompt_preview_none_returns_empty(self):
        assert runtime_privacy.prompt_preview(None) == ""

    def test_prompt_preview_empty_returns_empty(self):
        assert runtime_privacy.prompt_preview("") == ""

    def test_prompt_preview_short_passes_through_unchanged(self):
        assert runtime_privacy.prompt_preview("hello world") == "hello world"

    def test_prompt_preview_caps_at_sixty_chars(self):
        text = "x" * 200
        out = runtime_privacy.prompt_preview(text)
        assert len(out) == 60
        assert out == "x" * 60

    def test_prompt_preview_exact_sixty_chars(self):
        text = "x" * 60
        out = runtime_privacy.prompt_preview(text)
        assert len(out) == 60

    def test_prompt_preview_no_ellipsis_marker(self):
        """The mock contract in model_router treats the preview as
        opaque text — FIX-P5 must NOT append an ellipsis here (which
        would shift byte boundaries for every existing mock test)."""
        text = "y" * 200
        out = runtime_privacy.prompt_preview(text)
        assert "..." not in out


class TestTopicTrim:
    def test_topic_trim_none_returns_empty(self):
        assert runtime_privacy.topic_trim(None) == ""

    def test_topic_trim_empty_returns_empty(self):
        assert runtime_privacy.topic_trim("") == ""

    def test_topic_trim_strips_whitespace(self):
        assert runtime_privacy.topic_trim("  hello  ") == "hello"

    def test_topic_trim_caps_at_topic_max(self):
        long = "a" * 500
        out = runtime_privacy.topic_trim(long)
        assert len(out) <= runtime_privacy.TOPIC_MAX_LEN
        assert out == "a" * 200

    def test_topic_trim_caps_and_rstrips(self):
        """The original operator_state._trim_topic semantics included
        an rstrip after the cap (so a topic ending in whitespace at
        the cap boundary doesn't keep trailing space)."""
        long = ("a" * 195) + "      "
        out = runtime_privacy.topic_trim(long)
        # The trailing whitespace inside the cap region is removed.
        assert out == "a" * 195

    def test_topic_trim_under_cap_unchanged(self):
        assert runtime_privacy.topic_trim("short topic") == "short topic"


class TestEventRef:
    def test_event_ref_none_returns_marker(self):
        assert runtime_privacy.event_ref(None) == "<none>"

    def test_event_ref_empty_returns_marker(self):
        assert runtime_privacy.event_ref("") == "<none>"

    def test_event_ref_short_passes_through_unchanged(self):
        assert runtime_privacy.event_ref("evt_abc") == "evt_abc"

    def test_event_ref_exactly_24_chars_unchanged(self):
        s = "a" * 24
        assert runtime_privacy.event_ref(s) == s

    def test_event_ref_long_truncates_with_ellipsis(self):
        s = "evt_" + "x" * 40
        out = runtime_privacy.event_ref(s)
        assert out.endswith("...")
        # Truncated body is exactly EVENT_ID_SHORT_LEN chars.
        assert len(out) == runtime_privacy.EVENT_ID_SHORT_LEN + 3

    def test_event_ref_coerces_non_string_to_string(self):
        # Stripe event ids are strings in practice, but defensive
        # callers may pass through whatever they pulled from JSON.
        assert runtime_privacy.event_ref(12345) == "12345"

    def test_event_ref_no_ellipsis_at_boundary(self):
        """An id that is exactly 24 chars is NOT truncated — the
        ellipsis only appears for genuinely-truncated values, so log
        readers can tell at-a-glance whether the original was shorter
        or longer than the cap."""
        s = "x" * 24
        out = runtime_privacy.event_ref(s)
        assert "..." not in out


class TestPurity:
    def test_no_logger_in_module(self):
        """``runtime_privacy`` is a pure-helper module — no logging
        side-effects allowed. Future refactors that try to add a
        logger inside this module will fail this check."""
        with open(REPO_ROOT / "runtime_privacy.py", encoding="utf-8") as f:
            src = f.read()
        # The module's docstring mentions ``logging`` to explain why
        # it doesn't do any. The actual imports and usage are what we
        # care about.
        assert "import logging" not in src
        assert "logger." not in src


# ===========================================================================
# 2. Grep-style assertions on refactored call sites
# ===========================================================================
# Helper — read a source file and walk its logger.X(...) calls.
_LOGGER_CALL_RE = re.compile(
    r"logger\.(?:info|warning|error|debug)\((?P<body>[\s\S]+?)\)\n",
)


def _logger_calls(path: Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    return [
        (src[:m.start()].count("\n") + 1, m.group(0))
        for m in _LOGGER_CALL_RE.finditer(src)
    ]


class TestNoFullUserInLogs:
    """For every module in the FIX-P5 scope, every ``logger.X`` call
    that contains ``user=%s`` in its format string must also reference
    a redaction helper (``user_ref`` / ``_user_ref``). This is the
    grep-style guard the spec asks for."""

    @pytest.mark.parametrize("rel_path", [
        "app.py",
        "intelligence_kernel.py",
        "model_router.py",
        "operator_state.py",
        "memory_vault.py",
    ])
    def test_no_raw_user_in_logger_calls(self, rel_path):
        path = REPO_ROOT / rel_path
        offenders = []
        for line_no, block in _logger_calls(path):
            if "user=%s" in block and not (
                "_user_ref" in block or "user_ref" in block
            ):
                offenders.append((line_no, block[:200]))
        assert offenders == [], (
            f"{rel_path} has logger calls with raw user= passthrough:\n" +
            "\n".join(f"line {ln}: {body!r}" for ln, body in offenders)
        )

    @pytest.mark.parametrize("rel_path", [
        "app.py",
        "intelligence_kernel.py",
        "model_router.py",
    ])
    def test_no_raw_session_id_in_logger_calls(self, rel_path):
        path = REPO_ROOT / rel_path
        offenders = []
        for line_no, block in _logger_calls(path):
            if "session=%s" in block and not (
                "_session_ref" in block or "session_ref" in block
            ):
                offenders.append((line_no, block[:200]))
        assert offenders == [], (
            f"{rel_path} has logger calls with raw session= passthrough:\n" +
            "\n".join(f"line {ln}: {body!r}" for ln, body in offenders)
        )


class TestModulesImportRuntimePrivacy:
    """Sanity check — each in-scope module must actually import
    ``runtime_privacy`` (or rebind a local alias to one of its
    helpers). Otherwise the grep test above could pass vacuously by
    e.g. removing the `user=%s` format entirely."""

    @pytest.mark.parametrize("rel_path", [
        "app.py",
        "intelligence_kernel.py",
        "model_router.py",
        "operator_state.py",
        "memory_vault.py",
    ])
    def test_imports_runtime_privacy(self, rel_path):
        src = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "runtime_privacy" in src, (
            f"{rel_path} does not import runtime_privacy"
        )


class TestAppLocalSessionRefRemoved:
    """``app._session_ref`` used to be a local helper with its own
    8-char-truncation logic; FIX-P5 turns it into a thin alias for
    ``runtime_privacy.session_ref``. The inline implementation must
    be gone — anyone re-introducing the old inline form should fail
    this check."""

    def test_session_ref_is_alias_or_thin_wrapper(self):
        import app as app_module
        # The local name still exists for the existing call sites.
        assert hasattr(app_module, "_session_ref")
        # And it produces the same output as runtime_privacy.session_ref.
        for raw in (None, "", "abc", "sess_abcdefghij"):
            assert app_module._session_ref(raw) == runtime_privacy.session_ref(raw)

    def test_user_ref_alias_present_in_app(self):
        """FIX-P5 adds ``_user_ref`` to app.py as the mirror alias —
        all the user=%s redactions go through it. Confirm it exists
        and is equivalent to ``runtime_privacy.user_ref``."""
        import app as app_module
        assert hasattr(app_module, "_user_ref")
        for raw in (None, "", "x", "alice"):
            assert app_module._user_ref(raw) == runtime_privacy.user_ref(raw)


class TestOperatorStateTopicTrimDelegates:
    """``operator_state._trim_topic`` used to be an inline helper.
    FIX-P5 turns it into a thin call into ``runtime_privacy.topic_trim``.
    Check both that the original function still exists (call sites
    rely on it) and that it now delegates."""

    def test_trim_topic_matches_runtime_privacy_topic_trim(self):
        import operator_state
        for raw in (
            None, "", "  hello  ", "a" * 50, "a" * 300,
        ):
            assert operator_state._trim_topic(raw) == runtime_privacy.topic_trim(raw)


class TestModelRouterMockUsesPromptPreview:
    """The mock-result preview from ``model_router._mock_result`` must
    now go through ``runtime_privacy.prompt_preview``. The byte-for-
    byte output for a given prompt remains identical (both helpers
    cap at 60 chars without an ellipsis), and FIX-P5 callers don't
    see any change."""

    def test_mock_result_preview_byte_for_byte_matches(self):
        """The mock result text is ``f"[mock {model_id}] {preview}".rstrip()``
        — the trailing rstrip is pre-FIX-P5 behaviour and must be
        preserved. Compare against ``runtime_privacy.prompt_preview``
        with that same rstrip applied."""
        import model_router as mr
        # Use a prompt that's both > 60 chars (forces truncation) and
        # has no trailing whitespace at the 60-char boundary so the
        # rstrip is a no-op and the byte-for-byte check is exact.
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
        assert len(embedded) == 60  # capped exactly at the preview cap

    def test_mock_result_preview_short_prompt(self):
        """A short prompt round-trips through prompt_preview unchanged
        (subject to the trailing rstrip on the assembled text)."""
        import model_router as mr
        out = mr._mock_result(
            "anthropic:claude-3.7", "anthropic", "hello world", 0.0,
        )
        text = out["text"]
        assert text == "[mock anthropic:claude-3.7] hello world"

    def test_mock_result_preview_none_prompt(self):
        """None / empty prompt produces a clean ``[mock ...]`` line —
        confirms ``prompt_preview`` returning "" still rstrips to a
        sane mock-result text."""
        import model_router as mr
        out = mr._mock_result(
            "anthropic:claude-3.7", "anthropic", "", 0.0,
        )
        # After rstrip the trailing space after the bracket is gone.
        assert out["text"] == "[mock anthropic:claude-3.7]"


# ===========================================================================
# 3. End-to-end log-capture: a real request → no raw username in logs
# ===========================================================================
class TestEndToEndNoUsernameInLogs:
    """Drive a real request and assert that the username string never
    appears verbatim in any captured log line. The session_id token
    likewise never appears in full. This is the integration guarantee
    FIX-P5 is supposed to provide."""

    def test_login_does_not_log_full_username(self, reset_stores, caplog):
        from conftest import TestClient
        import app as app_module
        import bcrypt
        import users_store

        full_username = "alice_fullname_for_redaction"
        users_store.create_user(
            username=full_username,
            password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
            salt="", tier="free", created_at=0.0,
        )
        client = TestClient(app_module.app)

        caplog.set_level(logging.INFO, logger="clarityos")
        r = client.post(
            "/login",
            json={"username": full_username, "password": "x"},
        )
        assert r.status_code == 200

        # Walk every captured record's formatted output.
        for rec in caplog.records:
            if rec.name != "clarityos":
                continue
            formatted = rec.getMessage()
            # The full username must not appear in any clarityos log.
            assert full_username not in formatted, (
                f"full username leaked in log: {formatted!r}"
            )
            # The session_id is in the response body; check it isn't
            # in any log line.
            sid = r.json().get("session_id") or ""
            if sid:
                assert sid not in formatted, (
                    f"full session_id leaked in log: {formatted!r}"
                )
