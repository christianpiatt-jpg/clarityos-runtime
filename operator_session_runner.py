"""
operator_session_runner.py — Unit 39.

Single-call orchestrator that composes Units 36 + 38 into one operator
step. Knows nothing about ELINS internals, runtime modes, provider
keys, or routing tables — it just chains the two surfaces already
locked at v57 (Unit 36) and v58 (Unit 38).

ROLE
----
Top of the runtime stack. A UI layer or REPL calls this once per
operator step and gets back:

    1. the dispatcher result          (engine + kernel + UI surface)
    2. the model call result          (model_id + response + metadata)
    3. the merged vault state         (ready for persistence)

The session loop façade (Unit 40, ``session_loop.py``) sits one layer
above this and manages session_state + history. The FastAPI endpoint
that ships in a later unit will call this directly.

PURE & DETERMINISTIC (modulo route_request timestamps)
------------------------------------------------------
Same ``(operator_intent, vault_state)`` → byte-equal output **except**
for ``model.metadata.ts`` and ``model.response.ts``, which carry
``time.time()`` from ``route_request``. No I/O of its own, no new
network calls, no mutation of inputs.

PIPELINE (locked)
-----------------
1. Validate ``operator_intent`` is a dict.
2. Validate ``vault_state`` is a dict or ``None``.
3. ``dispatch_operator_intent(operator_intent, vault_state)``
       → dispatch result (Unit 36 output).
4. ``route_model_request(operator_intent, dispatch_result["model_route"])``
       → model result (Unit 38 output).
5. Compose locked-shape result. ``vault_update`` is lifted from
   ``dispatch_result["runtime"]["vault_update"]`` — Unit 35 already
   produced a fully merged state there; we just expose it at the top
   level for ergonomic persistence callers.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "session_id":   str,
      "operator_id":  str,
      "timestamp":    str,
      "runtime":      <full Unit 36 output>,
      "model":        <full Unit 38 output>,
      "vault_update": <merged vault state from Unit 35>,
    }

NESTED-NAMING NOTE
------------------
Unit 36's output contains a sub-key also called ``runtime`` (the
Unit 35 step output), so callers traverse ``result["runtime"]
["runtime"]["runtime_decision"]`` to reach the kernel's decision.
That clash predates this unit (it's in the v57 lock) and is preserved
deliberately — renaming would break the v57 contract.

Convenience top-level fields:

    result["session_id"]    == operator_intent["session_id"]
    result["vault_update"]  == result["runtime"]["runtime"]["vault_update"]

so the most common consumer paths skip one level.

PUBLIC API
----------
    run_operator_session_step(operator_intent: dict,
                              vault_state:     dict | None) -> dict
"""
from __future__ import annotations

from model_router import route_model_request
from runtime_dispatcher import dispatch_operator_intent


def _validate_operator_intent(intent) -> None:
    if not isinstance(intent, dict):
        raise ValueError(
            f"operator_intent must be a dict, got {type(intent).__name__}"
        )


def _validate_vault_state(state) -> None:
    if state is None:
        return
    if not isinstance(state, dict):
        raise ValueError(
            f"vault_state must be a dict or None, "
            f"got {type(state).__name__}"
        )


def run_operator_session_step(operator_intent,
                                vault_state) -> dict:
    """One operator step: dispatch → route → compose.

    Args:
        operator_intent: locked-shape intent (see Unit 35).
        vault_state:     prior vault state (Unit 35's previous
            ``vault_update`` output), or ``None`` on first session.

    Returns:
        Locked-shape session step result — see module docstring.

    Raises:
        ValueError: when ``operator_intent`` is not a dict or
            ``vault_state`` is not a dict / None, or when any
            downstream unit raises (validation, missing keys, etc.)
            — errors propagate unchanged.
    """
    _validate_operator_intent(operator_intent)
    _validate_vault_state(vault_state)

    dispatch_result = dispatch_operator_intent(operator_intent, vault_state)
    model_result = route_model_request(
        operator_intent, dispatch_result["model_route"],
    )

    return {
        "session_id":   operator_intent["session_id"],
        "operator_id":  operator_intent["operator_id"],
        "timestamp":    operator_intent["timestamp"],
        "runtime":      dispatch_result,
        "model":        model_result,
        "vault_update": dispatch_result["runtime"]["vault_update"],
    }
