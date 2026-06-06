# phase7_telemetry.py
"""
Phase 7 — telemetry recording API (drift / coherence / trust over time).

A thin, deterministic layer over ``phase7_storage``: it computes the Phase 7
metrics for each snapshot and delegates persistence to the active storage
backend (durable JSONL by default, in-memory when ``TESTING=1``). The public
API is unchanged from Phase 7.0:

    record_snapshot(operator_id, snapshot, timestamp) -> None
    get_history(operator_id, limit=100) -> list[TelemetryRecord]

No wall-clock; timestamps are passed in. ``TelemetryRecord`` is defined in
``phase7_storage`` (storage owns the persisted type) and re-exported here so
``from phase7_telemetry import TelemetryRecord`` keeps working.

See ``phase7_spec.md`` and CARD 7.1.
"""
import phase7_storage
from phase6_contracts import SuperstructureState
from phase7_drift import (
    compute_coherence_health,
    compute_drift,
    compute_trust_band,
)
from phase7_storage import TelemetryRecord  # re-exported for API stability

__all__ = ["TelemetryRecord", "record_snapshot", "get_history", "reset"]


def record_snapshot(
    operator_id: str,
    snapshot: SuperstructureState,
    timestamp: float,
) -> None:
    """Compute this snapshot's metrics and append it to durable telemetry.

    Drift is measured against the operator's previous snapshot (``None`` if
    this is the first). Coherence health is the rolling value across the
    operator's history *including* this snapshot. The trust band is derived
    from (drift, coherence_health), with a missing first-snapshot drift treated
    as 0.0. Append-only persistence is handled by ``phase7_storage``.
    """
    history = phase7_storage.load_history(operator_id, limit=None)

    prev = history[-1].superstructure if history else None
    drift = compute_drift(prev, snapshot) if prev is not None else None

    states = [record.superstructure for record in history]
    states.append(snapshot)
    coherence_health = compute_coherence_health(states)

    effective_drift = drift if drift is not None else 0.0
    trust_band = compute_trust_band(effective_drift, coherence_health)

    phase7_storage.append_record(
        operator_id,
        TelemetryRecord(
            timestamp=timestamp,
            superstructure=snapshot,
            drift=drift,
            coherence_health=coherence_health,
            trust_band=trust_band,
        ),
    )


def get_history(operator_id: str, limit: int = 100) -> list[TelemetryRecord]:
    """Return up to ``limit`` most-recent records for ``operator_id``.

    A fresh list in chronological order (oldest first) within the most-recent
    ``limit`` window. Unknown operator (or ``limit`` <= 0) yields ``[]``.
    """
    return phase7_storage.load_history(operator_id, limit=limit)


def reset() -> None:
    """Clear the active telemetry store (in-memory test backend only).

    Delegates to ``phase7_storage.reset`` — a no-op for the durable JSONL
    backend, which is append-only.
    """
    phase7_storage.reset()
