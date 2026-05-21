# /02_Modules/engine_runtime.py

from sentence_transformers import SentenceTransformer
from markoff_core import MarkoffModel

class EngineRuntime:
    """
    Runtime wrapper for the Markoff Engine v3.
    Exposes a clean API for ClarityOS:
      - classify(text)
      - predict_next_state(state_id)
      - predict_next_word(word)
      - train(text)
      - status()
    """

    def __init__(self):
        # Load embedding model
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

        # Initialize Markoff engine with embedding model
        self.engine = MarkoffModel(self.model)

    # -----------------------------
    # Core API exposed to ClarityOS
    # -----------------------------

    def classify(self, text: str):
        """Return the Sun Tzu state for the given text."""
        return self.engine.classify(text)

    def predict_next_state(self, from_state: str):
        """Return the most likely next Sun Tzu state."""
        return self.engine.predict_next_state(from_state)

    def predict_next_word(self, word: str):
        """Return the most likely next word."""
        return self.engine.predict_next_word(word)

    def train(self, text: str):
        """Train the engine on new text."""
        self.engine.train(text)

    def status(self):
        """Return engine health and training metrics."""
        return {
            "states": len(self.engine.states),
            "transitions": self.engine.transition_count(),
            "word_pairs": len(self.engine.word_transitions),
        }