from typing import Dict, Any
from orchestrator import EngineOrchestrator

class DispatcherV1:
    def __init__(self):
        self.orchestrator = EngineOrchestrator()

    def dispatch(self, call: Dict[str, Any]):
        op = call.get("op", "").strip()
        payload = call.get("payload", {}) or {}
        context = call.get("context", {}) or {}

        if op.startswith("#"):
            return self._dispatch_operator(op, payload, context)

        return self._dispatch_nl(op, context)

    def _dispatch_operator(self, op, payload, context):
        o = op.lower()

        if o.startswith("#memory"):
            r = self.orchestrator.process_memory(payload)
            return self.orchestrator.wrap_output(r, "memory", op, ["memory"], context)

        if o.startswith("#markoff"):
            r = self.orchestrator.process_markoff(payload)
            return self.orchestrator.wrap_output(r, "markoff", op, ["markoff"], context)

        if o.startswith("#lang"):
            r = self.orchestrator.process_langbridg(payload)
            return self.orchestrator.wrap_output(r, "langbridg", op, ["langbridg"], context)

        if o.startswith("#route"):
            text = payload.get("text", "")
            features = self.orchestrator.process_langbridg({"action": "features", "text": text})
            r = self.orchestrator.process_hybrid({"features": features, "context": context})
            return self.orchestrator.wrap_output(r, "hybrid", op, ["langbridg", "hybrid"], context)

        if o.startswith("#crawl"):
            r = self.orchestrator.process_metacrawler(payload)
            return self.orchestrator.wrap_output(r, "metacrawler", op, ["metacrawler"], context)

        return self.orchestrator.wrap_output({"error": f"Unknown operator '{op}'"},
                                             "dispatcher", op, ["dispatcher"], context)

    def _dispatch_nl(self, text, context):
        features = self.orchestrator.process_langbridg({"action": "features", "text": text})
        narrative = self.orchestrator.process_markoff({"text": text})
        elins = self.orchestrator.process_elins({"features": features, "narrative": narrative, "context": context})
        self.orchestrator.process_memory({"action": "write", "record": elins})

        payload = {"features": features, "narrative": narrative, "elins": elins}

        return self.orchestrator.wrap_output(payload, "pipeline", text,
                                             ["langbridg", "markoff", "elins", "memory"], context)
