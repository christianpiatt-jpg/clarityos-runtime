# grok_integration.py
# Grok integration layer for ClarityOS.
# Calls Markoff + Clarity engines via HTTP and merges results.

import json
import os
import concurrent.futures
import requests


# ------------------------------------------------------------
#  SERVICE DISCOVERY
# ------------------------------------------------------------

def _os_root():
    """
    Return the ClarityOS root directory.

    grok_integration.py lives in:
      clarity_engine/04_Operator/grok_integration.py

    So OS root is one level up from 04_Operator:
      clarity_engine/
    """
    here = os.path.dirname(os.path.abspath(__file__))      # .../clarity_engine/04_Operator
    return os.path.dirname(here)                           # .../clarity_engine


def _services_path():
    return os.path.join(_os_root(), "clarity_services.json")


def load_services():
    """
    Load clarity_services.json and return a dict:
      { name: { "type": ..., "url": ... }, ... }
    """
    path = _services_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    engines = {}
    for entry in data.get("engines", []):
        name = entry.get("name")
        if name:
            engines[name] = entry
    return engines


# ------------------------------------------------------------
#  LOW-LEVEL HTTP CALL
# ------------------------------------------------------------

def _call_engine(name, url, text, timeout=5):
    """
    Call a single engine endpoint.
    Returns (name, result_dict).
    """
    try:
        payload = {"text": text, "meta": {}}
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # Ensure engine name is present
        if "engine" not in data:
            data["engine"] = name
        return name, data
    except Exception as e:
        return name, {
            "engine": name,
            "error": f"HTTP call failed: {e}",
            "url": url
        }


# ------------------------------------------------------------
#  MERGE / CLARITY MODES
# ------------------------------------------------------------

def _merge_mirror(results):
    """
    Mirror mode: just return raw engine outputs.
    """
    return results


def _merge_merge(results):
    """
    Merge mode: combine summaries/interpretations/tags where present.
    """
    summary_parts = []
    interpretation_parts = []
    tags = []

    for name, res in results.items():
        if isinstance(res, dict):
            if "summary" in res:
                summary_parts.append(f"[{name}] {res['summary']}")
            if "interpretation" in res:
                interpretation_parts.append(f"[{name}] {res['interpretation']}")
            if "tags" in res and isinstance(res["tags"], list):
                tags.extend(res["tags"])

    merged = {
        "summary": " ".join(summary_parts) if summary_parts else None,
        "interpretation": " ".join(interpretation_parts) if interpretation_parts else None,
        "tags": list(dict.fromkeys(tags)) if tags else []
    }
    return merged


def _merge_clarity(results):
    """
    Clarity mode: prioritize clarity engine output, annotate with Markoff evidence.
    """
    clarity_res = results.get("clarity", {})
    markoff_res = results.get("markoff", {})

    clarity_summary = None
    clarity_level = None
    notes = []

    if isinstance(clarity_res, dict):
        clarity_summary = clarity_res.get("summary")
        clarity_level = clarity_res.get("clarity_level")
        if isinstance(clarity_res.get("notes"), list):
            notes.extend(clarity_res["notes"])

    markoff_score = None
    markoff_tags = []

    if isinstance(markoff_res, dict):
        markoff_score = markoff_res.get("score")
        if isinstance(markoff_res.get("tags"), list):
            markoff_tags = markoff_res["tags"]

    merged = {
        "clarity_summary": clarity_summary,
        "clarity_level": clarity_level,
        "notes": notes,
        "evidence": {
            "markoff_score": markoff_score,
            "markoff_tags": markoff_tags
        }
    }
    return merged


# ------------------------------------------------------------
#  PUBLIC ENTRYPOINT
# ------------------------------------------------------------

def call_grok_engines(text, mode="mirror", timeout=5):
    """
    Call all configured engines with the given text and merge according to mode.
    Modes:
      - mirror  → raw engine outputs
      - merge   → combined summary/interpretation/tags
      - clarity → clarity-focused synthesis with markoff evidence
    """
    services = load_services()
    if not services:
        return {
            "status": "error",
            "mode": mode,
            "inputs": {"text": text},
            "engines": {},
            "merged": {},
            "error": "No services configured in clarity_services.json"
        }

    # Call all engines in parallel
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(services)) as executor:
        futures = []
        for name, cfg in services.items():
            url = cfg.get("url")
            if not url:
                continue
            futures.append(executor.submit(_call_engine, name, url, text, timeout))

        for fut in concurrent.futures.as_completed(futures):
            name, res = fut.result()
            results[name] = res

    # Determine status
    if not results:
        status = "error"
    elif any(isinstance(v, dict) and "error" in v for v in results.values()):
        status = "partial"
    else:
        status = "ok"

    # Merge according to mode
    if mode == "mirror":
        merged = _merge_mirror(results)
    elif mode == "merge":
        merged = _merge_merge(results)
    elif mode == "clarity":
        merged = _merge_clarity(results)
    else:
        return {
            "status": "error",
            "mode": mode,
            "inputs": {"text": text},
            "engines": results,
            "merged": {},
            "error": f"unknown mode '{mode}'"
        }

    return {
        "status": status,
        "mode": mode,
        "inputs": {"text": text},
        "engines": results,
        "merged": merged
    }
