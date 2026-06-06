# phase9_ingest.py
"""
Phase 9.1 — Action Stream Ingestion.

The first moment ClarityOS sees operator behaviour as a *stream*: raw actions are
validated, normalized into ``ActionEvent`` (9.0), and appended to an append-only
continuity log, ready for the Phase 9.2 causal-graph integration.

    ingest_action(raw) -> ActionEvent              # validate + normalize
    store_action(event, continuity) -> None        # append (timestamp-sorted)
    load_recent_actions(continuity, now, window) -> list[ActionEvent]

**Continuity store.** ``continuity`` is a plain dict with an ``"actions"`` list —
``{"actions": [ActionEvent, ...]}`` — mirroring the Phase-7 telemetry continuity
mechanism (append-only, sorted by timestamp, no mutation / deletion). It is kept
Phase-9-local (a parallel log) rather than retrofitting the telemetry-specific
``phase7_storage``; this card adds no new persistence layer (in-memory only) and
no schema changes. A process-wide default lives here for the endpoint.

**No wall-clock.** ``load_recent_actions`` takes an explicit ``now`` (the card's
rules require the caller to supply it); nothing here reads the clock.

Pure / deterministic (ingestion has no randomness or wall-clock). Imports only
the 9.0 primitive + stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state.

See ``phase9_spec.md`` ("Phase 9.1 — Action Stream Ingestion").
"""
from phase9_actions import ActionEvent

# Magnitude bound — actions outside this band are rejected (9.1 validation).
MAGNITUDE_MIN = -1.0
MAGNITUDE_MAX = 1.0


def _is_number(value) -> bool:
    """A real number (int or float) but NOT a bool (``True`` is an ``int``)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def ingest_action(raw: dict) -> ActionEvent:
    """Validate + normalize a raw operator action into an ``ActionEvent``.

    Rules (all violations raise ``ValueError``): ``id`` and ``label`` are
    required strings; ``timestamp`` is a required, non-negative number;
    ``magnitude`` is optional (``None`` or a number within ``[-1, 1]``).
    Deterministic — no inference, randomness, or wall-clock.
    """
    if not isinstance(raw, dict):
        raise ValueError("action must be a JSON object")
    if not isinstance(raw.get("id"), str):
        raise ValueError("action.id is required and must be a string")
    if not isinstance(raw.get("label"), str):
        raise ValueError("action.label is required and must be a string")

    timestamp = raw.get("timestamp")
    if not _is_number(timestamp):
        raise ValueError("action.timestamp is required and must be a number")
    timestamp = float(timestamp)
    if timestamp < 0:
        raise ValueError("action.timestamp must be non-negative")

    magnitude = raw.get("magnitude")
    if magnitude is not None:
        if not _is_number(magnitude):
            raise ValueError("action.magnitude must be a number or null")
        magnitude = float(magnitude)
        if magnitude < MAGNITUDE_MIN or magnitude > MAGNITUDE_MAX:
            raise ValueError("action.magnitude must be within [-1, 1]")

    return ActionEvent(
        id=raw["id"],
        label=raw["label"],
        timestamp=timestamp,
        magnitude=magnitude,
    )


def store_action(event: ActionEvent, continuity: dict) -> None:
    """Append ``event`` to ``continuity["actions"]`` (created if absent), then
    keep the log sorted by timestamp (stable — equal timestamps retain insertion
    order). Append-only: events are never mutated, deleted, or reordered beyond
    the canonical timestamp sort."""
    continuity.setdefault("actions", []).append(event)
    continuity["actions"].sort(key=lambda e: e.timestamp)


def load_recent_actions(continuity: dict, now: float, window: float) -> list:
    """All actions with ``timestamp >= now - window``, sorted by timestamp.

    ``now`` is caller-supplied (no wall-clock here); ``window`` is the look-back
    span. Returns a fresh list."""
    cutoff = now - window
    actions = (continuity or {}).get("actions", [])
    return sorted(
        (event for event in actions if event.timestamp >= cutoff),
        key=lambda e: e.timestamp,
    )


# --- Process-wide default continuity (used by the POST /operator/action route) ---

_ACTION_CONTINUITY: dict = {"actions": []}


def get_action_continuity() -> dict:
    """The process-wide action continuity log (an ``{"actions": [...]}`` dict)."""
    return _ACTION_CONTINUITY


def _reset_for_tests() -> None:
    """Clear the process-wide action continuity (test/maintenance helper)."""
    _ACTION_CONTINUITY["actions"] = []
