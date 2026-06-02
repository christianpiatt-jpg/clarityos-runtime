"""
A20 — Cite-mode telemetry on the kernel_run log line.

A18 put grounding_status on the run_thread_message kernel_run line; A19
forwarded it over HTTP. A20 completes the operational telemetry: the same
structured line now also carries ``retry_used`` (did the single capped
re-query fire?). Combined with model_id (engine) and duration_ms (latency)
already on every line, operators can monitor cite-mode entirely from
kernel_run telemetry — no user text, model output, citations, or retry
instructions are ever logged.

NOTE (architecture): there is no separate ``telemetry`` module in this
codebase — kernel_logging.log_kernel_run is the per-run telemetry sink,
and cite_active is derivable (grounding_status is non-null iff #cite). So
A20 enriches the existing line rather than emitting a redundant parallel
event.
"""
from __future__ import annotations

import json

import pytest


GROUNDED = "According to the official agency report, the findings are summarized."
UNGROUNDED = "The structure is 330 meters tall."
UNGROUNDED_2 = "It rises to 1815 feet at the tip."
GROUNDED_FACT = "According to the official record, the structure is 330 meters tall."


class FakeRouter:
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
    monkeypatch.setattr(model_router, "route_request", FakeRouter(outputs))


def _last_thread_record(caplog):
    """The most recent run_thread_message kernel_run record."""
    recs = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "run_thread_message":
                recs.append(payload)
    assert recs, "expected a run_thread_message kernel_run line"
    return recs[-1]


def _send(monkeypatch, caplog, outputs, content, user="alice"):
    import intelligence_kernel as ik
    import threads_vault as tv
    _install_router(monkeypatch, outputs)
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    tid = tv.create_thread(user, "chat")["thread_id"]
    out = ik.run_thread_message(user, tid, content)
    return out, _last_thread_record(caplog)


def test_telemetry_grounded_first_try_no_retry(reset_stores, monkeypatch, caplog):
    _out, rec = _send(monkeypatch, caplog, [GROUNDED], "#cite who?")
    assert rec["meta"]["grounding_status"] == "grounded"
    assert rec["meta"]["retry_used"] is False


def test_telemetry_grounded_after_retry(reset_stores, monkeypatch, caplog):
    _out, rec = _send(
        monkeypatch, caplog, [UNGROUNDED, GROUNDED_FACT], "#cite how tall?",
    )
    assert rec["meta"]["grounding_status"] == "grounded"
    assert rec["meta"]["retry_used"] is True


def test_telemetry_incomplete_uses_retry(reset_stores, monkeypatch, caplog):
    _out, rec = _send(
        monkeypatch, caplog, [UNGROUNDED, UNGROUNDED_2], "#cite how tall?",
    )
    assert rec["meta"]["grounding_status"] == "incomplete"
    assert rec["meta"]["retry_used"] is True


def test_telemetry_non_cite_turn(reset_stores, monkeypatch, caplog):
    _out, rec = _send(monkeypatch, caplog, [UNGROUNDED], "how tall?")
    # cite_active is derivable: grounding_status is None on a non-#cite turn.
    assert rec["meta"]["grounding_status"] is None
    assert rec["meta"]["retry_used"] is False


def test_telemetry_records_engine_and_latency(reset_stores, monkeypatch, caplog):
    _out, rec = _send(monkeypatch, caplog, [GROUNDED], "#cite who?")
    # engine (model_id) + latency (duration_ms) ride the same line.
    assert rec["meta"]["model_id"]
    assert isinstance(rec["duration_ms"], (int, float))
    assert rec["duration_ms"] >= 0.0


def test_telemetry_logs_no_content(reset_stores, monkeypatch, caplog):
    user_text = "#cite UNIQUEQUESTIONTOKEN about something"
    assistant_text = "UNIQUEANSWERTOKEN per the official report."
    _out, rec = _send(monkeypatch, caplog, [assistant_text], user_text)
    blob = json.dumps(rec)
    # Neither the user's text nor the model output appears in telemetry…
    assert "UNIQUEQUESTIONTOKEN" not in blob
    assert "UNIQUEANSWERTOKEN" not in blob
    # …only non-content lengths.
    assert "user_content_len" in rec["meta"]
    assert "assistant_content_len" in rec["meta"]
