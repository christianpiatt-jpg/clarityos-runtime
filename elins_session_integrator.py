"""
elins_session_integrator.py — ELINS13 Unit 33.

ELINS session integrator. Binds the ELINS intelligence engine to the
runtime kernel by defining the canonical session entrypoint:
operator-intent + previous-state → assembled ELINS payload + vault
update.

ROLE
----
Bridge layer between the ELINS2-12 intelligence stack and the runtime
kernel. Takes raw evaluation material (Unit 21 batches, Unit 23/25/27
outputs, Unit 29 comparisons, optional fusion history) plus an
operator session context, then composes Units 31 + 32 to produce the
runtime-safe ELINS output. Pure composition over Units 31 + 32 — no
I/O, no persistence, no randomness. The RuntimeKernel (Unit 34 and
beyond) handles storage.

INPUT CONTRACTS (locked)
------------------------
``session_context``::

    {
      "session_id":    str (non-empty),
      "operator_id":   str (non-empty),
      "timestamp":     str (ISO-8601),
      "vault_state":   dict | None  # previous ELINS fusion state
      "runtime_flags": dict          # {allow_overrides, strict_mode, ...}
    }

``elins_inputs``::

    {
      "batches":             list | None   # Unit 21 batch outputs
      "cross_batch":         dict | None   # Unit 23 output
      "trend":               dict | None   # Unit 25 output
      "structural":          dict          # Unit 27 output    REQUIRED
      "regime_comparison":   dict          # Unit 29 output    REQUIRED
      "fusion_history":      list | None   # list of Unit 29 outputs
    }

OUTPUT CONTRACT (locked)
------------------------
::

    {
      "session_id":  str,
      "operator_id": str,
      "timestamp":   str,
      "elins": {
        "structural": <Unit 27 output, pass-through>,
        "regime":     <Unit 29 output, the appended comparison>,
        "fusion":     <Unit 31 output>,
        "long_arc":   <Unit 32 output>,
      },
      "decision":     "allow | warn | block",
      "tags":         list[str],
      "vault_update": {
        "fusion_history": list[dict],   # updated history (prior + new)
        "last_fusion":    <Unit 31 output>,
        "last_long_arc":  <Unit 32 output>,
      },
    }

LOGIC (locked)
--------------
1. Validate session context (required keys + types).
2. Validate ELINS inputs (structural + regime_comparison required;
   regime_comparison must carry the Unit 29 contract).
3. Resolve fusion history with the locked precedence:
        elins_inputs.fusion_history  >  vault_state.fusion_history  >  []
4. Append the new regime_comparison to the resolved history.
5. Run Unit 31 (``fuse_regime_history``) on the updated history.
6. Run Unit 32 (``evaluate_long_arc``) on the updated history.
7. Assemble the locked-shape output.

VAULT-SAFE SERIALIZATION
------------------------
Every field in the output is plain JSON: strings, ints/floats, lists,
or dicts. No tuples, no sets, no Python objects. Timestamps stay
strings; tags stay strings; histories stay lists.

PUBLIC API
----------
    run_elins_session(session_context: dict,
                      elins_inputs:    dict) -> dict
"""
from __future__ import annotations

from elins_operator_fusion import evaluate_long_arc
from elins_regime_fusion import fuse_regime_history


# Required key sets (locked).
_REQUIRED_SESSION_KEYS: tuple = ("session_id", "operator_id", "timestamp")
_REQUIRED_ELINS_INPUT_KEYS: tuple = ("structural", "regime_comparison")
_REQUIRED_REGIME_KEYS: tuple = (
    "regime_delta",
    "risk_assessment",
    "baseline",
    "candidate",
)


def _validate_session_context(ctx) -> None:
    if not isinstance(ctx, dict):
        raise ValueError(
            f"session_context must be a dict, got {type(ctx).__name__}"
        )
    for key in _REQUIRED_SESSION_KEYS:
        if key not in ctx:
            raise ValueError(
                f"session_context missing required key {key!r}"
            )
        val = ctx[key]
        if not isinstance(val, str) or not val:
            raise ValueError(
                f"session_context[{key!r}] must be a non-empty string, "
                f"got {val!r}"
            )


def _validate_elins_inputs(inputs) -> None:
    if not isinstance(inputs, dict):
        raise ValueError(
            f"elins_inputs must be a dict, got {type(inputs).__name__}"
        )
    for key in _REQUIRED_ELINS_INPUT_KEYS:
        if key not in inputs:
            raise ValueError(
                f"elins_inputs missing required key {key!r}"
            )
    structural = inputs["structural"]
    if not isinstance(structural, dict):
        raise ValueError(
            f"elins_inputs['structural'] must be a dict, "
            f"got {type(structural).__name__}"
        )
    rc = inputs["regime_comparison"]
    if not isinstance(rc, dict):
        raise ValueError(
            f"elins_inputs['regime_comparison'] must be a dict, "
            f"got {type(rc).__name__}"
        )
    for key in _REQUIRED_REGIME_KEYS:
        if key not in rc:
            raise ValueError(
                f"elins_inputs['regime_comparison'] missing "
                f"required Unit 29 key {key!r}"
            )
    if "fusion_history" in inputs and inputs["fusion_history"] is not None:
        if not isinstance(inputs["fusion_history"], list):
            raise ValueError(
                f"elins_inputs['fusion_history'] must be a list, "
                f"got {type(inputs['fusion_history']).__name__}"
            )


def _resolve_fusion_history(elins_inputs: dict,
                             vault_state) -> list:
    """Resolve the starting fusion history. Precedence (locked):

        1. elins_inputs.fusion_history     — caller-explicit
        2. vault_state.fusion_history      — vault continuity
        3. []                              — first session

    The resolved list is COPIED so subsequent mutation of the input
    leaves our internal state untouched.
    """
    history = elins_inputs.get("fusion_history")
    if history is None and isinstance(vault_state, dict):
        history = vault_state.get("fusion_history")
    if history is None:
        history = []
    if not isinstance(history, list):
        raise ValueError(
            f"fusion_history must be a list, got {type(history).__name__}"
        )
    return list(history)


def run_elins_session(session_context, elins_inputs) -> dict:
    """Canonical ELINS entrypoint for the runtime.

    Args:
        session_context: locked-shape session metadata (see module
            docstring).
        elins_inputs:    raw evaluation material; ``structural`` and
            ``regime_comparison`` are required.

    Returns:
        Locked-shape runtime-safe ELINS output — see module docstring
        for the full schema.

    Raises:
        ValueError on a malformed session_context or elins_inputs.
    """
    _validate_session_context(session_context)
    _validate_elins_inputs(elins_inputs)

    vault_state = session_context.get("vault_state")
    if vault_state is not None and not isinstance(vault_state, dict):
        raise ValueError(
            f"session_context['vault_state'] must be a dict or None, "
            f"got {type(vault_state).__name__}"
        )

    fusion_history = _resolve_fusion_history(elins_inputs, vault_state)
    regime_comparison = elins_inputs["regime_comparison"]
    structural = elins_inputs["structural"]

    updated_history = fusion_history + [regime_comparison]
    fusion = fuse_regime_history(updated_history)
    long_arc = evaluate_long_arc(updated_history)

    return {
        "session_id":  session_context["session_id"],
        "operator_id": session_context["operator_id"],
        "timestamp":   session_context["timestamp"],
        "elins": {
            "structural": structural,
            "regime":     regime_comparison,
            "fusion":     fusion,
            "long_arc":   long_arc,
        },
        "decision": long_arc["decision"],
        "tags":     list(long_arc["tags"]),
        "vault_update": {
            "fusion_history": updated_history,
            "last_fusion":    fusion,
            "last_long_arc":  long_arc,
        },
    }
