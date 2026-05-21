"""
elins_intelligence.py — ELINS2 Unit 9.

Composite intelligence surface. Single function that orchestrates every
ELINS2 primitive (Units 1-8) into one structured payload — used by the
``POST /elins/regression/runs/intelligence`` endpoint (Unit 10) and the
dashboard projection.

ROLE
----
Pure orchestrator. No new heuristics, no mutation, no logging. Every
sub-section delegates to an existing unit and surfaces its output
verbatim. Same inputs always produce byte-equal output.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "run_ids":   [...],
      "similarity": {
        "matrix": {run_a: {run_a: 1.0, run_b: 0.83, ...}, ...},
        "top_k":  {run_a: [(run_b, 0.83), ...], ...},
      },
      "clustering": {
        "assignments":       {run_a: "c0", ...},
        "cluster_summary":   {"c0": {...}, ...},
        "cluster_centroids": {"c0": medoid_id, ...},
        "silhouette":        float | null,
        "k":                 int,
      },
      "trends": {
        "sequence": {trend, slope, volatility, score, run_ids},
        "pairs":    {pair_id: {...}, ...},
      },
      "anomalies": {
        "runs":       {run_id: {score, level, reasons}, ...},
        "thresholds": {high, medium},
      },
      "scores": {
        "runs":           {run_id: {...}, ...},
        "pairs":          {pair_id: {...}, ...},
        "overall_health": float,
      },
      "narratives": {
        "runs":      {headline, bullets, details},
        "anomalies": {headline, bullets, details},
        "sequence":  {headline, bullets, details},
      },
      "sequences": {
        "analysis": {trend, overall_health, anomaly_fraction,
                     upward_fraction, downward_fraction,
                     stable_cluster_fraction},
        "best":     {run_ids, overall_health, trend, anomaly_fraction} | null,
        "worst":    {run_ids, overall_health, trend, anomaly_fraction} | null,
      },
    }

``best`` and ``worst`` are ``None`` whenever the input is smaller than
the default window (5). All other sections are always present with
well-formed empty-shape responses.

PUBLIC API
----------
    intelligence_for_run_ids(run_ids: list[str]) -> dict
"""
from __future__ import annotations

from elins_anomalies import detect_run_anomalies
from elins_clustering import cluster_runs
from elins_intelligence_cache import (
    DEFAULT_TTL_SECONDS,
    get_cached_intelligence,
    store_intelligence,
)
from elins_multi_summary import multi_run_summary
from elins_narratives import (
    summarize_anomalies,
    summarize_runs,
)
from elins_persistence import _validate_run_id, load_comparison_result
from elins_scoring import (
    compute_pair_scores,
    compute_run_scores,
    overall_health_score,
)
from elins_sequences import (
    _DEFAULT_WINDOW,
    analyze_sequence,
    best_sequence,
    worst_sequence,
)
from elins_similarity import similarity_matrix, top_k_similar_runs
from elins_trends import trend_for_run_sequence


# Default top-k for the per-run similarity neighbours.
_TOP_K_DEFAULT: int = 5

# Module-level toggle for the Unit 11 cache. Tests that want to exercise
# the raw orchestrator path without persistence side effects set this to
# False via monkeypatch. Production stays on (the default).
_CACHE_ENABLED: bool = True


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"intelligence_for_run_ids expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _ensure_runs_exist(run_ids: list) -> None:
    """Bail early with a clean FileNotFoundError if any run is missing.
    Without this, downstream callers (similarity_matrix, cluster_runs,
    ...) raise at varying points — the endpoint layer then maps to
    404, but the message is clearer when checked here once."""
    for rid in run_ids:
        load_comparison_result(rid)  # raises FileNotFoundError on miss


def _matrix_as_nested(run_ids: list, matrix: dict) -> dict:
    """Convert the tuple-keyed similarity matrix into a nested dict
    keyed by run_id for JSON serialisation."""
    out: dict = {}
    for a in run_ids:
        out[a] = {}
        for b in run_ids:
            out[a][b] = matrix.get((a, b), 0.0)
    return out


def _empty_similarity_section(run_ids: list) -> dict:
    """Section shape for empty / single-run input — matrix has a
    single self-entry, top_k is empty."""
    return {
        "matrix": {rid: {rid: 1.0} for rid in run_ids},
        "top_k":  {rid: [] for rid in run_ids},
    }


def _empty_clustering_section() -> dict:
    return {
        "assignments":       {},
        "cluster_summary":   {},
        "cluster_centroids": {},
        "silhouette":        None,
        "k":                 0,
    }


def _empty_trends_section(run_ids: list) -> dict:
    return {
        "sequence": {
            "trend":      "insufficient_data",
            "slope":      0.0,
            "volatility": 0.0,
            "score":      0.0,
            "run_ids":    list(run_ids),
        },
        "pairs": {},
    }


def _empty_anomalies_section() -> dict:
    return {
        "runs":       {},
        "thresholds": {"high": 0.7, "medium": 0.4},
    }


def _empty_scores_section() -> dict:
    return {
        "runs":           {},
        "pairs":          {},
        "overall_health": 0.0,
    }


def _build_similarity_section(run_ids: list) -> dict:
    """Compute pairwise similarity + top-k neighbours.

    Top-k entries are emitted as ``[other_run_id, similarity]`` lists
    rather than tuples so the fresh-compute output matches the cached
    (JSON-roundtripped) version byte-for-byte — see Unit 11.
    """
    if not run_ids:
        return _empty_similarity_section(run_ids)
    matrix = similarity_matrix(run_ids)
    nested = _matrix_as_nested(run_ids, matrix)
    top_k: dict = {}
    n = len(run_ids)
    # Cap the k to (n - 1) so the call never raises on tiny inputs.
    k = min(_TOP_K_DEFAULT, max(n - 1, 0))
    for rid in run_ids:
        if k == 0:
            top_k[rid] = []
        else:
            raw = top_k_similar_runs(rid, k=k)
            top_k[rid] = [[other, sim] for other, sim in raw]
    return {"matrix": nested, "top_k": top_k}


def _build_clustering_section(run_ids: list) -> dict:
    if not run_ids:
        return _empty_clustering_section()
    return cluster_runs(run_ids)


def _build_trends_section(run_ids: list) -> dict:
    if not run_ids:
        return _empty_trends_section(run_ids)
    sequence = trend_for_run_sequence(run_ids)
    pairs = multi_run_summary(run_ids)["pair_summaries"]
    return {"sequence": sequence, "pairs": pairs}


def _build_anomalies_section(run_ids: list) -> dict:
    if not run_ids:
        return _empty_anomalies_section()
    return detect_run_anomalies(run_ids)


def _build_scores_section(run_ids: list) -> dict:
    if not run_ids:
        return _empty_scores_section()
    return {
        "runs":           compute_run_scores(run_ids)["runs"],
        "pairs":          compute_pair_scores(run_ids)["pairs"],
        "overall_health": overall_health_score(run_ids),
    }


def _build_narratives_section(run_ids: list) -> dict:
    """Three narrative panes: runs, anomalies, sequence. Each carries
    the Unit 7 ``{headline, bullets, details}`` shape."""
    runs_narrative      = summarize_runs(run_ids)
    anomalies_narrative = summarize_anomalies(run_ids)
    # Sequence narrative is the per-sequence analysis dressed up
    # with a headline + bullets so callers can render it next to the
    # other two without consulting `sequences.analysis` directly.
    analysis = analyze_sequence(run_ids)
    sequence_narrative = _narrative_from_analysis(run_ids, analysis)
    return {
        "runs":      runs_narrative,
        "anomalies": anomalies_narrative,
        "sequence":  sequence_narrative,
    }


def _narrative_from_analysis(run_ids: list, analysis: dict) -> dict:
    """Dress the analyze_sequence reading in the Unit 7 narrative shape.
    Headlines mirror the trend / health pairing used in
    ``elins_narratives``."""
    num_runs = len(run_ids)
    trend = analysis.get("trend", "insufficient_data")
    health = float(analysis.get("overall_health", 0.0))

    if num_runs == 0:
        return {
            "headline": "No runs available to analyse.",
            "bullets": ["Run count is zero — no signals to report."],
            "details": dict(analysis),
        }

    headline = f"Sequence of {num_runs} runs has trend {trend!r} (health {health:.2f})."
    bullets = [
        f"Overall health: {health:.2f}.",
        f"Trend class: {trend}.",
        (
            f"Anomaly fraction: "
            f"{float(analysis.get('anomaly_fraction', 0.0)):.2f}."
        ),
        (
            f"Upward pairs: "
            f"{float(analysis.get('upward_fraction', 0.0)):.2f}; "
            f"downward pairs: "
            f"{float(analysis.get('downward_fraction', 0.0)):.2f}."
        ),
        (
            f"Stable-cluster fraction: "
            f"{float(analysis.get('stable_cluster_fraction', 0.0)):.2f}."
        ),
    ]
    return {
        "headline": headline,
        "bullets":  bullets,
        "details":  dict(analysis),
    }


def _build_sequences_section(run_ids: list) -> dict:
    """analyze_sequence + best/worst windows. Best/worst collapse to
    ``None`` whenever ``len(run_ids) < _DEFAULT_WINDOW`` so the caller
    doesn't have to special-case tiny inputs."""
    analysis = analyze_sequence(run_ids)
    if len(run_ids) >= _DEFAULT_WINDOW:
        best  = best_sequence(run_ids,  window=_DEFAULT_WINDOW)
        worst = worst_sequence(run_ids, window=_DEFAULT_WINDOW)
    else:
        best, worst = None, None
    return {
        "analysis": analysis,
        "best":     best,
        "worst":    worst,
    }


def intelligence_for_run_ids(run_ids) -> dict:
    """Compose every ELINS2 unit into a single intelligence payload.

    Args:
        run_ids: chronologically-ordered run identifiers. Caller is
            responsible for ordering — use
            ``elins_run_ordering.sort_run_ids_by_timestamp`` if needed.

    Returns:
        Locked-shape dict — see module docstring for the full key
        schema. Every top-level key is always present; sub-sections
        carry well-formed empty defaults for tiny inputs.

    Raises:
        ValueError if ``run_ids`` is not a list or contains a malformed
            id.
        FileNotFoundError if any run does not exist.
    """
    _validate_run_ids(run_ids)
    _ensure_runs_exist(run_ids)

    # Unit 11: cache lookup. Empty input still benefits — the empty
    # payload is identical across calls. Skipped entirely when the
    # module-level toggle is off.
    if _CACHE_ENABLED:
        cached = get_cached_intelligence(run_ids)
        if cached is not None:
            return cached

    payload = {
        "run_ids":    list(run_ids),
        "similarity": _build_similarity_section(run_ids),
        "clustering": _build_clustering_section(run_ids),
        "trends":     _build_trends_section(run_ids),
        "anomalies":  _build_anomalies_section(run_ids),
        "scores":     _build_scores_section(run_ids),
        "narratives": _build_narratives_section(run_ids),
        "sequences":  _build_sequences_section(run_ids),
    }

    if _CACHE_ENABLED:
        store_intelligence(run_ids, payload, ttl_seconds=DEFAULT_TTL_SECONDS)

    return payload
