import os
import json
from collections import Counter, defaultdict

GLOBAL_INDEX = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\01_Global\global_markov_index.jsonl"
LANES_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\02_Lanes"
BASIN_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\05_Maps\Basin_Maps"

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
            except json.JSONDecodeError:
                continue
    return records

def build_basin_map(records):
    primitive_counts = Counter()
    transition_counts = defaultdict(Counter)

    for r in records:
        p = r.get("primitive")
        ns = r.get("next_state")
        if p:
            primitive_counts[p] += 1
        if p and ns:
            transition_counts[p][ns] += 1

    return {
        "primitive_counts": primitive_counts,
        "transition_counts": {
            p: dict(c) for p, c in transition_counts.items()
        }
    }

def save_basin_map(name, basin_map):
    os.makedirs(BASIN_DIR, exist_ok=True)
    out_path = os.path.join(BASIN_DIR, f"{name}_basin_map.json")
    serializable = {
        "primitive_counts": dict(basin_map["primitive_counts"]),
        "transition_counts": basin_map["transition_counts"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    print(f"Saved basin map: {out_path}")

def main():
    print("Building basin maps...\n")

    # Global basin map
    global_records = load_records(GLOBAL_INDEX)
    global_basin = build_basin_map(global_records)
    save_basin_map("global", global_basin)

    # Lane-specific basin maps
    if os.path.exists(LANES_DIR):
        for file in os.listdir(LANES_DIR):
            if not file.endswith("_markov_index.jsonl"):
                continue
            lane_name = file.replace("_markov_index.jsonl", "")
            lane_path = os.path.join(LANES_DIR, file)
            lane_records = load_records(lane_path)
            basin = build_basin_map(lane_records)
            save_basin_map(lane_name, basin)

    print("\nBasin map build complete.")

if __name__ == "__main__":
    main()