# DEWEY

## Purpose

DEWEY is a conceptual-neighborhood indexing layer. A user defines
*neighborhoods* — named regions of embedding space anchored on a query — and
DEWEY indexes which of the user's stored objects (vault, library, timeline)
fall inside each neighborhood's basin. It also runs forward trajectory
forecasting driven by those neighborhoods. It is infrastructure: deterministic
vector geometry over embeddings, not a search or recommendation engine.

## Implementation location

Repo-root modules: `dewey_neighborhoods_store.py` (the `dewey_neighborhoods`
collection), `dewey_memberships_store.py` (the `dewey_memberships` collection),
`dewey_worker.py` (the synchronous membership worker), and `dewey_pipeline.py`
(the geometry, basin, and trajectory math — DEWEY v2 through v5.1). HTTP
endpoints are in `app.py`. `dewey_pipeline.py` is a shared module — it also
hosts ELINS-envelope and Markov-predictive helpers (see Non-goals).

## Data model

- **Neighborhood** (`dewey_neighborhoods` collection): `{id (nb_<token>), user,
  name, query, filters, origin_vector (L2-normalized embedding of query),
  λ_window (optional [λ_min, λ_max]), similarity_threshold (float in [-1, 1]),
  influence_radius (optional; null disables v4 multi-origin), max_origins (int,
  default 3), created_at, updated_at}`. `filters.domains` constrains basin
  membership by domain.
- **Membership** (`dewey_memberships` collection): `{id (mb_<token>),
  neighborhood_id, object_id, object_kind (vault | library | timeline), user,
  similarity, contributions (optional, v4), curvature (optional, v4),
  created_at}`. A membership row records that one stored object fell inside one
  neighborhood's basin.
- IDs (`nb_…` / `mb_…`) are opaque random tokens (`secrets.token_urlsafe`).
  Both stores have a `memory` and a `firestore` backend, selected by
  `CLARITYOS_BACKEND`.
- Embeddings are L2-normalized vectors — Vertex AI `text-embedding-005`, or a
  deterministic 32-dim SHA-256 hash fallback. An object's embedding is cached
  on its source document as `object_vector` and in `embeddings_cache_store`.

## APIs / entrypoints

- HTTP: `POST /dewey/neighborhoods/create`, `GET /dewey/neighborhoods/list`,
  `GET /dewey/neighborhoods/{nb_id}` (neighborhood + its memberships),
  `POST /dewey/neighborhoods/{nb_id}/refresh` (drop and rebuild memberships
  from the user's vault/library/timeline), `POST /dewey/backfill_vectors`
  (founder-only; backfills `object_vector` on legacy objects),
  `GET /metadata/dewey` (neighborhood metadata only — never vectors),
  `POST /trajectory/forecast`, `GET /trajectory/compare`.
- **`dewey_worker`** — `process_object(user, object_kind, object_id,
  object_doc)` indexes one new object against the user's neighborhoods;
  `refresh_neighborhood(neighborhood, objects, …)` rebuilds one neighborhood.
  Both are best-effort and never raise.
- **`dewey_pipeline`** — embedding (`embed_text`, `embed_text_cached`,
  `embed_object`), geometry (`similarity`, `geodesic_distance`,
  `directional_alignment`), basin gating (`is_within_basin`), v4 multi-origin
  (`secondary_origins_for`, `compute_contributions`, `compute_curvature`), and
  v5 trajectory forecasting (`step_state_forward`, `generate_trajectory`,
  `generate_alternative_branches`, `compute_trajectory_metrics`).
- **Stores** — `dewey_neighborhoods_store` and `dewey_memberships_store` expose
  `new_id` / `create` / `get` and list helpers;
  `dewey_memberships_store.delete_for_neighborhood` backs `/refresh`.

## Integration points

- **Vault / Library / Timeline** — every object write in `app.py` embeds the
  object (`embed_object`) and calls `dewey_worker.process_object`, so
  membership is indexed automatically on write.
- **embeddings_cache_store** — the Firestore embedding cache used by
  `embed_text_cached`.
- **Vertex AI** — `text-embedding-005`, gated by `GOOGLE_CLOUD_PROJECT` /
  `CLARITYOS_VERTEX_*`; when unavailable DEWEY uses the deterministic hash
  fallback.
- **Markov / trajectories** — `/trajectory/forecast` reads its start vector
  from `markov_states_store` and persists the result to `trajectories_store`.
- **ELINS** — trajectory forecasts anchor to an ELINS brief by similarity, and
  ELINS objects (`elins.primitive`, `elins.brief`) are valid DEWEY index
  targets.

## Invariants

- Given the input vectors, the geometry is deterministic: `similarity`,
  `is_within_basin`, `compute_contributions`, `compute_curvature`, and the base
  trajectory are pure functions of their inputs.
- Embedding never raises — a Vertex failure returns `None` and the caller falls
  back to the deterministic hash embed; `embed_object` always returns an
  L2-normalized vector.
- The worker is best-effort and never raises: every failure is caught and
  logged so the triggering vault/library/timeline write never fails because of
  DEWEY.
- Vectors are L2-normalized; `_normalize` returns a zero vector (never NaN,
  never an exception) for a sub-epsilon norm.
- Basin membership requires similarity ≥ `similarity_threshold` (default 0.3)
  **and** λ-window compatibility **and** domain-filter match.
- A neighborhood belongs to one user; `/dewey/neighborhoods/{nb_id}` and the
  trajectory endpoints return 403 on cross-user access and 404 when absent.
- `/refresh` is delete-then-rebuild: it removes every membership for the
  neighborhood before recomputing.

## Non-goals

- DEWEY is **not** the economic Membership layer. `dewey_memberships_store`
  records object-to-neighborhood membership; it is unrelated to
  `membership_store`, the Founding 500 cohort, billing, credits, or
  entitlements (see `docs/membership.md`).
- Not a search or recommendation engine — DEWEY does not retrieve or rank
  external content; it ranks the user's *own* neighborhoods by cosine
  similarity for trajectory prediction.
- Not a graph-theory engine — neighborhoods relate through cosine similarity
  (`secondary_origins_for`), not graph traversal or path algorithms.
- No scheduler — `dewey_worker` runs synchronously in the request thread; the
  move to Cloud Tasks / Pub-Sub is noted in code as future work, not
  implemented.
- `dewey_pipeline.py` also hosts ELINS-envelope vector helpers
  (`compute_*envelope_vector`) and Markov-predictive helpers
  (`compute_predictive_envelope`, `compute_envelope_metrics`). Those are
  consumed by ELINS / Markov and belong to those subsystems' docs, not here.

## Fiction removed

The 10e instruction named `dewey_neighbors.py` and `dewey_index.py`; neither
exists. The real DEWEY backend is the four modules above. DEWEY is not a
user-membership system, a billing-tier system, a search engine, a
recommendation engine, or a graph-theory engine — none of those are in the
code. Neighborhood and membership IDs are opaque random tokens, not
"deterministic region IDs". There is no semantic ranking of external content
and no neighborhood inference beyond the deterministic cosine-similarity vector
math described above.
