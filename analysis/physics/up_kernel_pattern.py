"""UP^ pattern binder — pure rename binder from the v52.2 M1/M3 summary
shape to the canonical schema shape.

See analysis/physics/up_kernel_spec.md and
analysis/schema/up_kernel_schema.json for the target field set.

The v52.2 M1/M3 summary uses prefix-form names (``M1_beta_E``,
``M3_p_int``, ``pattern_id``, ``DV``); the kernel schema uses suffix-form
names (``beta_E_M1``, ``p_int_M3``, ``pattern_code``, ``dv_name``). This
module is the single rename boundary — values flow through unchanged.

Pure module: stdlib only, no ELINS imports, no computation, no transforms,
no inference.
"""

from __future__ import annotations

from typing import Any, Dict

# v52.2 M1/M3 summary key  ->  canonical schema key.
# Mapping is intentionally explicit and total: missing any key fails loudly
# rather than silently dropping fields.
_V52_2_TO_SCHEMA: Dict[str, str] = {
    "DV":             "dv_name",
    "pattern_id":     "pattern_code",
    "M1_beta_E":      "beta_E_M1",
    "M1_p_E":         "p_E_M1",
    "M3_beta_E":      "beta_E_M3",
    "M3_p_E":         "p_E_M3",
    "M3_beta_int":    "beta_int_M3",
    "M3_p_int":       "p_int_M3",
    "perm_p_M1_E":    "perm_p_M1_E",
    "perm_p_M3_int":  "perm_p_M3_int",
    "interpretation": "interpretation",
}


def bind_patterns(
    dv_vector: Dict[str, Any],
    m123_row: Dict[str, Any],
) -> Dict[str, Any]:
    """Bind pattern stats from a v52.2 M1/M3 summary row to the schema shape.

    The DV vector is consulted purely as a presence-check anchor: a row
    can only be emitted for a DV that the region actually carries.

    Args:
        dv_vector: output of ``build_up_kernel_vector``.
        m123_row: a v52.2 M1/M3 summary row dict for one DV.

    Returns:
        A new dict with the eleven canonical schema fields, values copied
        verbatim from ``m123_row``.

    Raises:
        TypeError: either argument is not a mapping.
        KeyError: any required v52.2 key is missing, or the DV named in
            ``m123_row['DV']`` is not in ``dv_vector``.
    """
    if not isinstance(dv_vector, dict):
        raise TypeError(
            f"dv_vector must be a dict; got {type(dv_vector).__name__}"
        )
    if not isinstance(m123_row, dict):
        raise TypeError(
            f"m123_row must be a dict; got {type(m123_row).__name__}"
        )

    missing = [src for src in _V52_2_TO_SCHEMA if src not in m123_row]
    if missing:
        raise KeyError(f"m123 row is missing required keys: {missing}")

    dv_name = m123_row["DV"]
    if dv_name not in dv_vector:
        raise KeyError(
            f"m123_row['DV']={dv_name!r} is not present in the DV vector "
            f"(available: {sorted(dv_vector.keys())})"
        )

    return {dst: m123_row[src] for src, dst in _V52_2_TO_SCHEMA.items()}
