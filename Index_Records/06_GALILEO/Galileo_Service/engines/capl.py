def negotiate_mode(requested_mode: str | None):
    return requested_mode if requested_mode in ("conversational", "directive") else "conversational"

def apply_constraints(mode: str, text: str):
    return text