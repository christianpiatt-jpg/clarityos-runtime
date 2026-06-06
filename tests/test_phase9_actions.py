# tests/test_phase9_actions.py
#
# CARD 9.0 — action primitive: the ActionEvent record + its deterministic
# mapping to an "action"-type CausalNode. Primitive only — no ingestion, graph
# integration, propagation, motifs, or UI (those are 9.1–9.5).
import json
from copy import deepcopy
from dataclasses import asdict

import pytest

from phase8_structures import ACTION_NODE_TYPE, CausalNode
from phase9_actions import ActionEvent, make_action_node


# ---------------------------------------------------------------------------
# ActionEvent
# ---------------------------------------------------------------------------

def test_action_event_creation():
    e = ActionEvent(id="a1", label="Adjusted parameter by +0.7", timestamp=12.0, magnitude=0.7)
    assert e.id == "a1"
    assert e.label == "Adjusted parameter by +0.7"
    assert e.timestamp == 12.0
    assert e.magnitude == 0.7


def test_action_event_magnitude_optional_defaults_none():
    e = ActionEvent(id="a2", label="Opened app", timestamp=3.0)
    assert e.magnitude is None


def test_timestamp_required():
    # timestamp has no default → omitting it is a TypeError (actions are
    # inherently temporal).
    with pytest.raises(TypeError):
        ActionEvent(id="a3", label="No timestamp")


# ---------------------------------------------------------------------------
# make_action_node — deterministic mapping
# ---------------------------------------------------------------------------

def test_make_action_node_maps_all_fields():
    node = make_action_node(
        ActionEvent(id="a1", label="Adjusted parameter by +0.7", timestamp=12.0, magnitude=0.7)
    )
    assert isinstance(node, CausalNode)
    assert node.id == "a1"
    assert node.type == ACTION_NODE_TYPE == "action"
    assert node.label == "Adjusted parameter by +0.7"
    assert node.timestamp == 12.0
    assert node.value == 0.7          # magnitude → value


def test_make_action_node_none_magnitude_maps_to_none_value():
    node = make_action_node(ActionEvent(id="a2", label="Opened app", timestamp=3.0))
    assert node.value is None
    assert node.timestamp == 3.0
    assert node.type == "action"


def test_action_node_always_has_timestamp():
    # Even a zero timestamp is a real timestamp (not None).
    node = make_action_node(ActionEvent(id="a4", label="x", timestamp=0.0))
    assert node.timestamp is not None
    assert node.timestamp == 0.0


def test_deterministic_mapping():
    e = ActionEvent(id="a1", label="x", timestamp=5.0, magnitude=0.3)
    assert make_action_node(e) == make_action_node(deepcopy(e))


def test_no_side_effects_on_event():
    e = ActionEvent(id="a1", label="x", timestamp=5.0, magnitude=0.3)
    before = asdict(e)
    make_action_node(e)
    assert asdict(e) == before        # the source event is never mutated


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_json_serializable_output():
    e = ActionEvent(id="a1", label="Opened app", timestamp=5.0)
    json.dumps(asdict(e))                          # ActionEvent
    json.dumps(asdict(make_action_node(e)))        # the action CausalNode
