"""
elins_similarity.py — ELINS2 Unit 1.

Run-to-run similarity engine. Quantifies how close any two stored runs
are on a [0, 1] scale, where 1.0 = identical and values near 0 mean
maximally different.

ROLE
----
Foundational primitive for ELINS2 — clustering (Unit 2), anomaly
detection, narrative extraction, and intelligence dashboards all
consume similarity scores produced here.

FEATURE EXTRACTION
------------------
For each run, ``_extract_features`` pulls a deterministic feature
dictionary from the loaded envelope:

    * ``pair_ids``:    set of pair_ids present in the run
    * ``scores``:      {pair_id: (sp_score, ec_score)}
    * ``bands``:       {pair_id: (sp_band, ec_band)} (numeric encoded)
    * ``summary``:     Unit 14 summary_table output
    * ``source``:      metadata source tag (Unit 19)
    * ``evidence_dir``: metadata evidence dir (Unit 19)
    * ``is_legacy``:   True iff metadata is None (Unit 10 file format)

DISTANCE FORMULA
----------------
::

    distance =
        W1 * drift_magnitude_dist   (L2 over aligned scores)
      + W2 * drift_direction_dist   (L1 over aligned band numbers)
      + W3 * severity_diff          (|mean score| differences)
      + W4 * summary_table_diff     (L1 over band-count distributions)
      + W5 * pair_overlap_penalty   (1 - Jaccard of pair-id sets)
      + W6 * metadata_penalty       (source / evidence_dir mismatch)

    similarity = 1.0 / (1.0 + distance)

Each component is normalised to roughly [0, 1] so the weights are
directly interpretable. Legacy runs (``is_legacy=True``) short-circuit
to similarity = 0.0 (the spec's "Legacy runs → similarity = 0" rule).

I/O CONTRACT
------------
``compute_similarity`` / ``top_k_similar_runs`` / ``similarity_matrix``
load runs via the persistence layer. The inner extraction + distance
math is fully pure (no I/O, no logging).

PUBLIC API
----------
    compute_similarity(run_id_a, run_id_b) -> float
    top_k_similar_runs(run_id, k=5) -> list[tuple[str, float]]
    similarity_matrix(run_ids) -> dict[tuple[str, str], float]
"""
from __future__ import annotations

import math

from elins_persistence import (
    _validate_run_id,
    list_runs,
    load_comparison_result,
)
from elins_run_summary import summary_table


# ---- Locked module constants ----------------------------------------------
# Component weights. Sum doesn't need to be 1.0 — the 1/(1+distance)
# transform makes the absolute scale interpretable as "smaller distance
# → higher similarity".
_W_DRIFT_MAGNITUDE: float = 0.30
_W_DRIFT_DIRECTION: float = 0.20
_W_SEVERITY:        float = 0.15
_W_SUMMARY:         float = 0.15
_W_PAIR_OVERLAP:    float = 0.15
_W_METADATA:        float = 0.05

# Score domain: ELINS uses 0-10 integer scores.
_MAX_SCORE: float = 10.0

# Band → numeric encoding for L1 direction distance. "Strong" is the
# best, "Fails core logic" the worst. Missing/unknown bands map to 0
# (treated as worse than Fails).
_BAND_NUMERIC: dict = {
    "Strong":           4,
    "Acceptable":       3,
    "Weak":             2,
    "Fails core logic": 1,
    "Fails":            1,  # alias for Unit 14 short form
}
_MAX_BAND_NUMERIC: int = 4


def _extract_features(run_payload, metadata) -> dict:
    """Pure feature extraction from an already-loaded run.

    Args:
        run_payload: the inner ``result`` list of pair dicts.
        metadata: the envelope's metadata dict (or ``None`` for legacy).

    Returns:
        Feature dict consumed by ``_distance``.
    """
    is_legacy = metadata is None or not isinstance(metadata, dict)

    pair_ids: set = set()
    scores:   dict = {}
    bands:    dict = {}
    if isinstance(run_payload, list):
        for entry in run_payload:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("pair_id")
            if not isinstance(pid, str):
                continue
            sp_score = entry.get("single_party_score")
            ec_score = entry.get("economic_coercion_score")
            sp_band  = entry.get("single_party_band")
            ec_band  = entry.get("economic_coercion_band")
            pair_ids.add(pid)
            scores[pid] = (
                float(sp_score) if isinstance(sp_score, (int, float))
                and not isinstance(sp_score, bool) else 0.0,
                float(ec_score) if isinstance(ec_score, (int, float))
                and not isinstance(ec_score, bool) else 0.0,
            )
            bands[pid] = (
                _BAND_NUMERIC.get(sp_band, 0),
                _BAND_NUMERIC.get(ec_band, 0),
            )

    return {
        "is_legacy":    is_legacy,
        "pair_ids":     pair_ids,
        "scores":       scores,
        "bands":        bands,
        "summary":      summary_table(run_payload) if isinstance(run_payload, list) else None,
        "source":       (metadata or {}).get("source") if isinstance(metadata, dict) else None,
        "evidence_dir": (metadata or {}).get("evidence_dir") if isinstance(metadata, dict) else None,
    }


def _drift_magnitude_distance(a: dict, b: dict) -> float:
    """L2 distance over aligned (sp_score, ec_score) vectors. Pairs in
    only one run contribute as ``(0, 0)`` to the other side (treated as
    "absence")."""
    union = a["pair_ids"] | b["pair_ids"]
    if not union:
        return 0.0
    sse = 0.0
    for pid in union:
        a_sp, a_ec = a["scores"].get(pid, (0.0, 0.0))
        b_sp, b_ec = b["scores"].get(pid, (0.0, 0.0))
        sse += (a_sp - b_sp) ** 2 + (a_ec - b_ec) ** 2
    # Normalise by the maximum possible L2 over this union: each pair
    # could differ by 2 * MAX_SCORE^2 (sp + ec dimensions).
    max_sse = 2.0 * (_MAX_SCORE ** 2) * len(union)
    return math.sqrt(sse / max_sse) if max_sse > 0 else 0.0


def _drift_direction_distance(a: dict, b: dict) -> float:
    """L1 distance over aligned numeric band vectors. Pairs in only one
    run contribute as band-number 0 to the other side."""
    union = a["pair_ids"] | b["pair_ids"]
    if not union:
        return 0.0
    total = 0
    for pid in union:
        a_sp, a_ec = a["bands"].get(pid, (0, 0))
        b_sp, b_ec = b["bands"].get(pid, (0, 0))
        total += abs(a_sp - b_sp) + abs(a_ec - b_ec)
    # Maximum L1 over this union: each pair could differ by
    # 2 * _MAX_BAND_NUMERIC.
    max_total = 2 * _MAX_BAND_NUMERIC * len(union)
    return total / max_total if max_total > 0 else 0.0


def _severity_distance(a: dict, b: dict) -> float:
    """Absolute differences in mean scores per dimension, normalised."""
    if not a["summary"] or not b["summary"]:
        return 0.0
    diff = 0.0
    for dim in ("single_party_scores", "economic_coercion_scores"):
        a_mean = a["summary"][dim].get("mean") or 0.0
        b_mean = b["summary"][dim].get("mean") or 0.0
        diff += abs(a_mean - b_mean)
    return min(diff / (2.0 * _MAX_SCORE), 1.0)


def _summary_table_distance(a: dict, b: dict) -> float:
    """L1 distance over per-band counts in both dimensions, normalised
    by 2 * max(total_pairs)."""
    if not a["summary"] or not b["summary"]:
        return 0.0
    a_sum = a["summary"]
    b_sum = b["summary"]
    total = 0
    for dim in ("single_party_bands", "economic_coercion_bands"):
        for band in ("Strong", "Acceptable", "Weak", "Fails"):
            total += abs(a_sum[dim][band] - b_sum[dim][band])
    n = max(a_sum["total_pairs"], b_sum["total_pairs"], 1)
    return min(total / (2 * n), 1.0)


def _pair_overlap_penalty(a: dict, b: dict) -> float:
    """1 - Jaccard similarity over pair-id sets. 0 when fully
    overlapping, 1 when disjoint."""
    a_set = a["pair_ids"]
    b_set = b["pair_ids"]
    if not a_set and not b_set:
        return 0.0
    union = a_set | b_set
    inter = a_set & b_set
    if not union:
        return 0.0
    return 1.0 - (len(inter) / len(union))


def _metadata_penalty(a: dict, b: dict) -> float:
    """Penalty in [0, 1] for metadata mismatches.

    Two halves: source equality and evidence_dir equality. Each
    mismatch contributes 0.5. Both matching → 0.0; both differing →
    1.0.
    """
    penalty = 0.0
    if a["source"] != b["source"]:
        penalty += 0.5
    if a["evidence_dir"] != b["evidence_dir"]:
        penalty += 0.5
    return penalty


def _distance(a: dict, b: dict) -> float:
    """Composite weighted distance. Returns ``float("inf")`` if either
    side is legacy (so similarity collapses to 0)."""
    if a["is_legacy"] or b["is_legacy"]:
        return float("inf")
    return (
        _W_DRIFT_MAGNITUDE * _drift_magnitude_distance(a, b)
        + _W_DRIFT_DIRECTION * _drift_direction_distance(a, b)
        + _W_SEVERITY        * _severity_distance(a, b)
        + _W_SUMMARY         * _summary_table_distance(a, b)
        + _W_PAIR_OVERLAP    * _pair_overlap_penalty(a, b)
        + _W_METADATA        * _metadata_penalty(a, b)
    )


def _similarity_from_distance(distance: float) -> float:
    """Map distance to [0, 1] similarity. Infinity → 0 (legacy guard)."""
    if math.isinf(distance):
        return 0.0
    return 1.0 / (1.0 + distance)


def _features_for_run(run_id: str) -> dict:
    """Load a run by id and return its extracted features. Centralises
    the load + extract pattern used by all public callers."""
    envelope = load_comparison_result(run_id)
    return _extract_features(envelope.get("result"), envelope.get("metadata"))


def compute_similarity(run_id_a: str, run_id_b: str) -> float:
    """Compute the similarity score between two stored runs.

    Args:
        run_id_a, run_id_b: validated run identifiers.

    Returns:
        Similarity ∈ [0, 1]. Identical runs yield 1.0; legacy runs
        always yield 0.0.

    Raises:
        ValueError on a malformed run_id.
        FileNotFoundError if either run does not exist.
    """
    _validate_run_id(run_id_a)
    _validate_run_id(run_id_b)
    if run_id_a == run_id_b:
        # Optimisation + correctness lock: same id is always identical.
        feats = _features_for_run(run_id_a)
        if feats["is_legacy"]:
            return 0.0
        return 1.0
    return _similarity_from_distance(_distance(
        _features_for_run(run_id_a), _features_for_run(run_id_b),
    ))


def top_k_similar_runs(run_id: str, k: int = 5) -> list:
    """Return the top-k most similar runs to `run_id`, sorted by score
    descending. Ties broken alphabetically by run_id.

    Args:
        run_id: validated identifier of the target run.
        k: maximum number of results (>= 1). Default 5.

    Returns:
        list[tuple[str, float]] — (other_run_id, similarity) pairs.
        Empty list if no other runs exist. ``run_id`` itself is
        excluded from the result.

    Raises:
        ValueError on a malformed run_id or non-positive k.
        FileNotFoundError if `run_id` does not exist.
    """
    _validate_run_id(run_id)
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError(f"k must be a positive int, got {type(k).__name__}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    target = _features_for_run(run_id)
    scores: list = []
    for other in list_runs():
        if other == run_id:
            continue
        try:
            other_feats = _features_for_run(other)
        except FileNotFoundError:
            continue  # race: deleted between list and load
        sim = _similarity_from_distance(_distance(target, other_feats))
        scores.append((other, sim))
    scores.sort(key=lambda x: (-x[1], x[0]))
    return scores[:k]


def similarity_matrix(run_ids: list) -> dict:
    """Build a full pairwise similarity matrix as a dict keyed by
    ``(run_id_a, run_id_b)`` tuples.

    Args:
        run_ids: list of validated run identifiers.

    Returns:
        dict[tuple[str, str], float] containing every ordered pair
        (including diagonal). ``matrix[(a, a)] == 1.0`` and
        ``matrix[(a, b)] == matrix[(b, a)]``.

    Raises:
        ValueError if `run_ids` is not a list, or contains a malformed
            id.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"similarity_matrix expected a list, "
            f"got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)

    feats_by_id: dict = {rid: _features_for_run(rid) for rid in run_ids}

    matrix: dict = {}
    for a in run_ids:
        for b in run_ids:
            if a == b:
                matrix[(a, b)] = 0.0 if feats_by_id[a]["is_legacy"] else 1.0
                continue
            # Symmetric: compute once per unordered pair, fill both
            # cells.
            if (b, a) in matrix:
                matrix[(a, b)] = matrix[(b, a)]
                continue
            sim = _similarity_from_distance(_distance(
                feats_by_id[a], feats_by_id[b],
            ))
            matrix[(a, b)] = sim
    return matrix
