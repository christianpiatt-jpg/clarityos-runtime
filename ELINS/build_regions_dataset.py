#!/usr/bin/env python3
"""
Build regions_named.csv and regions_clusters.csv for the M1/M2/M3 protocol.

Pipeline:
  1. For each of 30 synthetic "days" rotating through topic_hint variants,
     call ELINS.regional_elins.run_regional_elins(region) for all 6
     regions. Yields 180 region runs.
  2. Build two envelope-weighted graphs over all runs:
       g_pre  = build_envelope_weighted_graph(runs, oriented=False)
       g_post = build_envelope_weighted_graph(runs, oriented=True)
     (Topology identical; edge weights differ via stress-lambda overlay.)
  3. Named-regions CSV: per (day, region), compute the metrics row using
     runs from that region cumulatively up to and including that day.
  4. Clusters CSV: enumerate connected components of the full graph (all
     days), produce one row per component with the same metrics.
  5. Sanity stats printed; CSVs written to analysis/physics/alternator/.

This driver does NOT touch persistent storage. It runs entirely in-process.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from collections import defaultdict, deque

# Ensure repo root is on sys.path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ELINS import regional_elins, region_metrics
import elins_entity_graph as eg


# -------------------- configuration --------------------

DAYS = 30
USER = "va_litigation"

_OUT_DIR = os.path.join(_REPO_ROOT, "analysis", "physics", "alternator")
os.makedirs(_OUT_DIR, exist_ok=True)
OUT_NAMED = os.path.join(_OUT_DIR, "regions_named.csv")
OUT_CLUSTERS = os.path.join(_OUT_DIR, "regions_clusters.csv")

# Per-region topic variants. Each region gets its own rotation of multi-
# entity phrases that mention only entities natural to that region.
# This keeps induced subgraphs regionally distinct: a US run never
# tags "Iran" or "OPEC" entities into the US cluster, because the topic
# strings for US never mention them. Cross-region overlap happens only
# when an entity appears in BOTH regions' topic vocabularies (rare by
# design here).
TOPIC_VARIANTS_BY_REGION = {
    "US": [
        "Federal Reserve and Treasury respond; Senate and Congress debate",
        "Supreme Court ruling pending; White House and Treasury respond",
        "Senate and Congress in deadlock; Federal Reserve cautious",
        "Treasury and White House align; Federal Reserve and Senate hesitate",
        "Supreme Court and Senate clash; Congress and White House divided",
        "Federal Reserve, Treasury, Senate, and Congress react to crisis",
        "White House and Supreme Court disagree; Senate and Treasury watch",
        "Congress and Federal Reserve debate; Senate and White House silent",
        "Treasury, Senate, and Federal Reserve deliberate; Supreme Court rules",
        "Federal Reserve and Treasury tighten; Senate and Congress respond",
    ],
    "EU": [
        "ECB and Brussels tighten; Germany and France align",
        "European Commission and Brussels debate; Germany and France clash",
        "ECB and European Commission caution; Germany and France diverge",
        "Brussels and ECB align; European Commission and Germany respond",
        "Germany and France resist; Brussels and European Commission press",
        "European Union and ECB steady; Germany, France, Brussels confer",
        "Germany and ECB align; Brussels and France hesitate",
        "European Commission and ECB tighten; Germany and France comply",
        "Brussels and Germany pressure France; ECB and European Commission watch",
        "European Union, ECB, Brussels, Germany, France converge",
    ],
    "MEA": [
        "Iran and Saudi Arabia in tension; Israel and Egypt watch",
        "OPEC and Iran posture; Saudi Arabia and Gulf respond",
        "Saudi Arabia, Iran, Israel, Egypt, and Gulf in flux",
        "OPEC and Saudi Arabia steady; Iran and Israel volatile",
        "Iran and Egypt diverge; Saudi Arabia, Israel, OPEC respond",
        "Gulf and OPEC align; Iran and Saudi Arabia compete",
        "Israel and Egypt confer; Iran, Saudi Arabia, Gulf react",
        "OPEC and Gulf tighten; Iran and Saudi Arabia in standoff",
        "Saudi Arabia, Israel, Egypt cooperate; Iran and Gulf cautious",
        "Iran, Saudi Arabia, Israel, Egypt, OPEC, and Gulf converge",
    ],
    "APAC": [
        "China and Taiwan strain; Japan, Korea, ASEAN watch",
        "Japan and Korea align; China and Taiwan in tension",
        "ASEAN and Australia brace; China, Japan, Korea respond",
        "China, Japan, Korea, Taiwan, ASEAN, Australia in flux",
        "Taiwan and Japan caution; China, Korea, ASEAN cautious",
        "Korea and Japan converge; China and Taiwan harden",
        "Australia and ASEAN watchful; China, Japan, Korea react",
        "China and Korea diverge; Japan, Taiwan, ASEAN respond",
        "Japan, Korea, ASEAN, Australia confer; China and Taiwan strain",
        "China, Japan, Korea, Taiwan, ASEAN, Australia coordinate",
    ],
    "Markets": [
        "S&P 500 and Nasdaq diverge; Bond market and Treasury yields shift",
        "Nasdaq and Bond market react; S&P 500 and Treasury yields steady",
        "Treasury yields and Bond market tighten; S&P 500 and Nasdaq fall",
        "S&P 500, Nasdaq, Bond market, Treasury yields all diverge",
        "Bond market and S&P 500 align; Nasdaq and Treasury yields move",
        "Treasury yields and Nasdaq spike; S&P 500 and Bond market hesitate",
        "Nasdaq and S&P 500 rally; Treasury yields and Bond market hold",
        "Bond market and Treasury yields ease; S&P 500 and Nasdaq mixed",
        "S&P 500 and Bond market diverge; Nasdaq and Treasury yields stable",
        "S&P 500, Nasdaq, Bond market, Treasury yields converge",
    ],
    "Tech": [
        "OpenAI and Anthropic compete; semiconductor and chip supply tight",
        "Anthropic and OpenAI release; chip and semiconductor industries respond",
        "Semiconductor demand peaks; OpenAI, Anthropic, chip suppliers move",
        "Chip and semiconductor capacity tight; OpenAI and Anthropic invest",
        "OpenAI and chip suppliers align; Anthropic and semiconductor hold",
        "Anthropic and OpenAI publish; chip and semiconductor tighten",
        "Semiconductor and chip supply ease; OpenAI and Anthropic expand",
        "OpenAI, Anthropic, chip, semiconductor sector reshapes",
        "Chip suppliers and Anthropic align; OpenAI and semiconductor diverge",
        "OpenAI, Anthropic, chip, semiconductor sectors converge",
    ],
}


# -------------------- step 1: synthesize runs --------------------

def synthesize_runs() -> list[dict]:
    runs: list[dict] = []
    print(f"Synthesizing {DAYS} days x {len(regional_elins.REGION_CODES)} regions = "
          f"{DAYS * len(regional_elins.REGION_CODES)} regional ELINS runs...")
    t0 = time.time()
    for d in range(DAYS):
        for region in regional_elins.REGION_CODES:
            variants = TOPIC_VARIANTS_BY_REGION[region]
            topic = variants[d % len(variants)]
            run = regional_elins.run_regional_elins(
                region, USER, topic_hint=topic,
            )
            run["_day_index"] = d
            ents = eg.extract_entities(run)
            run["_extracted_entities"] = [e["name"] for e in ents]
            runs.append(run)
    print(f"  done in {time.time()-t0:.1f}s")
    return runs


# -------------------- step 2: build graphs --------------------

def build_graphs(runs: list[dict]) -> tuple[dict, dict]:
    print("Building envelope-weighted graphs (pre + post orientation)...")
    g_pre = region_metrics.build_envelope_weighted_graph(runs, oriented=False)
    g_post = region_metrics.build_envelope_weighted_graph(runs, oriented=True)
    print(f"  full graph: {len(g_pre['entities'])} entities, "
          f"{len(g_pre['edges'])} edges")
    return g_pre, g_post


# -------------------- step 3: named-region rows --------------------

def write_named_csv(runs: list[dict], out_path: str) -> int:
    """Per (day, region): graph snapshots are cumulative through that day."""
    print(f"Writing named-region rows to {out_path}...")
    rows: list[dict] = []
    by_region: dict[str, list[dict]] = defaultdict(list)
    by_region_through_day: dict[tuple, list[dict]] = defaultdict(list)
    for r in runs:
        by_region[r["region_code"]].append(r)

    for d in range(DAYS):
        runs_through_d = [r for r in runs if r["_day_index"] <= d]
        g_pre_d = region_metrics.build_envelope_weighted_graph(
            runs_through_d, oriented=False)
        g_post_d = region_metrics.build_envelope_weighted_graph(
            runs_through_d, oriented=True)
        for region in regional_elins.REGION_CODES:
            region_runs_through_d = [
                r for r in runs_through_d if r["region_code"] == region
            ]
            row = region_metrics.region_metrics_row(
                region, region_runs_through_d, g_pre_d, g_post_d)
            row["day_index"] = d
            variants = TOPIC_VARIANTS_BY_REGION[region]
            row["topic_hint"] = variants[d % len(variants)]
            row["region_label"] = region
            rows.append(row)

    cols = [
        "day_index", "region_label", "topic_hint",
        "node_count", "edge_count", "triangle_count",
        "E", "E_oriented", "r", "orientation_score",
        "triangle_homogeneity_pre", "triangle_homogeneity_post", "delta",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"  {len(rows)} rows written.")
    return len(rows)


# -------------------- step 4: cluster rows --------------------

def connected_components(entities: set, edges: dict) -> list[set]:
    adj: dict = defaultdict(set)
    for e in edges.values():
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    seen: set = set()
    comps: list[set] = []
    for n in entities:
        if n in seen:
            continue
        # BFS
        comp: set = {n}
        q = deque([n])
        seen.add(n)
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        comps.append(comp)
    return comps


def write_clusters_csv(runs: list[dict], g_pre: dict, g_post: dict, out_path: str) -> int:
    print(f"Writing cluster rows to {out_path}...")
    ents_all = set(g_pre.get("entities", {}).keys())
    edges_all = g_pre.get("edges", {})
    comps = connected_components(ents_all, edges_all)
    print(f"  {len(comps)} connected components in the full graph "
          f"(sizes: {sorted([len(c) for c in comps], reverse=True)[:10]} ...)")

    rows = []
    for i, comp in enumerate(comps):
        # Find all runs where ANY entity from comp appears
        runs_in_comp = [
            r for r in runs
            if any(e in comp for e in r.get("_extracted_entities", []))
        ]
        edges_pre = {
            k: v for k, v in g_pre["edges"].items()
            if v["a"] in comp and v["b"] in comp
        }
        edges_post = {
            k: v for k, v in g_post["edges"].items()
            if v["a"] in comp and v["b"] in comp
        }
        triangles = region_metrics.find_triangles(comp, edges_pre)
        th_pre = region_metrics.triangle_homogeneity(triangles, edges_pre)
        th_post = region_metrics.triangle_homogeneity(triangles, edges_post)
        rows.append({
            "cluster_id": f"cc_{i:03d}",
            "node_count": len(comp),
            "edge_count": len(edges_pre),
            "triangle_count": len(triangles),
            "runs_in_cluster": len(runs_in_comp),
            "E": region_metrics.conflict_mass_E(runs_in_comp, oriented=False),
            "E_oriented": region_metrics.conflict_mass_E(runs_in_comp, oriented=True),
            "r": region_metrics.graph_radius(comp, edges_pre),
            "orientation_score": region_metrics.orientation_score(runs_in_comp),
            "triangle_homogeneity_pre": th_pre,
            "triangle_homogeneity_post": th_post,
            "delta": th_post - th_pre,
        })

    cols = [
        "cluster_id", "node_count", "edge_count", "triangle_count",
        "runs_in_cluster", "E", "E_oriented", "r", "orientation_score",
        "triangle_homogeneity_pre", "triangle_homogeneity_post", "delta",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"  {len(rows)} cluster rows written.")
    return len(rows)


# -------------------- step 5: sanity --------------------

def print_summary(runs: list[dict], g_pre: dict, g_post: dict) -> None:
    print("\n--- summary ---")
    print(f"runs:           {len(runs)}")
    by_region: dict = defaultdict(int)
    for r in runs:
        by_region[r["region_code"]] += 1
    print(f"runs/region:    {dict(by_region)}")
    print(f"entities total: {len(g_pre['entities'])}")
    print(f"edges total:    {len(g_pre['edges'])}")
    sample_intens = (runs[0].get("primitives") or {}).get("intensities") or {}
    print(f"sample run primitives (region=US, day=0): {sample_intens}")


def main():
    runs = synthesize_runs()
    g_pre, g_post = build_graphs(runs)
    print_summary(runs, g_pre, g_post)
    write_named_csv(runs, OUT_NAMED)
    write_clusters_csv(runs, g_pre, g_post, OUT_CLUSTERS)
    print("\nDone.")


if __name__ == "__main__":
    main()
