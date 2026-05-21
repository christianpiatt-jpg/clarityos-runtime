def interpret(text: str, goal: str | None = None):
    return {"meaning": text, "goal_Y": goal, "action_X": None}

def truth_test(state):
    return {
        "system_truth": "aligned",
        "drift": False,
        "lurking_variables": []
    }