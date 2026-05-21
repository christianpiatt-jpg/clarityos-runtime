"""
DEWEY v2 — manifold math.

This module replaces the v1 stubs with the spec's geometric definitions:
similarity is cosine in normalized embedding space, distance = 1 - similarity,
λ-window is a [min, max] range, domain filter operates on `filters.domains`,
basin gating uses `similarity_threshold` (default 0.3 if missing).

Embedding source
----------------
The spec says to "call the existing model you already use for ELINS text
embeddings." No such model is wired into this codebase yet, so `embed_text`
falls back to a deterministic hash-based pseudo-embedding (32-dim, normalized).
The fallback keeps the pipeline runnable end-to-end; it is NOT semantically
meaningful — cosine similarity between hash vectors is essentially random.

When a real embedding source is chosen (Vertex AI text-embedding,
OpenAI text-embedding-3, sentence-transformers, etc.), replace the body
of `_real_embed(text)` only. The rest of this module — and the worker —
work unchanged.

Public API:
    embed_text(text)                            -> list[float]
    embed_object(obj)                           -> list[float]
    similarity(a, b)                            -> float in [-1, 1]
    geodesic_distance(a, b)                     -> float in [0, 2]
    directional_alignment(obj_vec, origin_vec)  -> float in [-1, 1]
    λ_compatibility(λ_value, λ_window)          -> bool
    domain_filter(obj_domains, filter_domains)  -> bool
    extract_lambda(obj)                         -> float | None
    extract_domains(obj)                        -> list[str]
    is_within_basin(obj, neighborhood)          -> tuple[bool, float]
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import random
import threading
import time
from typing import Any, Optional

import embeddings_cache_store

logger = logging.getLogger("clarityos.dewey_pipeline")

# Fallback dimensionality when Vertex is unreachable. Math doesn't care
# about exact dim as long as embed_text returns the same dim per call.
_FALLBACK_DIM = 32
_EPS = 1e-9

# Vertex AI config
_VERTEX_LOCATION = os.environ.get("CLARITYOS_VERTEX_LOCATION", "us-central1")
_VERTEX_MODEL_NAME = os.environ.get("CLARITYOS_VERTEX_EMBED_MODEL", "text-embedding-005")


# ---------------------------------------------------------------------------
# Vertex AI text-embedding-005
#
# Lazy module-level init. We don't retry init failures within a revision —
# if the API isn't enabled or IAM isn't granted, the symptom is durable
# until the next deploy. On every cold start we get one init attempt; on
# every text we get one model call (no caching per spec — DEWEY v3).
# ---------------------------------------------------------------------------
_vertex_lock = threading.Lock()
_vertex_state: dict = {"initialized": False, "model": None, "error": None}


def _init_vertex_once():
    if _vertex_state["initialized"]:
        return _vertex_state["model"]
    with _vertex_lock:
        if _vertex_state["initialized"]:
            return _vertex_state["model"]
        try:
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if not project:
                import google.auth  # type: ignore
                _, project = google.auth.default()
            if not project:
                _vertex_state["error"] = "no project id available"
                logger.warning("dewey_pipeline vertex init: no project id; falling back")
                _vertex_state["initialized"] = True
                return None
            import vertexai  # type: ignore
            from vertexai.language_models import TextEmbeddingModel  # type: ignore
            vertexai.init(project=project, location=_VERTEX_LOCATION)
            _vertex_state["model"] = TextEmbeddingModel.from_pretrained(_VERTEX_MODEL_NAME)
            logger.info(
                "dewey_pipeline vertex initialised project=%s location=%s model=%s",
                project, _VERTEX_LOCATION, _VERTEX_MODEL_NAME,
            )
        except Exception as e:
            _vertex_state["error"] = str(e)
            logger.warning(
                "dewey_pipeline vertex init failed: %s — using hash fallback", e,
            )
        finally:
            _vertex_state["initialized"] = True
    return _vertex_state["model"]


def _real_embed(text: str) -> Optional[list[float]]:
    """Vertex AI text-embedding-005. Returns an L2-normalized vector, or
    None on any failure (caller falls back to the deterministic hash embed).

    DEWEY must remain non-failing — every error path returns None instead
    of raising. The caller in `embed_text` substitutes the hash fallback
    transparently."""
    if not text:
        return None
    model = _init_vertex_once()
    if model is None:
        return None
    try:
        results = model.get_embeddings([text])
        vec = list(results[0].values)
    except Exception as e:
        logger.warning("dewey_pipeline vertex call failed: %s", e)
        return None
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-12:
        return None
    return [x / norm for x in vec]


def _fallback_embed(text: str) -> list[float]:
    """Deterministic hash-based pseudo-embedding. NOT semantic — only
    keeps the pipeline runnable when no real embedder is wired."""
    if not text:
        text = ""
    out: list[float] = []
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    while len(out) < _FALLBACK_DIM:
        for b in digest:
            out.append((b / 255.0) * 2.0 - 1.0)
            if len(out) == _FALLBACK_DIM:
                break
        digest = hashlib.sha256(digest).digest()
    return out


def _normalize(vec: list[float]) -> list[float]:
    """L2-normalize. Returns a zero vector of the same length if ||v||
    is below eps (rather than raising or returning NaN)."""
    if not vec:
        return []
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < _EPS:
        return [0.0] * len(vec)
    return [x / norm for x in vec]


def embed_text(text: str) -> list[float]:
    """Embed text into a normalized vector. Tries the real embedder; if
    that returns None, uses the hash-based fallback. Always L2-normalized.

    NOTE: this is the v2 entry point — bypasses the Firestore cache. Use
    `embed_text_cached` for the v3 cache-aware path. `embed_text` remains
    in place because `dewey_neighborhoods_store` writes the origin_vector
    once at neighborhood-create time and there's no value in caching that
    one-shot call (the query text rarely repeats across neighborhoods)."""
    text = text or ""
    raw = _real_embed(text)
    if raw is None:
        raw = _fallback_embed(text)
    return _normalize(list(raw))


def embed_text_cached(text: str) -> Optional[list[float]]:
    """v3 cache-aware embed. Returns None if text is empty (per spec).

    Lookup order:
      1. sha256(text) → embeddings_cache (Firestore)
      2. miss → _real_embed (Vertex) → normalize → cache → return
      3. real failed → hash fallback → normalize → cache → return

    All paths return L2-normalized vectors. Cache writes are best-effort:
    failures are logged but not raised."""
    if not text:
        return None
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()

    cached = embeddings_cache_store.get(key)
    if cached is not None:
        logger.info("dewey_pipeline cache_hit key=%s", key[:12])
        return cached

    logger.info("dewey_pipeline cache_miss key=%s", key[:12])
    raw = _real_embed(text)
    used_fallback = False
    if raw is None:
        raw = _fallback_embed(text)
        used_fallback = True
    vec = _normalize(list(raw))

    embeddings_cache_store.put(key, vec, time.time())
    logger.info(
        "dewey_pipeline cache_stored key=%s source=%s dim=%d",
        key[:12], "fallback" if used_fallback else "vertex", len(vec),
    )
    return vec


# ---------------------------------------------------------------------------
# Object-to-text dispatch (per v2 spec)
# ---------------------------------------------------------------------------
def embed_object(obj: dict) -> list[float]:
    """v3: routes through the Firestore embedding cache. For empty object
    text we return a deterministic zero-fallback vector so downstream
    similarity math is defined (it just won't match anything semantic)."""
    text = _object_text(obj)
    v = embed_text_cached(text) if text else None
    if v is None:
        v = _normalize(_fallback_embed(text or ""))
    return v


def _object_text(obj: dict) -> str:
    """Pick the canonical text per object kind per v2 spec.

    - ELINS primitive (kind=elins.primitive): primitive.summary
    - ELINS brief (kind=elins.brief): brief.summary or brief.body
    - Vault / Library: title + "\\n\\n" + content
    - Timeline (generic): summary if present, else content
    """
    kind = obj.get("kind", "")
    if kind == "elins.primitive":
        # v2 spec: embed primitive.summary. The ingestion route stuffs the
        # primitive dict into event.data, so the primitive's own summary is
        # at data.summary, not the synthetic event.summary (which the route
        # sets to primitive.name as a display label).
        data = obj.get("data") or {}
        return (
            data.get("summary")
            or obj.get("summary")
            or data.get("name")
            or data.get("label")
            or ""
        )
    if kind == "elins.brief":
        data = obj.get("data") or {}
        return obj.get("summary") or data.get("body") or data.get("content") or ""
    # Vault items have `type`; library items have `title` + `content` and no `type`.
    if "type" in obj or ("title" in obj and "content" in obj):
        title = obj.get("title") or ""
        content = obj.get("content") or ""
        if title and content:
            return f"{title}\n\n{content}"
        return title or content
    # Generic timeline events
    if obj.get("summary"):
        return obj["summary"]
    if obj.get("content"):
        return obj["content"]
    return ""


# ---------------------------------------------------------------------------
# Similarity / distance / alignment
# ---------------------------------------------------------------------------
def similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]. Vectors are assumed L2-normalized,
    so this is just the dot product. Result is clamped for numeric safety."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))


def geodesic_distance(a: list[float], b: list[float]) -> float:
    """Distance in [0, 2]. Per v2 spec: distance = 1 - similarity.
    Monotone in similarity, so callers can threshold either."""
    return 1.0 - similarity(a, b)


def directional_alignment(obj_vec: list[float], origin_vec: list[float]) -> float:
    """For DEWEY v2: alignment ≡ cosine similarity between origin and
    object. (Real EP-direction projection lands when primitive direction
    vectors are available; for now this is just similarity.)"""
    return similarity(obj_vec, origin_vec)


# ---------------------------------------------------------------------------
# λ-window and domain filter
# ---------------------------------------------------------------------------
def extract_lambda(obj: dict) -> Optional[float]:
    """Pull λ from a primitive's data payload, if present.

    For non-primitives, returns None (so they pass λ-window checks per
    spec — non-primitive objects are not excluded by missing λ)."""
    if obj.get("kind") == "elins.primitive":
        data = obj.get("data") or {}
        for key in ("λ", "lambda", "lambda_value", "decay"):
            if key in data:
                try:
                    return float(data[key])
                except (TypeError, ValueError):
                    pass
    for key in ("λ", "lambda"):
        if key in obj:
            try:
                return float(obj[key])
            except (TypeError, ValueError):
                pass
    return None


def λ_compatibility(λ_value: Optional[float], λ_window: Any) -> bool:  # noqa: PLC2401
    """v2 λ-window is an optional [λ_min, λ_max] range stored on the
    neighborhood. Truth table per spec:

        neighborhood λ_window  | object λ      | result
        ----------------------|---------------|--------
        unset / None / []     | any           | True
        [min, max]            | None          | True   (don't exclude non-primitives)
        [min, max]            | min ≤ λ ≤ max | True
        [min, max]            | otherwise     | False

    A v1 scalar λ_window has no v2 semantics — treat as unset."""
    if not λ_window:
        return True
    if λ_value is None:
        return True
    try:
        if isinstance(λ_window, (list, tuple)) and len(λ_window) == 2:
            λ_min, λ_max = float(λ_window[0]), float(λ_window[1])
            return λ_min <= λ_value <= λ_max
        return True
    except (TypeError, ValueError):
        return True


def extract_domains(obj: dict) -> list[str]:
    """Domains attached to the object. Primitives carry domains in
    `data.domains`; other objects have empty domains by default."""
    if obj.get("kind") == "elins.primitive":
        data = obj.get("data") or {}
        d = data.get("domains")
        if isinstance(d, list):
            return [str(x) for x in d]
    d = obj.get("domains")
    if isinstance(d, list):
        return [str(x) for x in d]
    return []


def domain_filter(obj_domains: list[str], filter_domains: list[str]) -> bool:
    """v2 domain filter:
        - filter_domains empty/absent  → True
        - filter_domains specified, obj has domains → require intersection
        - filter_domains specified, obj has no domains → True
          (per spec: don't exclude non-primitive objects for missing domain field)
    """
    if not filter_domains:
        return True
    if not obj_domains:
        return True
    return bool(set(obj_domains) & set(filter_domains))


# ---------------------------------------------------------------------------
# Basin membership
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# v4 — multi-origin contributions and curvature
# ---------------------------------------------------------------------------
def secondary_origins_for(
    neighborhood: dict,
    all_user_neighborhoods: list[dict],
) -> list[dict]:
    """v4: return the other neighborhoods M (same user) whose origin is
    "close" to N's origin in similarity space — i.e. similarity(O_N, O_M) >= 0.5.
    Excludes N itself."""
    O_N = list(neighborhood.get("origin_vector") or [])
    if not O_N:
        return []
    n_id = neighborhood.get("id")
    out: list[dict] = []
    for M in all_user_neighborhoods:
        if M.get("id") == n_id:
            continue
        O_M = list(M.get("origin_vector") or [])
        if not O_M or len(O_M) != len(O_N):
            continue
        if similarity(O_N, O_M) >= 0.5:
            out.append(M)
    return out


def compute_contributions(
    v_obj: list[float],
    neighborhood: dict,
    secondaries: list[dict],
    max_origins: int = 3,
) -> Optional[list[dict]]:
    """v4: assemble the list of origin contributions for this (object, N) pair.

    Returns None if `influence_radius` is null on N (no propagation), or if
    no candidate origin is within the band (s ≥ threshold − r), or if all
    candidate raw weights collapse to 0.

    Each returned item: {origin_id, similarity, weight}. Weights are
    max(s, 0) normalized so that sum(weights) == 1. Capped at `max_origins`
    candidates by descending similarity before normalization."""
    influence_radius = neighborhood.get("influence_radius")
    if influence_radius is None:
        return None
    threshold = float(neighborhood.get("similarity_threshold", 0.3))
    try:
        r = float(influence_radius)
    except (TypeError, ValueError):
        return None
    band_floor = threshold - r

    O_N = list(neighborhood.get("origin_vector") or [])
    candidates: list[dict] = []

    s_N = similarity(O_N, v_obj)
    if s_N >= band_floor:
        candidates.append({
            "origin_id": neighborhood.get("id"),
            "similarity": float(s_N),
        })

    for M in secondaries or []:
        O_M = list(M.get("origin_vector") or [])
        if not O_M or len(O_M) != len(v_obj):
            continue
        s_M = similarity(O_M, v_obj)
        if s_M < band_floor:
            continue
        candidates.append({
            "origin_id": M.get("id"),
            "similarity": float(s_M),
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["similarity"], reverse=True)
    candidates = candidates[: max(1, int(max_origins))]

    raw = [max(c["similarity"], 0.0) for c in candidates]
    total = sum(raw)
    if total == 0.0:
        return None
    for c, w in zip(candidates, raw):
        c["weight"] = w / total

    return candidates


def compute_curvature(
    v_obj: list[float],
    primary_origin_vec: list[float],
    contributions: Optional[list[dict]],
    all_user_neighborhoods: list[dict],
) -> Optional[float]:
    """v4: scalar curvature ≡ sim_mean − sim_primary, where:
        O_mean    = normalize(Σ w_k · O_k) over contributions
        sim_mean  = similarity(O_mean, v_obj)
        sim_prim  = similarity(O_N, v_obj)

    Returns None when contributions is None/empty (no enrichment to compute).
    """
    if not contributions:
        return None
    lookup = {nb.get("id"): list(nb.get("origin_vector") or []) for nb in all_user_neighborhoods}
    if not primary_origin_vec:
        return None
    dim = len(primary_origin_vec)
    accum = [0.0] * dim
    for c in contributions:
        O_k = lookup.get(c.get("origin_id"))
        if not O_k or len(O_k) != dim:
            continue
        try:
            w = float(c.get("weight", 0.0))
        except (TypeError, ValueError):
            continue
        for i, x in enumerate(O_k):
            accum[i] += w * x
    O_mean = _normalize(accum)
    sim_mean = similarity(O_mean, v_obj)
    sim_primary = similarity(primary_origin_vec, v_obj)
    return float(sim_mean - sim_primary)


# ---------------------------------------------------------------------------
# Top-N selection + predictive step (used by Markov v3 / DEWEY v5)
# ---------------------------------------------------------------------------
def top_neighborhoods_for(
    v: list[float],
    neighborhoods: list[dict],
    k: int = 5,
) -> list[dict]:
    """Return top-k neighborhoods by similarity(v, origin_vector). Each
    returned entry is a SHALLOW COPY of the source neighborhood doc with
    a `similarity` field added."""
    scored: list[dict] = []
    for nb in neighborhoods or []:
        origin = nb.get("origin_vector")
        if not origin:
            continue
        scored.append({**nb, "similarity": float(similarity(v, origin))})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[: max(0, int(k))]


def top_neighborhoods_with_curvature(
    v: list[float],
    all_user_neighborhoods: list[dict],
    k: int = 3,
) -> list[dict]:
    """Top-k neighborhoods by similarity, plus a per-entry `curvature`
    computed using the full neighborhood set as the secondary-origin basis.

    For neighborhoods without `influence_radius` set, curvature comes back
    as None (matching `compute_curvature`)."""
    top = top_neighborhoods_for(v, all_user_neighborhoods, k=k)
    for nb in top:
        secondaries = secondary_origins_for(nb, all_user_neighborhoods)
        contribs = compute_contributions(
            v, nb, secondaries,
            max_origins=int(nb.get("max_origins", 3)),
        )
        nb["curvature"] = compute_curvature(
            v, list(nb.get("origin_vector") or []),
            contribs, all_user_neighborhoods,
        )
    return top


def predict_next_state(
    prev_state_vector: list[float],
    user_neighborhoods: list[dict],
    top_n: int = 5,
    state_weight: float = 0.6,
    origin_weight: float = 0.4,
) -> list[float]:
    """Forward-step predictor used by Markov v3 / DEWEY v5.

    Algorithm (matches the future v5 `step_state_forward` per spec):
      1. Find top-N neighborhoods for `prev_state_vector`.
      2. Weighted origin: w_k = max(sim_k, 0) / sum(max(sim_k, 0));
         v_origins = normalize(Σ w_k * origin_k).
      3. v_next = normalize(state_weight * prev_state_vector + origin_weight * v_origins).

    Falls back to a copy of `prev_state_vector` when the user has no
    neighborhoods or none score above zero."""
    if not prev_state_vector:
        return list(prev_state_vector or [])
    top = top_neighborhoods_for(prev_state_vector, user_neighborhoods, k=top_n)
    if not top:
        return list(prev_state_vector)
    raw_weights = [max(nb["similarity"], 0.0) for nb in top]
    total = sum(raw_weights)
    if total == 0.0:
        return list(prev_state_vector)
    dim = len(prev_state_vector)
    accum = [0.0] * dim
    for nb, w in zip(top, raw_weights):
        origin = nb.get("origin_vector") or []
        if len(origin) != dim:
            continue
        wn = w / total
        for i, x in enumerate(origin):
            accum[i] += wn * x
    v_origins = _normalize(accum)
    combined = [
        state_weight * prev_state_vector[i] + origin_weight * v_origins[i]
        for i in range(dim)
    ]
    return _normalize(combined)


def compute_noise_component(
    v_proj: list[float],
    v_obs: list[float],
    prev_state: list[float],
    top_neighborhoods: list[dict],
    alpha: float = 0.15,
) -> list[float]:
    """4/3-1 subtractive constraint — estimate a small noise direction to
    subtract from `v_proj`.

    Three contributions, each independently L2-normalized then averaged
    with equal weight, then scaled by `alpha` so the subtraction nudges
    rather than dominates:
      1. drift: orthogonal residual of (v_obs − prev) wrt prev (the part of
         the observation change that doesn't lie along the recent direction).
      2. curvature anomaly: weighted sum of top neighborhood origins, weighted
         by |curvature|. Empty when curvature is unset on all top entries.
      3. domain shift: raw delta v_obs − prev_state.

    Returns a vector the same length as v_proj. May be all zeros if no
    component contributed (e.g., first turn of a session)."""
    dim = len(v_proj)
    if dim == 0:
        return []
    have_prev = prev_state and len(prev_state) == dim
    have_obs = v_obs and len(v_obs) == dim

    domain_shift = (
        [v_obs[i] - prev_state[i] for i in range(dim)]
        if have_prev and have_obs else [0.0] * dim
    )

    if have_prev and have_obs:
        proj_scalar = sum(domain_shift[i] * prev_state[i] for i in range(dim))
        drift = [domain_shift[i] - proj_scalar * prev_state[i] for i in range(dim)]
    else:
        drift = [0.0] * dim

    curv_anomaly = [0.0] * dim
    for nb in top_neighborhoods or []:
        c = nb.get("curvature")
        if c is None:
            continue
        try:
            weight = abs(float(c))
        except (TypeError, ValueError):
            continue
        if weight <= 0.0:
            continue
        origin = nb.get("origin_vector")
        if not origin or len(origin) != dim:
            continue
        for i, x in enumerate(origin):
            curv_anomaly[i] += weight * x

    accum = [0.0] * dim
    for component in (drift, curv_anomaly, domain_shift):
        n = math.sqrt(sum(x * x for x in component))
        if n > 1e-9:
            for i in range(dim):
                accum[i] += (component[i] / n) / 3.0
    return [alpha * x for x in accum]


# ---------------------------------------------------------------------------
# DEWEY v5 — trajectory forecasting
# ---------------------------------------------------------------------------
def step_state_forward(
    current_state_vector: list[float],
    user_neighborhoods: list[dict],
) -> tuple[list[float], dict, list[dict]]:
    """One forward step in state space.

    Returns `(v_next, qc_envelope, dominant_neighborhoods)`:
      - v_next = `predict_next_state(current, neighborhoods, top_n=5)`
      - qc_envelope:
          qc_stability = similarity(current, v_next)
          qc_drift     = 1 − qc_stability
          qc_predictive = exp(−qc_drift · 3)
          qc_pressure  = mean |curvature| over top-3 neighborhoods at v_next
      - dominant_neighborhoods: top 3 by similarity to v_next, each carrying
        `{neighborhood_id, similarity, curvature}`. Curvature is None for
        neighborhoods without `influence_radius`.

    All math runs locally; no Firestore writes."""
    if not current_state_vector:
        return list(current_state_vector or []), {
            "qc_stability": 1.0, "qc_drift": 0.0,
            "qc_predictive": 1.0, "qc_pressure": 0.0,
        }, []

    v_next = predict_next_state(current_state_vector, user_neighborhoods, top_n=5)

    qc_stability = float(similarity(current_state_vector, v_next))
    qc_drift = 1.0 - qc_stability
    try:
        qc_predictive = float(math.exp(-qc_drift * 3.0))
    except OverflowError:
        qc_predictive = 0.0

    top3 = top_neighborhoods_with_curvature(v_next, user_neighborhoods, k=3)
    curvs = [abs(float(nb["curvature"])) for nb in top3 if nb.get("curvature") is not None]
    qc_pressure = float(sum(curvs) / len(curvs)) if curvs else 0.0

    dominant = [
        {
            "neighborhood_id": nb.get("id"),
            "similarity": float(nb["similarity"]),
            "curvature": nb.get("curvature"),
        }
        for nb in top3
    ]
    qc_envelope = {
        "qc_stability": qc_stability,
        "qc_drift": float(qc_drift),
        "qc_predictive": qc_predictive,
        "qc_pressure": qc_pressure,
    }
    return v_next, qc_envelope, dominant


def generate_trajectory(
    start_state_vector: list[float],
    horizon_steps: int,
    user_neighborhoods: list[dict],
    branch_label: str = "base",
) -> tuple[list[dict], dict]:
    """Iterate `step_state_forward` `horizon_steps` times. Returns
    `(steps, partial_summary)` — the summary contains the base mean
    scores; the calling route adds branching_factor and ELINS anchoring."""
    horizon = max(0, int(horizon_steps))
    steps: list[dict] = []
    v = list(start_state_vector)
    for i in range(1, horizon + 1):
        v_next, qc, dom = step_state_forward(v, user_neighborhoods)
        steps.append({
            "step_index": i,
            "state_vector": v_next,
            "qc_envelope": qc,
            "dominant_neighborhoods": dom,
            "branch_label": branch_label,
        })
        v = v_next

    if steps:
        n = len(steps)
        stability_score = sum(s["qc_envelope"]["qc_stability"] for s in steps) / n
        drift_score = sum(s["qc_envelope"]["qc_drift"] for s in steps) / n
        pressure_score = sum(s["qc_envelope"]["qc_pressure"] for s in steps) / n
    else:
        stability_score = 0.0
        drift_score = 0.0
        pressure_score = 0.0

    return steps, {
        "stability_score": float(stability_score),
        "drift_score": float(drift_score),
        "pressure_score": float(pressure_score),
    }


def generate_alternative_branches(
    start_state_vector: list[float],
    horizon_steps: int,
    user_neighborhoods: list[dict],
    num_branches: int = 2,
    perturbation_norm: float = 0.1,
    seed: Optional[int] = None,
) -> list[tuple[list[dict], dict]]:
    """For each of `num_branches`, perturb `start_state_vector` by a small
    random direction with norm ≈ `perturbation_norm`, then run a
    trajectory. Returns a list of `(branch_steps, branch_summary)` tuples,
    one per branch.

    Seeded for repeatability when `seed is not None` (useful in tests)."""
    rng = random.Random(seed) if seed is not None else random.Random()
    branches: list[tuple[list[dict], dict]] = []
    if not start_state_vector:
        return branches
    dim = len(start_state_vector)
    for b in range(1, max(0, int(num_branches)) + 1):
        eps = [rng.gauss(0.0, 1.0) for _ in range(dim)]
        eps_n = math.sqrt(sum(x * x for x in eps)) or 1.0
        eps = [(x / eps_n) * float(perturbation_norm) for x in eps]
        perturbed = _normalize([start_state_vector[i] + eps[i] for i in range(dim)])
        steps, summary = generate_trajectory(
            perturbed, horizon_steps, user_neighborhoods,
            branch_label=f"alt_{b}",
        )
        branches.append((steps, summary))
    return branches


# ---------------------------------------------------------------------------
# DEWEY v5.1 — trajectory stability + divergence metrics
# ---------------------------------------------------------------------------
def compute_trajectory_metrics(steps: list[dict]) -> dict:
    """v5.1 — compute per-trajectory metrics from a flattened step list.

    Returns:
      stability_variance     — variance of qc_stability across base steps
      mean_branch_divergence — mean cosine distance between alt and base
                                at the same step_index, averaged within each
                                branch then averaged across branches
      max_branch_divergence  — max cosine distance observed across all
                                (branch, step_index) pairs

    All zeros when there's no base or no alt branches. Defensive against
    legacy step shapes (missing qc_envelope, mismatched vector dims)."""
    if not steps:
        return {
            "stability_variance": 0.0,
            "mean_branch_divergence": 0.0,
            "max_branch_divergence": 0.0,
        }

    # 1. Partition by branch_label, sort by step_index.
    branches: dict[str, list[dict]] = {}
    for s in steps:
        label = s.get("branch_label", "base")
        branches.setdefault(label, []).append(s)
    for label in branches:
        branches[label].sort(key=lambda x: int(x.get("step_index", 0)))

    base_steps = branches.get("base", [])
    alt_branches = {k: v for k, v in branches.items() if k != "base"}

    # 2. stability_variance over base.
    if base_steps:
        stabilities: list[float] = []
        for s in base_steps:
            try:
                stabilities.append(float((s.get("qc_envelope") or {}).get("qc_stability", 0.0)))
            except (TypeError, ValueError):
                stabilities.append(0.0)
        n = len(stabilities)
        mean = sum(stabilities) / n
        stability_variance = sum((x - mean) ** 2 for x in stabilities) / n
    else:
        stability_variance = 0.0

    # 3-4. branch divergence — index base_steps by step_index for O(1) lookup.
    base_by_idx = {int(s.get("step_index", -1)): s for s in base_steps}
    branch_means: list[float] = []
    all_distances: list[float] = []
    for _label, alt_steps in alt_branches.items():
        per_branch: list[float] = []
        for alt in alt_steps:
            i = int(alt.get("step_index", -1))
            base = base_by_idx.get(i)
            if not base:
                continue
            base_v = base.get("state_vector") or []
            alt_v = alt.get("state_vector") or []
            if not base_v or not alt_v or len(base_v) != len(alt_v):
                continue
            d = 1.0 - similarity(base_v, alt_v)
            per_branch.append(d)
            all_distances.append(d)
        if per_branch:
            branch_means.append(sum(per_branch) / len(per_branch))

    mean_branch_divergence = (
        sum(branch_means) / len(branch_means) if branch_means else 0.0
    )
    max_branch_divergence = max(all_distances) if all_distances else 0.0

    return {
        "stability_variance": float(stability_variance),
        "mean_branch_divergence": float(mean_branch_divergence),
        "max_branch_divergence": float(max_branch_divergence),
    }


# ---------------------------------------------------------------------------
# Markov v3 — predictive envelope evolution
# ---------------------------------------------------------------------------
def compute_predictive_envelope(
    prev_state_vector: list[float],
    user_neighborhoods: list[dict],
    top_n: int = 5,
) -> list[float]:
    """Markov v3 predictive envelope.

    Per spec: pure weighted-mean origin (no blend with prev_state). Differs
    from `predict_next_state` (which blends 0.6·prev + 0.4·origins) — this
    one returns the origin-cluster centroid in normalized space.

    Algorithm:
      1. Top-N neighborhoods by similarity to `prev_state_vector`.
      2. w_k = max(sim_k, 0) / Σ max(sim_k, 0)
      3. predictive_vector = normalize(Σ w_k · origin_k)

    Falls back to `prev_state_vector` (copy) when no neighborhoods exist
    or all sims ≤ 0 (so the field has a sensible default for the spec
    "envelope_predictive_vector defaults to state_vector")."""
    if not prev_state_vector:
        return list(prev_state_vector or [])
    top = top_neighborhoods_for(prev_state_vector, user_neighborhoods, k=top_n)
    if not top:
        return list(prev_state_vector)
    raw = [max(nb["similarity"], 0.0) for nb in top]
    total = sum(raw)
    if total == 0.0:
        return list(prev_state_vector)
    dim = len(prev_state_vector)
    accum = [0.0] * dim
    for nb, w in zip(top, raw):
        origin = nb.get("origin_vector") or []
        if len(origin) != dim:
            continue
        wn = w / total
        for i, x in enumerate(origin):
            accum[i] += wn * x
    return _normalize(accum)


def compute_envelope_metrics(
    prev_state: Optional[dict],
    new_state: dict,
) -> dict:
    """Markov v3 envelope evolution metrics — differences between
    consecutive QC envelopes. Returns zeros on the first turn (`prev_state
    is None`) per spec defaults."""
    if not prev_state:
        return {"stability_trend": 0.0, "drift_trend": 0.0, "pressure_trend": 0.0}
    p = prev_state.get("qc_envelope") or {}
    n = new_state.get("qc_envelope") or {}
    def _g(d: dict, k: str) -> float:
        try:
            return float(d.get(k, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return {
        "stability_trend": _g(n, "qc_stability") - _g(p, "qc_stability"),
        "drift_trend": _g(n, "qc_drift") - _g(p, "qc_drift"),
        "pressure_trend": _g(n, "qc_pressure") - _g(p, "qc_pressure"),
    }


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------
def compute_envelope_vector(elins_briefs: list[dict]) -> Optional[list[float]]:
    """v2 envelope vector: equal-weight sum of brief object_vectors,
    L2-normalized. Returns None if the list is empty or no brief carries
    a vector. Briefs missing or with a wrong-dim object_vector are skipped
    silently."""
    if not elins_briefs:
        return None
    accum: Optional[list[float]] = None
    for brief in elins_briefs:
        v = brief.get("object_vector")
        if not v:
            continue
        if accum is None:
            accum = list(v)
            continue
        if len(v) != len(accum):
            continue
        for i, x in enumerate(v):
            accum[i] += x
    if accum is None:
        return None
    return _normalize(accum)


def compute_strength_weighted_envelope_vector(
    elins_briefs: list[dict],
) -> Optional[list[float]]:
    """v3 envelope vector: strength-weighted mean of brief object_vectors,
    L2-normalized. Returns None if all strengths sum to ≤0 or no brief has
    a usable vector — caller should treat this as "envelope inactive".

    Note: superseded by `compute_multilayer_envelope_vector` for v3.5+.
    Kept for any caller that explicitly wants timescale-agnostic weighting."""
    if not elins_briefs:
        return None
    accum: Optional[list[float]] = None
    total_w = 0.0
    for brief in elins_briefs:
        v = brief.get("object_vector")
        if not v:
            continue
        try:
            w = float(brief.get("strength", 1.0))
        except (TypeError, ValueError):
            w = 1.0
        if w <= 0.0:
            continue
        if accum is None:
            accum = [w * x for x in v]
        else:
            if len(v) != len(accum):
                continue
            for i in range(len(v)):
                accum[i] += w * v[i]
        total_w += w
    if accum is None or total_w == 0.0:
        return None
    return _normalize(accum)


# Per spec §4 — timescale weights for the multi-layer envelope vector.
# These multiply `strength` so each brief's contribution is `strength * timescale_weight`.
ENVELOPE_TIMESCALE_VECTOR_WEIGHT = {
    "short": 0.5,
    "mid": 1.0,
    "long": 2.0,
}


def compute_multilayer_envelope_vector(
    elins_briefs: list[dict],
) -> Optional[list[float]]:
    """v3.5 envelope vector: per-brief weight = `strength * timescale_weight`,
    summed across all briefs and L2-normalized.

    Timescale weights (per spec): short=0.5, mid=1.0, long=2.0. Briefs whose
    `timescale` is missing or unrecognized are treated as "mid" (weight 1.0).
    Returns `None` when nothing contributes."""
    if not elins_briefs:
        return None
    accum: Optional[list[float]] = None
    total_w = 0.0
    for brief in elins_briefs:
        v = brief.get("object_vector")
        if not v:
            continue
        try:
            strength = float(brief.get("strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        if strength <= 0.0:
            continue
        ts = brief.get("timescale", "mid")
        ts_w = ENVELOPE_TIMESCALE_VECTOR_WEIGHT.get(ts, ENVELOPE_TIMESCALE_VECTOR_WEIGHT["mid"])
        w = strength * ts_w
        if w <= 0.0:
            continue
        if accum is None:
            accum = [w * x for x in v]
        else:
            if len(v) != len(accum):
                continue
            for i in range(len(v)):
                accum[i] += w * v[i]
        total_w += w
    if accum is None or total_w == 0.0:
        return None
    return _normalize(accum)


# ---------------------------------------------------------------------------
def is_within_basin(
    obj: dict,
    neighborhood: dict,
    obj_vec: Optional[list[float]] = None,
) -> tuple[bool, float]:
    """v2/v3 basin rule: similarity ≥ similarity_threshold AND λ-compatible
    AND domain-match. Returns `(in_basin, similarity_score)`.

    v3: callers can pass `obj_vec` to skip embedding (avoids redundant
    cache lookups when the worker already has the persisted vector).
    Pre-supplied vectors are assumed normalized — if the persisted vector
    has the wrong magnitude, sim will read low rather than crashing."""
    if obj_vec is None:
        obj_vec = embed_object(obj)
    origin_vec = list(neighborhood.get("origin_vector") or [])
    # Defensive re-normalize on read in case an old (pre-v2) neighborhood
    # was written without origin-vector normalization.
    origin_vec = _normalize(origin_vec) if origin_vec else origin_vec

    sim = similarity(obj_vec, origin_vec)

    threshold = float(neighborhood.get("similarity_threshold", 0.3))
    if sim < threshold:
        return False, sim

    if not λ_compatibility(extract_lambda(obj), neighborhood.get("λ_window")):
        return False, sim

    filter_domains = (neighborhood.get("filters") or {}).get("domains") or []
    if not domain_filter(extract_domains(obj), filter_domains):
        return False, sim

    return True, sim
