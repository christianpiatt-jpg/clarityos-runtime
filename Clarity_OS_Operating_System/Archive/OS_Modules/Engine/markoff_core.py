# markoff_core.py
# Operator‑grade Markoff Engine Core

from collections import defaultdict
import random

class MarkoffModel:
    """
    Minimal, deterministic Markoff engine.
    Tracks:
        - state transitions
        - word transitions
        - frequency counts
    """

    def __init__(self):
        # State → next state → count
        self.state_transitions = defaultdict(lambda: defaultdict(int))

        # Word → next word → count
        self.word_transitions = defaultdict(lambda: defaultdict(int))

        # Global counters
        self.total_states = 0
        self.total_transitions = 0
        self.total_word_pairs = 0

    # -------------------- TRAINING --------------------

    def train_states(self, sequence):
        """
        Train on a sequence of states (strings).
        Example: ["neutral", "pressure", "somatic", "release"]
        """
        if len(sequence) < 2:
            return

        self.total_states += len(sequence)

        for a, b in zip(sequence, sequence[1:]):
            self.state_transitions[a][b] += 1
            self.total_transitions += 1

    def train_words(self, tokens):
        """
        Train on a list of tokens.
        Example: ["the", "cat", "sat"]
        """
        if len(tokens) < 2:
            return

        for a, b in zip(tokens, tokens[1:]):
            self.word_transitions[a][b] += 1
            self.total_word_pairs += 1

    # -------------------- PREDICTION --------------------

    def next_state(self, current):
        """
        Predict the next state based on weighted transitions.
        """
        options = self.state_transitions.get(current)
        if not options:
            return None

        return self._weighted_choice(options)

    def next_word(self, current):
        """
        Predict the next word based on weighted transitions.
        """
        options = self.word_transitions.get(current)
        if not options:
            return None

        return self._weighted_choice(options)

    # -------------------- INTERNAL UTILS --------------------

    def _weighted_choice(self, mapping):
        """
        mapping: {item: count}
        Returns a weighted random choice.
        """
        items = list(mapping.keys())
        weights = list(mapping.values())
        return random.choices(items, weights=weights, k=1)[0]

    # -------------------- STATUS / EXPORT --------------------

    def status(self):
        return {
            "states": self.total_states,
            "transitions": self.total_transitions,
            "word_pairs": self.total_word_pairs
        }

    def export(self):
        """
        Export raw transition tables.
        """
        return {
            "state_transitions": {k: dict(v) for k, v in self.state_transitions.items()},
            "word_transitions": {k: dict(v) for k, v in self.word_transitions.items()},
            "stats": self.status()
        }
