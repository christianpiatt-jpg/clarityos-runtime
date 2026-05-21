import os
import json
from collections import Counter, defaultdict

LANES_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\02_Lanes"
FORECAST_DIR = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\07_Forecasts"
GLOBAL_INDEX = r"C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Index_Records\01_Global\global_markov_index.jsonl"

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

def build_transition_matrix(records):
    transitions = defaultdict(Counter)
    for r in records:
        p = r.get("primitive")
        ns = r.get("next_state")
        if p and ns:
            transitions[p][ns] += 1
    return transitions

def compute_forecast(transitions):
    forecast = {}
    for primitive, next_states in transitions.items():
        total = sum(next_states.values())
        if total == 0:
            continue
        forecast[primitive] = {
            ns: count / total for ns, count in next_states.items()
        }
    return forecast

def save_forecast(name, forecast):
    os.makedirs(FORECAST_DIR, exist_ok=True)
    out_path = os.path.join(FORECAST_DIR, f"{name}_forecast.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(forecast, f, indent=2)
    print(f"Saved forecast: {out_path}")

def main():
    print("Building forecasts...\n")

    # Global forecast
    global_records = load_records(GLOBAL_INDEX)
    global_transitions = build_transition_matrix(global_records)
    global_forecast = compute_forecast(global_transitions)
    save_forecast("global", global_forecast)

    # Lane forecasts
    if os.path.exists(LANES_DIR):
        for file in os.listdir(LANES_DIR):
            if not file.endswith("_markov_index.jsonl"):
                continue
            lane_name = file.replace("_markov_index.jsonl", "")
            lane_path = os.path.join(LANES_DIR, file)
            lane_records = load_records(lane_path)
            transitions = build_transition_matrix(lane_records)
            forecast = compute_forecast(transitions)
            save_forecast(lane_name, forecast)

    print("\nForecast build complete.")

if __name__ == "__main__":
    main()