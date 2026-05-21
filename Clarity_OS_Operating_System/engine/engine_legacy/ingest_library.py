import os
import json
import requests
from datetime import datetime

# -----------------------------------------
# CONFIGURATION
# -----------------------------------------

# Root of your entire Clarity Library
ROOT_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS"

# Output directories inside your OS
GLOBAL_INDEX = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\01_Global\global_markov_index.jsonl"
LANES_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\02_Lanes"

# Markov-Online API endpoint
API_URL = "http://127.0.0.1:8000/analyze"

# -----------------------------------------
# HELPERS
# -----------------------------------------

def is_text_file(path):
    return path.lower().endswith(".txt") or path.lower().endswith(".md")

def extract_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"Could not read {path}: {e}")
        return None

def detect_lanes(path):
    lanes = []

    # Lawsuit lane detection
    if "lawsuit" in path.lower() or "case" in path.lower():
        lanes.append("lawsuit")

    # ELINS detection
    if "elins" in path.lower():
        lanes.append("elins")

    # Notes lane
    if "notes" in path.lower():
        lanes.append("notes")

    # OS lane
    if "operating_system" in path.lower() or "clarity_os" in path.lower():
        lanes.append("os")

    return lanes if lanes else ["general"]

def send_to_markov(text):
    try:
        resp = requests.post(API_URL, json={"text": text})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error sending to Markov API: {e}")
        return None

def write_global_record(record):
    os.makedirs(os.path.dirname(GLOBAL_INDEX), exist_ok=True)
    with open(GLOBAL_INDEX, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def write_lane_record(record, lanes):
    for lane in lanes:
        lane_file = os.path.join(LANES_DIR, f"{lane}_markov_index.jsonl")
        os.makedirs(os.path.dirname(lane_file), exist_ok=True)
        with open(lane_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

# -----------------------------------------
# MAIN INGESTION LOOP
# -----------------------------------------

def ingest_library():
    print("Starting full-library ingestion...\n")

    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            path = os.path.join(root, file)

            if not is_text_file(path):
                continue

            print(f"Processing: {path}")

            text = extract_text(path)
            if not text:
                continue

            lanes = detect_lanes(path)
            result = send_to_markov(text)
            if not result:
                continue

            record = {
                "path": path,
                "lanes": lanes,
                "primitive": result.get("primitive"),
                "confidence": result.get("confidence"),
                "next_state": result.get("next_state"),
                "timestamp": datetime.now().isoformat()
            }

            write_global_record(record)
            write_lane_record(record, lanes)

    print("\nIngestion complete.")

# -----------------------------------------
# ENTRY POINT
# -----------------------------------------

if __name__ == "__main__":
    ingest_library()