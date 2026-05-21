"""
runtime_continuity.py — Unit 37.

Continuity reentry layer. Reconstructs an operator session from
persisted vault state so the runtime kernel can resume long-arc
ELINS intelligence across cold starts. Pure, deterministic, no I/O.

ROLE
----
First continuity-level module. Sits below the runtime kernel
(Unit 35) and the dispatcher (Unit 36): given a (session_id,
operator_id, vault_state) tuple from disk, return the continuity
object the kernel needs to seed its next ``run_runtime_step`` call.

This is the OS's "resume where you left off" layer. The vault layer
above handles I/O; this module just extracts and shapes.

PIPELINE (locked)
-----------------
1. Validate ``session_id`` and ``operator_id`` (non-empty strings).
2. Validate ``vault_state`` (dict or None).
3. Extract the ELINS sub-state from ``vault_state.elins`` (if any).
4. Pull the three continuity fields:
       * last_fusion       — Unit 31 output, or None
       * last_long_arc     — Unit 32 output, or None
       * fusion_history    — list of Unit 29 outputs, or []
5. Resolve ``runtime_mode`` from ``vault_state.runtime_mode`` if
   present and valid; default ``"normal"``.
6. Resolve ``timestamp`` deterministically from the most recent
   activity carried in the continuity (``last_fusion.timestamp``
   wins over ``last_long_arc.timestamp``); empty string when no
   prior activity exists.
7. Return the locked-shape continuity object.

PURE & DETERMINISTIC
--------------------
Same inputs → byte-equal output. No I/O, no network, no randomness,
no model calls. No mutation of inputs.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "session_id":  str,
      "operator_id": str,
      "timestamp":   str,
      "continuity": {
        "elins": {
          "last_fusion":    dict | None,
          "last_long_arc":  dict | None,
          "fusion_history": list[dict],
        },
        "runtime_mode": "normal | strict | diagnostic",
      },
    }

PUBLIC API
----------
    resume_runtime_session(session_id:  str,
                            operator_id: str,
                            vault_state: dict | None) -> dict
"""
from __future__ import annotations


# Locked runtime modes (mirror Unit 34 + Unit 35).
_VALID_RUNTIME_MODES: tuple = ("normal", "strict", "diagnostic")
_DEFAULT_RUNTIME_MODE: str = "normal"


def _validate_session_id(session_id) -> None:
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"session_id must be a non-empty string, got {session_id!r}"
        )


def _validate_operator_id(operator_id) -> None:
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError(
            f"operator_id must be a non-empty string, got {operator_id!r}"
        )


def _validate_vault_state(vault_state) -> None:
    if vault_state is None:
        return
    if not isinstance(vault_state, dict):
        raise ValueError(
            f"vault_state must be a dict or None, "
            f"got {type(vault_state).__name__}"
        )


def _extract_elins_substate(vault_state) -> dict:
    """Return the ELINS sub-state from vault_state, or an empty dict
    when no prior ELINS history exists (cold start)."""
    if not isinstance(vault_state, dict):
        return {}
    elins = vault_state.get("elins")
    if not isinstance(elins, dict):
        return {}
    return elins


def _resolve_fusion_history(elins_substate: dict) -> list:
    """Pull the fusion history from the ELINS sub-state. Always
    returns a list — empty when there's no prior history. Copies
    so mutation of the returned list does not affect the vault."""
    history = elins_substate.get("fusion_history")
    if not isinstance(history, list):
        return []
    return list(history)


def _resolve_last_fusion(elins_substate: dict):
    """Pull last_fusion from the ELINS sub-state. Returns None when
    absent or malformed — the caller treats None as cold-start."""
    val = elins_substate.get("last_fusion")
    if not isinstance(val, dict):
        return None
    return val


def _resolve_last_long_arc(elins_substate: dict):
    """Pull last_long_arc from the ELINS sub-state. Returns None when
    absent or malformed."""
    val = elins_substate.get("last_long_arc")
    if not isinstance(val, dict):
        return None
    return val


def _resolve_runtime_mode(vault_state) -> str:
    """Resolve runtime_mode from the top-level vault state. Defaults
    to ``"normal"`` when absent. Invalid values fall back to default
    (deliberately tolerant — vault writes from outside this module
    must not crash continuity reentry)."""
    if not isinstance(vault_state, dict):
        return _DEFAULT_RUNTIME_MODE
    mode = vault_state.get("runtime_mode")
    if isinstance(mode, str) and mode in _VALID_RUNTIME_MODES:
        return mode
    return _DEFAULT_RUNTIME_MODE


def _resolve_timestamp(last_fusion, last_long_arc) -> str:
    """Pick a deterministic timestamp from the most recent activity.

    Precedence (locked):
        1. last_fusion.timestamp
        2. last_long_arc.timestamp
        3. ""    (no prior activity)
    """
    for source in (last_fusion, last_long_arc):
        if isinstance(source, dict):
            ts = source.get("timestamp")
            if isinstance(ts, str) and ts:
                return ts
    return ""


def resume_runtime_session(session_id,
                            operator_id,
                            vault_state) -> dict:
    """Reconstruct a runtime session from persisted vault state.

    Args:
        session_id:  non-empty string identifying the session to resume.
        operator_id: non-empty string identifying the operator.
        vault_state: dict carrying prior runtime state (typically the
            ``vault_update`` field of the most recent
            ``run_runtime_step`` output). ``None`` on a true cold
            start with no prior history.

    Returns:
        Locked-shape continuity object — see module docstring.

    Raises:
        ValueError on malformed session_id / operator_id / vault_state.
    """
    _validate_session_id(session_id)
    _validate_operator_id(operator_id)
    _validate_vault_state(vault_state)

    elins_substate = _extract_elins_substate(vault_state)
    last_fusion = _resolve_last_fusion(elins_substate)
    last_long_arc = _resolve_last_long_arc(elins_substate)
    fusion_history = _resolve_fusion_history(elins_substate)
    runtime_mode = _resolve_runtime_mode(vault_state)
    timestamp = _resolve_timestamp(last_fusion, last_long_arc)

    return {
        "session_id":  session_id,
        "operator_id": operator_id,
        "timestamp":   timestamp,
        "continuity": {
            "elins": {
                "last_fusion":    last_fusion,
                "last_long_arc":  last_long_arc,
                "fusion_history": fusion_history,
            },
            "runtime_mode": runtime_mode,
        },
    }
