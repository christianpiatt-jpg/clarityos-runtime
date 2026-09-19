"""
A28 — Kernel migration: run_thread_message routed through the directive engine.

A18's bespoke inline #cite block (parse_cite_directive + _apply_cite_grounding)
is retired; the kernel now calls directive_engine for ALL seven directives.
These tests cover the migration at the kernel boundary:

* non-directive turns are byte-identical (no engine effect)
* #cite behaviour preserved end-to-end (grounded / retry / incomplete) and
  grounding_status still derived + surfaced (A18/A19/A20 back-compat)
* output-transforming directives (#structure, #operator) actually reach the
  persisted/returned assistant message
* directives + directive_metadata propagate to the return dict
* kernel log carries directive NAMES (content-free) — directive_metadata is
  deliberately NOT logged (content-safety, e.g. #compare target names)
* malformed / word-bound / unknown prefixes fall through to a normal turn
* stacked directives both report
"""
from __future__ import annotations

import json

import pytest


GROUNDED = "According to the official agency report, the findings are summarized."
UNGROUNDED = "The structure is 330 meters tall."
UNGROUNDED_2 = "It rises to 1815 feet at the tip."


class FakeRouter:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = []

    def __call__(self, model_id, prompt, **kwargs):
        self.calls.append({"model_id": model_id, "prompt": prompt})
        text = self._outputs.pop(0) if self._outputs else "(exhausted)"
        return {"ok": True, "model_id": model_id, "provider": "fake",
                "text": text, "mock": True, "ts": 0.0}


def _install(monkeypatch, outputs):
    import model_router
    fake = FakeRouter(outputs)
    monkeypatch.setattr(model_router, "route_request", fake)
    return fake


def _thread(user="alice"):
    import threads_vault as tv
    return tv.create_thread(user, "chat")["thread_id"]


def _last_log(caplog):
    rec = None
    for r in caplog.records:
        if r.message.startswith("kernel_run "):
            p = json.loads(r.message.split(" ", 1)[1])
            if p.get("kind") == "run_thread_message":
                rec = p
    return rec


# ---------------------------------------------------------------------------
# non-directive turns unchanged
# ---------------------------------------------------------------------------
def test_non_directive_turn_unchanged(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install(monkeypatch, [UNGROUNDED, UNGROUNDED, UNGROUNDED])  # no directive
    out = ik.run_thread_message("alice", _thread(), "how tall is it?")
    assert len(fake.calls) == 3                       # #366: one call per lane
    assert out["directives"] == []
    assert out["directive_metadata"] == {}
    assert out["grounding_status"] is None
    assert out["assistant_message"]["content"].startswith("reading")   # #366: the reply is the reading


# ---------------------------------------------------------------------------
# #cite under A4 (#366): the vendor answers rows, the reply is the reading,
# and a reading carries no citation -- #cite settles "incomplete" without a
# re-query (a retry would hand the pilot a lane's JSON). A ruling on #cite
# under A4 is owed (Part B return). grounding_status is still derived.
# ---------------------------------------------------------------------------
def test_cite_settles_incomplete_over_the_reading(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install(monkeypatch, [GROUNDED, GROUNDED, GROUNDED])
    out = ik.run_thread_message("alice", _thread(), "#cite who?")
    assert len(fake.calls) == 3
    assert out["directives"] == ["cite"]
    assert out["grounding_status"] == "incomplete"
    assert out["directive_metadata"]["cite"]["status"] == "incomplete"


def test_cite_never_retries_under_a4(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install(monkeypatch, [UNGROUNDED, UNGROUNDED_2, UNGROUNDED_2])
    out = ik.run_thread_message("alice", _thread(), "#cite how tall?")
    assert len(fake.calls) == 3                       # the lanes, never a fourth
    assert out["grounding_status"] == "incomplete"
    assert out["directive_metadata"]["cite"]["retry_used"] is False   # none fired; the flag says what happened
    assert UNGROUNDED_2 not in out["assistant_message"]["content"]


# ---------------------------------------------------------------------------
# output-transforming directives reach the assistant message
# ---------------------------------------------------------------------------
def test_structure_transforms_assistant_message(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import structure_format
    _install(monkeypatch, ["* alpha\n\n\n* beta   "] * 3)
    out = ik.run_thread_message("alice", _thread(), "#structure format it")
    # #366 -- the transform runs over the READING, not over a lane's text
    assert "alpha" not in out["assistant_message"]["content"]
    assert "reading" in out["assistant_message"]["content"]
    assert out["directives"] == ["structure"]
    assert out["directive_metadata"]["structure"]["status"] == "formatted"
    assert out["grounding_status"] is None


def test_operator_transforms_assistant_message(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    _install(monkeypatch, ["We should ship now. There is a risk of delay."])
    out = ik.run_thread_message("alice", _thread(), "#operator brief")
    assert out["assistant_message"]["content"].startswith("# Operator Brief")
    assert out["directives"] == ["operator"]


# ---------------------------------------------------------------------------
# stacked directives
# ---------------------------------------------------------------------------
def test_stacked_cite_and_structure(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    _install(monkeypatch, [GROUNDED] * 3)
    out = ik.run_thread_message("alice", _thread(), "#cite #structure question")
    assert out["directives"] == ["cite", "structure"]
    assert set(out["directive_metadata"]) == {"cite", "structure"}
    assert out["grounding_status"] == "incomplete"      # #366: a reading carries no citation (ruling owed)


# ---------------------------------------------------------------------------
# kernel log: directive names only, content-free
# ---------------------------------------------------------------------------
def test_log_carries_directive_names(reset_stores, monkeypatch, caplog):
    import intelligence_kernel as ik
    _install(monkeypatch, [UNGROUNDED, UNGROUNDED_2, UNGROUNDED_2])
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    ik.run_thread_message("alice", _thread(), "#cite how tall?")
    rec = _last_log(caplog)
    assert rec["meta"]["directives"] == ["cite"]
    assert rec["meta"]["grounding_status"] == "incomplete"
    assert rec["meta"]["retry_used"] is False          # #366: no re-query fires under A4
    assert rec["meta"]["direction"] == "query" and rec["meta"]["lanes"] == 3 and rec["meta"]["halted"] is False


def test_log_excludes_directive_metadata_content(reset_stores, monkeypatch, caplog):
    import intelligence_kernel as ik
    # #compare extracts target names (content) into directive_metadata; the
    # return dict carries them, but the kernel LOG must not.
    _install(monkeypatch, ["Python is faster than Java."] * 3)
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    out = ik.run_thread_message("alice", _thread(), "#compare them")
    # functional payload on the return dict (#366: #compare reads the
    # READING, so the targets are whatever the reading names -- a lane's
    # "Python"/"Java" never reach it):
    assert "compare" in out["directive_metadata"]
    assert "Python" not in json.dumps(out["directive_metadata"])
    # and never in the telemetry log line:
    rec = _last_log(caplog)
    assert rec["meta"]["directives"] == ["compare"]
    assert "Python" not in json.dumps(rec)
    assert "directive_metadata" not in rec["meta"]


# ---------------------------------------------------------------------------
# malformed / word-bound / unknown prefixes -> normal turn
# ---------------------------------------------------------------------------
def test_unknown_hashtoken_is_normal_turn(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    _install(monkeypatch, ["a reply"])
    out = ik.run_thread_message("alice", _thread(), "#unknown do something")
    assert out["directives"] == []
    assert out["directive_metadata"] == {}
    # The unknown token stays in the persisted user message (not consumed).
    assert out["user_message"]["content"] == "#unknown do something"


def test_word_bound_prefix_is_normal_turn(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    _install(monkeypatch, ["a reply"])
    out = ik.run_thread_message("alice", _thread(), "#citecisely worded")
    assert out["directives"] == []
    assert out["grounding_status"] is None


def test_bare_directive_rejected(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install(monkeypatch, [GROUNDED])
    with pytest.raises(ValueError):
        ik.run_thread_message("alice", _thread(), "#cite")
    assert len(fake.calls) == 0
