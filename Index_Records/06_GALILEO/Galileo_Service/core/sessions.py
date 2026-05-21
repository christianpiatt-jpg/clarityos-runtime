# core/sessions.py

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sessions.json"

def load_sessions():
    if not DATA_PATH.exists():
        return {}
    with open(DATA_PATH, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_sessions(sessions):
    with open(DATA_PATH, "w") as f:
        json.dump(sessions, f, indent=2)

def create_session(user_id):
    sessions = load_sessions()
    session_id = f"{user_id}_default"
    sessions[session_id] = {"user": user_id, "active": True}
    save_sessions(sessions)
    return session_id

def validate_session(user_id, session_id):
    sessions = load_sessions()
    if session_id not in sessions:
        return False
    return sessions[session_id]["user"] == user_id
