# ----------------------------------------------------
# Markoff Engine v3 — Interpreter (with FORECAST + AUTOLOAD)
# ----------------------------------------------------

print(">>> NEW INTERPRETER LOADED <<<")

import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

from library_scanner import LibraryScanner
from markoff_core import MarkoffModel


# ----------------------------------------------------
# THERMODYNAMIC FORECASTER (stub)
# ----------------------------------------------------
def thermo_forecast(
    query: str,
    narrative_library,
    elins_library,
    lawsuit_library=None,
):
    """
    ELIN-aware thermodynamic forecaster (placeholder).
    Replace with your real synthesis logic.
    """

    lines = []
    lines.append(f"Query: {query}")
    lines.append("")
    lines.append("Macro pattern: [derived from narrative_library]")
    lines.append("Micro pattern: [derived from elins_library]")

    if lawsuit_library is not None:
        lines.append("Case pattern: [derived from lawsuit_library]")
    else:
        lines.append("Case pattern: [not included — no + lawsuit modifier]")

    lines.append("")
    lines.append("Cross-basin alignment: [macro ↔ micro ↔ case]")
    lines.append("7/14/21-day curvature: [forecasted pressure evolution]")
    lines.append("Structural attractors: [likely structural outcomes]")
    lines.append("Operator notes: [practical, structural guidance]")

    return "\n".join(lines)


# ----------------------------------------------------
# AUTOLOAD: Clarity Library Subsystems
# ----------------------------------------------------
def load_text_folder(folder_path):
    """Load all .txt files from a folder recursively."""
    texts = []
    folder = Path(folder_path)
    if not folder.exists():
        print(f"[WARN] Folder not found: {folder_path}")
        return texts

    for f in folder.rglob("*.txt"):
        try:
            texts.append(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Could not read {f}: {e}")
    return texts


SUBSYSTEM_PATHS = {
    "ELINS_PLUS": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PLUS",
    "ELINS_PLUS_PRO": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PLUS_PRO",
    "ELINS_PRO": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_PRO",
    "LAWBRIDG": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\Lawbridg References",
    "NARRATIVE": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\Narrative_Architecture",
    "ELINS_LIBRARY": r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library\02_Subsystems\ELINS_Library",
}


def autoload(engine):
    engine.subsystems = {}
    total_loaded = 0

    print("\n=== AUTOLOADING SUBSYSTEM LIBRARIES ===")

    for name, path in SUBSYSTEM_PATHS.items():
        print(f"Loading {name} ...")
        texts = load_text_folder(path)
        engine.subsystems[name] = texts
        print(f"  → Loaded {len(texts)} documents.")
        total_loaded += len(texts)

    print(f"\nTotal documents loaded: {total_loaded}")

    print("\nTraining engine on loaded subsystems...")
    for name, texts in engine.subsystems.items():
        for text in texts:
            engine.train(text)

    print("Autoload complete.\n")

# ----------------------------------------------------
# DIAGNOSTIC ENGINE (placeholder)
# ----------------------------------------------------
def diagnostic_engine(query: str, engine):
    """
    Placeholder diagnostic engine.
    Replace with real structural / ELINS-aware logic later.
    """
    lines = []
    lines.append(f"Diagnostic query: {query}")
    lines.append("")
    lines.append("State classification:")
    try:
        sid = engine.classify(query)
        lines.append(f"  → {sid}")
    except Exception as e:
        lines.append(f"  [error during classification: {e}]")

    lines.append("")
    lines.append("Next-state prediction:")
    try:
        if sid:
            nxt = engine.predict_next_state(sid)
            lines.append(f"  → {nxt}")
        else:
            lines.append("  → no state available")
    except Exception as e:
        lines.append(f"  [error during next-state prediction: {e}]")

    lines.append("")
    lines.append("Word-level prediction:")
    try:
        first_word = query.split()[0] if query.strip() else None
        if first_word:
            nxt_word = engine.predict_next_word(first_word)
            lines.append(f"  → {nxt_word}")
        else:
            lines.append("  → no word available")
    except Exception as e:
        lines.append(f"  [error during word prediction: {e}]")

    lines.append("")
    lines.append("Structural notes:")
    lines.append("  [placeholder — add ELINS/curvature/pressure logic here]")

    return "\n".join(lines)
def run_interpreter(engine: MarkoffModel):
    """
    Main interactive loop for Markoff Engine v3.
    Supports:
      - scan
      - classify
      - predict-state
      - predict-word
      - forecast: [query] [+ lawsuit]
      - diagnose: diagnostic_engine()
      - default: train on input
    """
# ----------------------------------------------------
# VECTOR ENGINE (placeholder)
# ----------------------------------------------------
def vector_engine(query: str, engine):
    """
    Placeholder vector engine.
    Returns embedding info + nearest states.
    """
    lines = []
    lines.append(f"Vector query: {query}")
    lines.append("")

    # Embedding
    try:
        emb = engine.model.encode([query])[0]
        lines.append(f"Embedding length: {len(emb)}")
        lines.append("First 5 dims: " + ", ".join(f"{x:.4f}" for x in emb[:5]))
    except Exception as e:
        lines.append(f"[error computing embedding: {e}]")
        return "\n".join(lines)

    lines.append("")
    lines.append("Nearest states (placeholder):")
    try:
        sims = []
        for sid, state in engine.states.items():
            vec = state.get("embedding")
            if vec is not None:
                dot = sum(a*b for a, b in zip(emb, vec))
                sims.append((dot, sid))

        sims.sort(reverse=True)
        top = sims[:5]

        for score, sid in top:
            lines.append(f"  {sid}   score={score:.4f}")

        if not top:
            lines.append("  [no stored state vectors available]")

    except Exception as e:
        lines.append(f"[error computing nearest states: {e}]")

    lines.append("")
    lines.append("Vector notes:")
    lines.append("  [placeholder — add basin mapping / curvature logic here]")

    return "\n".join(lines)
# ----------------------------------------------------
# VECTOR ENGINE (placeholder)
# ----------------------------------------------------
def vector_engine(query: str, engine):
    """
    Placeholder vector engine.
    Returns embedding info + nearest states.
    """
    lines = []
    lines.append(f"Vector query: {query}")
    lines.append("")

    # Embedding
    try:
        emb = engine.model.encode([query])[0]
        lines.append(f"Embedding length: {len(emb)}")
        lines.append("First 5 dims: " + ", ".join(f"{x:.4f}" for x in emb[:5]))
    except Exception as e:
        lines.append(f"[error computing embedding: {e}]")
        return "\n".join(lines)

    lines.append("")
    lines.append("Nearest states (placeholder):")
    try:
        sims = []
        for sid, state in engine.states.items():
            vec = state.get("embedding")
            if vec is not None:
                dot = sum(a*b for a, b in zip(emb, vec))
                sims.append((dot, sid))

        sims.sort(reverse=True)
        top = sims[:5]

        for score, sid in top:
            lines.append(f"  {sid}   score={score:.4f}")

        if not top:
            lines.append("  [no stored state vectors available]")

    except Exception as e:
        lines.append(f"[error computing nearest states: {e}]")

    lines.append("")
    lines.append("Vector notes:")
    lines.append("  [placeholder — add basin mapping / curvature logic here]")

    return "\n".join(lines)

# ----------------------------------------------------
# GALILEO LOCAL WRAPPER (CALLABLE BY COPILOT)
# ----------------------------------------------------
def galileo_local(query: str, engine):
    q = query.strip()

    if q.startswith("diagnose:"):
        return diagnostic_engine(q[len("diagnose:"):].strip(), engine)

    if q.startswith("forecast:"):
        return thermo_forecast(
            query=q[len("forecast:"):].strip(),
            narrative_library=engine.subsystems.get("NARRATIVE"),
            elins_library=engine.subsystems.get("ELINS_LIBRARY"),
            lawsuit_library=None
        )

    if q.startswith("map:"):
        return vector_engine(q[len("map:"):].strip(), engine)

    engine.train(q)
    return "trained"

# ----------------------------------------------------
# MAIN INTERPRETER LOOP
# ----------------------------------------------------
def run_interpreter(engine):
    scanner = LibraryScanner(engine)

    print("Markoff Engine v3 — Ready")
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down.")
            break

        if not command:
            continue

        # EXIT
        if command.lower() in ("exit", "quit"):
            print("Shutting down.")
            break

        # SCAN
        if command.lower().startswith("scan"):
            folder = command[4:].strip()
            sentences, trained = scanner.scan_folder(folder)
            print(f"Scanned {sentences} sentences.")
            print(f"Trained on {trained} transitions.")
            continue

        # CLASSIFY
        if command.lower().startswith("classify "):
            text = command[len("classify "):].strip()
            state_id = engine.classify(text)
            if state_id is None:
                print("No state classification available.")
            else:
                state = engine.states.get(state_id, {})
                label = state.get("label", state_id)
                print(f"Classified as state {state_id}: {label}")
            continue

        # PREDICT NEXT STATE
        if command.lower().startswith("predict-state "):
            sid = command[len("predict-state "):].strip()
            next_state = engine.predict_next_state(sid)
            if next_state is None:
                print("No prediction available.")
            else:
                state = engine.states.get(next_state, {})
                label = state.get("label", next_state)
                print(f"Predicted next state: {next_state} ({label})")
            continue

        # PREDICT NEXT WORD
        if command.lower().startswith("predict-word "):
            w = command[len("predict-word "):].strip()
            nxt = engine.predict_next_word(w)
            if nxt is None:
                print("No prediction available.")
            else:
                print(f"Predicted next word: {nxt}")
            continue

        # FORECAST
        if command.lower().startswith("forecast:"):
            raw_query = command[len("forecast:"):].strip()

            include_lawsuit = False
            q_lower = raw_query.lower()
            if "+ lawsuit" in q_lower:
                include_lawsuit = True
                raw_query = q_lower.replace("+ lawsuit", "").strip()

            narrative_library = engine.subsystems.get("NARRATIVE", None)
            elins_library = engine.subsystems.get("ELINS_LIBRARY", None)
            lawsuit_library = engine.subsystems.get("LAWBRIDG", None) if include_lawsuit else None

            forecast_text = thermo_forecast(
                query=raw_query,
                narrative_library=narrative_library,
                elins_library=elins_library,
                lawsuit_library=lawsuit_library,
            )

            print("\n=== THERMODYNAMIC FORECAST ===")
            print(forecast_text)
            print("================================\n")
            continue

        # DIAGNOSE
        if command.lower().startswith("diagnose:"):
            raw_query = command[len("diagnose:"):].strip()
            result = diagnostic_engine(raw_query, engine)
            print("\n=== DIAGNOSTIC REPORT ===")
            print(result)
            print("================================\n")
            continue

        # MAP
        if command.lower().startswith("map:"):
            raw_query = command[len("map:"):].strip()
            result = vector_engine(raw_query, engine)
            print("\n=== VECTOR MAP ===")
            print(result)
            print("================================\n")
            continue

        # DEFAULT: TRAIN
        engine.train(command)
        print("Trained on input.")

# ----------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------
if __name__ == "__main__":
    engine = MarkoffModel(model=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"))
    autoload(engine)
    run_interpreter(engine)