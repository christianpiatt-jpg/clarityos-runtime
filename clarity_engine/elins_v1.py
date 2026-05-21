from typing import Dict, Any
from datetime import datetime
import uuid

class ELINSv1:
    def __init__(self):
        self.version = "1.0"

    def generate(self, features: Dict[str, Any], narrative: Dict[str, Any], context: Dict[str, Any]):
        return {
            "elins_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "text": features.get("text"),
            "tokens": features.get("tokens"),
            "intent": features.get("intent"),
            "length": features.get("length"),
            "interpretation": narrative.get("interpretation"),
            "polarity": narrative.get("polarity"),
            "tags": narrative.get("tags"),
            "basin": narrative.get("basin"),
            "confidence": narrative.get("confidence"),
            "surface": context.get("surface", "console"),
            "operator_state": context.get("operator_state", "stable"),
            "elins_version": self.version,
        }
