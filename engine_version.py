# engine_version.py
"""
ClarityOS operator-intelligence engine — release version marker.

This is the version of the **engine cohort** (the operator-intelligence stack,
Phases 1–12: runtime, telemetry, continuity, operator state, temporal, causal,
behavioral, forecasting, recommendations, hardening). It is intentionally
*separate* from the deployed ClarityOS Cloud product version reported by
``app.py`` (4.x line); the engine cohort versions on its own semantic line and
this constant must never overwrite the product version.

Pure constants — no logic, no I/O, no wall-clock, no randomness. Importing this
module has no side effects.

See ``/release/notes/v1.0.0-rc1.md`` and ``/spec/clarityos_spec_v1.md``.
"""

# Semantic version of the engine cohort (NOT the ClarityOS Cloud product).
ENGINE_VERSION = "1.0.0-rc1"

# The repository tag that marks this release candidate (engine-scoped).
ENGINE_RELEASE_TAG = "engine-operator-v1.0.0-rc1"

# Human-readable scope of the cohort this version covers.
ENGINE_PHASES = (
    "Phases 1-12 — runtime, telemetry, continuity, operator state, temporal, "
    "causal, behavioral, forecasting, recommendations, hardening"
)
