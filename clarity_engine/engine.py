from typing import Dict, Any


class MarkoffEngine:
    """
    ClarityOS v1 — Structural Markoff Classifier
    Dependency‑free, deterministic, and self‑contained.
    """

    def __init__(self):
        pass

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = payload.get("text", "")
        return self.run(text)

    def run(self, text: str) -> Dict[str, Any]:
        polarity = self._polarity(text)
        signal = self._signal_type(text)
        tags = self._tags(text)
        basin = self._basin(text)

        return {
            "interpretation": signal,
            "polarity": polarity,
            "tags": tags,
            "basin": basin,
            "confidence": 0.78,
        }

    # ------------------------------------------------------------
    # INTERNAL CLASSIFIERS
    # ------------------------------------------------------------

    def _polarity(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["good", "great", "improving", "strong"]):
            return "positive"
        if any(w in t for w in ["bad", "worse", "decline", "broken"]):
            return "negative"
        return "neutral"

    def _signal_type(self, text: str) -> str:
        t = text.lower()
        if "?" in text:
            return "inquiry"
        if any(w in t for w in ["should", "need to", "must"]):
            return "directive"
        if any(w in t for w in ["error", "issue", "problem"]):
            return "alert"
        return "statement"

    def _tags(self, text: str):
        t = text.lower()
        tags = []
        for word in ["system", "engine", "model", "stability", "performance", "risk"]:
            if word in t:
                tags.append(word)
        return tags

    def _basin(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["chaos", "unstable", "confusion"]):
            return "chaotic"
        if any(w in t for w in ["stable", "clear", "coherent"]):
            return "stable"
        return "neutral"
