import os
import json
from datetime import datetime
from collections import defaultdict, Counter

GLOBAL_INDEX = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\01_Global\global_markov_index.jsonl"
LANES_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\02_Lanes"
DRIFT_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\06_Logs\Drift_Logs"

def load_records(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except:
                continue
    return records

def compute_drift(records):
    # Drift = change in primitive distribution over time
    # We group by day, then compare day-to-day
    by_day = defaultdict(list)
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            continue
        day = ts.split("T")[0]
        by_day[day].append(r)

    # Sort days
    days = sorted(by_day.keys())
    drift_log = []

    prev_counts = None

    for day in days:
        day_records = by_day[day]
        counts = Counter(r.get("primitive") for r in day_records if r.get("primitive"))

        if prev_counts is not None:
            drift = {}
            all_keys = set(prev_counts.keys()) | set(counts.keys())
            for k in all_keys:
                drift[k] = counts.get(k, 0) - prev_counts.get(k, 0)
        else:
            drift = {k: counts[k] for k in counts}

        drift_log.append({
            "day": day,
            "counts": dict(counts),
            "drift": drift
        })

        prev_counts = counts

    return drift_log

def save_drift_log(name, drift_log):
    os.makedirs(DRIFT_DIR, exist_ok=True)
    out_path = os.path.join(DRIFT_DIR, f"{name}_drift_log.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(drift_log, f, indent=2)
    print(f"Saved drift log: {out_path}")

def main():
    print("Building drift logs...\n")

    # Global drift
    global_records = load_records(GLOBAL_INDEX)
    global_drift = compute_drift(global_records)
    save_drift_log("global", global_drift)

    # Lane drift
    if os.path.exists(LANES_DIR):
        for file in os.listdir(LANES_DIR):
            if not file.endswith("_markov_index.jsonl"):
                continue
            lane_name = file.replace("_markov_index.jsonl", "")
            lane_path = os.path.join(LANES_DIR, file)
            lane_records = load_records(lane_path)
            drift = compute_drift(lane_records)
            save_drift_log(lane_name, drift)

    print("\nDrift log build complete.")

if __name__ == "__main__":
    main()