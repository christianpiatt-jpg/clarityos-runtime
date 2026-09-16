"""
Housekeeping "held at tag" (COW-1 2026-09-16, ruled CT-1) -- the backend half.

#113  the cockpit thread panels send thread_id: a run on any thread the member
      owns records a turn, and the ELINS wire's _meta.n_points counts that
      thread's scored turns, floored at 1 (a read that happened is one point,
      never 0): 1 after one or two reads, 2 after three -- so n > 1 after the
      panel's ELINS + physics + ELINS on one thread; no thread, or a thread
      the member does not own, is 1 (never a 500). Scored vs recorded turns
      is CT-1's ruling (the RETURN names it).
#154  app._user_ref is a HASH (runtime_privacy.user_hash == users_store._uref),
      never the address prefix runtime_privacy.user_ref returns; an absent id
      keeps "<none>"; no logger call in app.py -- or in any runtime module
      (root, el_ins, ELINS) -- carries a bare identity; v29_hardening's
      structured line carries the same hash (it was a 12-char prefix); the
      prefix helper has no caller left in the runtime tree.
"""
from __future__ import annotations

import ast
import json
import re
import secrets
import time
from pathlib import Path

import pytest

from conftest import TestClient, seed_controller

import memory_vault
import model_router as mr
import runtime_privacy
import sessions_store
import threads_vault
import turn_record as tr
import users_store


@pytest.fixture(autouse=True)
def _clean(reset_stores):
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    yield


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _member(username: str = "member_h"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.update_user(username, {
        "membership_status": "active", "membership_tier": "founding_500",
    })
    seed_controller(username)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


_PHYSICS = {
    "field_curvature": {"intensity": "medium", "gradient_direction": "mixed", "stability": "unstable",
                        "dominant_forces": [], "notes": "n"},
    "edge_pressure": {"signal_clarity": "mixed", "signal_intensity": "medium", "coherence": "fragmented",
                      "perceived_posture": [], "risk_of_misread": "high", "notes": "n"},
    "relational_primitives": {"trust": "low", "alignment": "misaligned", "boundary": "soft", "agency": "partial",
                              "distance": "increasing", "dominant_pattern": [], "notes": "n"},
    "external_expression": {"recommended_posture": [], "risk_if_unchanged": "drift"},
}


def _fake_anthropic(monkeypatch):
    def handler(model_id, prompt, *, temperature, max_tokens):
        return {"ok": True, "model_id": model_id, "provider": "anthropic",
                "text": json.dumps(_PHYSICS), "mock": False, "ts": 0.0}
    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", handler)


# ===========================================================================
# #113 -- a cockpit thread counts
# ===========================================================================
def test_113_a_cockpit_thread_counts_its_scored_turns_on_the_thread_surface(client, monkeypatch):
    _fake_anthropic(monkeypatch)
    user, h = _member()
    tid = threads_vault.create_thread(user, "Cockpit")["thread_id"]      # a plain thread, not a relationship
    elins = {"input": {"raw_text": "the ridge is contested and the pressure is rising"},
             "surface": "thread", "thread_id": tid}
    r1 = client.post("/elins/v2/run", headers=h, json=elins)
    assert r1.status_code == 200, r1.text
    n1 = r1.json()["_meta"]["n_points"]
    assert n1 == 1                       # one read on an owned thread: one point, never 0
    # the panel's physics half records a turn on the same thread (no field asked on this surface)
    p = client.post("/me/emotional_physics/analyze", headers=h,
                    json={"text": "the ridge is contested", "surface": "thread", "thread_id": tid})
    assert p.status_code == 200, p.text
    r2 = client.post("/elins/v2/run", headers=h, json=elins)
    assert r2.status_code == 200, r2.text
    n2 = r2.json()["_meta"]["n_points"]
    assert n2 == 2 and n2 > 1 and n2 > n1     # three reads on the thread, two of them scored
    # the same number /turns serves for the thread
    turns = client.get(f"/me/relationships/{tid}/turns", headers=h).json()
    assert n2 == turns["trust_signal"]["scored_turns"] and turns["turn_count"] == 3
    # no thread: one read, said honestly
    bare = client.post("/elins/v2/run", headers=h, json={"input": {"raw_text": "x"}, "surface": "thread"})
    assert bare.json()["_meta"]["n_points"] == 1
    # a thread the member does not own: 1, nothing recorded, never a 500
    _, h2 = _member("member_i")
    foreign = client.post("/elins/v2/run", headers=h2, json=elins)
    assert foreign.status_code == 200 and foreign.json()["_meta"]["n_points"] == 1
    assert client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turn_count"] == 3


# ===========================================================================
# #154 -- a hash, never the prefix
# ===========================================================================
def test_154_user_ref_is_a_hash_and_never_the_address_prefix(app_module):
    addr = "someone.private@example.com"
    ref = app_module._user_ref(addr)
    assert re.fullmatch(r"[0-9a-f]{16}", ref)
    assert ref == users_store._uref(addr)
    assert "someone" not in ref and "@" not in ref
    # the prefix helper is unchanged and is no longer what app logs for a user
    assert runtime_privacy.user_ref(addr).startswith("someone.")
    assert ref != runtime_privacy.user_ref(addr)
    # an absent id keeps the marker
    assert app_module._user_ref(None) == "<none>"
    assert app_module._user_ref("") == "<none>"


# ===========================================================================
# #154 (b) -- no log line carries a bare identity, and nothing logs the prefix
# ===========================================================================
_LOG_LEVELS = {"debug", "info", "warning", "error", "exception", "critical"}
_IDENT_NAMES = {"username", "user", "email", "email_lower", "user_id", "operator_id", "inviter", "admin_user", "smtp_to"}
_IDENT_ATTRS = {"username", "email", "user", "user_id", "operator_id"}
_IDENT_KEYS = {"user", "username", "email", "user_id", "operator_id"}
# the hashes (and the session ref, and len): a call to one of these is NOT an identity on the line
_HASH_HELPERS = {"_user_ref", "user_hash", "_uref", "redact_user", "_email_hash", "login_record_ref",
                 "_session_ref", "session_ref", "len"}
_V29_SINKS = {"log_event", "TimedBlock", "enforce_rate_limit"}


def _callee(node: ast.Call) -> str:
    fn = node.func
    return fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""


def _bare_identity(node: ast.AST) -> bool:
    """A log argument that IS a user identity, unwrapped: a name, an attribute
    (req.username), a subscript (session["user"]), an f-string carrying one,
    an ``or`` / conditional carrying one, or a call (str(user), json.dumps of
    it) carrying one -- unless the call is one of the hash helpers."""
    if isinstance(node, ast.Name):
        return node.id in _IDENT_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _IDENT_ATTRS
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and key.value in _IDENT_KEYS
    if isinstance(node, ast.JoinedStr):
        return any(_bare_identity(v.value) for v in node.values if isinstance(v, ast.FormattedValue))
    if isinstance(node, ast.BoolOp):
        return any(_bare_identity(v) for v in node.values)
    if isinstance(node, ast.IfExp):
        return _bare_identity(node.body) or _bare_identity(node.orelse)
    if isinstance(node, ast.Call):
        if _callee(node) in _HASH_HELPERS:
            return False
        return any(_bare_identity(a) for a in node.args) or any(_bare_identity(k.value) for k in node.keywords)
    return False


def _logger_calls(tree: ast.AST):
    """Every logger.<level>( call, and logger.log(level, ...) -- yielded as
    (call, args-to-inspect)."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "logger"):
            if node.func.attr in _LOG_LEVELS:
                yield node, list(node.args) + [kw.value for kw in node.keywords]
            elif node.func.attr == "log":
                yield node, list(node.args[1:]) + [kw.value for kw in node.keywords]


def _double_hashed_v29_users(tree: ast.AST):
    """v29_hardening.log_event / TimedBlock / enforce_rate_limit hash the user
    themselves (#154): a caller that hands them an already-hashed value puts a
    hash of a hash on the line -- a value that joins with nothing."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee(node) in _V29_SINKS:
            for kw in node.keywords:
                if kw.arg == "user" and isinstance(kw.value, ast.Call) and _callee(kw.value) in _HASH_HELPERS:
                    yield node


def test_154_b_no_logger_call_in_app_carries_a_bare_identity(app_module):
    src = Path(app_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = []
    for call, args in _logger_calls(tree):
        for arg in args:
            if _bare_identity(arg):
                bad.append(f"app.py:{call.lineno}: {ast.get_source_segment(src, arg)}")
    assert bad == [], "a log line carries a hash, never an address: " + "; ".join(bad)
    twice = [f"app.py:{c.lineno}" for c in _double_hashed_v29_users(tree)]
    assert twice == [], "log_event hashes the user itself; never hand it a hash: " + ", ".join(twice)


def test_154_c_user_hash_is_the_uref_shape_and_the_prefix_has_no_caller_left():
    addr = "someone.private@example.com"
    assert runtime_privacy.user_hash(addr) == users_store._uref(addr)
    assert re.fullmatch(r"[0-9a-f]{16}", runtime_privacy.user_hash(addr))
    assert runtime_privacy.user_hash(None) == runtime_privacy.user_hash("") == "<none>"
    assert runtime_privacy.user_hash(123) == "<none>"          # type: ignore[arg-type]
    # the runtime tree (see _runtime_files below), tests excluded
    callers = []
    for p in _runtime_files():
        if p.name == "runtime_privacy.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\b(?:runtime_privacy|_privacy)\.user_ref\(", text) or re.search(r"import .*\buser_ref\b", text):
            callers.append(p.name)
    assert callers == [], "the prefix is not a log reference: " + ", ".join(callers)


def _runtime_files():
    """The runtime tree: root modules (probe scripts starting with "_" excluded)
    plus the packages app.py imports -- el_ins, ELINS, problem_solver, api.
    tests are not the runtime; sos_runtime is a separate Cloud Run service
    with its own gate and is not walked here."""
    root = Path(runtime_privacy.__file__).resolve().parent
    files = [p for p in root.glob("*.py") if not p.name.startswith("_")]
    for pkg in ("el_ins", "ELINS", "problem_solver", "api"):
        files += list((root / pkg).rglob("*.py"))
    return files


def test_154_d_the_detector_sees_every_shape_it_claims_to():
    for src in ("username", "req.username", 'session["user"]', "self.user", 'f"u={user}"', "smtp_to", "user_id",
                'smtp_to or "<user-resolved>"', "str(user_id)", "json.dumps(user)", 'user if user else "-"',
                "runtime_privacy.user_ref(user)"):          # the PREFIX helper is not a hash
        assert _bare_identity(ast.parse(src, mode="eval").body), src
    for src in ("_user_ref(user)", "runtime_privacy.user_hash(user)", "users_store._uref(user)", "len(user)",
                "source", "user_ref", "type_filter", "record[\"billing_id\"]", "json.dumps(record)",
                "type(exc).__name__", "_session_ref(sid)"):
        assert not _bare_identity(ast.parse(src, mode="eval").body), src
    # logger.log(level, ...) is walked with the level skipped; the double-hash shape is seen
    tree = ast.parse('logger.log(level, "x %s", user)\nv29_hardening.log_event("e", user=_user_ref(u))')
    assert [len(a) for _, a in _logger_calls(tree)] == [2]
    assert len(list(_double_hashed_v29_users(tree))) == 1


def test_154_e_no_logger_call_in_the_runtime_tree_carries_a_bare_identity():
    bad = []
    for p in _runtime_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for call, args in _logger_calls(tree):
            for arg in args:
                if _bare_identity(arg):
                    bad.append(f"{p.name}:{call.lineno}")
        bad += [f"{p.name}:{c.lineno} (hash of a hash)" for c in _double_hashed_v29_users(tree)]
    assert bad == [], "a log line carries a hash, never an address: " + ", ".join(bad)


def test_154_f_the_v29_structured_line_carries_the_same_hash(caplog):
    import logging
    import v29_hardening
    addr = "someone.private@example.com"
    assert v29_hardening.redact_user(addr) == users_store._uref(addr) == runtime_privacy.user_hash(addr)
    assert v29_hardening.redact_user(None) == v29_hardening.redact_user("") == "<anon>"
    caplog.set_level(logging.INFO)
    v29_hardening.log_event("housekeeping_pin", user=addr, route="/pin")
    lines = [r.getMessage() for r in caplog.records if "housekeeping_pin" in r.getMessage()]
    assert lines, "log_event emitted nothing"
    for line in lines:
        assert addr not in line and addr[:12] not in line and "@" not in line
        assert f"user={users_store._uref(addr)}" in line
