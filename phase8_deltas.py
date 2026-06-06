# phase8_deltas.py
"""
Phase 8.6 — Causal Deltas (temporal change in causal structure).

The causal analogue of Phase-7 drift: where 8.1–8.4 compute the causal system at
a single instant, 8.6 compares two snapshots and reports how the structure
*moved*. This is the first time ClarityOS can say "a new bottleneck emerged",
"a feedback loop resolved", or "this causal chain is weakening".

    compute_causal_deltas(prev, curr) -> dict

``prev`` and ``curr`` are each a causal-state dict with the keys ``influence``
(``{node_id: float}``), ``centrality`` (``{node_id: float}``), ``motifs``
(``{feedback_loops, bottlenecks, attractors}`` — the 8.3 ``analyze_motifs``
shape), and ``chains`` (the 8.4 ``scored_chains_to_dicts`` list). All four are
optional; missing pieces are treated as empty.

Output (every collection sorted, every dict keyed in sorted order):

    {"influence_delta":  {node_id: float},          # curr - prev, clamped [-1, 1]
     "centrality_delta": {node_id: float},          # curr - prev, clamped [-1, 1]
     "motif_delta": {"new_loops", "resolved_loops",
                     "new_bottlenecks", "resolved_bottlenecks",
                     "new_attractors", "resolved_attractors"},
     "chain_delta": {"new_chains", "resolved_chains", "score_shift"}}

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state.

See ``phase8_spec.md`` ("Phase 8.6 — Causal Deltas").
"""

# Deltas are bounded the same way the underlying quantities are: influence and
# centrality live in [0, 1], so a difference lives in [-1, 1]; chain scores live
# in [0, 1], so a mean shift lives in [-1, 1].
DELTA_MIN = -1.0
DELTA_MAX = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scalar_delta(prev_map: dict, curr_map: dict) -> dict:
    """Per-node ``curr - prev`` over the union of node ids, clamped to
    ``[-1, 1]``, returned in sorted-key order.

    A node present only in ``curr`` deltas up from 0 (it appeared); a node
    present only in ``prev`` deltas down to 0 (it dropped out) — both are real
    causal movement, so the union (not just ``curr``'s keys) is compared.
    """
    prev_map = prev_map or {}
    curr_map = curr_map or {}
    keys = sorted(set(prev_map) | set(curr_map))
    return {
        key: _clamp(
            float(curr_map.get(key, 0.0)) - float(prev_map.get(key, 0.0)),
            DELTA_MIN, DELTA_MAX,
        )
        for key in keys
    }


def _motif_delta(prev_motifs: dict, curr_motifs: dict) -> dict:
    """New / resolved members for each motif family.

    For each family, ``new = curr - prev`` and ``resolved = prev - curr``.
    Feedback loops are compared by their node-sequence signature (each loop is a
    list of node ids); bottlenecks and attractors are compared as node-id sets.
    All outputs are sorted.
    """
    prev_motifs = prev_motifs or {}
    curr_motifs = curr_motifs or {}

    prev_loops = {tuple(loop) for loop in prev_motifs.get("feedback_loops", [])}
    curr_loops = {tuple(loop) for loop in curr_motifs.get("feedback_loops", [])}
    prev_bottlenecks = set(prev_motifs.get("bottlenecks", []))
    curr_bottlenecks = set(curr_motifs.get("bottlenecks", []))
    prev_attractors = set(prev_motifs.get("attractors", []))
    curr_attractors = set(curr_motifs.get("attractors", []))

    return {
        "new_loops": [list(loop) for loop in sorted(curr_loops - prev_loops)],
        "resolved_loops": [list(loop) for loop in sorted(prev_loops - curr_loops)],
        "new_bottlenecks": sorted(curr_bottlenecks - prev_bottlenecks),
        "resolved_bottlenecks": sorted(prev_bottlenecks - curr_bottlenecks),
        "new_attractors": sorted(curr_attractors - prev_attractors),
        "resolved_attractors": sorted(prev_attractors - curr_attractors),
    }


def _chain_signature(chain: dict) -> tuple:
    """A chain's identity for comparison: the ordered tuple of its node ids."""
    return tuple(node.get("id") for node in (chain or {}).get("nodes", []))


def _mean_score(chains: list) -> float:
    """Mean of the chains' ``score`` fields (0.0 for an empty set)."""
    scores = [float(chain.get("score", 0.0)) for chain in chains]
    return sum(scores) / len(scores) if scores else 0.0


def _chain_delta(prev_chains: list, curr_chains: list) -> dict:
    """Chains that appeared / disappeared (by node-sequence signature) plus the
    mean-score shift.

    ``new_chains`` / ``resolved_chains`` are the node-id sequences (sorted) that
    are present in only ``curr`` / only ``prev``. ``score_shift`` is
    ``mean(curr scores) - mean(prev scores)``, clamped to ``[-1, 1]``.
    """
    prev_chains = prev_chains or []
    curr_chains = curr_chains or []

    prev_sigs = {_chain_signature(chain) for chain in prev_chains}
    curr_sigs = {_chain_signature(chain) for chain in curr_chains}

    return {
        "new_chains": sorted(list(sig) for sig in (curr_sigs - prev_sigs)),
        "resolved_chains": sorted(list(sig) for sig in (prev_sigs - curr_sigs)),
        "score_shift": _clamp(
            _mean_score(curr_chains) - _mean_score(prev_chains), DELTA_MIN, DELTA_MAX,
        ),
    }


def compute_causal_deltas(prev: dict, curr: dict) -> dict:
    """Temporal change between two causal-state snapshots.

    ``prev`` / ``curr`` each carry ``influence`` / ``centrality`` / ``motifs`` /
    ``chains`` (all optional). When ``prev`` and ``curr`` are equal (e.g. no
    previous snapshot exists, so the caller passes the same state for both), all
    deltas are zero / empty. Fully deterministic; output is JSON-serialisable.
    """
    prev = prev or {}
    curr = curr or {}
    return {
        "influence_delta": _scalar_delta(prev.get("influence"), curr.get("influence")),
        "centrality_delta": _scalar_delta(prev.get("centrality"), curr.get("centrality")),
        "motif_delta": _motif_delta(prev.get("motifs"), curr.get("motifs")),
        "chain_delta": _chain_delta(prev.get("chains"), curr.get("chains")),
    }
