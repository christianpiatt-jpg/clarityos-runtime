"""
A18 — #cite kernel-path integration tests.

Covers the wiring of the A17 validator (cite_mode) into
intelligence_kernel.run_thread_message — Option A: kernel-path, mode-gated,
retry-capped. cite_mode.py itself stays untouched; these tests exercise the
runtime behaviour of the gate:

* #cite prefix is detected, stripped, and consumed this turn only
* an ungrounded reply triggers a single deterministic re-query
* the retry is hard-capped at one (no loop, no recursion)
* a reply still ungrounded after the retry returns grounding_status="incomplete"
* non-#cite turns are completely unaffected (no validation, no extra call,
  grounding_status=None)
* the existing run_thread_message return contract is preserved
* a bare "#cite" (empty after strip) is rejected like any empty turn
* the grounding_status surfaces on the kernel_run log line
"""
from __future__ import annotations

import json

import pytest


# A grounded reply: carries a citation signal ("according to" + "report"),
# with no bare number / superlative / opinion that would trip the validator.
GROUNDED = "According to the official agency report, the findings are summarized."
# Ungrounded factual replies: bare numbers, no citation.
UNGROUNDED_FACT = "The structure is 330 meters tall."
UNGROUNDED_FACT_2 = "It rises to 1815 feet at the tip."
# A grounded version of the same factual claim (citation now present).
GROUNDED_FACT = "According to the official record, the structure is 330 meters tall."


class FakeRouter:
    """Records every call and returns scripted texts in order."""

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls: list[dict] = []

    def __call__(self, model_id, prompt, **kwargs):
        self.calls.append({"model_id": model_id, "prompt": prompt})
        text = self._outputs.pop(0) if self._outputs else "(exhausted)"
        return {
            "ok": True, "model_id": model_id, "provider": "fake",
            "text": text, "mock": True, "ts": 0.0,
        }


def _install_router(monkeypatch, outputs):
    import model_router
    fake = FakeRouter(outputs)
    monkeypatch.setattr(model_router, "route_request", fake)
    return fake


def _new_thread(user="alice"):
    import threads_vault as tv
    return tv.create_thread(user, "chat")["thread_id"]


# ---------------------------------------------------------------------------
def test_cite_prefix_detected_and_stripped(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import threads_vault as tv
    fake = _install_router(monkeypatch, [GROUNDED])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite What is the tower height?")

    # #366 -- one call per lane (three), no retry; the vendor answers rows,
    # the reply is the reading, and a reading carries no citation: #cite
    # settles "incomplete" without a re-query. A ruling on #cite under A4 is
    # owed (Part B return).
    assert len(fake.calls) == 3
    assert out["grounding_status"] == "incomplete"
    # The directive token is stripped from the persisted user turn...
    assert out["user_message"]["content"] == "What is the tower height?"
    # ...and never reaches any lane prompt...
    assert all("#cite" not in c["prompt"].lower() for c in fake.calls)
    # ...nor the stored transcript.
    _, msgs = tv.get_thread("alice", tid)
    assert msgs[0]["content"] == "What is the tower height?"


def test_ungrounded_reply_no_longer_triggers_a_retry(reset_stores, monkeypatch):
    """#366 -- a #cite re-query would append the validator's instruction to
    an algebra prompt and hand the pilot a lane's JSON as the reply. No
    retry fires: three lane calls, none carrying the re-query instruction,
    the status settled "incomplete", retry_used False on the wire (none was
    used). A ruling on #cite under A4 is owed (Part B return)."""
    import intelligence_kernel as ik
    import cite_mode
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT, GROUNDED_FACT, GROUNDED_FACT])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite How tall is it?")

    assert len(fake.calls) == 3                                    # one per lane, no retry
    assert out["grounding_status"] == "incomplete"
    assert out["directive_metadata"]["cite"]["retry_used"] is False
    assert not any(cite_mode.FACTUAL_REQUERY in c["prompt"] for c in fake.calls)
    assert all(c["prompt"].startswith("[ClarityOS ep-up.v1] lane=") for c in fake.calls)
    # The reply is the reading; no lane's text rides it.
    assert out["assistant_message"]["content"].startswith("reading")
    assert GROUNDED_FACT not in out["assistant_message"]["content"]


def test_the_retry_budget_is_zero_under_a4(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT, UNGROUNDED_FACT_2, UNGROUNDED_FACT_2])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite How tall is it?")

    # Exactly the lanes: three calls, never a fourth.
    assert len(fake.calls) == 3
    assert out["grounding_status"] == "incomplete"
    assert UNGROUNDED_FACT_2 not in out["assistant_message"]["content"]


def test_opinion_without_basis_settles_incomplete_without_a_retry(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import cite_mode
    fake = _install_router(
        monkeypatch, ["It is the best option.", "x", "x"],
    )
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite which option?")

    assert len(fake.calls) == 3
    assert not any(cite_mode.OPINION_REQUERY in c["prompt"] for c in fake.calls)
    assert out["grounding_status"] == "incomplete"


def test_normal_mode_unaffected(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    # No #cite: no validation, no grounding status; the lanes run as always.
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT, UNGROUNDED_FACT, UNGROUNDED_FACT])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "How tall is it?")

    assert len(fake.calls) == 3
    assert out["grounding_status"] is None
    assert out["assistant_message"]["content"].startswith("reading")


def test_return_contract_preserved(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    _install_router(monkeypatch, [GROUNDED])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "hello")

    for key in ("meta", "user_message", "assistant_message", "model_id"):
        assert key in out
    assert out["meta"]["message_count"] == 2
    # Additive field present + None on a non-#cite turn.
    assert "grounding_status" in out
    assert out["grounding_status"] is None


def test_cite_only_content_rejected(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    fake = _install_router(monkeypatch, [GROUNDED])
    tid = _new_thread()
    # "#cite" with nothing after it strips to empty → ValueError (→ 400).
    with pytest.raises(ValueError):
        ik.run_thread_message("alice", tid, "#cite")
    # And it never reached the model.
    assert len(fake.calls) == 0


def test_grounding_status_on_kernel_log(reset_stores, monkeypatch, caplog):
    import intelligence_kernel as ik
    _install_router(monkeypatch, [UNGROUNDED_FACT, UNGROUNDED_FACT_2])
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    tid = _new_thread()

    ik.run_thread_message("alice", tid, "#cite how tall?")

    statuses = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "run_thread_message":
                statuses.append(payload["meta"].get("grounding_status"))
    assert "incomplete" in statuses
