"""
elins_runtime_actions.py — ELINS13 Unit 34.

ELINS runtime actions. Maps an ELINS session output (Unit 33) into
runtime-level events, applies strict-mode and operator-override
semantics, and emits an audit block — all without mutating either
input.

ROLE
----
Final integration layer between ELINS and the RuntimeKernel. Pure
composition over Unit 33's output. No I/O, no persistence, no
randomness. The RuntimeKernel consumes this module's output and
handles propagation / storage.

DECISION PIPELINE (locked order)
--------------------------------
    1. base_decision = elins_output["decision"]
    2. if runtime_mode == "strict":  apply strict adjustment
                                     (allow→warn, warn→block)
    3. if runtime_context.override:  override.override_decision wins

Override is the operator's final word — applied AFTER strict so a
"strict + operator-overrides-to-allow" path resolves cleanly.

RUNTIME EVENT VOCABULARY (locked)
----------------------------------
The only events the runtime may emit from ELINS::

    runtime_allow
    runtime_warn
    runtime_block
    runtime_escalate
    runtime_override
    runtime_long_arc_whipsaw
    runtime_long_arc_persistent_risk
    runtime_long_arc_persistent_degradation

Insertion order (locked, deterministic):

    [decision_event, runtime_override?, runtime_escalate?,
     runtime_long_arc_whipsaw?, runtime_long_arc_persistent_risk?,
     runtime_long_arc_persistent_degradation?]

Each event appears at most once.

ESCALATION RULES (locked)
-------------------------
``runtime_escalate`` fires when ANY of:

    * elins long_arc_assessment == "persistent_risk"
    * elins long_arc_assessment == "persistent_degradation"
    * elins long_arc_assessment == "oscillating_regime" AND whipsaw
    * runtime_context.override.escalate == True

OVERRIDE STRUCTURE (locked)
---------------------------
``runtime_context.override`` is optional. When present::

    {
      "override_decision": "allow | warn | block",
      "escalate":          bool,
      "audit_note":        str,
    }

Override is validated; only ``override_decision`` is required, the
other fields are optional.

OUTPUT SHAPE (locked)
---------------------
::

    {
      "session_id":  str,
      "operator_id": str,
      "timestamp":   str,
      "decision":    "allow | warn | block",
      "runtime_events": list[str],
      "overrides":      dict,          # echo of validated override
      "audit": {
        "elins_decision":      <original ELINS decision before strict/override>,
        "runtime_mode":        "normal | strict | diagnostic",
        "tags":                list[str],
        "long_arc_assessment": str,
      },
    }

PUBLIC API
----------
    apply_elins_runtime_actions(runtime_context: dict,
                                 elins_output:    dict) -> dict
"""
from __future__ import annotations


# Locked event vocabulary.
EVENT_RUNTIME_ALLOW:    str = "runtime_allow"
EVENT_RUNTIME_WARN:     str = "runtime_warn"
EVENT_RUNTIME_BLOCK:    str = "runtime_block"
EVENT_RUNTIME_ESCALATE: str = "runtime_escalate"
EVENT_RUNTIME_OVERRIDE: str = "runtime_override"
EVENT_RUNTIME_LA_WHIPSAW:                 str = "runtime_long_arc_whipsaw"
EVENT_RUNTIME_LA_PERSISTENT_RISK:         str = "runtime_long_arc_persistent_risk"
EVENT_RUNTIME_LA_PERSISTENT_DEGRADATION:  str = "runtime_long_arc_persistent_degradation"

# Locked vocabularies.
_VALID_DECISIONS: tuple = ("allow", "warn", "block")
_VALID_RUNTIME_MODES: tuple = ("normal", "strict", "diagnostic")
_REQUIRED_RUNTIME_CTX_KEYS: tuple = (
    "session_id", "operator_id", "timestamp", "runtime_mode",
)
_REQUIRED_ELINS_OUTPUT_KEYS: tuple = ("decision", "elins", "tags")

# Decision → event map.
_DECISION_EVENT_MAP: dict = {
    "allow": EVENT_RUNTIME_ALLOW,
    "warn":  EVENT_RUNTIME_WARN,
    "block": EVENT_RUNTIME_BLOCK,
}

# Strict-mode adjustment (locked).
_STRICT_ADJUSTMENT: dict = {
    "allow": "warn",
    "warn":  "block",
    "block": "block",
}


def _validate_runtime_context(ctx) -> None:
    if not isinstance(ctx, dict):
        raise ValueError(
            f"runtime_context must be a dict, got {type(ctx).__name__}"
        )
    for key in _REQUIRED_RUNTIME_CTX_KEYS:
        if key not in ctx:
            raise ValueError(
                f"runtime_context missing required key {key!r}"
            )
    for key in ("session_id", "operator_id", "timestamp"):
        val = ctx[key]
        if not isinstance(val, str) or not val:
            raise ValueError(
                f"runtime_context[{key!r}] must be a non-empty string, "
                f"got {val!r}"
            )
    mode = ctx["runtime_mode"]
    if mode not in _VALID_RUNTIME_MODES:
        raise ValueError(
            f"runtime_context['runtime_mode'] must be one of "
            f"{_VALID_RUNTIME_MODES}, got {mode!r}"
        )
    if "previous_actions" in ctx and ctx["previous_actions"] is not None:
        if not isinstance(ctx["previous_actions"], list):
            raise ValueError(
                f"runtime_context['previous_actions'] must be a list, "
                f"got {type(ctx['previous_actions']).__name__}"
            )


def _validate_elins_output(elins_output) -> None:
    if not isinstance(elins_output, dict):
        raise ValueError(
            f"elins_output must be a dict, "
            f"got {type(elins_output).__name__}"
        )
    for key in _REQUIRED_ELINS_OUTPUT_KEYS:
        if key not in elins_output:
            raise ValueError(
                f"elins_output missing required key {key!r}"
            )
    if elins_output["decision"] not in _VALID_DECISIONS:
        raise ValueError(
            f"elins_output['decision'] must be one of "
            f"{_VALID_DECISIONS}, got {elins_output['decision']!r}"
        )
    elins_block = elins_output["elins"]
    if not isinstance(elins_block, dict) or "fusion" not in elins_block:
        raise ValueError(
            "elins_output['elins'] must be a dict containing 'fusion' "
            "(Unit 31 output)"
        )
    fusion = elins_block["fusion"]
    if not isinstance(fusion, dict):
        raise ValueError(
            f"elins_output['elins']['fusion'] must be a dict, "
            f"got {type(fusion).__name__}"
        )
    if "long_arc_assessment" not in fusion:
        raise ValueError(
            "elins_output['elins']['fusion'] missing 'long_arc_assessment'"
        )
    if "oscillation" not in fusion or "whipsaw" not in fusion["oscillation"]:
        raise ValueError(
            "elins_output['elins']['fusion']['oscillation']['whipsaw'] "
            "is required"
        )


def _validate_override(override) -> None:
    if not isinstance(override, dict):
        raise ValueError(
            f"runtime_context['override'] must be a dict, "
            f"got {type(override).__name__}"
        )
    if "override_decision" not in override:
        raise ValueError(
            "runtime_context['override'] missing required key "
            "'override_decision'"
        )
    if override["override_decision"] not in _VALID_DECISIONS:
        raise ValueError(
            f"runtime_context['override']['override_decision'] must be "
            f"one of {_VALID_DECISIONS}, "
            f"got {override['override_decision']!r}"
        )
    if "escalate" in override and not isinstance(override["escalate"], bool):
        raise ValueError(
            f"runtime_context['override']['escalate'] must be a bool, "
            f"got {type(override['escalate']).__name__}"
        )
    if "audit_note" in override and not isinstance(
        override["audit_note"], str,
    ):
        raise ValueError(
            f"runtime_context['override']['audit_note'] must be a string, "
            f"got {type(override['audit_note']).__name__}"
        )


def apply_elins_runtime_actions(runtime_context, elins_output) -> dict:
    """Apply runtime-level actions to a Unit 33 ELINS output.

    Args:
        runtime_context: locked-shape runtime metadata. Optional
            ``override`` key carries operator override directives.
        elins_output:    the locked-shape Unit 33 output.

    Returns:
        Locked-shape runtime-safe action payload — see module
        docstring for the full schema.

    Raises:
        ValueError on a malformed runtime_context, elins_output, or
        override.
    """
    _validate_runtime_context(runtime_context)
    _validate_elins_output(elins_output)

    elins_decision = elins_output["decision"]
    fusion = elins_output["elins"]["fusion"]
    long_arc_assessment = fusion["long_arc_assessment"]
    whipsaw = bool(fusion["oscillation"]["whipsaw"])
    runtime_mode = runtime_context["runtime_mode"]

    # Step 1+2: base decision + strict adjustment.
    decision = elins_decision
    if runtime_mode == "strict":
        decision = _STRICT_ADJUSTMENT[decision]

    # Step 3: override (operator's final word).
    override = runtime_context.get("override")
    overrides_out: dict = {}
    if override is not None:
        _validate_override(override)
        decision = override["override_decision"]
        # Echo the override fields the operator actually supplied.
        for key in ("override_decision", "escalate", "audit_note"):
            if key in override:
                overrides_out[key] = override[key]

    # Build runtime_events in locked insertion order.
    events: list = [_DECISION_EVENT_MAP[decision]]

    if override is not None:
        events.append(EVENT_RUNTIME_OVERRIDE)

    should_escalate = (
        long_arc_assessment == "persistent_risk"
        or long_arc_assessment == "persistent_degradation"
        or (long_arc_assessment == "oscillating_regime" and whipsaw)
        or (
            override is not None
            and bool(override.get("escalate", False))
        )
    )
    if should_escalate:
        events.append(EVENT_RUNTIME_ESCALATE)

    if whipsaw:
        events.append(EVENT_RUNTIME_LA_WHIPSAW)
    if long_arc_assessment == "persistent_risk":
        events.append(EVENT_RUNTIME_LA_PERSISTENT_RISK)
    elif long_arc_assessment == "persistent_degradation":
        events.append(EVENT_RUNTIME_LA_PERSISTENT_DEGRADATION)

    return {
        "session_id":  runtime_context["session_id"],
        "operator_id": runtime_context["operator_id"],
        "timestamp":   runtime_context["timestamp"],
        "decision":    decision,
        "runtime_events": events,
        "overrides":   overrides_out,
        "audit": {
            "elins_decision":      elins_decision,
            "runtime_mode":        runtime_mode,
            "tags":                list(elins_output.get("tags", [])),
            "long_arc_assessment": long_arc_assessment,
        },
    }
