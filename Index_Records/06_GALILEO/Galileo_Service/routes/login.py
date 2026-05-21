# routes/login.py

from fastapi import APIRouter
from core.users import create_user
from core.sessions import create_session

router = APIRouter()

@router.post("/login")
def login(payload: dict):
    user_id = payload.get("user")
    if not user_id:
        return {"error": "user field required"}

    # Create user if not exists
    create_user(user_id)

    # Create session for this user
    session_id = create_session(user_id)

    return {
        "user": user_id,
        "session": session_id,
        "message": "session created"
    }
