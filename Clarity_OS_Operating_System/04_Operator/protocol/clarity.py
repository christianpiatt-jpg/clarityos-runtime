# clarity.py — #clarity over the log (v1)

import json
from pathlib import Path
from protocol.logging import LOG_PATH


def load_log():
    if not LOG_PATH.exists():
        return []

    entries = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except:
                continue
    return entries


def latest_conversation_id(entries):
    if not entries:
        return None
    # last conversation_id seen in the log
    return entries[-1].get("conversation_id")


def thread_for_conversation(entries, conversation_id):
    return [e for e in entries if e.get("conversation_id") == conversation_id]


def summarize_thread(thread):
    if not thread:
        return {
            "conversation_id": None,
            "turns": 0,
            "summary": "no conversation found",
        }

    convo_id = thread[0].get("conversation_id")
    turns = len(thread)

    last_user = next(
        (e for e in reversed(thread) if e.get("role") == "user"),
        None,
    )
    last_engine = next(
        (e for e in reversed(thread) if e.get("role") == "engine"),
        None,
    )

    summary = {
        "conversation_id": convo_id,
        "turns": turns,
        "last_user_text": last_user.get("text") if last_user else None,
        "last_engine_output": last_engine.get("engine_output") if last_engine else None,
    }

    return summary


def clarity_over_log():
    entries = load_log()
    convo_id = latest_conversation_id(entries)
    if not convo_id:
        return {"error": "no conversations in log"}

    thread = thread_for_conversation(entries, convo_id)
    summary = summarize_thread(thread)

    return {
        "mode": "#clarity",
        "conversation_id": summary["conversation_id"],
        "turns": summary["turns"],
        "last_user_text": summary["last_user_text"],
        "last_engine_output": summary["last_engine_output"],
    }
