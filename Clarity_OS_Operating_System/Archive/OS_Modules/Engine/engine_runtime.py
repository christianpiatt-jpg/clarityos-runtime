# engine_runtime.py
# Operator‑grade EngineRuntime for Clarity_OS

from __future__ import annotations

# Flexible imports: works both as package and as direct script.
try:
    from Engine.markoff_core import MarkoffModel
    from Engine.state.session_state import SessionState
    from Engine.somatic.somatic_register import SomaticRegister
    from Engine.utils.text_utils import tokenize
except ImportError:
    from markoff_core import MarkoffModel
    from state.session_state import SessionState
    from somatic.somatic_register import SomaticRegister
    from utils.text_utils import tokenize


class EngineRuntime:
    """
    Core runtime wrapper around:
        - MarkoffModel (symbolic transitions)
        - SessionState (conversation / context)
        - SomaticRegister (pressure / somatic trace)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.model = MarkoffModel()
        self.state = SessionState(session_id=session_id)
        self.somatic = SomaticRegister(session_id=session_id)

    # -------------------- INGEST / TRAIN --------------------

    def ingest_text(self, text: str, role: str = "user"):
        """
        Ingest raw text into the engine:
            - store in SessionState
            - update somatic register (placeholder heuristic)
            - train Markoff word transitions
        """
        self.state.add_message(role=role, content=text)

        tokens = tokenize(text)
        self.model.train_words(tokens)

        # Simple placeholder pressure heuristic: length‑based
        pressure = min(1.0, len(tokens) / 100.0)
        self.somatic.record(pressure=pressure, label="ingest", meta={"token_count": len(tokens)})

    # -------------------- QUERY / STATUS --------------------

    def status(self) -> dict:
        """
        Return a compact status snapshot for cockpit / telemetry.
        """
        m = self.model.status()
        s = self.state.summary()
        som = self.somatic.snapshot()

        return {
            "session_id": self.session_id,
            "model": m,
            "session": {
                "message_count": s["message_count"],
                "created_at": s["created_at"],
            },
            "somatic": som,
        }

    # -------------------- SIMPLE NEXT‑WORD DEMO --------------------

    def suggest_next_word(self, current: str) -> str | None:
        return self.model.next_word(current)


if __name__ == "__main__":
    # Simple boot test
    eng = EngineRuntime("test-session")
    eng.ingest_text("This is a small test of the Markoff engine runtime.")
    print("Engine loaded:", eng.status())
