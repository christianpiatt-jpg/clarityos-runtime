# logging.py — ClarityOS Logging Layer v1

import json
import uuid
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "conversations.jsonl"


def now():
    return datetime.utcnow().isoformat() + "Z"


def new_conversation_id():
    return "local-" + uuid.uuid4().hex[:8]


def append_packet(packet: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(packet) + "\n")


def next_turn_id(conversation_id: str):
    if not LOG_PATH.exists():
        return 1

    last = 0
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("conversation_id") == conversation_id:
                    last = max(last, obj.get("turn_id", 0))
            except:
                continue
    return last + 1
