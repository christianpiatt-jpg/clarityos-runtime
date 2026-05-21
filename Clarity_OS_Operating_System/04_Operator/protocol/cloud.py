# cloud.py — Operator Bridge v1 (OB‑1) + Logging Layer v1

import json
import urllib.request

from protocol.logging import (
    append_packet,
    next_turn_id,
    new_conversation_id,
    now,
)

CLOUD_ENGINE_URL = "https://clarity-engine-1013523799586.us-east4.run.app/ingest"

# Persistent conversation ID for this console session
CONVO_ID = new_conversation_id()


# ------------------------------------------------------------
#  CLOUD CALL
# ------------------------------------------------------------

def call_engine(text: str):
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        CLOUD_ENGINE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


# ------------------------------------------------------------
#  FORMATTING
# ------------------------------------------------------------

def format_packet(packet: dict) -> str:
    trace_id = packet.get("trace_id", "n/a")
    input_text = packet.get("input", "")
    output = packet.get("output", {})

    lines = []
    lines.append("CLOUD ENGINE RESPONSE")
    lines.append("---------------------")
    lines.append(f"trace_id: {trace_id}")
    lines.append(f"input   : {input_text}")

    if isinstance(output, dict):
        for k, v in output.items():
            lines.append(f"{k:10}: {v}")
    else:
        lines.append(f"output  : {output}")

    return "\n".join(lines)


# ------------------------------------------------------------
#  MAIN ENTRYPOINT
# ------------------------------------------------------------

def run(args: str) -> str:
    text = args.strip().strip('"')
    if not text:
        return "cloud: no text provided"

    # --- log user turn ---
    turn_id = next_turn_id(CONVO_ID)
    append_packet({
        "conversation_id": CONVO_ID,
        "turn_id": turn_id,
        "source": "console",
        "role": "user",
        "text": text,
        "timestamp": now()
    })

    # --- call engine ---
    try:
        packet = call_engine(text)
    except Exception as e:
        return f"cloud: error calling engine: {e}"

    # --- log engine turn ---
    turn_id = next_turn_id(CONVO_ID)
    append_packet({
        "conversation_id": CONVO_ID,
        "turn_id": turn_id,
        "source": "cloud",
        "role": "engine",
        "engine_output": packet,
        "timestamp": now()
    })

    return format_packet(packet)
