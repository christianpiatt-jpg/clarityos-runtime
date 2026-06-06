# phase7_storage.py
"""
Phase 7 — durable, non-gated persistence for telemetry records.

Two interchangeable backends behind one module-level interface:

  * JsonlTelemetryStore  — append-only JSONL log, one file per operator at
                           ``<root>/<operator_id>.jsonl`` (root defaults to
                           ``data/telemetry/``). The durable default.
  * MemoryTelemetryStore — in-memory mirror of the Phase 7.0 behaviour. Used
                           automatically when ``TESTING=1``.

Shared interface (both backends and the module-level facade):

    append_record(operator_id: str, record: TelemetryRecord) -> None
    load_history(operator_id: str, limit: int | None = None) -> list[TelemetryRecord]

This is *structural* telemetry, NOT private operator data: it is deliberately
unencrypted and lives entirely outside the privacy-gated vault /
``operator_state``. No wall-clock, no randomness, no external services. Imports
nothing from the CI-gated runtime spine — only ``phase6_contracts`` (for the
``SuperstructureState`` shape) plus the stdlib.

``TelemetryRecord`` is defined here (storage owns the persisted record type)
and re-exported by ``phase7_telemetry`` so the Phase 7.0 import surface
(``from phase7_telemetry import TelemetryRecord``) keeps working.

See ``phase7_spec.md`` (storage section) and CARD 7.1.
"""
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from phase6_contracts import (
    SuperCoherenceState,
    SuperEssenceState,
    SuperIdentityState,
    SuperIntegrationState,
    SuperPatternState,
    SuperstructureState,
)


# Operator ids become filenames; keep them to a safe, traversal-proof token.
_OPERATOR_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")

# Default on-disk location for the JSONL backend.
DEFAULT_ROOT = Path("data") / "telemetry"


@dataclass
class TelemetryRecord:
    """One append-only telemetry point for an operator.

    ``drift`` is ``None`` for an operator's first snapshot (no prior to
    compare). ``coherence_health`` and ``trust_band`` are always populated.
    Every field is JSON-serialisable; the nested ``superstructure`` round-trips
    via ``dataclasses.asdict`` and ``record_from_dict``.
    """
    timestamp: float
    superstructure: SuperstructureState
    drift: float | None
    coherence_health: float | None
    trust_band: str | None


def _validate_operator_id(operator_id: str) -> str:
    """Reject ids that aren't safe single-segment filenames.

    Both backends validate identically so they stay interchangeable.
    """
    if (
        not isinstance(operator_id, str)
        or operator_id in (".", "..")
        or not _OPERATOR_ID_RE.match(operator_id)
    ):
        raise ValueError(
            f"invalid operator_id {operator_id!r}: expected 1-128 chars of "
            "[A-Za-z0-9_.-] (it is used as a filename)"
        )
    return operator_id


def _slice(records: list, limit) -> list:
    """Shared limit semantics: ``None`` -> all; ``>0`` -> most recent N;
    ``<=0`` -> ``[]``. Always returns a fresh list."""
    if limit is None:
        return list(records)
    if limit <= 0:
        return []
    return list(records[-limit:])


# --- JSON (de)serialisation -------------------------------------------------

def record_to_dict(record: TelemetryRecord) -> dict:
    """Fully nested, JSON-serialisable dict for a TelemetryRecord."""
    return asdict(record)


def record_to_json(record: TelemetryRecord) -> str:
    """Deterministic single-line JSON for a TelemetryRecord (sorted keys)."""
    return json.dumps(record_to_dict(record), sort_keys=True, separators=(",", ":"))


def record_from_dict(data: dict) -> TelemetryRecord:
    """Reconstruct a TelemetryRecord (incl. the nested SuperstructureState)."""
    s = data["superstructure"]
    superstructure = SuperstructureState(
        pattern=SuperPatternState(**s["pattern"]),
        integration=SuperIntegrationState(**s["integration"]),
        coherence=SuperCoherenceState(**s["coherence"]),
        essence=SuperEssenceState(**s["essence"]),
        identity=SuperIdentityState(**s["identity"]),
    )
    return TelemetryRecord(
        timestamp=data["timestamp"],
        superstructure=superstructure,
        drift=data["drift"],
        coherence_health=data["coherence_health"],
        trust_band=data["trust_band"],
    )


def record_from_json(line: str) -> TelemetryRecord:
    """Parse one JSONL line back into a TelemetryRecord."""
    return record_from_dict(json.loads(line))


# --- Backends ---------------------------------------------------------------

class MemoryTelemetryStore:
    """In-memory, append-only mirror of Phase 7.0 (used when ``TESTING=1``)."""

    def __init__(self) -> None:
        self._data: dict[str, list[TelemetryRecord]] = {}

    def append_record(self, operator_id: str, record: TelemetryRecord) -> None:
        _validate_operator_id(operator_id)
        self._data.setdefault(operator_id, []).append(record)

    def load_history(
        self, operator_id: str, limit: int | None = None
    ) -> list[TelemetryRecord]:
        _validate_operator_id(operator_id)
        return _slice(self._data.get(operator_id, []), limit)

    def reset(self) -> None:
        """Clear all operators (test/maintenance helper)."""
        self._data.clear()


class JsonlTelemetryStore:
    """Append-only JSONL log, one file per operator under ``root``.

    Each ``append_record`` writes one JSON line and never rewrites or deletes
    existing lines. ``root`` is created on first append (idempotent — the only
    side effect); reading an absent operator yields ``[]``.
    """

    def __init__(self, root=None) -> None:
        self._root = Path(root) if root is not None else DEFAULT_ROOT

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, operator_id: str) -> Path:
        _validate_operator_id(operator_id)
        return self._root / f"{operator_id}.jsonl"

    def append_record(self, operator_id: str, record: TelemetryRecord) -> None:
        path = self._path_for(operator_id)
        self._root.mkdir(parents=True, exist_ok=True)
        line = record_to_json(record)
        # newline="\n" keeps file bytes deterministic across platforms.
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")

    def load_history(
        self, operator_id: str, limit: int | None = None
    ) -> list[TelemetryRecord]:
        path = self._path_for(operator_id)
        if not path.is_file():
            return []
        records: list[TelemetryRecord] = []
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                records.append(record_from_json(line))
        return _slice(records, limit)

    # No reset(): the durable log is strictly append-only / no deletions.


# --- Module-level facade (backend selected by TESTING) ----------------------

def _make_default_store():
    """JSONL by default; in-memory when ``TESTING=1`` (per the Phase 7.1 card)."""
    if os.environ.get("TESTING") == "1":
        return MemoryTelemetryStore()
    return JsonlTelemetryStore(DEFAULT_ROOT)


_STORE = None


def _active_store():
    """Lazily resolve the process-wide store on first use."""
    global _STORE
    if _STORE is None:
        _STORE = _make_default_store()
    return _STORE


def append_record(operator_id: str, record: TelemetryRecord) -> None:
    _active_store().append_record(operator_id, record)


def load_history(
    operator_id: str, limit: int | None = None
) -> list[TelemetryRecord]:
    return _active_store().load_history(operator_id, limit=limit)


def reset() -> None:
    """Clear the active store if it supports clearing.

    The in-memory test backend clears its dict; the durable JSONL backend is
    append-only and has no reset (a documented no-op for it).
    """
    store = _active_store()
    if hasattr(store, "reset"):
        store.reset()
