"""UP^ DV vector builder — pure selector over a region-metrics row.

See analysis/physics/up_kernel_spec.md for the canonical DV definitions
and the operator's role. This module performs **no computation, no
transforms, no inference, and no ELINS imports**. It is a pure selector
that copies the five canonical UP^ DV values out of a region-metrics
row already produced by the v52.2 backend (ELINS/region_metrics.py).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

UP_KERNEL_DVS: Tuple[str, ...] = (
    "delta_total_weight",
    "delta_mean_edge",
    "delta_pct_total",
    "delta_inv_weight",
    "delta_pct_total_weak",
)


def build_up_kernel_vector(row: Dict[str, Any]) -> Dict[str, Any]:
    """Select the five canonical UP^ DVs from a region-metrics row.

    Values are copied verbatim — no scaling, no recomputation, no
    defaulting, no fallback. Output key order matches ``UP_KERNEL_DVS``.

    Raises:
        TypeError: ``row`` is not a mapping.
        KeyError: any of the five DVs is missing from ``row``.
    """
    if not isinstance(row, dict):
        raise TypeError(f"row must be a dict; got {type(row).__name__}")
    missing = [k for k in UP_KERNEL_DVS if k not in row]
    if missing:
        raise KeyError(f"region-metrics row is missing UP^ DVs: {missing}")
    return {k: row[k] for k in UP_KERNEL_DVS}
