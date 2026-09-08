"""
#139 -- the insight window: tail-anchored, sized per surface, kernel-
authoritative. + the summary_turn passenger (#190 needs it).

WHAT THESE PIN. The table is the ruling (personal 6,000 · thread 12,000 ·
tail); cut_window keeps the LAST characters and says so; the coverage
numbers come from the caller's boundaries and are ABSENT (never guessed)
when those are missing or wrong; both insight routes accept the two new
fields, cut with the one helper, and return the window in _meta; the
reply-path budget is untouched; a summary is stamped with the
message_count it was made at, in turns, never a clock.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import json  # noqa: E402
import secrets  # noqa: E402
import time  # noqa: E402

import bcrypt  # noqa: E402
import pytest  # noqa: E402

import intelligence_kernel as ik  # noqa: E402
import model_router as mr  # noqa: E402
import threads_vault  # noqa: E402


def _transcript(n: int, length: int):
    """n messages of `length` content chars, joined as the browser joins them
    (transcriptWindow.composeTranscript / computeBoundaries). Returns
    (text, cumulative end offsets)."""
    # each message carries its index so "in the window" is falsifiable
    parts = [("user: " if i % 2 == 0 else "assistant: ") + ("%02d" % i) + ("x" * (length - 2))
             for i in range(n)]
    text = "\n".join(parts)
    ends, cum = [], 0
    for i, p in enumerate(parts):
        cum += (0 if i == 0 else 1) + len(p)
        ends.append(cum)
    return text, ends


def _expected_coverage(ends, start):
    """The browser's own arithmetic, written independently of the kernel."""
    starts = [0] + [e + 1 for e in ends[:-1]]
    first = next(i for i, e in enumerate(ends) if e > start)
    return {
        "first": first + 1,
        "last": len(ends),
        "whole": sum(1 for s in starts if s >= start),
        "mid": start > 0 and starts[first] < start,
    }


# --------------------------------------------------------------------------
# cut_window
# --------------------------------------------------------------------------
def test_the_table_is_the_ruling():
    assert ik.WINDOW_CHARS == {"personal": 6_000, "thread": 12_000}
    assert ik.WINDOW_DEFAULT_SURFACE == "thread" and ik.WINDOW_ANCHOR == "tail"


def test_thread_surface_keeps_the_last_12000():
    text = ("H" * 500) + ("Z" * 12_000)
    w, m = ik.cut_window(text, "thread")
    assert w == "Z" * 12_000
    assert m["window_anchor"] == "tail" and m["window_surface"] == "thread" and m["window_cap"] == 12_000
    assert m["window_chars"] == 12_000 and m["total_chars"] == 12_500


def test_personal_surface_keeps_the_last_6000():
    text = ("H" * 500) + ("Z" * 6_000)
    w, m = ik.cut_window(text, "personal")
    assert w == "Z" * 6_000 and m["window_cap"] == 6_000 and m["window_surface"] == "personal"


def test_default_and_unknown_surfaces_are_thread():
    text = "Z" * 13_000
    assert ik.cut_window(text)[1]["window_surface"] == "thread"
    assert ik.cut_window(text, None)[1]["window_chars"] == 12_000
    assert ik.cut_window(text, "operator")[1]["window_surface"] == "thread"


def test_a_short_text_reads_whole():
    w, m = ik.cut_window("a short note", "thread")
    assert w == "a short note" and m["window_chars"] == m["total_chars"] == 12


def test_coverage_from_boundaries_on_a_96k_thread():
    text, ends = _transcript(44, 2_180)          # ~96k chars, 44 messages
    assert ends[-1] == len(text)
    w, m = ik.cut_window(text, "thread", ends)
    start = len(text) - 12_000
    exp = _expected_coverage(ends, start)
    assert m["window_coverage"] == "boundaries" and m["window_coverage_reason"] is None
    assert m["total_messages"] == 44 and m["window_last_message"] == 44
    assert m["window_first_message"] == exp["first"] and m["window_messages"] == exp["whole"]
    assert m["window_truncated_mid_message"] is exp["mid"] is True
    # the window really is the tail: it ends where the text ends and holds
    # the whole of message first+1 but not message first-1
    assert text.endswith(w)
    parts = text.split("\n")
    assert parts[exp["first"]] in w              # first+1 (0-based first)
    assert parts[exp["first"] - 2] not in w      # first-1


def test_coverage_on_a_boundary_aligned_cut_is_not_mid_message():
    # three messages; the window starts exactly at the start of message 2
    parts = ["user: " + "a" * 100, "assistant: " + "b" * 100, "user: " + "c" * 100]
    text = "\n".join(parts)
    ends = [len(parts[0]), len(parts[0]) + 1 + len(parts[1]), len(text)]
    cap_needed = len(parts[1]) + 1 + len(parts[2])   # messages 2-3 exactly
    ik.WINDOW_CHARS["_test"] = cap_needed
    try:
        w, m = ik.cut_window(text, "_test", ends)
    finally:
        del ik.WINDOW_CHARS["_test"]
    assert w == parts[1] + "\n" + parts[2]
    assert m["window_first_message"] == 2 and m["window_messages"] == 2
    assert m["window_truncated_mid_message"] is False


@pytest.mark.parametrize("bad,reason", [
    (None, "no message boundaries"),
    ([], "non-empty list"),
    ("1,2", "non-empty list"),
    ([1, "2"], "non-negative ints"),
    ([1, True], "non-negative ints"),
    ([5, 3], "must increase"),
    ([5, 5], "must increase"),
    ([3, 7], "do not end at total_chars"),
])
def test_coverage_is_absent_never_guessed_when_boundaries_are_missing_or_wrong(bad, reason):
    text = "user: hello\nassistant: there"       # 28 chars
    _, m = ik.cut_window(text, "thread", bad)
    assert m["window_coverage"] == "ABSENT" and reason in m["window_coverage_reason"]
    for k in ("total_messages", "window_messages", "window_first_message",
              "window_last_message", "window_truncated_mid_message"):
        assert m[k] is None, k
    assert m["window_chars"] == 28            # the cut itself still stands


def test_empty_text_has_no_window_and_no_coverage():
    w, m = ik.cut_window("", "thread", [0])
    assert w == "" and m["window_chars"] == 0 and m["total_chars"] == 0
    assert m["window_coverage"] == "ABSENT" and "empty" in m["window_coverage_reason"]


def test_coverage_counts_code_points_the_way_the_browser_must():
    """An emoji is one code point and two UTF-16 units. The browser counts
    code points (Array.from); a browser that counted .length would overshoot
    and the kernel marks that ABSENT rather than misplacing every message."""
    parts = ["user: hi \U0001F600 there", "assistant: ok \U0001F44D", "user: and then"]
    text = "\n".join(parts)
    ends, cum = [], 0
    for i, p in enumerate(parts):
        cum += (0 if i == 0 else 1) + len(p)          # code points
        ends.append(cum)
    _, m = ik.cut_window(text, "thread", ends)
    assert m["window_coverage"] == "boundaries" and m["total_messages"] == 3
    utf16 = [len(text[:e].encode("utf-16-le")) // 2 for e in ends]   # what JS .length would say
    assert utf16[-1] == ends[-1] + 2
    _, m2 = ik.cut_window(text, "thread", utf16)
    assert m2["window_coverage"] == "ABSENT" and "do not end at total_chars" in m2["window_coverage_reason"]


def test_cut_window_is_deterministic_and_refuses_non_text():
    text, ends = _transcript(9, 300)
    assert ik.cut_window(text, "personal", ends) == ik.cut_window(text, "personal", list(ends))
    with pytest.raises(ValueError):
        ik.cut_window(None, "thread")   # type: ignore[arg-type]


def test_the_reply_path_budget_is_untouched():
    assert ik.THREAD_CONTEXT_CHAR_BUDGET == 6_000


# --------------------------------------------------------------------------
# run_emotional_physics
# --------------------------------------------------------------------------
def _valid_payload():
    return {
        "field_curvature": {"pattern": "steady"}, "edge_pressure": {"signal": "clear"},
        "relational_primitives": {"boundary": "held"}, "external_expression": {"tone": "plain"},
    }


def _install_fake_handler(monkeypatch, response_text):
    captured = {"model_id": None, "prompt": None}

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        captured["model_id"] = model_id
        captured["prompt"] = prompt
        return {"ok": True, "model_id": model_id, "provider": "anthropic",
                "text": response_text, "mock": False, "ts": 0.0}

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", fake_handler)
    return captured


def test_physics_meta_declares_a_tail_window_of_12000_on_a_96k_transcript(reset_stores, monkeypatch):
    captured = _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    text, ends = _transcript(44, 2_180)
    out = ik.run_emotional_physics("alice", text, surface="thread", message_boundaries=ends)
    m = out["_meta"]
    assert m["window_chars"] == 12_000 and m["window_anchor"] == "tail" and m["window_surface"] == "thread"
    assert m["total_chars"] == len(text) and m["total_messages"] == 44 and m["window_last_message"] == 44
    assert m["window_coverage"] == "boundaries" and 1 < m["window_first_message"] <= 44
    # the prompt carries exactly the window
    user_tail = captured["prompt"].split("SITUATION:\n", 1)[1]
    assert user_tail == text[-12_000:].strip()
    assert out["_meta"]["parse_error"] is None


def test_a_whitespace_tail_window_is_refused_never_sent_empty(reset_stores, monkeypatch):
    """The head has content, the last 12,000 characters are whitespace: the
    model must not be handed an empty situation (a refuter's catch)."""
    captured = _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    text = "user: real content here\nassistant: " + (" " * 12_000)
    with pytest.raises(ValueError) as e:
        ik.run_emotional_physics("alice", text, surface="thread")
    assert "window is empty" in str(e.value)
    assert captured["prompt"] is None                   # no model call


def test_physics_personal_surface_is_6000(reset_stores, monkeypatch):
    _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    text, ends = _transcript(20, 500)
    m = ik.run_emotional_physics("alice", text, surface="personal", message_boundaries=ends)["_meta"]
    assert m["window_chars"] == 6_000 and m["window_surface"] == "personal"


def test_physics_default_is_thread_and_coverage_absent_without_boundaries(reset_stores, monkeypatch):
    _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    text, _ = _transcript(20, 500)
    m = ik.run_emotional_physics("alice", text)["_meta"]
    assert m["window_surface"] == "thread" and m["window_chars"] == min(12_000, len(text))
    assert m["window_coverage"] == "ABSENT" and m["window_messages"] is None


# --------------------------------------------------------------------------
# the two routes
# --------------------------------------------------------------------------
from conftest import TestClient  # noqa: E402
import app as appmod  # noqa: E402
import sessions_store  # noqa: E402
import users_store  # noqa: E402

client = TestClient(appmod.app)


def _session(user: str) -> dict:
    users_store.create_user(
        username=user, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def test_physics_route_accepts_surface_and_boundaries_and_returns_the_window(reset_stores, monkeypatch):
    _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    h = _session("w_alice")
    text, ends = _transcript(44, 2_180)
    r = client.post("/me/emotional_physics/analyze", headers=h,
                    json={"text": text, "surface": "thread", "message_boundaries": ends})
    assert r.status_code == 200, r.text[:200]
    m = r.json()["_meta"]
    assert m["window_chars"] == 12_000 and m["window_anchor"] == "tail" and m["total_messages"] == 44
    r = client.post("/me/emotional_physics/analyze", headers=h,
                    json={"text": text, "surface": "personal", "message_boundaries": ends})
    assert r.json()["_meta"]["window_chars"] == 6_000
    r = client.post("/me/emotional_physics/analyze", headers=h, json={"text": text, "surface": "operator"})
    assert r.status_code == 422                 # the two surfaces are the whole vocabulary


def test_elins_route_cuts_with_the_same_helper_and_declares(reset_stores):
    h = _session("w_bob")
    text, ends = _transcript(44, 2_180)
    r = client.post("/elins/v2/run", headers=h,
                    json={"input": {"raw_text": text}, "surface": "thread", "message_boundaries": ends})
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    m = body["_meta"]
    assert m["window_chars"] == 12_000 and m["window_anchor"] == "tail" and m["window_last_message"] == 44
    # the engine READ the window: L1 measures the stripped window, never the whole
    l1 = body["pipeline"]["L1_ingest"]
    assert 0 < l1["char_count"] <= 12_000 and l1["char_count"] == len(text[-12_000:].strip())
    assert "raw_text" not in body["input"] and "text" not in l1      # #177 holds
    r = client.post("/elins/v2/run", headers=h,
                    json={"input": {"raw_text": text}, "surface": "personal", "message_boundaries": ends})
    assert r.json()["_meta"]["window_chars"] == 6_000 and r.json()["pipeline"]["L1_ingest"]["char_count"] <= 6_000


def test_both_routes_refuse_a_whitespace_tail_with_the_reason(reset_stores, monkeypatch):
    _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    h = _session("w_erin")
    text = "user: real content here\nassistant: " + (" " * 12_000)
    r = client.post("/me/emotional_physics/analyze", headers=h, json={"text": text, "surface": "thread"})
    assert r.status_code == 400 and "window is empty" in r.text
    r = client.post("/elins/v2/run", headers=h, json={"input": {"raw_text": text}, "surface": "thread"})
    assert r.status_code == 400 and "window is empty" in r.text and "12000" in r.text


def test_the_door_refuses_non_int_boundaries(reset_stores, monkeypatch):
    """Pydantic would coerce True -> 1 and "11" -> 11 into plausible offsets;
    StrictInt refuses them at the door."""
    _install_fake_handler(monkeypatch, json.dumps(_valid_payload()))
    h = _session("w_fay")
    text = "user: hello\nassistant: there"
    for bad in ([True, 28], ["11", "28"], [11.5, 28]):
        r = client.post("/me/emotional_physics/analyze", headers=h,
                        json={"text": text, "surface": "thread", "message_boundaries": bad})
        assert r.status_code == 422, (bad, r.status_code)
        r = client.post("/elins/v2/run", headers=h,
                        json={"input": {"raw_text": text}, "message_boundaries": bad})
        assert r.status_code == 422, (bad, r.status_code)


def test_elins_route_without_the_fields_reads_the_default_surface(reset_stores):
    h = _session("w_carol")
    text, _ = _transcript(10, 300)
    r = client.post("/elins/v2/run", headers=h, json={"input": {"raw_text": text}})
    assert r.status_code == 200, r.text[:200]
    m = r.json()["_meta"]
    assert m["window_surface"] == "thread" and m["window_chars"] == len(text) and m["window_coverage"] == "ABSENT"


# --------------------------------------------------------------------------
# the summary_turn passenger (#190)
# --------------------------------------------------------------------------
def _stub_router(monkeypatch, text="a summary of the thread"):
    monkeypatch.setattr(mr, "route_request", lambda model_id, prompt, **kw: {
        "ok": True, "text": text, "model_id": model_id, "provider": "fake", "mock": True, "ts": 0.0,
    })


def _fill(user, tid, n):
    for i in range(n):
        threads_vault.append_message(user, tid, {
            "role": "user" if i % 2 == 0 else "assistant", "content": "m%d" % i,
            "ts_ms": 1_700_000_000_000 + i, "model": None,
        })


def test_summary_turn_is_the_message_count_at_summarize_in_turns_not_a_clock(reset_stores, monkeypatch):
    _stub_router(monkeypatch)
    tid = threads_vault.create_thread("s_alice", title="t")["thread_id"]
    assert threads_vault.get_thread_meta("s_alice", tid)["summary_turn"] is None
    _fill("s_alice", tid, 3)
    out = ik.summarize_thread("s_alice", tid)
    assert out["meta"]["summary_turn"] == 3 == out["meta"]["message_count"]
    # the thread grows; the stamp stays: age = message_count - summary_turn
    _fill("s_alice", tid, 2)
    meta = threads_vault.get_thread_meta("s_alice", tid)
    assert meta["summary_turn"] == 3 and meta["message_count"] == 5
    # a fresh summary re-stamps
    assert ik.summarize_thread("s_alice", tid)["meta"]["summary_turn"] == 5


def test_summary_turn_clears_with_the_summary(reset_stores, monkeypatch):
    _stub_router(monkeypatch)
    tid = threads_vault.create_thread("s_bob", title="t")["thread_id"]
    _fill("s_bob", tid, 2)
    assert ik.summarize_thread("s_bob", tid)["meta"]["summary_turn"] == 2
    cleared = threads_vault.update_thread_summary("s_bob", tid, None, 1)
    assert cleared["summary_turn"] is None and cleared["summary"] is None


def test_legacy_meta_without_the_stamp_reads_none_and_junk_reads_none():
    base = {"thread_id": "t", "title": None, "created_at": 1, "updated_at": 2, "message_count": 4, "archived": False}
    assert threads_vault._coerce_meta(base, thread_id="t")["summary_turn"] is None
    assert threads_vault._coerce_meta({**base, "summary_turn": "4"}, thread_id="t")["summary_turn"] is None
    assert threads_vault._coerce_meta({**base, "summary_turn": True}, thread_id="t")["summary_turn"] is None
    assert threads_vault._coerce_meta({**base, "summary_turn": -1}, thread_id="t")["summary_turn"] is None
    assert threads_vault._coerce_meta({**base, "summary_turn": 4}, thread_id="t")["summary_turn"] == 4


def test_the_wire_carries_summary_turn(reset_stores, monkeypatch):
    _stub_router(monkeypatch)
    h = _session("s_dave")
    tid = threads_vault.create_thread("s_dave", title="t")["thread_id"]
    _fill("s_dave", tid, 2)
    r = client.get("/me/threads/%s/summary" % tid, headers=h)
    assert r.status_code == 200, r.text[:200]
    assert r.json()["meta"]["summary_turn"] is None
    r = client.post("/me/threads/%s/summarize" % tid, headers=h, json={})
    assert r.status_code == 200, r.text[:200]
    assert r.json()["meta"]["summary_turn"] == 2
    r = client.get("/me/threads", headers=h)
    row = [t for t in r.json()["threads"] if t["thread_id"] == tid][0]
    assert row["summary_turn"] == 2
