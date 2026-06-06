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

    # Grounded on first try → exactly one model call, no retry.
    assert len(fake.calls) == 1
    assert out["grounding_status"] == "grounded"
    # The directive token is stripped from the persisted user turn...
    assert out["user_message"]["content"] == "What is the tower height?"
    # ...and never reaches the model prompt...
    assert "#cite" not in fake.calls[0]["prompt"].lower()
    # ...nor the stored transcript.
    _, msgs = tv.get_thread("alice", tid)
    assert msgs[0]["content"] == "What is the tower height?"


def test_ungrounded_reply_triggers_single_retry(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import cite_mode
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT, GROUNDED_FACT])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite How tall is it?")

    # First reply ungrounded → one retry → grounded.
    assert len(fake.calls) == 2
    assert out["grounding_status"] == "grounded"
    # The retry prompt carries the validator's re-query instruction.
    assert cite_mode.FACTUAL_REQUERY in fake.calls[1]["prompt"]
    # The grounded retry is what gets persisted + returned.
    assert out["assistant_message"]["content"] == GROUNDED_FACT


def test_retry_is_capped_and_marks_incomplete(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    # Both replies ungrounded → the retry budget is still exactly one.
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT, UNGROUNDED_FACT_2])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite How tall is it?")

    # Hard cap: exactly two calls total (initial + one retry), never three.
    assert len(fake.calls) == 2
    assert out["grounding_status"] == "incomplete"
    # Best-effort: the retried output is returned even though ungrounded.
    assert out["assistant_message"]["content"] == UNGROUNDED_FACT_2


def test_opinion_without_basis_triggers_retry(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import cite_mode
    # Opinion with no declared basis → retry; second reply declares a basis.
    grounded_opinion = "It is the best option based on the customer ratings."
    fake = _install_router(
        monkeypatch, ["It is the best option.", grounded_opinion],
    )
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "#cite which option?")

    assert len(fake.calls) == 2
    assert cite_mode.OPINION_REQUERY in fake.calls[1]["prompt"]
    assert out["grounding_status"] == "grounded"


def test_normal_mode_unaffected(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    # No #cite: even an ungrounded factual reply must NOT trigger a retry.
    fake = _install_router(monkeypatch, [UNGROUNDED_FACT])
    tid = _new_thread()

    out = ik.run_thread_message("alice", tid, "How tall is it?")

    assert len(fake.calls) == 1
    assert out["grounding_status"] is None
    assert out["assistant_message"]["content"] == UNGROUNDED_FACT


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
