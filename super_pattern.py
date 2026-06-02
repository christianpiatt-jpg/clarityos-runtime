# super_pattern.py
from typing import Dict

from phase6_contracts import SuperPatternState


def _score_keywords(text: str, positives: list[str], negatives: list[str]) -> float:
    t = text.lower()
    pos = sum(t.count(k) for k in positives)
    neg = sum(t.count(k) for k in negatives)
    total = pos + neg
    if total == 0:
        return 0.0
    score = (pos - neg) / total
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def compute_super_pattern(meta: Dict[str, str]) -> SuperPatternState:
    # concatenate all meta strings
    all_text = " ".join(meta.values()).lower()

    patterns = {
        "consolidation": ["consolidation", "merge", "unify"],
        "extraction": ["extract", "extraction", "distill"],
        "compression": ["compress", "compression", "reduce"],
        "stability": ["stable", "stability", "steady"],
    }

    pattern_scores: Dict[str, float] = {}
    for name, kws in patterns.items():
        pattern_scores[name] = sum(all_text.count(k) for k in kws)

    if pattern_scores:
        dominant_pattern = max(pattern_scores.items(), key=lambda x: x[1])[0]
        max_score = max(pattern_scores.values())
        pattern_strength = 0.0 if max_score == 0 else min(1.0, max_score / (max_score + 5.0))
    else:
        dominant_pattern = "none"
        pattern_strength = 0.0

    pattern_stability = _score_keywords(
        all_text,
        positives=["stable", "stability", "steady", "robust"],
        negatives=["unstable", "fragile", "volatile"],
    )

    pattern_coherence = _score_keywords(
        all_text,
        positives=["coherent", "coherence", "aligned", "alignment", "integrated"],
        negatives=["fragmented", "incoherent", "misaligned"],
    )

    pattern_identity = f"{dominant_pattern}:stable-{pattern_stability:.2f}"

    return SuperPatternState(
        dominant_pattern=dominant_pattern,
        pattern_strength=pattern_strength,
        pattern_stability=pattern_stability,
        pattern_coherence=pattern_coherence,
        pattern_identity=pattern_identity,
    )
