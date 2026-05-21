import json
import os

BASE = os.path.join(
    os.path.expanduser("~"),
    "OneDrive",
    "Documents",
    "Library_Clarity_OS",
    "Index_Records"
)

def load_json(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return json.load(f)

def get_lanes():
    lanes_path = os.path.join(BASE, "00_Lanes", "lanes.json")
    return load_json(lanes_path)

def get_global_index():
    path = os.path.join(BASE, "01_Global", "global_index.json")
    return load_json(path)

def get_lane_index(lane):
    path = os.path.join(BASE, "02_Lane_Indexes", f"{lane}_index.json")
    return load_json(path)

def get_basin(lane):
    path = os.path.join(BASE, "03_Basin_Maps", f"{lane}_basin.json")
    return load_json(path)

def get_drift(lane):
    path = os.path.join(BASE, "04_Drift_Logs", f"{lane}_drift.json")
    return load_json(path)

def get_forecast(lane):
    path = os.path.join(BASE, "05_Forecasts", f"{lane}_forecast.json")
    return load_json(path)