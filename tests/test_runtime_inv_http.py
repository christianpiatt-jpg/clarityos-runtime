"""
PASS-6 Phase A — BD1 (app) architectural invariants.

Locked invariants covered:
    INV-H1 — No FIX-P5-scoped logger emits a raw user_id substring
             (grep-style AST/source-level guard)
    INV-H2 — Same for session_id
    INV-H3 — /billing/intent/confirm response field projection: only
             the safe field set; client_secret + raw metadata absent
    INV-H4 — /me/billing maps billing_state=="failed" → status="failed"
    INV-H5 — _session_ref / _user_ref are byte-identical aliases for
             runtime_privacy.session_ref / user_ref
"""
from __future__ import annotations

import re
import secrets
import time
from pathlib import Path

import pytest

import runtime_privacy


_FIXP5_MODULES = (
    "app.py",
    "intelligence_kernel.py",
    "model_router.py",
    "operator_state.py",
    "memory_vault.py",
)

_LOGGER_CALL_RE = re.compile(
    r"logger\.(?:info|warning|error|debug)\((?P<body>[\s\S]+?)\)\n",
)


def _logger_calls(path: Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    return [
        (src[:m.start()].count("\n") + 1, m.group(0))
        for m in _LOGGER_CALL_RE.finditer(src)
    ]


# ---------------------------------------------------------------------------
# INV-H1 — No raw user_id in FIX-P5-scoped logger calls
# ---------------------------------------------------------------------------
class TestINV_H1_NoRawUserIdInLoggers:
    @pytest.mark.parametrize("rel", _FIXP5_MODULES)
    def test_inv_h1_no_raw_user_passthrough(self, rel):
        path = Path(rel)
        offenders: list[tuple[int, str]] = []
        for line_no, block in _logger_calls(path):
            if "user=%s" in block and not (
                "_user_ref" in block or "user_ref" in block
            ):
                offenders.append((line_no, block[:200]))
        assert offenders == [], (
            f"INV-H1 violated — {rel} has logger calls with raw user= "
            f"passthrough:\n" +
            "\n".join(f"  line {ln}: {body!r}" for ln, body in offenders)
        )


# ---------------------------------------------------------------------------
# INV-H2 — No raw session_id in FIX-P5-scoped logger calls
# ---------------------------------------------------------------------------
class TestINV_H2_NoRawSessionIdInLoggers:
    # session= appears in app.py + intelligence_kernel.py + model_router.py.
    # operator_state + memory_vault don't have session-bearing log lines,
    # but we scan them anyway for defence in depth.
    @pytest.mark.parametrize("rel", _FIXP5_MODULES)
    def test_inv_h2_no_raw_session_passthrough(self, rel):
        path = Path(rel)
        offenders: list[tuple[int, str]] = []
        for line_no, block in _logger_calls(path):
            if "session=%s" in block and not (
                "_session_ref" in block or "session_ref" in block
            ):
                offenders.append((line_no, block[:200]))
        assert offenders == [], (
            f"INV-H2 violated — {rel} has logger calls with raw session= "
            f"passthrough:\n" +
            "\n".join(f"  line {ln}: {body!r}" for ln, body in offenders)
        )


# ---------------------------------------------------------------------------
# INV-H3 — /billing/intent/confirm response field projection
# ---------------------------------------------------------------------------
class TestINV_H3_BillingConfirmFieldProjection:
    _SAFE_FIELDS: frozenset[str] = frozenset({
        "intent_id", "status", "amount", "kind", "mode",
        "description", "created_ts", "confirmed_ts",
        "failed_ts", "failure_code",
    })
    _FORBIDDEN_FIELDS: frozenset[str] = frozenset({
        "client_secret", "metadata",
    })

    @pytest.fixture
    def app_module(self, reset_stores):
        import app as app_module
        return app_module

    @pytest.fixture
    def client(self, app_module):
        from conftest import TestClient
        return TestClient(app_module.app)

    def _make_user(self, username="inv_h3_user"):
        import bcrypt
        import sessions_store
        import users_store
        pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
        users_store.create_user(
            username=username, password_hash=pwd_hash, salt="",
            tier="free", created_at=time.time(),
        )
        users_store.update_user(username, {"cohort": "founder"})
        sid = "sess_" + secrets.token_urlsafe(16)
        sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
        return username, sid

    def test_inv_h3_response_carries_only_safe_fields(
        self, app_module, client, manual_confirm,
    ):
        import billing_intents
        user, sid = self._make_user("inv_h3_a")
        intent = billing_intents.create_payment_intent(
            user, 1.0, "x", kind="g_credit_single",
            metadata={"secret_marker": "should-never-leak"},
        )

        r = client.post(
            "/billing/intent/confirm",
            headers={"X-Session-ID": sid},
            json={"intent_id": intent["intent_id"]},
        )
        assert r.status_code == 200
        body = r.json()
        intent_block = body["intent"]
        actual_keys = set(intent_block.keys())

        # Every field in the response is in the allow-list.
        unexpected = actual_keys - self._SAFE_FIELDS
        assert unexpected == set(), (
            f"INV-H3 violated — /billing/intent/confirm response carries "
            f"unexpected fields {unexpected!r}"
        )

        # No forbidden field appears at any depth.
        for forbidden in self._FORBIDDEN_FIELDS:
            assert forbidden not in repr(body), (
                f"INV-H3 violated — {forbidden!r} appears in response body"
            )

        # And the marker we stuffed into metadata isn't in the response.
        assert "should-never-leak" not in repr(body)


# ---------------------------------------------------------------------------
# INV-H4 — /me/billing failed→failed mapping
# ---------------------------------------------------------------------------
class TestINV_H4_MeBillingFailedMapping:
    @pytest.fixture
    def app_module(self, reset_stores):
        import app as app_module
        return app_module

    @pytest.fixture
    def client(self, app_module):
        from conftest import TestClient
        return TestClient(app_module.app)

    def _make_user(self, username, billing_state):
        import bcrypt
        import sessions_store
        import users_store
        pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
        users_store.create_user(
            username=username, password_hash=pwd_hash, salt="",
            tier="free", created_at=time.time(),
        )
        users_store.update_user(
            username, {"cohort": "founder", "billing_state": billing_state},
        )
        sid = "sess_" + secrets.token_urlsafe(16)
        sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
        return username, sid

    @pytest.mark.parametrize("state,expected", [
        ("active",       "active"),
        ("past_due",     "past_due"),
        ("grace_period", "grace_period"),
        ("cancelled",    "canceled"),
        ("failed",       "failed"),    # The PASS-4 FIX-P1 distinction.
    ])
    def test_inv_h4_mapping_table(self, app_module, client, state, expected):
        user, sid = self._make_user(f"inv_h4_{state}", state)
        r = client.get("/me/billing", headers={"X-Session-ID": sid})
        assert r.status_code == 200
        assert r.json()["status"] == expected, (
            f"INV-H4 violated — billing_state={state!r} mapped to "
            f"{r.json()['status']!r}, expected {expected!r}"
        )


# ---------------------------------------------------------------------------
# INV-H5 — _session_ref / _user_ref are byte-identical aliases
# ---------------------------------------------------------------------------
class TestINV_H5_LocalHelpersAreAliases:
    @pytest.mark.parametrize("raw", [
        None, "", "x", "alice", "ünïcödé_user", "sess_abcdefghijklmn",
    ])
    def test_inv_h5_session_ref_matches_runtime_privacy(self, raw):
        import app as app_module
        assert app_module._session_ref(raw) == runtime_privacy.session_ref(raw)

    @pytest.mark.parametrize("raw", [
        None, "", "x", "alice", "very_long_username_xx",
    ])
    def test_inv_h5_user_ref_matches_runtime_privacy(self, raw):
        import app as app_module
        assert app_module._user_ref(raw) == runtime_privacy.user_ref(raw)
