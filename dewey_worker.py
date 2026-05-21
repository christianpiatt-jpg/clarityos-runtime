"""
DEWEY worker. Synchronous, in-process.

Triggered from vault/library/ELINS write handlers. Iterates the user's
neighborhoods, runs `is_within_basin` on each, and writes a membership
row when the object falls inside.

Best-effort: any failure is logged and swallowed so the primary write
(vault/library/ELINS) that triggered this never sees a worker error.

For v1 this runs in the request thread. Move to Cloud Tasks / Pub/Sub if
membership writes start to dominate request latency.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import dewey_neighborhoods_store
import dewey_memberships_store
import dewey_pipeline
from dewey_pipeline import is_within_basin

logger = logging.getLogger("clarityos.dewey_worker")


def _backfill_object_vector(object_kind: str, object_id: str, obj_vec: list[float]) -> None:
    """Persist a freshly-computed vector back to its source store. Called
    by the worker when it encounters a legacy object without object_vector.

    Imports are local to avoid a top-level circular dependency between
    the worker and the route handlers."""
    try:
        if object_kind == "vault":
            import vault_store
            doc = vault_store.get(object_id)
            if doc:
                doc["object_vector"] = obj_vec
                vault_store.update(object_id, doc)
        elif object_kind == "library":
            import library_store
            doc = library_store.get(object_id)
            if doc:
                doc["object_vector"] = obj_vec
                library_store.update(object_id, doc)
        elif object_kind == "timeline":
            import timeline_store
            doc = timeline_store.get(object_id)
            if doc:
                doc["object_vector"] = obj_vec
                timeline_store.update(object_id, doc)
        else:
            return
        logger.info(
            "dewey worker vector_backfilled kind=%s id=%s dim=%d",
            object_kind, object_id, len(obj_vec),
        )
    except Exception as e:
        logger.warning(
            "dewey worker vector_backfill failed kind=%s id=%s err=%s",
            object_kind, object_id, e,
        )


def process_object(user: str, object_kind: str, object_id: str, object_doc: dict) -> int:
    """Process a single new object against the user's neighborhoods.

    object_kind: "vault" | "library" | "timeline"
    Returns count of memberships written. Never raises.

    v3: prefers the persisted `object_vector` on the doc and only
    re-embeds + writes back if it's missing (legacy object pre-v3)."""
    try:
        neighborhoods = dewey_neighborhoods_store.list_for_user(user)
    except Exception as e:
        logger.warning("dewey worker neighborhood-list failed user=%s err=%s", user, e)
        return 0

    obj_vec = object_doc.get("object_vector")
    if obj_vec:
        logger.info(
            "dewey worker using_persisted_vector kind=%s id=%s dim=%d",
            object_kind, object_id, len(obj_vec),
        )
    else:
        obj_vec = dewey_pipeline.embed_object(object_doc)
        _backfill_object_vector(object_kind, object_id, obj_vec)

    written = 0
    for nb in neighborhoods:
        try:
            in_basin, sim = is_within_basin(object_doc, nb, obj_vec=obj_vec)
            if not in_basin:
                continue
            # v4 enrichments — contributions + curvature for hard members.
            secondaries = dewey_pipeline.secondary_origins_for(nb, neighborhoods)
            contributions = dewey_pipeline.compute_contributions(
                obj_vec, nb, secondaries,
                max_origins=int(nb.get("max_origins", 3)),
            )
            curvature = dewey_pipeline.compute_curvature(
                obj_vec,
                list(nb.get("origin_vector") or []),
                contributions,
                neighborhoods,
            )
            membership_id = dewey_memberships_store.new_id()
            dewey_memberships_store.create(membership_id, {
                "id": membership_id,
                "neighborhood_id": nb["id"],
                "object_id": object_id,
                "object_kind": object_kind,
                "user": user,
                "similarity": float(sim),
                "contributions": contributions,
                "curvature": curvature,
                "created_at": time.time(),
            })
            written += 1
        except Exception as e:
            logger.warning(
                "dewey worker membership-write failed nb=%s obj=%s err=%s",
                nb.get("id"), object_id, e,
            )
    if written:
        logger.info(
            "dewey worker user=%s kind=%s obj=%s memberships=%d",
            user, object_kind, object_id, written,
        )
    return written


def refresh_neighborhood(
    neighborhood: dict,
    objects: list[tuple[str, dict]],
    all_user_neighborhoods: Optional[list[dict]] = None,
) -> int:
    """Recompute memberships for a single neighborhood across a supplied
    set of (object_kind, object_doc) pairs. Caller is expected to have
    already cleared previous memberships for this neighborhood.

    v3: prefers persisted `object_vector` on each object; falls back to
    fresh embed (and backfill) if missing.

    v4: computes per-membership contributions and curvature using the
    user's full neighborhood set. If `all_user_neighborhoods` isn't
    supplied, fetches it once from `dewey_neighborhoods_store`.

    Returns count of memberships written.
    """
    user = neighborhood.get("user", "")
    if all_user_neighborhoods is None:
        try:
            all_user_neighborhoods = dewey_neighborhoods_store.list_for_user(user)
        except Exception:
            all_user_neighborhoods = [neighborhood]
    secondaries = dewey_pipeline.secondary_origins_for(neighborhood, all_user_neighborhoods)
    primary_origin = list(neighborhood.get("origin_vector") or [])
    max_origins = int(neighborhood.get("max_origins", 3))

    written = 0
    for object_kind, object_doc in objects:
        try:
            obj_vec = object_doc.get("object_vector")
            if not obj_vec:
                obj_vec = dewey_pipeline.embed_object(object_doc)
                obj_id = object_doc.get("id")
                if obj_id:
                    _backfill_object_vector(object_kind, obj_id, obj_vec)
            in_basin, sim = is_within_basin(object_doc, neighborhood, obj_vec=obj_vec)
            if not in_basin:
                continue
            contributions = dewey_pipeline.compute_contributions(
                obj_vec, neighborhood, secondaries, max_origins=max_origins,
            )
            curvature = dewey_pipeline.compute_curvature(
                obj_vec, primary_origin, contributions, all_user_neighborhoods,
            )
            membership_id = dewey_memberships_store.new_id()
            dewey_memberships_store.create(membership_id, {
                "id": membership_id,
                "neighborhood_id": neighborhood["id"],
                "object_id": object_doc.get("id", ""),
                "object_kind": object_kind,
                "user": user,
                "similarity": float(sim),
                "contributions": contributions,
                "curvature": curvature,
                "created_at": time.time(),
            })
            written += 1
        except Exception as e:
            logger.warning(
                "dewey refresh membership-write failed nb=%s obj=%s err=%s",
                neighborhood.get("id"), object_doc.get("id"), e,
            )
    return written
