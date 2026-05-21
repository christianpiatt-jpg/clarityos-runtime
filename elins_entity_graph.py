"""
v37 — Cross-cluster entity graph + ELINS network view.

Pure deterministic graph builder over ELINS objects. Same input → same
output. No model calls, no random, no clock dependency. Edges are
undirected and keyed by the pair ``"<a>||<b>"`` with ``a < b`` so the
serialised graph is plain JSON.

Public API:
    build_entity_graph(elins_runs)
    merge_entity_graph(existing, new)
    get_entity_neighbors(graph, entity, limit=20)
    get_entity_timeseries(graph, entity)
    search_entities(graph, q, limit=50)
    extract_entities(elins_obj)              # exposed for tests
    EMPTY_GRAPH                              # static empty-graph fixture
    GRAPH_VERSION

Graph shape (the dict returned by ``build`` / ``merge``):

    {
      "entities": {
        "<name>": {
          "degree":   int,
          "clusters": [cluster_id, ...],
          "domains":  {domain_key: count, ...},
          "ep_stats": {"sum": float, "count": int, "mean": float},
          "appearances": [
            {"ts": float, "ep_mean": float, "domains": {...}, "cluster": str}
          ]
        },
        ...
      },
      "edges": {
        "<a>||<b>": {
          "a": "<a>", "b": "<b>",
          "weight": float, "co_occurrences": int,
          "first_ts": float, "last_ts": float
        },
        ...
      },
      "version":    "entity_graph.v37.1",
      "updated_ts": float
    }

The graph is deliberately small + pure: callers can persist via
``ELINS.elins_project.save_entity_graph`` and load via the matching
loaders.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

GRAPH_VERSION: str = "entity_graph.v37.1"

EMPTY_GRAPH: dict = {
    "entities": {},
    "edges": {},
    "version": GRAPH_VERSION,
    "updated_ts": 0.0,
}

# Lexical entity-term seed list. Compiled from the regional profiles +
# a small global pool. The set is stable per-deploy so extraction is
# deterministic — adding a region's entity_terms over time is the
# growth path, not runtime mutation.
_LEXICAL_ENTITIES: tuple = (
    # US
    "United States", "Federal Reserve", "Supreme Court", "Senate",
    "Congress", "White House", "Treasury",
    # EU
    "European Union", "Brussels", "ECB", "European Commission",
    "Germany", "France",
    # MEA
    "Iran", "Saudi Arabia", "Israel", "Egypt", "Gulf", "OPEC",
    # APAC
    "China", "Japan", "Korea", "Taiwan", "ASEAN", "Australia",
    # Markets
    "S&P 500", "Nasdaq", "Treasury yields", "Bond market",
    "Equity market", "FX market",
    # Tech
    "AI", "Frontier model", "Semiconductor", "Data center",
    "OpenAI", "Anthropic",
)

# Lowercase representation → canonical (Title) form. Built once at
# module import for fast scanning.
_LEXICAL_BY_LOWER: dict[str, str] = {e.lower(): e for e in _LEXICAL_ENTITIES}

# Pre-compiled word-boundary regexes per entity. Plain substring match
# was too aggressive ("AI" hits "raise"); ``\b`` boundaries respect
# token edges and special chars like "&" / "." naturally fall outside
# ``\w`` so ``S&P 500`` still matches.
_LEXICAL_REGEXES: tuple = tuple(
    (re.compile(r"\b" + re.escape(e) + r"\b", re.IGNORECASE), e)
    for e in _LEXICAL_ENTITIES
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _edge_key(a: str, b: str) -> str:
    if a == b:
        raise ValueError("self-edges are not allowed")
    return f"{a}||{b}" if a < b else f"{b}||{a}"


def _round(x: float, places: int = 4) -> float:
    return round(float(x), places)


def _normalise_entity(name: str) -> str:
    """Trim + collapse whitespace. Keep case; the lexical pass already
    canonicalises."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip())


def _ts_of(elins_obj: dict) -> float:
    """Best-effort timestamp extraction. Falls back to 0.0 so deterministic
    fixtures with no ts still build a graph."""
    candidates = (
        elins_obj.get("regional_run_ts"),
        (elins_obj.get("input_phase") or {}).get("ts"),
        (elins_obj.get("output_object") or {}).get("ts"),
        elins_obj.get("ts"),
    )
    for c in candidates:
        if isinstance(c, (int, float)) and c > 0:
            return float(c)
    return 0.0


def _ep_mean_of(elins_obj: dict) -> float:
    ep = elins_obj.get("ep_field_summary") or {}
    try:
        return float(ep.get("intensity_mean") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _domains_of(elins_obj: dict) -> dict[str, float]:
    dm = elins_obj.get("domain_mapping") or {}
    scores = dm.get("scores") or {}
    out: dict[str, float] = {}
    for k, v in scores.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _cluster_of(elins_obj: dict) -> str:
    region = elins_obj.get("region_code")
    if isinstance(region, str) and region:
        return region
    return "global"


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------
def extract_entities(elins_obj: dict) -> list[dict]:
    """Return the list of entities recognised in a single ELINS run.

    Each entity dict has: ``{"name", "source"}``. Entities are de-duped
    on canonical name (case-insensitive) but preserve the first source
    that introduced them. Sources are ordered most-authoritative-first
    so ESO anchors win over lexical hits.
    """
    if not isinstance(elins_obj, dict):
        return []
    seen: dict[str, dict] = {}

    def _add(name: str, source: str) -> None:
        canon = _normalise_entity(name)
        if not canon:
            return
        key = canon.lower()
        if key in seen:
            return
        seen[key] = {"name": canon, "source": source}

    # 1. ESO anchors (regional ELINS with cloud_perplexity ESO).
    ext = elins_obj.get("external_signals") or {}
    for anchor in (ext.get("anchors") or []):
        _add(str(anchor), "eso_anchor")
    for sig in (ext.get("signals") or []):
        if isinstance(sig, dict):
            anchor = sig.get("anchor")
            if anchor:
                _add(str(anchor), "eso_signal")

    # 2. Synthesis-mirrored anchors (kept for forward-compat clients).
    syn = elins_obj.get("synthesis") or {}
    for anchor in (syn.get("external_anchors") or []):
        _add(str(anchor), "synthesis_anchor")

    # 3. topic_hint (regional ELINS).
    topic = elins_obj.get("topic_hint")
    if isinstance(topic, str) and topic.strip():
        _add(topic.strip(), "topic_hint")

    # 4. Lexical scan over the scenario text. Word-boundary regex so
    # short tokens ("AI") don't hit substrings ("raise").
    text = (elins_obj.get("input_phase") or {}).get("text") or ""
    if text:
        for pattern, canon in _LEXICAL_REGEXES:
            if pattern.search(text):
                _add(canon, "lexical")

    return list(seen.values())


# ---------------------------------------------------------------------------
# build_entity_graph
# ---------------------------------------------------------------------------
def _ingest_run_into_graph(graph: dict, elins_obj: dict) -> None:
    entities = extract_entities(elins_obj)
    if not entities:
        return
    ts = _ts_of(elins_obj)
    ep_mean = _ep_mean_of(elins_obj)
    domains = _domains_of(elins_obj)
    cluster = _cluster_of(elins_obj)

    # Per-entity update.
    for ent in entities:
        name = ent["name"]
        rec = graph["entities"].setdefault(name, {
            "degree": 0,
            "clusters": [],
            "domains": {},
            "ep_stats": {"sum": 0.0, "count": 0, "mean": 0.0},
            "appearances": [],
        })
        if cluster not in rec["clusters"]:
            rec["clusters"].append(cluster)
        for k, v in domains.items():
            rec["domains"][k] = round(rec["domains"].get(k, 0.0) + v, 4)
        ep_stats = rec["ep_stats"]
        ep_stats["sum"] = round(ep_stats["sum"] + ep_mean, 4)
        ep_stats["count"] = ep_stats["count"] + 1
        ep_stats["mean"] = _round(
            ep_stats["sum"] / max(1, ep_stats["count"])
        )
        rec["appearances"].append({
            "ts": ts,
            "ep_mean": _round(ep_mean),
            "domains": dict(domains),
            "cluster": cluster,
        })

    # Pairwise edges (undirected, dedup via lex-sorted key).
    names = sorted({e["name"] for e in entities})
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            key = _edge_key(a, b)
            edge = graph["edges"].setdefault(key, {
                "a": a, "b": b,
                "weight": 0.0, "co_occurrences": 0,
                "first_ts": ts if ts > 0 else 0.0,
                "last_ts": ts if ts > 0 else 0.0,
            })
            edge["co_occurrences"] += 1
            # Weight blends ep_mean (always > 0 for meaningful runs) plus
            # a small base 1.0 so edges from low-EP runs still register.
            edge["weight"] = _round(edge["weight"] + 1.0 + ep_mean)
            if ts > 0:
                if edge["first_ts"] in (0.0, None) or ts < edge["first_ts"]:
                    edge["first_ts"] = ts
                if ts > (edge["last_ts"] or 0.0):
                    edge["last_ts"] = ts


def _recompute_degrees(graph: dict) -> None:
    """Walk edges and set entity.degree to the count of distinct
    neighbours. Avoids drift between mutate paths."""
    neighbours: dict[str, set] = {}
    for key, edge in graph["edges"].items():
        a, b = edge["a"], edge["b"]
        neighbours.setdefault(a, set()).add(b)
        neighbours.setdefault(b, set()).add(a)
    for name, rec in graph["entities"].items():
        rec["degree"] = len(neighbours.get(name, ()))


def build_entity_graph(elins_runs: Iterable[dict]) -> dict:
    """Build a fresh graph from a list of ELINS objects."""
    if elins_runs is None:
        raise ValueError("elins_runs must be a list")
    graph = {
        "entities": {},
        "edges": {},
        "version": GRAPH_VERSION,
        "updated_ts": 0.0,
    }
    runs_list = list(elins_runs)
    for run in runs_list:
        if not isinstance(run, dict):
            raise ValueError("each run must be a dict")
        _ingest_run_into_graph(graph, run)
    _recompute_degrees(graph)
    if runs_list:
        max_ts = max((_ts_of(r) for r in runs_list), default=0.0)
        graph["updated_ts"] = _round(max_ts)
    return graph


# ---------------------------------------------------------------------------
# merge_entity_graph
# ---------------------------------------------------------------------------
def _validate_graph(g: dict, *, name: str) -> None:
    if not isinstance(g, dict):
        raise ValueError(f"{name} must be a dict")
    if "entities" not in g or "edges" not in g:
        raise ValueError(f"{name} is missing required keys")


def merge_entity_graph(existing: dict, new: dict) -> dict:
    """Combine two graphs into a single new graph. Pure: neither input
    is mutated."""
    _validate_graph(existing, name="existing")
    _validate_graph(new, name="new")
    out = {
        "entities": {},
        "edges": {},
        "version": GRAPH_VERSION,
        "updated_ts": 0.0,
    }

    # Entities — union, with per-field reduction.
    all_names = set(existing["entities"].keys()) | set(new["entities"].keys())
    for name in all_names:
        a = existing["entities"].get(name)
        b = new["entities"].get(name)
        rec = {
            "degree": 0,
            "clusters": [],
            "domains": {},
            "ep_stats": {"sum": 0.0, "count": 0, "mean": 0.0},
            "appearances": [],
        }
        for src in (a, b):
            if not src:
                continue
            for cluster in src.get("clusters") or []:
                if cluster not in rec["clusters"]:
                    rec["clusters"].append(cluster)
            for k, v in (src.get("domains") or {}).items():
                rec["domains"][k] = round(
                    rec["domains"].get(k, 0.0) + float(v or 0.0), 4,
                )
            ep_src = src.get("ep_stats") or {}
            rec["ep_stats"]["sum"] = round(
                rec["ep_stats"]["sum"] + float(ep_src.get("sum") or 0.0), 4,
            )
            rec["ep_stats"]["count"] += int(ep_src.get("count") or 0)
            for app in src.get("appearances") or []:
                rec["appearances"].append(dict(app))
        rec["ep_stats"]["mean"] = _round(
            rec["ep_stats"]["sum"] / max(1, rec["ep_stats"]["count"])
        )
        # Sort by ts; preserve duplicates — every appearance is a real
        # event. The scheduler builds a fresh delta per pass, so the
        # existing + delta inputs to merge are always disjoint. Callers
        # that accidentally merge the same graph twice would double-count
        # by design (a caller bug, not something we paper over).
        rec["appearances"].sort(key=lambda a: float(a.get("ts") or 0.0))
        out["entities"][name] = rec

    # Edges — union with weight + co_occurrence sums; ts min/max.
    all_keys = set(existing["edges"].keys()) | set(new["edges"].keys())
    for key in all_keys:
        a = existing["edges"].get(key) or {}
        b = new["edges"].get(key) or {}
        merged = {
            "a": a.get("a") or b.get("a"),
            "b": a.get("b") or b.get("b"),
            "weight": _round(float(a.get("weight") or 0.0) + float(b.get("weight") or 0.0)),
            "co_occurrences": int(a.get("co_occurrences") or 0) + int(b.get("co_occurrences") or 0),
        }
        first_candidates = [
            float(x) for x in (a.get("first_ts"), b.get("first_ts"))
            if isinstance(x, (int, float)) and x > 0
        ]
        last_candidates = [
            float(x) for x in (a.get("last_ts"), b.get("last_ts"))
            if isinstance(x, (int, float)) and x > 0
        ]
        merged["first_ts"] = min(first_candidates) if first_candidates else 0.0
        merged["last_ts"] = max(last_candidates) if last_candidates else 0.0
        out["edges"][key] = merged

    _recompute_degrees(out)
    out["updated_ts"] = _round(max(
        float(existing.get("updated_ts") or 0.0),
        float(new.get("updated_ts") or 0.0),
    ))
    return out


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------
def get_entity_neighbors(graph: dict, entity: str, limit: int = 20) -> list[dict]:
    """Return neighbours of ``entity`` sorted by edge weight desc."""
    _validate_graph(graph, name="graph")
    if not isinstance(entity, str) or not entity:
        raise ValueError("entity must be a non-empty string")
    name = _normalise_entity(entity)
    out: list[dict] = []
    for key, edge in (graph.get("edges") or {}).items():
        if edge["a"] != name and edge["b"] != name:
            continue
        other = edge["b"] if edge["a"] == name else edge["a"]
        rec = (graph.get("entities") or {}).get(other) or {}
        domains = rec.get("domains") or {}
        top_domains = [
            k for k, _ in sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        ]
        out.append({
            "name": other,
            "weight": float(edge.get("weight") or 0.0),
            "co_occurrences": int(edge.get("co_occurrences") or 0),
            "first_ts": float(edge.get("first_ts") or 0.0),
            "last_ts": float(edge.get("last_ts") or 0.0),
            "top_domains": top_domains,
        })
    out.sort(key=lambda r: (-r["weight"], r["name"]))
    return out[: max(1, int(limit))]


def get_entity_timeseries(graph: dict, entity: str) -> list[dict]:
    """Return chronological appearances of ``entity``.

    Each item: ``{ts, ep_mean, domains, cluster}``. Stable sort on ts.
    """
    _validate_graph(graph, name="graph")
    name = _normalise_entity(entity or "")
    rec = (graph.get("entities") or {}).get(name) or {}
    apps = list(rec.get("appearances") or [])
    apps.sort(key=lambda a: float(a.get("ts") or 0.0))
    return [
        {
            "ts": float(a.get("ts") or 0.0),
            "ep_mean": float(a.get("ep_mean") or 0.0),
            "domains": dict(a.get("domains") or {}),
            "cluster": a.get("cluster"),
        }
        for a in apps
    ]


def search_entities(graph: dict, q: str, limit: int = 50) -> list[dict]:
    """Substring (case-insensitive) search over entity names. Returns
    ``[{name, degree, top_domains, ep_mean, clusters}, ...]`` ordered
    by degree desc, name asc."""
    _validate_graph(graph, name="graph")
    if not isinstance(q, str):
        return []
    qq = q.strip().lower()
    out: list[dict] = []
    for name, rec in (graph.get("entities") or {}).items():
        if qq and qq not in name.lower():
            continue
        domains = rec.get("domains") or {}
        top_domains = [
            k for k, _ in sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        ]
        out.append({
            "name": name,
            "degree": int(rec.get("degree") or 0),
            "ep_mean": float((rec.get("ep_stats") or {}).get("mean") or 0.0),
            "top_domains": top_domains,
            "clusters": list(rec.get("clusters") or []),
        })
    out.sort(key=lambda r: (-r["degree"], r["name"]))
    return out[: max(1, int(limit))]


def get_entity(graph: dict, entity: str) -> Optional[dict]:
    """Return the raw entity record (or None). Used by the entity detail
    endpoint to render summary stats without forcing the client to walk
    the whole graph."""
    _validate_graph(graph, name="graph")
    name = _normalise_entity(entity or "")
    rec = (graph.get("entities") or {}).get(name)
    return dict(rec) if rec is not None else None


# ---------------------------------------------------------------------------
# Convenience: build_and_merge — used by the macro scheduler
# ---------------------------------------------------------------------------
def build_and_merge(
    existing: Optional[dict], new_runs: Iterable[dict],
) -> dict:
    """Build a delta graph from ``new_runs`` and merge into ``existing``.

    If ``existing`` is None, returns the delta as the new graph.
    Convenience for the macro scheduler integration.
    """
    delta = build_entity_graph(new_runs)
    if not existing:
        return delta
    return merge_entity_graph(existing, delta)
