from typing import Dict, Any, List
from datetime import datetime
import uuid

class MetacrawlerV1:
    def __init__(self):
        self.version = "1.0"
        self.targets = [
            {"id": "nyt", "url": "https://www.nytimes.com"},
            {"id": "bbc", "url": "https://www.bbc.com"},
            {"id": "guardian", "url": "https://www.theguardian.com"},
        ]

    def handle(self, payload: Dict[str, Any]):
        action = payload.get("action")

        if action == "run":
            return self.run()

        if action == "targets":
            return {"targets": self.targets}

        if action == "health":
            return {"status": "ok", "version": self.version}

        return {"error": f"Unknown metacrawler action '{action}'"}

    def run(self):
        packets: List[Dict[str, Any]] = []
        for target in self.targets:
            packets.append({
                "packet_id": str(uuid.uuid4()),
                "source_id": target["id"],
                "url": target["url"],
                "headline": "Sample headline (v1 stub)",
                "timestamp": datetime.utcnow().isoformat(),
                "section": "general",
                "language": "en",
                "region": "global",
                "ingested_at": datetime.utcnow().isoformat(),
            })

        return {"status": "ok", "count": len(packets), "packets": packets}

