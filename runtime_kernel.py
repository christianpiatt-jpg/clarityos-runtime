"""
runtime_kernel.py — Unit 35.

Runtime kernel core. The central execution loop for ClarityOS:
operator intent + session context + vault state → ELINS evaluation +
runtime decision + vault update + operator-facing view.

ROLE
----
First runtime-level module. Wires ELINS (Units 33 + 34) into a
deterministic step function. No model calls, no persistence, no
network — those belong to the outer dispatcher (Unit 36) and the
vault storage layer respectively. This unit is the pure-functional
"runtime step" the dispatcher will eventually call inside a real
operator loop.

PIPELINE
--------
1. Validate ``operator_intent`` and ``session_context``.
2. Resolve the ELINS sub-state from ``vault_state.elins`` (if any).
3. Build the Unit 33 session context, including:
       * session_id / operator_id / timestamp (from session_context)
       * vault_state          (the ELINS sub-state from vault)
       * runtime_flags        (derived from session_context.runtime_mode)
4. Extract ``elins_inputs`` from ``operator_intent.payload`` (required
   key — the upstream pipeline must have already computed Unit 27 +
   Unit 29 outputs and bundled them under that key).
5. Call ``run_elins_session`` (Unit 33) → ELINS output.
6. Build the Unit 34 runtime context, including:
       * session_id / operator_id / timestamp
       * runtime_mode         (from session_context)
       * optional override    (from operator_intent.payload.override)
7. Call ``apply_elins_runtime_actions`` (Unit 34) → runtime action.
8. Merge vault state: replace ``elins`` sub-state with the new
   ELINS vault_update; preserve every other sub-state untouched.
9. Build the operator view (deterministic headline + safe details).
10. Return the locked-shape runtime step output.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "session_id":      str,
      "operator_id":     str,
      "timestamp":       str,
      "runtime_decision": "allow | warn | block",
      "runtime_events":  list[str],
      "elins_block":     <full Unit 33 output>,
      "vault_update":    {<merged vault state>},
      "operator_view": {
        "headline": str,
        "details":  {
          "decision":            str,
          "runtime_events":      list[str],
          "tags":                list[str],
          "long_arc_assessment": str,
          "regime_start":        str,
          "regime_end":          str,
          "risk_level":          str,
        },
      },
    }

PUBLIC API
----------
    run_runtime_step(operator_intent: dict,
                     session_context: dict,
                     vault_state:     dict | None) -> dict
"""
from __future__ import annotations

from elins_runtime_actions import apply_elins_runtime_actions
from elins_session_integrator import run_elins_session


# Locked intent vocabulary.
_VALID_INTENT_TYPES: tuple = ("query", "action", "plan", "diagnostic")

# Locked runtime modes (mirror Unit 34).
_VALID_RUNTIME_MODES: tuple = ("normal", "strict", "diagnostic")

# Required context / intent keys.
_REQUIRED_INTENT_KEYS: tuple = (
    "session_id", "operator_id", "timestamp", "intent_type", "payload",
)
_REQUIRED_SESSION_CTX_KEYS: tuple = (
    "session_id", "operator_id", "timestamp", "runtime_mode",
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
    for key in ("session_id", "operator_id", "timestamp"):
        val = intent[key]
        if not isinstance(val, str) or not val:
            raise ValueError(
                f"operator_intent[{key!r}] must be a non-empty string, "
                f"got {val!r}"
            )
    if intent["intent_type"] not in _VALID_INTENT_TYPES:
        raise ValueError(
            f"operator_intent['intent_type'] must be one of "
            f"{_VALID_INTENT_TYPES}, got {intent['intent_type']!r}"
        )
    if not isinstance(intent["payload"], dict):
        raise ValueError(
            f"operator_intent['payload'] must be a dict, "
            f"got {type(intent['payload']).__name__}"
        )
    if "elins_inputs" not in intent["payload"]:
        raise ValueError(
            "operator_intent['payload'] missing required key "
            "'elins_inputs' (upstream pipeline must supply Unit 27 + "
            "Unit 29 outputs under that key)"
        )


def _validate_session_context(ctx) -> None:
    if not isinstance(ctx, dict):
        raise ValueError(
            f"session_context must be a dict, got {type(ctx).__name__}"
        )
    for key in _REQUIRED_SESSION_CTX_KEYS:
        if key not in ctx:
            raise ValueError(
                f"session_context missing required key {key!r}"
            )
    for key in ("session_id", "operator_id", "timestamp"):
        val = ctx[key]
        if not isinstance(val, str) or not val:
            raise ValueError(
                f"session_context[{key!r}] must be a non-empty string, "
                f"got {val!r}"
            )
    if ctx["runtime_mode"] not in _VALID_RUNTIME_MODES:
        raise ValueError(
            f"session_context['runtime_mode'] must be one of "
            f"{_VALID_RUNTIME_MODES}, got {ctx['runtime_mode']!r}"
        )


def _validate_vault_state(state) -> None:
    if state is None:
        return
    if not isinstance(state, dict):
        raise ValueError(
            f"vault_state must be a dict or None, "
            f"got {type(state).__name__}"
        )


def _build_elins_session_context(session_context: dict,
                                  vault_state) -> dict:
    """Construct the Unit 33 session context from runtime inputs."""
    elins_substate = None
    if isinstance(vault_state, dict):
        elins_substate = vault_state.get("elins")
        if elins_substate is not None and not isinstance(
            elins_substate, dict,
        ):
            raise ValueError(
                "vault_state['elins'] must be a dict or absent, "
                f"got {type(elins_substate).__name__}"
            )
    return {
        "session_id":    session_context["session_id"],
        "operator_id":   session_context["operator_id"],
        "timestamp":     session_context["timestamp"],
        "vault_state":   elins_substate,
        "runtime_flags": {
            "allow_overrides": True,
            "strict_mode":     session_context["runtime_mode"] == "strict",
        },
    }


def _build_runtime_context(session_context: dict,
                            override) -> dict:
    """Construct the Unit 34 runtime context. Override is optional."""
    out = {
        "session_id":       session_context["session_id"],
        "operator_id":      session_context["operator_id"],
        "timestamp":        session_context["timestamp"],
        "runtime_mode":     session_context["runtime_mode"],
        "previous_actions": [],
    }
    if override is not None:
        out["override"] = override
    return out


def _merge_vault_state(vault_state,
                        elins_vault_update: dict) -> dict:
    """Replace ELINS sub-state with the new update; preserve every
    other top-level key from the prior vault state."""
    merged: dict = {}
    if isinstance(vault_state, dict):
        for key, val in vault_state.items():
            if key == "elins":
                continue
            merged[key] = val
    merged["elins"] = elins_vault_update
    return merged


def _operator_headline(decision: str,
                       long_arc_assessment: str,
                       runtime_events: list) -> str:
    """Deterministic single-sentence operator headline."""
    prefix = decision.upper()
    if long_arc_assessment == "persistent_degradation":
        return f"{prefix}: Persistent degradation detected."
    if long_arc_assessment == "persistent_risk":
        return f"{prefix}: Persistent risk across recent regimes."
    if "runtime_long_arc_whipsaw" in runtime_events:
        return f"{prefix}: Whipsaw oscillation detected."
    if long_arc_assessment == "stabilizing":
        return f"{prefix}: Regime stabilizing."
    if long_arc_assessment == "benign":
        return f"{prefix}: Benign long-arc state."
    return f"{prefix}: Operator step evaluated."


def _operator_details(elins_block: dict,
                      runtime_action: dict) -> dict:
    """Locked-shape safe subset of ELINS + runtime info. No internal
    wiring is exposed — only operator-relevant fields."""
    fusion = elins_block["elins"]["fusion"]
    trajectory = fusion["trajectory"]
    cumulative = fusion["cumulative_risk"]
    return {
        "decision":            runtime_action["decision"],
        "runtime_events":      list(runtime_action["runtime_events"]),
        "tags":                list(elins_block.get("tags", [])),
        "long_arc_assessment": fusion["long_arc_assessment"],
        "regime_start":        trajectory.get("start_regime", ""),
        "regime_end":          trajectory.get("end_regime", ""),
        "risk_level":          cumulative.get("risk_level", "low"),
    }


def run_runtime_step(operator_intent,
                      session_context,
                      vault_state) -> dict:
    """Single runtime step.

    Args:
        operator_intent: locked-shape intent dict — see module
            docstring for the schema. ``payload.elins_inputs`` is
            required and feeds Unit 33.
        session_context: locked-shape runtime session metadata.
        vault_state:     dict carrying prior runtime state, including
            an ``"elins"`` sub-state from a previous step. May be
            ``None`` on the first session.

    Returns:
        Locked-shape runtime step output — see module docstring.

    Raises:
        ValueError on malformed inputs.
    """
    _validate_operator_intent(operator_intent)
    _validate_session_context(session_context)
    _validate_vault_state(vault_state)

    elins_session_ctx = _build_elins_session_context(
        session_context, vault_state,
    )
    elins_inputs = operator_intent["payload"]["elins_inputs"]
    elins_block = run_elins_session(elins_session_ctx, elins_inputs)

    override = operator_intent["payload"].get("override")
    runtime_context = _build_runtime_context(session_context, override)
    runtime_action = apply_elins_runtime_actions(
        runtime_context, elins_block,
    )

    merged_vault = _merge_vault_state(
        vault_state, elins_block["vault_update"],
    )

    long_arc_assessment = elins_block["elins"]["fusion"][
        "long_arc_assessment"
    ]
    headline = _operator_headline(
        runtime_action["decision"],
        long_arc_assessment,
        runtime_action["runtime_events"],
    )
    details = _operator_details(elins_block, runtime_action)

    return {
        "session_id":  session_context["session_id"],
        "operator_id": session_context["operator_id"],
        "timestamp":   session_context["timestamp"],
        "runtime_decision": runtime_action["decision"],
        "runtime_events":   list(runtime_action["runtime_events"]),
        "elins_block":      elins_block,
        "vault_update":     merged_vault,
        "operator_view": {
            "headline": headline,
            "details":  details,
        },
    }
