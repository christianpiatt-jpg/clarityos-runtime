"""
elins_clustering.py — ELINS2 Unit 2.

Multi-run drift clustering. Groups stored runs by behavioural
similarity using hierarchical agglomerative clustering on top of the
ELINS2 Unit 1 similarity matrix, then assigns each cluster a
semantic drift label.

ROLE
----
Foundation for trend detection, anomaly detection, narrative
extraction, and intelligence dashboards. Clustering is purely
descriptive — it does not mutate runs, only inspects them.

ALGORITHM
---------
1. Load similarity matrix via ``elins_similarity.similarity_matrix``.
   Convert to distance: ``d = 1 - similarity`` (range [0, 1]).
2. Start with N singleton clusters, one per run_id.
3. Repeatedly merge the two closest clusters by AVERAGE LINKAGE — the
   pair whose mean pairwise distance is smallest. Ties are broken by
   the alphabetically-smaller representative pair (deterministic).
4. Stop when ``k`` clusters remain.
5. When ``k`` is omitted, sweep k from 2 to min(n-1, MAX_K) and pick
   the k with the highest silhouette score. With ties, prefer the
   smaller k (parsimony).

CLUSTER LABELS
--------------
For each cluster, sort members by ``metadata.created_at`` (Unit 23
ordering, legacy runs sort last). Run Unit 13's ``detect_drift`` over
the sequence. The cluster label is decided by the dominant pair-level
direction:

    "stable"          — majority of common pairs are stable
    "upward drift"    — majority are trending_up
    "downward drift"  — majority are trending_down
    "oscillation"    — majority are volatile
    "anomaly"         — cluster of size 1, or insufficient overlap

REPRESENTATIVE RUN
------------------
"Centroid" of each cluster = the medoid — the member with the
minimum sum of distances to the other members. With ties, the
alphabetically-smaller run_id wins.

I/O CONTRACT
------------
Loads runs once via ``similarity_matrix``; reloads them inside the
cluster-labeling step (Unit 13's ``detect_drift_for_run_ids``). No
logging, no network, no randomness.

PUBLIC API
----------
    cluster_runs(run_ids, k=None) -> dict
        Returns ``{
            "assignments":       {run_id: cluster_id},
            "cluster_summary":   {cluster_id: <summary dict>},
            "cluster_centroids": {cluster_id: <medoid run_id>},
            "silhouette":        float | None,
            "k":                 int,
        }``
"""
from __future__ import annotations

from elins_persistence import _validate_run_id, load_comparison_result
from elins_run_drift import detect_drift_for_run_ids
from elins_run_ordering import sort_run_ids_by_timestamp
from elins_similarity import similarity_matrix


# Maximum k to try when k is None. Above this the silhouette sweep
# becomes meaningless (clusters too small).
_MAX_K: int = 8

# Drift bucket → cluster label.
_DRIFT_LABEL_MAP: dict = {
    "stable":         "stable",
    "trending_up":    "upward drift",
    "trending_down":  "downward drift",
    "volatile":       "oscillation",
}

_LABEL_ANOMALY:    str = "anomaly"
_LABEL_STABLE:     str = "stable"
_DRIFT_BUCKETS:    tuple = (
    "stable", "trending_up", "trending_down", "volatile",
)


def _build_distance_matrix(run_ids: list) -> dict:
    """Build ``{(a, b): distance}`` from the similarity matrix. Distance
    is ``1 - similarity``."""
    sim = similarity_matrix(run_ids)
    return {key: 1.0 - val for key, val in sim.items()}


def _average_linkage(dist: dict, cluster_a: list, cluster_b: list) -> float:
    """Mean pairwise distance between two clusters of run_ids."""
    pairs = [
        dist[(a, b)] for a in cluster_a for b in cluster_b
    ]
    if not pairs:
        return 0.0
    return sum(pairs) / len(pairs)


def _agglomerate(run_ids: list, dist: dict, target_k: int) -> list:
    """Run hierarchical agglomerative clustering until `target_k`
    clusters remain. Returns list[list[run_id]] in deterministic order
    (alphabetical by first member)."""
    clusters: list = [[rid] for rid in sorted(run_ids)]
    while len(clusters) > target_k:
        best_pair = None
        best_dist = float("inf")
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = _average_linkage(dist, clusters[i], clusters[j])
                if d < best_dist or (
                    d == best_dist and best_pair is not None and (
                        clusters[i][0], clusters[j][0]
                    ) < (
                        clusters[best_pair[0]][0],
                        clusters[best_pair[1]][0],
                    )
                ):
                    best_dist = d
                    best_pair = (i, j)
        if best_pair is None:
            break
        i, j = best_pair
        merged = sorted(clusters[i] + clusters[j])
        clusters = (
            clusters[:i] + clusters[i + 1:j] + clusters[j + 1:] + [merged]
        )
        clusters.sort(key=lambda c: c[0])
    return clusters


def _silhouette_score(clusters: list, dist: dict) -> float:
    """Standard silhouette score over a clustering.

    Returns 0.0 if there's only one cluster or all clusters are
    singletons (no within-cluster distances to compare)."""
    if len(clusters) < 2:
        return 0.0
    # Map each point to its cluster index.
    point_to_cluster: dict = {}
    for idx, members in enumerate(clusters):
        for pid in members:
            point_to_cluster[pid] = idx
    all_points = list(point_to_cluster.keys())

    scores: list = []
    for p in all_points:
        same_cluster = [
            q for q in all_points
            if point_to_cluster[q] == point_to_cluster[p] and q != p
        ]
        if not same_cluster:
            scores.append(0.0)  # singleton → undefined
            continue
        a_p = sum(dist[(p, q)] for q in same_cluster) / len(same_cluster)

        b_p = float("inf")
        for other_idx, other_members in enumerate(clusters):
            if other_idx == point_to_cluster[p]:
                continue
            mean_d = sum(dist[(p, q)] for q in other_members) / len(other_members)
            if mean_d < b_p:
                b_p = mean_d
        if b_p == float("inf"):
            scores.append(0.0)
            continue
        denom = max(a_p, b_p)
        if denom == 0:
            scores.append(0.0)
            continue
        scores.append((b_p - a_p) / denom)
    return sum(scores) / len(scores) if scores else 0.0


def _pick_best_k(run_ids: list, dist: dict) -> tuple:
    """Sweep k from 2 to min(n-1, _MAX_K) and pick the k with the
    highest silhouette. Returns ``(best_k, best_clusters, best_score)``.
    Ties favour smaller k (parsimony)."""
    n = len(run_ids)
    max_k = min(n - 1, _MAX_K)
    if max_k < 2:
        return n, [[rid] for rid in sorted(run_ids)], 0.0

    best_k = 2
    best_clusters: list = []
    best_score = -float("inf")
    for k in range(2, max_k + 1):
        clusters = _agglomerate(run_ids, dist, k)
        score = _silhouette_score(clusters, dist)
        if score > best_score:
            best_score = score
            best_k = k
            best_clusters = clusters
    return best_k, best_clusters, best_score


def _medoid(cluster_members: list, dist: dict) -> str:
    """Member with minimum sum of distances to the other members. Tie
    broken alphabetically."""
    if len(cluster_members) == 1:
        return cluster_members[0]
    best_id = cluster_members[0]
    best_total = float("inf")
    for candidate in sorted(cluster_members):
        total = sum(
            dist[(candidate, other)]
            for other in cluster_members if other != candidate
        )
        if total < best_total:
            best_total = total
            best_id = candidate
    return best_id


def _cluster_label(members: list) -> str:
    """Assign a semantic drift label to a cluster.

    Singletons → "anomaly". Otherwise sort by timestamp, run Unit 13
    drift detection, take majority direction across common pairs.
    """
    if len(members) <= 1:
        return _LABEL_ANOMALY
    sorted_members = sort_run_ids_by_timestamp(list(members))
    if len(sorted_members) < 2:
        return _LABEL_ANOMALY
    direction = detect_drift_for_run_ids(sorted_members)

    counts = {
        bucket: len(direction.get(bucket, []))
        for bucket in _DRIFT_BUCKETS
    }
    total = sum(counts.values())
    if total == 0:
        # No common pairs across the cluster → can't classify behaviour.
        return _LABEL_ANOMALY
    winning_bucket = max(_DRIFT_BUCKETS, key=lambda b: (counts[b], b))
    return _DRIFT_LABEL_MAP.get(winning_bucket, _LABEL_STABLE)


def _cluster_id(idx: int) -> str:
    """Canonical cluster id format: ``c0``, ``c1``, ..."""
    return f"c{idx}"


def cluster_runs(run_ids: list, k=None) -> dict:
    """Cluster a set of stored runs.

    Args:
        run_ids: list of validated run identifiers. Must contain at
            least 1 entry.
        k: target number of clusters. When ``None`` (default), picked
            via silhouette sweep (k in 2..min(n-1, 8)).

    Returns:
        ``{
            "assignments":       {run_id: cluster_id},
            "cluster_summary":   {cluster_id: {
                "members": [...],
                "label":   "stable | upward drift | ...",
                "size":    int,
            }},
            "cluster_centroids": {cluster_id: medoid_run_id},
            "silhouette":        float | None,  # None if k explicit
            "k":                 int,
        }``

        Cluster ids are deterministic ``c0``, ``c1``, ... ordered by
        each cluster's alphabetically-smallest member.

    Raises:
        ValueError if `run_ids` is malformed, empty, or k is invalid.
        FileNotFoundError if any run does not exist.
    """
    if not isinstance(run_ids, list):
        raise ValueError(
            f"cluster_runs expected a list, got {type(run_ids).__name__}"
        )
    if len(run_ids) < 1:
        raise ValueError("cluster_runs requires >= 1 run_id, got 0")
    for rid in run_ids:
        _validate_run_id(rid)
    if k is not None:
        if isinstance(k, bool) or not isinstance(k, int):
            raise ValueError(
                f"k must be a positive int or None, got {type(k).__name__}"
            )
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        if k > len(run_ids):
            raise ValueError(
                f"k cannot exceed len(run_ids); got k={k}, n={len(run_ids)}"
            )

    deduped = list(dict.fromkeys(run_ids))
    n = len(deduped)

    if n == 1:
        rid = deduped[0]
        # Verify the run exists — multi-run path catches this via
        # similarity_matrix, but the single-run short-circuit would
        # otherwise silently accept a ghost id.
        load_comparison_result(rid)
        return {
            "assignments":       {rid: _cluster_id(0)},
            "cluster_summary":   {
                _cluster_id(0): {
                    "members": [rid],
                    "label":   _LABEL_ANOMALY,
                    "size":    1,
                },
            },
            "cluster_centroids": {_cluster_id(0): rid},
            "silhouette":        None,
            "k":                 1,
        }

    dist = _build_distance_matrix(deduped)

    if k is None:
        chosen_k, clusters, silhouette = _pick_best_k(deduped, dist)
    else:
        clusters = _agglomerate(deduped, dist, k)
        chosen_k = k
        silhouette = (
            _silhouette_score(clusters, dist) if k >= 2 else None
        )

    # Deterministic cluster id order: clusters sorted by smallest member.
    clusters_sorted = sorted(clusters, key=lambda c: c[0])

    assignments: dict = {}
    summary:     dict = {}
    centroids:   dict = {}
    for idx, members in enumerate(clusters_sorted):
        cid = _cluster_id(idx)
        for m in members:
            assignments[m] = cid
        summary[cid] = {
            "members": sorted(members),
            "label":   _cluster_label(members),
            "size":    len(members),
        }
        centroids[cid] = _medoid(members, dist)

    return {
        "assignments":       assignments,
        "cluster_summary":   summary,
        "cluster_centroids": centroids,
        "silhouette":        silhouette,
        "k":                 chosen_k,
    }
