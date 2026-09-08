"""
#146 -- EL/INS reads the reply as a verifier (R5.2d): deterministic, no
store, one log line, acted on by nothing.

WHAT THESE PIN. Two analyze_text calls per member turn, both in
deterministic mode (the router is called exactly once -- the chat call --
and never by the analyzer); the log line's shape (ids, enum words, the
stop and refusal marks, acted_on False) and what it never carries (the
input, the reply); an analyzer exception becoming status ABSENT with a
reason while the turn completes; a refusal-shaped reply verified all the
same; the reply byte-equal to what the router returned; nothing written
to el_ins_store.
"""
from __future__ import annotations

import logging
import time

import pytest

import el_ins
import intelligence_kernel as ik
import model_router as mr
import threads_vault

LOGGER = "clarityos.intelligence_kernel"
INPUT = "The board demands accountability for the catastrophic panic and the doom."
REPLY = "According to the committee, the regulation and the statute govern the process."
REFUSAL = "I can't help with that request, but the policy and the statute may."


class FakeRouter:
    """Records every call; returns scripted replies in order."""

    def __init__(self, outputs, stop_reason=None):
        self._outputs = list(outputs)
        self._stop = stop_reason
        self.calls: list[dict] = []

    def __call__(self, model_id, prompt, **kwargs):
        self.calls.append({"model_id": model_id, "prompt": prompt})
        text = self._outputs.pop(0) if self._outputs else "(exhausted)"
        out = {"ok": True, "model_id": model_id, "provider": "fake",
               "text": text, "mock": True, "ts": time.time()}
        if self._stop is not None:
            out["stop_reason"] = self._stop
        return out


@pytest.fixture(autouse=True)
def _isolate(reset_stores):
    el_ins._reset_for_tests()
    yield
    el_ins._reset_for_tests()


def _router(monkeypatch, outputs, stop_reason=None):
    fake = FakeRouter(outputs, stop_reason=stop_reason)
    monkeypatch.setattr(mr, "route_request", fake)
    return fake


def _spy_analyze(monkeypatch):
    """Wrap the package's analyze_text so every call is recorded, mode included."""
    real = el_ins.analyze_text
    calls: list[dict] = []

    def spy(text, *, provider_mode="auto"):
        calls.append({"text": text, "provider_mode": provider_mode})
        return real(text, provider_mode=provider_mode)

    monkeypatch.setattr(el_ins, "analyze_text", spy)
    return calls


def _turn(user, text):
    tid = threads_vault.create_thread(user, title="t")["thread_id"]
    return tid, ik.run_thread_message(user, tid, text)


def _verify_lines(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == LOGGER and r.getMessage().startswith("el_ins.verify payload=")]


# --------------------------------------------------------------------------
# the helper
# --------------------------------------------------------------------------
def test_verify_el_ins_returns_both_sides_in_deterministic_mode(monkeypatch):
    calls = _spy_analyze(monkeypatch)
    v = ik.verify_el_ins(INPUT, REPLY)
    assert v["instrument"] == "el_ins"
    assert v["input"]["analysis"]["ratio_classification"] == "high_el"
    assert v["reply"]["analysis"]["ratio_classification"] == "high_ins"
    assert v["input"]["reasoning_mode"] == "stabilize" and v["reply"]["reasoning_mode"] == "expand"
    assert [c["provider_mode"] for c in calls] == ["deterministic", "deterministic"]
    assert [c["text"] for c in calls] == [INPUT, REPLY]


def test_verify_el_ins_never_raises_and_returns_a_different_kind(monkeypatch):
    def boom(text, *, provider_mode="auto"):
        raise RuntimeError("analyzer down " + "x" * 200)
    monkeypatch.setattr(el_ins, "analyze_text", boom)
    v = ik.verify_el_ins(INPUT, REPLY)
    assert v == {"instrument": "el_ins", "status": "ABSENT", "reason": v["reason"]}
    assert v["reason"].startswith("RuntimeError: analyzer down") and len(v["reason"]) <= 80


# --------------------------------------------------------------------------
# on the member turn
# --------------------------------------------------------------------------
def test_two_deterministic_calls_per_turn_and_the_router_is_called_once(monkeypatch):
    fake = _router(monkeypatch, [REPLY])
    calls = _spy_analyze(monkeypatch)
    tid, out = _turn("v_alice", INPUT)
    assert len(fake.calls) == 1, "the analyzer must never phone the router"
    assert [c["provider_mode"] for c in calls] == ["deterministic", "deterministic"]
    assert [c["text"] for c in calls] == [INPUT, REPLY]
    # the reply is byte-equal to what the router returned: acted on by nothing
    assert out["assistant_message"]["content"] == REPLY
    # no store write: the verifier persists nothing
    assert el_ins.get_recent_el_ins("v_alice") == []
    assert el_ins.get_thread_el_ins("v_alice", tid) == []


def test_the_line_carries_ids_marks_and_words_never_the_texts(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _router(monkeypatch, [REPLY])
    tid, out = _turn("v_bob", INPUT)
    lines = _verify_lines(caplog)
    assert len(lines) == 1, lines
    line = lines[0]
    assert "'thread_id': '%s'" % tid in line
    assert "'run_id': 'ABSENT'" in line          # the thread path mints none
    assert "'turn': 0" in line                   # the first turn's index, from the seal
    assert "'model_id': '%s'" % out["model_id"] in line
    assert "'stop_reason': None" in line         # raw vendor value; None on mock
    assert "'refusal': False" in line
    assert "'input': {'ratio_classification': 'high_el', 'reasoning_mode': 'stabilize'}" in line
    assert "'reply': {'ratio_classification': 'high_ins', 'reasoning_mode': 'expand'}" in line
    assert "'status': 'ok'" in line and "'acted_on': False" in line
    assert INPUT not in line and REPLY not in line
    # lexicon hits (el_components / ins_components are member words) never ride the line
    for word in ("panic", "doom", "catastrophic", "statute", "regulation", "committee"):
        assert word not in line, word
    assert "el_components" not in line and "stability_notes" not in line
    assert "v_bob" not in line                   # never the member


def test_an_analyzer_exception_is_absent_with_a_reason_and_the_turn_completes(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _router(monkeypatch, [REPLY])

    def boom(text, *, provider_mode="auto"):
        raise ValueError("no lexicon")
    monkeypatch.setattr(el_ins, "analyze_text", boom)
    tid, out = _turn("v_carol", INPUT)
    assert out["assistant_message"]["content"] == REPLY
    line = _verify_lines(caplog)[0]
    assert "'status': 'ABSENT'" in line and "'reason': 'ValueError: no lexicon'" in line
    assert "'input': 'ABSENT'" in line and "'reply': 'ABSENT'" in line
    assert "'acted_on': False" in line


def test_a_refusal_is_marked_and_still_verified(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _router(monkeypatch, [REFUSAL])
    tid, out = _turn("v_dave", INPUT)
    assert out["assistant_message"]["content"] == REFUSAL      # stored as-is; the mark is a log
    line = _verify_lines(caplog)[0]
    assert "'refusal': True" in line
    assert "'input': {'ratio_classification': 'high_el'" in line
    assert "'reply': {'ratio_classification': " in line and "'reply': 'ABSENT'" not in line


def test_a_stop_that_is_not_end_turn_is_marked_and_still_verified(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _router(monkeypatch, [REPLY], stop_reason="max_tokens")
    _turn("v_erin", INPUT)
    line = _verify_lines(caplog)[0]
    assert "'stop_reason': 'max_tokens'" in line
    assert "'reply': {'ratio_classification': 'high_ins'" in line


def test_no_vendor_text_reads_reply_absent_not_balanced(monkeypatch, caplog):
    """The kernel persists its own "(no reply)" sentinel when the vendor
    returns nothing; the verifier must not grade that placeholder."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    _router(monkeypatch, [""])
    _, out = _turn("v_gil", INPUT)
    assert out["assistant_message"]["content"] == "(no reply)"     # unchanged behaviour
    line = _verify_lines(caplog)[0]
    assert "'reply': 'ABSENT'" in line and "'reason': 'no_reply'" in line
    assert "'input': {'ratio_classification': 'high_el'" in line   # the input is still verified
    assert "'status': 'ok'" in line and "balanced" not in line


def test_verify_el_ins_with_no_reply_returns_the_word(monkeypatch):
    calls = _spy_analyze(monkeypatch)
    v = ik.verify_el_ins(INPUT, None)
    assert v["reply"] == "ABSENT" and v["input"]["analysis"]["ratio_classification"] == "high_el"
    assert len(calls) == 1                       # nothing analyzed for the absent side


def test_the_return_contract_and_the_reply_are_unchanged(monkeypatch):
    _router(monkeypatch, [REPLY])
    _, out = _turn("v_fay", INPUT)
    assert set(out) == {
        "meta", "user_message", "assistant_message", "model_id", "reasoning_mode",
        "anomalies", "grounding_status", "directives", "directive_metadata", "vendor_calls",
    }
    assert "el_ins" not in str(out["meta"]) and out["reasoning_mode"] is None
