# session_state.py
# Tracks per‑session conversational / engine state.

from dataclasses import dataclass, field
from typing import List, Dict, Any
import time

@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time.time)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, tags: Dict[str, Any] | None = None):
        self.messages.append({
            "role": role,
            "content": content,
            "tags": tags or {},
            "ts": time.time()
        })

    def last_message(self) -> Dict[str, Any] | None:
        return self.messages[-1] if self.messages else None

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "message_count": len(self.messages),
            "meta": self.meta
        }
