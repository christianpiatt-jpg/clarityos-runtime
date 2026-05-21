# routes/markoff.py

from fastapi import APIRouter
from core.sessions import validate_session
from engines.markoff_engine import run_markoff  # adjust import if needed

router = APIRouter()

@router.post("/markoff/run")
def markoff_run(payload: dict):
    user = payload.get("user")
    session = payload.get("session")
    text = payload.get("input")
    mode = payload.get("mode", "markoff")

    if not user or not session:
        return {"error": "user and session required"}

    if not validate_session(user, session):
        return {"error": "invalid session"}

    # Call your Markoff engine
    output = run_markoff(text, mode)

    return {
        "user": user,
        "session": session,
        "output": output
    }
