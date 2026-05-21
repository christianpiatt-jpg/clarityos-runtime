import re

class PrimitiveClassifier:
    """
    A simple semantic classifier for clarity primitives.
    Uses keyword clusters to map text to a primitive.
    """

    def __init__(self):
        # Keyword clusters for each primitive
        self.clusters = {
            "pressure": [
                "pressure", "push", "force", "tension", "strain",
                "stress", "tight", "squeeze", "load", "demand"
            ],
            "opening": [
                "open", "opening", "opens", "release", "relief",
                "space", "gap", "breath", "expand", "expansion"
            ],
            "collapse": [
                "collapse", "break", "breakdown", "fall", "crack",
                "failure", "snap", "implode", "ruin"
            ],
            "inversion": [
                "invert", "inversion", "flip", "reverse", "turn",
                "swap", "inside out", "upside down"
            ],
            "boundary": [
                "boundary", "limit", "edge", "border", "line",
                "threshold", "barrier"
            ],
            "signal": [
                "signal", "cue", "hint", "indicator", "message",
                "tell", "sign", "pattern"
            ],
            "drift": [
                "drift", "slide", "slip", "fade", "wander",
                "dissolve", "blur"
            ],
            "compression": [
                "compress", "compression", "compact", "tighten",
                "condense", "contract"
            ],
            "release": [
                "release", "let go", "unload", "relax", "ease",
                "soften", "drop"
            ],
            "conflict": [
                "fight", "argue", "conflict", "battle", "clash",
                "attack", "resist", "oppose"
            ]
        }

    def classify(self, text):
        """
        Returns (primitive, confidence)
        Confidence is a simple count of matched keywords.
        """

        text = text.lower()
        scores = {}

        for primitive, keywords in self.clusters.items():
            score = 0
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    score += 1
            scores[primitive] = score

        # Pick the primitive with the highest score
        best = max(scores, key=scores.get)
        confidence = scores[best]

        # If no keywords matched, return "unknown"
        if confidence == 0:
            return "unknown", 0

        return best, confidence