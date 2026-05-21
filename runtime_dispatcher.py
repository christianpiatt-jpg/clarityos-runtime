"""
runtime_dispatcher.py — Unit 36.

Runtime dispatcher and model-router surface. Sits above the runtime
kernel (Unit 35) and bridges the operator → model-router → kernel →
ELINS loop.

ROLE
----
First operator-loop module. Pure-functional contract layer for the
real router that will eventually plug in. No actual model calls — the
``model_route`` is a rule-based stub today and will be replaced with
the live router (already present elsewhere in the codebase) when
ClarityOS boots end-to-end.

PIPELINE
--------
1. Validate ``operator_intent``.
2. Classify the intent to choose a ``model_route`` (locked):
       * diagnostic  → local
       * plan        → claude
       * query       → copilot
       * action      → gemini
       * fallback    → copilot
3. Build ``session_context`` for Unit 35 from the operator_intent +
   default runtime_mode (overridable via ``operator_intent.payload.runtime_mode``).
4. Call ``run_runtime_step`` (Unit 35) → full runtime block.
5. Map ``runtime_decision`` + ``runtime_events`` to an operator-facing
   UI response:
       * allow → severity "info"
       * warn  → severity "warning"
       * block → severity "critical"
       * headline from operator_view.headline
       * body: short textual summary of decision + key signals
       * tags: union of ELINS tags + runtime events
6. Return the locked-shape dispatch result.

PURE & DETERMINISTIC
--------------------
Same operator_intent + same vault_state → byte-equal output. No I/O,
no network, no randomness, no model calls.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "session_id":  str,
      "operator_id": str,
      "timestamp":   str,
      "model_route": {
        "engine": "copilot | claude | gemini | grok | local",
        "reason": str,
      },
      "runtime": <full Unit 35 output>,
      "ui_response": {
        "headline": str,
        "body":     str,
        "severity": "info | warning | critical",
        "tags":     list[str],
      },
    }

PUBLIC API
----------
    dispatch_operator_intent(operator_intent: dict,
                              vault_state:     dict | None) -> dict
"""
from __future__ import annotations

from runtime_kernel import run_runtime_step


# Locked engine vocabulary.
_VALID_ENGINES: tuple = ("copilot", "claude", "gemini", "grok", "local")

# Locked severity vocabulary.
_SEV_INFO:     str = "info"
_SEV_WARNING:  str = "warning"
_SEV_CRITICAL: str = "critical"

_DECISION_SEVERITY_MAP: dict = {
    "allow": _SEV_INFO,
    "warn":  _SEV_WARNING,
    "block": _SEV_CRITICAL,
}

# Locked runtime modes (mirror Unit 35).
_VALID_RUNTIME_MODES: tuple = ("normal", "strict", "diagnostic")
_DEFAULT_RUNTIME_MODE: str = "normal"

# Required intent keys (mirror Unit 35 + dispatcher-specific).
_REQUIRED_INTENT_KEYS: tuple = (
    "session_id", "operator_id", "timestamp", "intent_type", "payload",
)


def _validate_operator_intent(intent) -> None:
    if not isinstance(intent, dict):
        raise ValueError(
            f"operator_intent must be a dict, got {type(intent).__name__}"
        )
    for key in _REQUIRED_INTENT_KEYS:
        if key not in intent:
            raise ValueError(
                f"operator_intent missing required key {key!r}"
            )
    if not isinstance(intent["payload"], dict):
        raise ValueError(
            f"operator_intent['payload'] must be a dict, "
            f"got {type(intent['payload']).__name__}"
        )


def _select_engine(intent: dict) -> dict:
    """Rule-based engine routing per the locked spec. Returns
    ``{engine, reason}``."""
    intent_type = intent["intent_type"]
    if intent_type == "diagnostic":
        return {
            "engine": "local",
            "reason": "diagnostic intents stay on-device",
        }
    if intent_type == "plan":
        return {
            "engine": "claude",
            "reason": "plan intents route to the planning engine",
        }
    if intent_type == "query":
        return {
            "engine": "copilot",
            "reason": "query intents route to the copilot engine",
        }
    if intent_type == "action":
        return {
            "engine": "gemini",
            "reason": "action intents route to the action engine",
        }
    # Fallback — unreachable while Unit 35 strictly validates the
    # intent_type vocabulary, but kept for spec completeness.
    return {
        "engine": "copilot",
        "reason": "fallback routing",
    }


def _build_session_context_for_kernel(intent: dict) -> dict:
    """Construct the session context Unit 35 expects from the
    operator intent. Runtime mode comes from
    ``payload.runtime_mode`` when supplied; otherwise normal."""
    payload = intent["payload"]
    runtime_mode = payload.get("runtime_mode", _DEFAULT_RUNTIME_MODE)
    if runtime_mode not in _VALID_RUNTIME_MODES:
        raise ValueError(
            f"operator_intent.payload['runtime_mode'] must be one of "
            f"{_VALID_RUNTIME_MODES}, got {runtime_mode!r}"
        )
    return {
        "session_id":   intent["session_id"],
        "operator_id":  intent["operator_id"],
        "timestamp":    intent["timestamp"],
        "runtime_mode": runtime_mode,
    }


def _build_ui_body(runtime: dict) -> str:
    """One-paragraph textual summary of the runtime step. Combines
    headline + key ELINS signals into operator-readable copy."""
    operator_view = runtime["operator_view"]
    details = operator_view["details"]
    risk_level = details.get("risk_level", "low")
    long_arc = details.get("long_arc_assessment", "benign")
    n_events = len(details.get("runtime_events", []))
    return (
        f"{operator_view['headline']} "
        f"Long-arc assessment: {long_arc}; risk level: {risk_level}; "
        f"{n_events} runtime event(s) emitted."
    )


def _build_tags(runtime: dict) -> list:
    """Union of ELINS long-arc tags + runtime events. Alpha-sorted,
    deduped — deterministic for byte-equal output."""
    elins_tags = runtime["elins_block"].get("tags", []) or []
    runtime_events = runtime.get("runtime_events", []) or []
    return sorted(set(elins_tags) | set(runtime_events))


def dispatch_operator_intent(operator_intent,
                              vault_state) -> dict:
    """Dispatch an operator intent through the runtime kernel and
    assemble the UI-facing response.

    Args:
        operator_intent: locked-shape intent. ``payload.elins_inputs``
            is required (forwarded to Unit 35 → Unit 33).
        vault_state:     prior vault state. ``None`` on first session.

    Returns:
        Locked-shape dispatch result — see module docstring.

    Raises:
        ValueError on malformed inputs.
    """
    _validate_operator_intent(operator_intent)

    model_route = _select_engine(operator_intent)
    session_ctx = _build_session_context_for_kernel(operator_intent)

    runtime = run_runtime_step(
        operator_intent, session_ctx, vault_state,
    )

    severity = _DECISION_SEVERITY_MAP[runtime["runtime_decision"]]
    headline = runtime["operator_view"]["headline"]
    body = _build_ui_body(runtime)
    tags = _build_tags(runtime)

    return {
        "session_id":  operator_intent["session_id"],
        "operator_id": operator_intent["operator_id"],
        "timestamp":   operator_intent["timestamp"],
        "model_route": model_route,
        "runtime":     runtime,
        "ui_response": {
            "headline": headline,
            "body":     body,
            "severity": severity,
            "tags":     tags,
        },
    }
