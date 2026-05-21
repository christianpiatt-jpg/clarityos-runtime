import json
import os
from datetime import datetime

# -----------------------------------------
# 1. PRIMITIVE CLASSIFIER (starter version)
# -----------------------------------------

PRIMITIVES = {
    "conflict": ["war", "attack", "violence", "tension", "protest"],
    "cooperation": ["deal", "agreement", "ally", "support", "partnership"],
    "resource": ["oil", "water", "energy", "food", "supply"],
    "legitimacy": ["election", "court", "law", "authority", "govern"],
    "identity": ["race", "religion", "culture", "gender", "group"],
    "motion": ["move", "shift", "change", "trend", "flow"],
    "collapse": ["crisis", "failure", "breakdown", "default", "chaos"],
    "renewal": ["growth", "recovery", "innovation", "reform", "rebirth"]
}

def classify(text):
    text_lower = text.lower()
    scores = {p: 0 for p in PRIMITIVES}

    for primitive, keywords in PRIMITIVES.items():
        for kw in keywords:
            if kw in text_lower:
                scores[primitive] += 1

    # pick the primitive with the highest score
    best = max(scores, key=scores.get)
    confidence = scores[best]

    return best, confidence

# -----------------------------------------
# 2. TRANSITION TABLE
# -----------------------------------------

TRANSITION_FILE = "transitions.json"

def load_transitions():
    if not os.path.exists(TRANSITION_FILE):
        return {}
    with open(TRANSITION_FILE, "r") as f:
        return json.load(f)

def save_transitions(t):
    with open(TRANSITION_FILE, "w") as f:
        json.dump(t, f, indent=2)

def update_transition(prev, current):
    t = load_transitions()
    if prev not in t:
        t[prev] = {}
    if current not in t[prev]:
        t[prev][current] = 0
    t[prev][current] += 1
    save_transitions(t)

def predict_next(current):
    t = load_transitions()
    if current not in t:
        return None
    next_states = t[current]
    if not next_states:
        return None
    return max(next_states, key=next_states.get)

# -----------------------------------------
# 3. HISTORY LOG
# -----------------------------------------

def log_event(text, primitive, confidence):
    with open("history.log", "a") as f:
        f.write(f"{datetime.now()} | {primitive} ({confidence}) | {text}\n")

# -----------------------------------------
# 4. MAIN LOOP
# -----------------------------------------

def main():
    print("Markoff Engine v1 — Starter Logic")
    print("Enter text to classify. Type 'exit' to quit.\n")

    last_primitive = None

    while True:
        text = input("> ")

        if text.lower() == "exit":
            break

        primitive, confidence = classify(text)
        log_event(text, primitive, confidence)

        if last_primitive:
            update_transition(last_primitive, primitive)

        next_pred = predict_next(primitive)

        print(f"\nPrimitive: {primitive}")
        print(f"Confidence: {confidence}")
        if next_pred:
            print(f"Predicted next state: {next_pred}")
        else:
            print("Predicted next state: (none yet)")

        print("")
        last_primitive = primitive
def analyze(text):
    """
    API-friendly wrapper for the Markoff engine.
    Takes a text string and returns a JSON-serializable dict.
    """
    primitive, confidence = classify(text)

    # Load previous primitive if exists
    transitions = load_transitions()
    last_primitive = None
    if transitions:
        # last key in transitions is the last primitive seen
        last_primitive = list(transitions.keys())[-1]

    # Update transitions if we have a previous primitive
    if last_primitive:
        update_transition(last_primitive, primitive)

    # Predict next state
    next_pred = predict_next(primitive)

    # Log event
    log_event(text, primitive, confidence)

    return {
        "primitive": primitive,
        "confidence": confidence,
        "next_state": next_pred
    }


if __name__ == "__main__":
    main()