"""UP^ kernel row constructor — combines the DV selector and the pattern
binder and validates the result against the JSON schema.

See analysis/physics/up_kernel_spec.md and
analysis/schema/up_kernel_schema.json.

Pure module: stdlib only, no ELINS imports, no computation, no transforms,
no inference. The schema is loaded once at import; validation reads only
the constraints the schema actually declares (``type``, ``enum``,
``minimum``, ``maximum``, ``required``, ``additionalProperties``).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .up_kernel_pattern import bind_patterns
from .up_kernel_vector import build_up_kernel_vector

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "schema", "up_kernel_schema.json")
)

with open(_SCHEMA_PATH, "r", encoding="utf-8") as _fh:
    _SCHEMA: Dict[str, Any] = json.load(_fh)


# bool is a subclass of int in Python; exclude it explicitly so that
# `True` / `False` cannot satisfy "integer" or "number" by accident.
_TYPE_CHECKERS = {
    "string":  lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number":  lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _validate_against_schema(row: Dict[str, Any], schema: Dict[str, Any]) -> None:
    if schema.get("type") == "object" and not isinstance(row, dict):
        raise ValueError(f"row must be an object; got {type(row).__name__}")

    properties = schema.get("properties", {})

    for k in schema.get("required", []):
        if k not in row:
            raise ValueError(f"row missing required field: {k}")

    if schema.get("additionalProperties") is False:
        extras = [k for k in row if k not in properties]
        if extras:
            raise ValueError(f"row contains keys not in schema: {extras}")

    for k, v in row.items():
        prop = properties.get(k)
        if prop is None:
            continue

        ptype = prop.get("type")
        if ptype is not None:
            check = _TYPE_CHECKERS.get(ptype)
            if check is None:
                raise ValueError(
                    f"schema property {k!r} declares unsupported type {ptype!r}"
                )
            if not check(v):
                raise ValueError(
                    f"row[{k!r}]={v!r} does not satisfy schema type {ptype!r}"
                )

        enum = prop.get("enum")
        if enum is not None and v not in enum:
            raise ValueError(
                f"row[{k!r}]={v!r} is not in schema enum {enum!r}"
            )

        if "minimum" in prop and v < prop["minimum"]:
            raise ValueError(
                f"row[{k!r}]={v!r} is below schema minimum {prop['minimum']}"
            )
        if "maximum" in prop and v > prop["maximum"]:
            raise ValueError(
                f"row[{k!r}]={v!r} is above schema maximum {prop['maximum']}"
            )


def make_up_kernel_row(
    region_metrics_row: Dict[str, Any],
    m123_row: Dict[str, Any],
) -> Dict[str, Any]:
    """Build one schema-conforming UP^ kernel row from v52.2 inputs.

    Pipeline:
        1. ``build_up_kernel_vector(region_metrics_row)`` selects the five DVs.
        2. ``bind_patterns(dv_vector, m123_row)`` renames v52.2 stats to
           canonical schema names, gated on DV presence.
        3. The resulting row is validated against
           ``analysis/schema/up_kernel_schema.json``.

    Args:
        region_metrics_row: a v52.2 region-metrics row carrying the five
            UP^ DVs.
        m123_row: a v52.2 M1/M3 summary row for one of those DVs.

    Returns:
        A new dict matching ``up_kernel_schema.json``.

    Raises:
        TypeError, KeyError: from the selector or the binder.
        ValueError: if the assembled row fails schema validation.
    """
    dv_vector = build_up_kernel_vector(region_metrics_row)
    row = bind_patterns(dv_vector, m123_row)
    _validate_against_schema(row, _SCHEMA)
    return row
