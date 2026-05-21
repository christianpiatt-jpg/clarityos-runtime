# somatic_register.py
# Tracks pressure / somatic signal over time.

from dataclasses import dataclass, field
from typing import List, Dict, Any
import time

@dataclass
class SomaticEvent:
    ts: float
    pressure: float
    label: str
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SomaticRegister:
    session_id: str
    events: List[SomaticEvent] = field(default_factory=list)
    current_pressure: float = 0.0

    def record(self, pressure: float, label: str, meta: Dict[str, Any] | None = None):
        self.current_pressure = pressure
        self.events.append(
            SomaticEvent(
                ts=time.time(),
                pressure=pressure,
                label=label,
                meta=meta or {}
            )
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_pressure": self.current_pressure,
            "event_count": len(self.events)
        }
