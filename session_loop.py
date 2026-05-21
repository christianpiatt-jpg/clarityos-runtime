"""
session_loop.py — Unit 40 (extended at v61 / Unit 43 with persistence).

Session loop façade. Wraps Unit 39
(``operator_session_runner.run_operator_session_step``) with a tiny
session_state container that tracks history. Designed for REPLs,
unit-test loops, and the first UI surface.

v61 / Unit 43 — persistence-integrated. ``start_session`` now hydrates
the operator's vault from ``runtime_persistence.load_vault`` when one
exists (cold-start operators still get an empty vault, same as v40).
``step_session`` writes both the updated vault (keyed by operator_id)
and the updated session (keyed by session_id) to
``runtime_persistence`` after each step so sessions survive process
restarts. The session_state shape is unchanged.

v64 / Unit 64 — lost-update fix. ``step_session`` now reloads both
session and vault from persistence at the top of every call before
applying the step. The caller's ``session_state`` argument is used
only for identity (``session_id`` + ``operator_id``); the actual
vault_state + history applied to the step come from disk/memory
storage. This supersedes the v61 "vault hydrated only at start"
contract — concurrent sessions for the same operator no longer
overwrite each other with arbitrarily stale state. Last writer still
wins (lock guarantees atomicity, not merge), but each writer sees
the latest committed snapshot.

ROLE
----
Convenience layer above Unit 39. The runner is a pure single-step
function: it has no concept of "session" beyond what the caller hands
in. This module supplies the session-state plumbing so a caller can:

    1. ``start_session(operator_id)`` once
    2. ``step_session(state, "what do I do next?")`` per operator turn

without re-assembling vault_state, history, or session_id by hand.

IMMUTABILITY POLICY (locked)
----------------------------
``step_session`` **returns a new session_state**; it never mutates the
input. Callers that want long-running sessions should rebind:

    state = start_session("op_alice")
    out   = step_session(state, "first step")
    state = out["session_state"]    # rebind, do not mutate

This matches every other module in the runtime stack and lets tests
compare before/after snapshots.

NON-DETERMINISM (clearly bounded)
---------------------------------
Unlike Units 35–39, this layer is **not byte-deterministic** because:

    * ``start_session`` mints a session_id from ``uuid4``
    * ``step_session`` stamps each history entry with ``datetime.now``

Both sources are concentrated in two module-level helpers
(``_make_session_id`` and ``_now``) so tests can monkey-patch them
for full determinism. The runtime stack below this layer remains
deterministic — Unit 40 is the only injection point.

ELINS INPUTS — DEFAULT BENIGN STUB
----------------------------------
Unit 33 requires ``elins_inputs.structural`` (Unit 27 output) and
``elins_inputs.regime_comparison`` (Unit 29 output). The session
façade has no way to compute these from operator text alone — that's
the job of an upstream ELINS pipeline. For the in-memory façade we
supply a benign-stable stub via ``_default_elins_inputs`` so the
chain exercises end-to-end. Real callers replace the stub by
patching the helper or by extending this module with a real
inputs-builder in a later unit.

SESSION STATE SHAPE (locked)
----------------------------
::

    {
      "session_id":  str,
      "operator_id": str,
      "vault_state": dict,           # Unit 35's merged vault state
      "history": [
        {
          "timestamp":        str,
          "intent_type":      str,
          "text":             str,
          "runtime_decision": "allow | warn | block",
          "engine":           "copilot | claude | gemini | grok | local",
        },
        ...
      ],
    }

PUBLIC API
----------
    start_session(operator_id: str) -> dict
    step_session(session_state: dict, text: str, *,
                  intent_type: str = "query") -> dict
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import runtime_persistence
import runtime_providers
from operator_session_runner import run_operator_session_step


# Locked vocabulary (mirrors Unit 35).
_VALID_INTENT_TYPES: tuple = ("query", "action", "plan", "diagnostic")


# ---------------------------------------------------------------------------
# Bounded non-determinism — patchable helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    """Return current UTC time as ISO-8601. Tests monkey-patch."""
    return datetime.now(timezone.utc).isoformat()


def _make_session_id() -> str:
    """Mint a fresh session_id. Tests monkey-patch."""
    return "sess-" + uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Default benign-stable ELINS inputs stub
# ---------------------------------------------------------------------------
def _default_elins_inputs() -> dict:
    """Benign-stable Unit 27 + Unit 29 stub so the façade exercises
    the full chain end-to-end without an upstream pipeline. Returns
    a fresh dict each call so callers / step_session don't share
    state across history entries."""
    return {
        "batches":           [],
        "cross_batch":       None,
        "trend":             None,
        "structural": {
            "timeline":            [],
            "regime_class":        "stable",
            "volatility_variance": 0.001,
            "breakpoints":         [],
            "structural_events":   [],
            "summary":             "stable.",
        },
        "regime_comparison": {
            "regime_delta":    "same",
            "risk_assessment": "low",
            "baseline":        {"regime_class": "stable"},
            "candidate":       {"regime_class": "stable"},
            "volatility_delta":  {"absolute": 0.0, "relative": 0.0},
            "breakpoint_delta":  {
                "baseline_count": 0, "candidate_count": 0, "delta": 0,
            },
            "event_summary": {
                "new_events":       [],
                "resolved_events":  [],
                "persistent_events": [],
            },
            "summary": "",
        },
        "fusion_history": None,
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
_REQUIRED_SESSION_KEYS: tuple = (
    "session_id", "operator_id", "vault_state", "history",
)


def _validate_operator_id(operator_id) -> None:
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError(
            f"operator_id must be a non-empty string, got {operator_id!r}"
        )


def _validate_text(text) -> None:
    if not isinstance(text, str):
        raise ValueError(
            f"text must be a string, got {type(text).__name__}"
        )


def _validate_intent_type(intent_type) -> None:
    if intent_type not in _VALID_INTENT_TYPES:
        raise ValueError(
            f"intent_type must be one of {_VALID_INTENT_TYPES}, "
            f"got {intent_type!r}"
        )


def _validate_session_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError(
            f"session_state must be a dict, got {type(state).__name__}"
        )
    for key in _REQUIRED_SESSION_KEYS:
        if key not in state:
            raise ValueError(
                f"session_state missing required key {key!r}"
            )
    if not isinstance(state["session_id"], str) or not state["session_id"]:
        raise ValueError("session_state['session_id'] must be a non-empty string")
    if not isinstance(state["operator_id"], str) or not state["operator_id"]:
        raise ValueError("session_state['operator_id'] must be a non-empty string")
    if not isinstance(state["vault_state"], dict):
        raise ValueError("session_state['vault_state'] must be a dict")
    if not isinstance(state["history"], list):
        raise ValueError("session_state['history'] must be a list")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def start_session(operator_id) -> dict:
    """Begin a session for ``operator_id``.

    v61 / Unit 43: hydrates ``vault_state`` from
    ``runtime_persistence.load_vault(operator_id)`` when a vault
    exists for this operator. ``session_id`` is always fresh — the
    vault is per-operator long-lived state; sessions are per-thread
    ephemeral wrappers around it. The new session is saved
    immediately so a later ``/start`` with ``resume=true`` can find
    it.

    Args:
        operator_id: non-empty string.

    Returns:
        Locked-shape session_state — see module docstring.

    Raises:
        ValueError: when ``operator_id`` is empty / not a string.
    """
    _validate_operator_id(operator_id)
    # Try to hydrate the operator's vault from persistence. None when
    # no prior vault exists — falls back to an empty dict so the
    # cold-start behaviour matches v40.
    prior_vault = runtime_persistence.load_vault(operator_id)
    vault_state: dict = prior_vault if isinstance(prior_vault, dict) else {}
    state = {
        "session_id":  _make_session_id(),
        "operator_id": operator_id,
        "vault_state": vault_state,
        "history":     [],
    }
    # Persist the fresh session shell so a subsequent
    # ``runtime_persistence.load_session(session_id)`` can find it.
    runtime_persistence.save_session(state)
    return state


def step_session(session_state,
                  text,
                  *,
                  intent_type: str = "query") -> dict:
    """Advance the session by one operator step.

    Builds an operator_intent from the session_state + text + intent_type,
    calls Unit 39, then returns a new session_state with the vault
    updated and a history entry appended.

    Args:
        session_state: prior session_state (typically returned from
            ``start_session`` or a previous ``step_session``).
        text: operator's input text. Free-form; the runtime layer
            doesn't currently inspect it semantically — the model
            router only uses it for the prompt preview.
        intent_type: locked vocabulary
            (``query | action | plan | diagnostic``). Defaults to
            ``"query"``.

    Returns:
        ``{
            "session_state": <new state with appended history + new vault>,
            "step_result":   <full Unit 39 output>,
          }``

    Raises:
        ValueError: when inputs are malformed, or when any downstream
            unit raises (validation, missing keys). Errors propagate
            unchanged so callers can distinguish façade-level
            problems from runtime-level ones via the message text.
    """
    _validate_session_state(session_state)
    _validate_text(text)
    _validate_intent_type(intent_type)

    # v64 / Unit 64 — Lost-update fix.
    #
    # Reload session + vault from persistence before applying the
    # step. The caller's ``session_state`` is now used only for
    # identity (session_id + operator_id); the actual vault_state +
    # history come from the persistence layer. This supersedes the
    # v61-documented "vault hydrated only at start" rationale:
    # under v64, every step reloads, so two sessions stepping
    # concurrently for the same operator each see the latest
    # committed state at call time. Last-writer-still-wins, but
    # nobody writes against arbitrarily stale state.
    #
    # If persistence misses (e.g. session was never saved before the
    # very first step — unusual since start_session saves the shell,
    # but possible under racy reset_for_tests), fall back to the
    # caller's session_state so the step still completes deterministically.
    session_id = session_state["session_id"]
    operator_id = session_state["operator_id"]
    stored_session = runtime_persistence.load_session(session_id)
    stored_vault = runtime_persistence.load_vault(operator_id)

    effective_history = (
        list(stored_session["history"])
        if isinstance(stored_session, dict)
        and isinstance(stored_session.get("history"), list)
        else list(session_state["history"])
    )
    effective_vault: dict = (
        stored_vault
        if isinstance(stored_vault, dict)
        else session_state["vault_state"]
    )

    timestamp = _now()

    # v64 / Unit 65 — Vault-stored model preference.
    # ``get_operator_model`` walks the resolution chain (vault →
    # first-available-provider → fallback). When the resolved
    # (provider, model) maps to a SUPPORTED_MODELS id, we inject it
    # under ``payload.preferred_model_id`` so Unit 38's
    # route_model_request picks it over the engine-based default.
    # Absent / invalid → no injection, existing v58 resolution wins.
    preferred_provider, preferred_model = runtime_providers.get_operator_model(
        effective_vault,
    )
    try:
        preferred_model_id = runtime_providers.model_id_for(
            preferred_provider, preferred_model,
        )
    except ValueError:
        preferred_model_id = None

    payload: dict = {
        "text":         text,
        "runtime_mode": "normal",
        "elins_inputs": _default_elins_inputs(),
    }
    if preferred_model_id:
        payload["preferred_model_id"] = preferred_model_id

    operator_intent = {
        "session_id":  session_id,
        "operator_id": operator_id,
        "timestamp":   timestamp,
        "intent_type": intent_type,
        "payload":     payload,
    }

    step_result = run_operator_session_step(
        operator_intent, effective_vault,
    )

    # Pull the operator-relevant signals out of the step result and
    # append a compact history entry. ``runtime_decision`` lives
    # under runtime.runtime per the nested-naming clash documented
    # in operator_session_runner.py.
    runtime_decision = (
        step_result["runtime"]["runtime"]["runtime_decision"]
    )
    engine = step_result["runtime"]["model_route"]["engine"]

    # v64 / Unit 65 — Provider-error recording.
    # When the real-HTTP path in model_router fails, the response
    # dict carries a ``fallback_error`` field (set by ``_mock_result``
    # when called with ``error=...``). We surface that into the
    # history entry as an optional ``provider_error`` field so
    # operators can see which steps degraded to mock. Absent on
    # success.
    history_entry: dict = {
        "timestamp":        timestamp,
        "intent_type":      intent_type,
        "text":             text,
        "runtime_decision": runtime_decision,
        "engine":           engine,
    }
    model_response = (
        step_result.get("model", {}).get("response", {})
        if isinstance(step_result.get("model"), dict)
        else {}
    )
    fallback_error = model_response.get("fallback_error") if isinstance(model_response, dict) else None
    if isinstance(fallback_error, str) and fallback_error:
        history_entry["provider_error"] = fallback_error

    new_state = {
        "session_id":  session_id,
        "operator_id": operator_id,
        "vault_state": step_result["vault_update"],
        "history": effective_history + [history_entry],
    }

    # v61 / Unit 43 — persist both. Vault keyed by operator_id (long-
    # lived per-operator ELINS continuity); session keyed by session_id
    # (ephemeral per-thread state, includes vault_state + history).
    # v64 / Unit 64 — saves stay after the step succeeds. If
    # ``run_operator_session_step`` raises, neither save executes, so
    # persisted state is unchanged (Scenario B in
    # test_step_session_lost_update.py).
    runtime_persistence.save_vault(
        new_state["operator_id"], new_state["vault_state"],
    )
    runtime_persistence.save_session(new_state)

    return {
        "session_state": new_state,
        "step_result":   step_result,
    }
