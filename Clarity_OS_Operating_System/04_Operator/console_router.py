"""
ClarityOS Operator Console v3.0
Pure Cyan Mode v2 — upgraded operator-grade monochrome interface.
"""

import sys
sys.path.insert(0, r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS")

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time
import requests
from clarity_engine.kernel import get_os
from grok_integration import call_grok_engines
from clarity_engine.clarityos_init import run_clarity_markoff

# ANSI cyan
CYAN = "\033[96m"
RESET = "\033[0m"


def c(text):
    """Wrap text in cyan."""
    return f"{CYAN}{text}{RESET}"


def log(msg):
    """System log channel (cyan)."""
    print(c(f"[sys] {msg}"))


def pretty(obj):
    """Pretty-print dicts and lists in cyan."""
    if isinstance(obj, dict):
        inner = ", ".join(f"{k}: {v}" for k, v in obj.items())
        return c("{ " + inner + " }")
    if isinstance(obj, list):
        inner = ", ".join(str(x) for x in obj)
        return c("[ " + inner + " ]")
    return c(str(obj))


# ------------------------------------------------------------
#  COMMAND IMPLEMENTATIONS
# ------------------------------------------------------------

def CLARITY_BOOT():
    os = get_os()
    try:
        health = os.health()
    except Exception:
        health = {"error": "health() not available"}

    return {
        "kernel": "online",
        "os_type": type(os).__name__,
        "orchestrator": type(os.orchestrator).__name__ if hasattr(os, "orchestrator") else None,
        "subsystems": {
            "library": hasattr(os, "library"),
            "narrative": hasattr(os, "narrative"),
            "analytics": hasattr(os, "analytics"),
            "elins": hasattr(os, "elins"),
            "mesh": hasattr(os, "mesh"),
            "memory": hasattr(os, "memory"),
            "global_arc": hasattr(os, "global_arc"),
            "hydronic_maps": hasattr(os, "hydronic_maps"),
        },
        "health": health,
    }


def DIAG_OS():
    os = get_os()
    if hasattr(os, "health"):
        try:
            return os.health()
        except Exception as e:
            return {"error": f"health() failed: {e}"}
    return {"error": "health() not implemented on OS"}


def CMD_HELP():
    return {
        "commands": [
            "boot",
            "diag",
            "grok <text>",
            "copilot <text>",
            "clarity_markoff <text>",
            "exit",
        ]
    }


def CMD_GROK(args):
    if not args:
        return {"error": "grok requires text"}
    text = " ".join(args)
    return call_grok_engines(text, mode="mirror")


def CMD_COPILOT(args):
    if not args:
        return {"error": "copilot requires text"}
    text = " ".join(args)

    try:
        resp = requests.post(
            "http://127.0.0.1:8001/clarify",
            json={"text": text},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": f"copilot request failed: {e}"}


def CMD_CLARITY_MARKOFF(args):
    if not args:
        return {"error": "clarity_markoff requires text"}
    text = " ".join(args)
    try:
        return run_clarity_markoff(text, mode="merge")
    except Exception as e:
        return {"error": f"clarity_markoff failed: {e}"}


# ------------------------------------------------------------
#  ROUTER
# ------------------------------------------------------------

def dispatch(raw: str):
    text = raw.strip()
    if not text:
        return None

    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "boot":
        return CLARITY_BOOT()

    if cmd == "diag":
        return DIAG_OS()

    if cmd == "help":
        return CMD_HELP()

    if cmd == "grok":
        return CMD_GROK(args)

    if cmd == "copilot":
        return CMD_COPILOT(args)

    if cmd == "clarity_markoff":
        return CMD_CLARITY_MARKOFF(args)

    if cmd in ("exit", "quit"):
        log("Shutting down console.")
        sys.exit(0)

    return {"error": f"unknown command '{cmd}'"}


# ------------------------------------------------------------
#  MAIN LOOP (if run directly)
# ------------------------------------------------------------

if __name__ == "__main__":
    log("Console router online.")
    while True:
        try:
            raw = input(c(">> "))
            out = dispatch(raw)
            if out is not None:
                print(pretty(out))
        except KeyboardInterrupt:
            log("Interrupted. Exiting.")
            break
