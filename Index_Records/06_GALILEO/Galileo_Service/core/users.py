# core/users.py

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "users.json"

def load_users():
    if not DATA_PATH.exists():
        return {}
    with open(DATA_PATH, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_users(users):
    with open(DATA_PATH, "w") as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    users = load_users()
    return users.get(user_id)

def create_user(user_id):
    users = load_users()
    if user_id not in users:
        users[user_id] = {"id": user_id}
        save_users(users)
    return users[user_id]
