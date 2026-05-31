# phase9_actions.py
"""
Phase 9.0 — Action Primitive Specification.

Introduces the operator *action* as a first-class causal primitive: the
``ActionEvent`` record and its deterministic mapping to an ``"action"``-type
``CausalNode``. This is the causal atom Phase 8 has been missing — once actions
enter the graph (9.2+), the multi-chain explanations (8.4), causal deltas (8.6),
and stability forecast (8.7) gain a real behavioral source instead of the
analytics→narrative fallback.

9.0 defines the primitive ONLY: no ingestion (9.1), no graph integration (9.2),
no propagation change (9.3), no behavioral motifs (9.4), no UI (9.5).

    ActionEvent(id, label, timestamp, magnitude=None)
    make_action_node(event) -> CausalNode

Action semantics (see ``phase9_spec.md``): actions are first-class causal nodes;
they ALWAYS carry a timestamp; they MAY carry a magnitude; they influence system
state (drift / coherence / alerts / factors / other actions) but never receive
influence from system-generated nodes (narrative / stability / summaries).

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitive + stdlib — nothing from the CI-gated runtime spine.

See ``phase9_spec.md`` ("Phase 9.0 — Action Primitive Specification").
"""
from dataclasses import dataclass

from phase8_structures import ACTION_NODE_TYPE, CausalNode, make_node


@dataclass
class ActionEvent:
    """An operator action.

    ``timestamp`` is required — actions are inherently temporal. ``magnitude`` is
    the optional intensity (e.g. "Adjusted parameter by +0.7" → ``0.7``); it is
    ``None`` for actions with no magnitude (e.g. "Opened app" → ``None``).
    """
    id: str
    label: str
    timestamp: float
    magnitude: float | None = None


def make_action_node(event: ActionEvent) -> CausalNode:
    """Deterministically map an ``ActionEvent`` to an ``"action"``-type
    ``CausalNode``.

    A pure 1:1 mapping — no inference, transformation, or randomness:
    ``id``/``label``/``timestamp`` pass through and ``value`` carries the
    magnitude. The result is structurally identical to any other ``CausalNode``,
    so it slots into the Phase-8 graph machinery unchanged (once 9.2 wires it in).
    """
    return make_node(
        id=event.id,
        type=ACTION_NODE_TYPE,
        label=event.label,
        timestamp=event.timestamp,
        value=event.magnitude,
    )
