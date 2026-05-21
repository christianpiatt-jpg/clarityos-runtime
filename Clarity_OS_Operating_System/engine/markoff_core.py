# ---------------------------------------------------------
# Markoff Engine v3 — Relational Thermodynamic State Engine
# ---------------------------------------------------------
#
# Core Function:
#   Models how language moves through relational thermodynamic states.
#   Detects pressure, drift, collapse, and strategic posture using a
#   bilevel architecture:
#
#   • Micro Layer
#       Word → word transitions
#       Local pressure mechanics
#       Linguistic curvature + drift detection
#
#   • Macro Layer
#       Sun Tzu relational states
#       State → state transitions
#       Strategic posture + relational thermodynamics
#
#   • Classifier Layer
#       Embedding-based mapping of text → Sun Tzu state
#       Semantic field → relational state vector
#
# Integration:
#   When bound to the Planetary Mesh (900-series), the engine contributes:
#       - global diagnostics
#       - cross-basin relational pressure maps
#       - curvature signatures
#       - systemic risk indicators
#
#   This makes Markoff the interpretive core of ClarityOS:
#       - micro → macro translation
#       - narrative → thermodynamic mapping
#       - text → relational state motion
#
# ---------------------------------------------------------

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer


class MarkoffModel:
    print(">>> INSTANTIATING MarkoffModel FROM markoff_core.py <<<")
    """
    Relational Thermodynamic Engine (v3)

    Bilevel architecture:
      - Micro Layer:
            Tracks word-level transitions and local pressure.
            Models curvature, drift, and linguistic acceleration.

      - Macro Layer:
            Tracks Sun Tzu relational states and transitions.
            Models strategic posture, relational thermodynamics,
            and state-to-state motion.

      - Classifier Layer:
            Embedding-based mapping of text → Sun Tzu state.
            Converts semantic fields into relational state vectors.

    When bound to the Planetary Mesh:
      - contributes global diagnostics
      - synchronizes relational pressure across basins
      - supports hydronic overlays
      - feeds curvature + drift signatures into the mesh router
    """

    # -----------------------------------------------------
    # Construction
    # -----------------------------------------------------
    def __init__(self, model: Optional[SentenceTransformer] = None):
        # Word-level transitions: (w1, w2) -> count
        self.word_transitions: Counter[Tuple[str, str]] = Counter()

        # State store: id -> state object
        self.states: Dict[str, Dict[str, Any]] = {}

        # State embeddings: id -> vector
        self.state_embeddings: Dict[str, np.ndarray] = {}

        # State-level transitions: list of {"from": id, "to": id}
        self.transitions: List[Dict[str, str]] = []

        # Embedding model (injected from markoff.py or external engine)
        self.model: Optional[SentenceTransformer] = model

        # Last classified state (for transition chaining)
        self._last_state: Optional[str] = None

        # Planetary Mesh binding (900-series integration)
        self.mesh_router = None

        # Initialize Sun Tzu core states
        self._init_sun_tzu_states()

    # -----------------------------------------------------
    # Planetary Mesh integration
    # -----------------------------------------------------
    def bind_mesh_router(self, mesh_router: Any) -> None:
        """
        Bind the Planetary Mesh Router to the Markoff Engine.
        Enables global diagnostics and planetary-scale routing.
        """
        self.mesh_router = mesh_router

    def global_diagnostics(self) -> Dict[str, Any]:
        """
        Return global relational-thermodynamic diagnostics via the
        Planetary Mesh Router. If the mesh is not bound, return a
        structured error object.
        """
        if not self.mesh_router:
            return {"error": "Mesh router not bound"}

        return self.mesh_router.global_diag()

    def mesh_status(self) -> Dict[str, Any]:
        """
        Convenience wrapper for mesh status reporting.
        """
        if not self.mesh_router:
            return {"error": "Mesh router not bound"}

        return self.mesh_router.mesh_status()

    # -----------------------------------------------------
    # Sun Tzu core states (relational thermodynamics)
    # -----------------------------------------------------
    def _init_sun_tzu_states(self) -> None:
        """
        Five fundamental relational states, each with a thermodynamic flavor.
        """
        core_states = {
            "S1": {
                "label": "Moral Law",
                "description": "Alignment of vectors; shared purpose; low-entropy coherence.",
                "keywords": ["alignment", "coherence", "shared", "trust", "purpose"],
            },
            "S2": {
                "label": "Heaven",
                "description": "Timing, cycles, phase; temperature over time.",
                "keywords": ["timing", "season", "cycle", "momentum", "phase"],
            },
            "S3": {
                "label": "Earth",
                "description": "Terrain, constraints, gradients; pressure differentials.",
                "keywords": ["terrain", "ground", "constraints", "friction", "boundary"],
            },
            "S4": {
                "label": "Commander",
                "description": "Identity, stance, character; local control of pressure routing.",
                "keywords": ["identity", "character", "stance", "clarity", "temperament"],
            },
            "S5": {
                "label": "Method & Discipline",
                "description": "Systems, logistics, order; how mass and pressure are organized.",
                "keywords": ["system", "method", "discipline", "logistics", "process"],
            },
        }

        for sid, sobj in core_states.items():
            self.add_state(sid, sobj)

    # -----------------------------------------------------
    # State management
    # -----------------------------------------------------
    def add_state(self, state_id: str, state_obj: Dict[str, Any]) -> None:
        self.states[state_id] = state_obj
        if self.model is not None:
            self.state_embeddings[state_id] = self._embed_state(state_obj)

    def _ensure_state_embeddings(self) -> None:
        if self.model is None:
            return
        for sid, sobj in self.states.items():
            if sid not in self.state_embeddings:
                self.state_embeddings[sid] = self._embed_state(sobj)

    def _embed_state(self, state_obj: Dict[str, Any]) -> np.ndarray:
        """
        Embed a state using its label + description + keywords.
        """
        label = state_obj.get("label", "")
        desc = state_obj.get("description", "")
        keywords = " ".join(state_obj.get("keywords", []))
        text = f"{label}. {desc}. {keywords}"
        vec = self.model.encode([text])[0]
        return np.array(vec, dtype=float)

    # -----------------------------------------------------
    # Embedding helpers
    # -----------------------------------------------------
    def set_model(self, model: SentenceTransformer) -> None:
        """
        Allow late injection of the embedding model if needed.
        """
        self.model = model
        self.state_embeddings.clear()
        self._ensure_state_embeddings()

    def _embed_text(self, text: str) -> Optional[np.ndarray]:
        if self.model is None:
            return None
        vec = self.model.encode([text])[0]
        return np.array(vec, dtype=float)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    # -----------------------------------------------------
    # Classification: text → Sun Tzu state
    # -----------------------------------------------------
    def classify(self, text: str) -> Optional[str]:
        """
        Classify text into one of the Sun Tzu states using embeddings.
        Returns state_id or None.
        """
        if self.model is None or not self.states:
            return None

        self._ensure_state_embeddings()
        text_vec = self._embed_text(text)
        if text_vec is None:
            return None

        best_state = None
        best_score = -1.0

        for sid, svec in self.state_embeddings.items():
            score = self._cosine_similarity(text_vec, svec)
            if score > best_score:
                best_score = score
                best_state = sid

        return best_state

    # -----------------------------------------------------
    # Transitions (macro: state → state)
    # -----------------------------------------------------
    def add_transition(self, from_state: str, to_state: str) -> None:
        if from_state in self.states and to_state in self.states:
            self.transitions.append({"from": from_state, "to": to_state})

    def transition_count(self) -> int:
        """
        Total number of state-level transitions.
        Scanner uses this to measure training.
        """
        return len(self.transitions)

    def _state_transition_counts(self) -> Dict[Tuple[str, str], int]:
        counts: Dict[Tuple[str, str], int] = defaultdict(int)
        for t in self.transitions:
            key = (t["from"], t["to"])
            counts[key] += 1
        return counts

    # -----------------------------------------------------
    # Word-level transitions (micro)
    # -----------------------------------------------------
    def _tokenize(self, text: str) -> List[str]:
        # Simple whitespace tokenizer; can be upgraded later
        return [w.strip() for w in text.split() if w.strip()]

    def _train_words(self, text: str) -> None:
        tokens = self._tokenize(text)
        for i in range(len(tokens) - 1):
            pair = (tokens[i].lower(), tokens[i + 1].lower())
            self.word_transitions[pair] += 1

    # -----------------------------------------------------
    # Training: text → micro + macro
    # -----------------------------------------------------
    def train(self, text: str) -> None:
        """
        Train both:
          - word-level transitions
          - state-level transitions via classification
        """
        # Micro layer
        self._train_words(text)

        # Macro layer: classify text into a state and create a transition
        current_state = self.classify(text)
        if current_state is None:
            return

        if self._last_state is not None:
            self.add_transition(self._last_state, current_state)

        self._last_state = current_state

    # -----------------------------------------------------
    # Prediction
    # -----------------------------------------------------
    def predict_next_state(self, from_state: str) -> Optional[str]:
        """
        Predict the most likely next state from a given state.
        """
        counts = self._state_transition_counts()
        candidates = {to for (frm, to), c in counts.items() if frm == from_state}
        if not candidates:
            return None

        best_to = None
        best_count = -1
        for to in candidates:
            c = counts[(from_state, to)]
            if c > best_count:
                best_count = c
                best_to = to
        return best_to

    def predict_next_word(self, word: str) -> Optional[str]:
        """
        Predict the most likely next word given a word.
        """
        word = word.lower()
        candidates = {w2 for (w1, w2), c in self.word_transitions.items() if w1 == word}
        if not candidates:
            return None

        best_w2 = None
        best_count = -1
        for w2 in candidates:
            c = self.word_transitions[(word, w2)]
            if c > best_count:
                best_count = c
                best_w2 = w2
        return best_w2

    # -----------------------------------------------------
    # Primary runtime entrypoint
    # -----------------------------------------------------
    def run(self, text: str) -> Dict[str, Any]:
        """
        Primary entrypoint for ClarityOS.
        Routes text through the Markoff engine and returns a
        compact diagnostic bundle.
        """
        try:
            tokens = self._tokenize(text)

            # Update micro transitions
            for w1, w2 in zip(tokens, tokens[1:]):
                self.word_transitions[(w1.lower(), w2.lower())] += 1

            # Simple next-word forecast
            if tokens:
                last = tokens[-1].lower()
                candidates = {
                    w2: count
                    for (w1, w2), count in self.word_transitions.items()
                    if w1 == last
                }
                forecast = max(candidates, key=candidates.get) if candidates else None
            else:
                forecast = None

            # Macro classification
            state_id = self.classify(text)

            return {
                "tokens": tokens,
                "forecast": forecast,
                "transition_count_micro": len(self.word_transitions),
                "transition_count_macro": self.transition_count(),
                "state": state_id,
            }

        except Exception as e:
            return {
                "error": str(e),
                "tokens": [],
                "forecast": None,
                "transition_count_micro": len(self.word_transitions),
                "transition_count_macro": self.transition_count(),
                "state": None,
            }


__all__ = ["MarkoffModel"]


if __name__ == "__main__":
    # Minimal REPL-style harness for local testing.
    # In production, ClarityOS runtime should construct and manage the engine.
    try:
        print("[MarkoffCore] Local test harness. Type text, Ctrl+C to exit.")
        engine = MarkoffModel(model=None)  # model should be injected in real use

        while True:
            line = input("> ").strip()
            if not line:
                continue
            result = engine.run(line)
            print(result)

    except KeyboardInterrupt:
        print("\n[MarkoffCore] Exiting.")
