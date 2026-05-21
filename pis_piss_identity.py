"""
pis_piss_identity.py — Phase 13 PIS / PISS dual-surface identity layer.

Pure stdlib. Three public functions:

    describe_pis()        -> dict
        Static description of the Personal Intelligence System
        (internal OS: math, posture, identity, trust, stability).

    describe_piss()       -> dict
        Static description of the Personal Intelligence Surfaces Stack
        (external surfaces: routes, dashboards, consoles, public
        interfaces).

    summarize_pis_piss()  -> dict
        Combined structure suitable for a single founder dashboard.
        Carries both halves plus a relationship block and notes[].

Contract per tests/acceptance/pis_piss_identity.md:
    - read-only;
    - never raises (returns empty dicts + descriptive notes on failure);
    - takes no parameters (the layer is purely taxonomic);
    - never persists.

The descriptions are deliberately stable. Adding a new component to
PIS or a new surface to PISS does not require updating this file —
the top-level taxonomy holds. Update only when a section header
itself changes.
"""
from __future__ import annotations

from typing import Any


_PIS_DESCRIPTION = {
    "name":    "PIS",
    "expanded": "Personal Intelligence System",
    "purpose": (
        "Internal OS that owns the math, posture, identity, trust, "
        "stability, vault, and continuity layers. Versioned and "
        "stable; amendments are additive."
    ),
    "components": [
        "kernel (analysis/physics/up_kernel_spec.md)",
        "contracts (UP_M123_CONTRACT_v1.0.0 / v1.1.0 / v2.0.0)",
        "alternator registry (gated, region, library)",
        "paired sign-flip permutation engine",
        "stability_math + run_quality + trust_center_math + narrative_drift",
        "identity_engine (Phase 8 coherence layer)",
        "surfaces_unification (Phase 10)",
        "operator_mode (Phase 11)",
        "launch_readiness (Phase 12)",
        "vault snapshot store (per-session)",
        "continuity_reentry (cold-start hydration)",
        "cross_surface_continuity (single entrypoint)",
        "runtime scheduler (cadence + macro passes)",
    ],
    "guarantees": [
        "public function signatures are versioned",
        "amendments are additive — no silent retraction",
        "frozen artefacts are never overwritten by runtime",
        "every record carries a contract_version reference",
        "PIS is unaware of PISS — never special-cases for a surface",
    ],
    "boundaries": [
        "no user-level personalization",
        "no recommendations or rankings",
        "no automation that mutates external state",
        "no marketing copy",
        "no inference without preregistration of the analysis",
    ],
}


_PISS_DESCRIPTION = {
    "name":    "PISS",
    "expanded": "Personal Intelligence Surfaces Stack",
    "purpose": (
        "External surface stack that consumes PIS outputs. Owns "
        "founder routes, public site, phone screens, desktop "
        "initiator/GUI, chat surface, and operator console. "
        "Evolvable; new surfaces ship without touching PIS internals."
    ),
    "surfaces": [
        "web — web/src/routes/* (founder console + dashboards)",
        "phone — phone/app/* (Expo screens)",
        "desktop — _scratch/clarityos_desktop_initiator.py + clarityos_desktop_ui.py",
        "chat — _scratch/clarityos_chat_ui.py",
        "launch entrypoint — _scratch/clarityos_launch.py",
        "founder dashboards — /founder/{acceptance,analytics,telemetry,identity,console,surfaces,operator,launch,identity/pis-piss}",
        "verification banners — ?verify=1 annotation across all founder routes",
    ],
    "guarantees": [
        "consumes PIS via public function surface only",
        "never bypasses the contract",
        "never writes back into PIS state",
        "every payload faithfully reflects PIS-computed values",
        "wholesale replacement of PISS does not touch PIS",
    ],
    "boundaries": [
        "no inference",
        "no math beyond rendering (gauges, tables, layouts)",
        "no behavioral gating",
        "no automation",
        "no user-level personalization",
    ],
}


_RELATIONSHIP = {
    "directionality": "PIS → PISS only. PISS never writes back into PIS state.",
    "shared_concepts": [
        {"concept": "telemetry",         "source": "trust_center_math + narrative_drift", "surface": "/founder/telemetry"},
        {"concept": "readiness",         "source": "launch_readiness",                    "surface": "/founder/launch"},
        {"concept": "posture",           "source": "operator_mode",                       "surface": "/founder/operator"},
        {"concept": "identity_coherence","source": "identity_engine",                     "surface": "/founder/identity"},
        {"concept": "surface_coherence", "source": "surfaces_unification",                "surface": "/founder/surfaces"},
        {"concept": "pis_piss_taxonomy", "source": "pis_piss_identity (this module)",     "surface": "/founder/identity/pis-piss"},
    ],
    "load_bearing_property": (
        "PISS can be replaced wholesale (different framework, "
        "different OS, different visual language) without touching "
        "PIS. PIS produces the same outputs regardless of which "
        "surface renders them."
    ),
}


def describe_pis() -> dict:
    """Return the static description of the Personal Intelligence System."""
    try:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _PIS_DESCRIPTION.items()}
    except Exception:
        return {
            "name":    "PIS",
            "expanded": "Personal Intelligence System",
            "purpose": "no description available",
            "components": [],
            "guarantees": [],
            "boundaries": [],
        }


def describe_piss() -> dict:
    """Return the static description of the Personal Intelligence Surfaces Stack."""
    try:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _PISS_DESCRIPTION.items()}
    except Exception:
        return {
            "name":    "PISS",
            "expanded": "Personal Intelligence Surfaces Stack",
            "purpose": "no description available",
            "surfaces": [],
            "guarantees": [],
            "boundaries": [],
        }


def summarize_pis_piss() -> dict:
    """Return the combined PIS / PISS structure for a single dashboard."""
    notes: list[str] = []
    try:
        pis = describe_pis()
    except Exception:
        pis = {}
        notes.append("describe_pis raised — returned empty")
    try:
        piss = describe_piss()
    except Exception:
        piss = {}
        notes.append("describe_piss raised — returned empty")
    try:
        rel = {k: (list(v) if isinstance(v, list) else v) for k, v in _RELATIONSHIP.items()}
    except Exception:
        rel = {}
        notes.append("relationship structure raised — returned empty")
    return {
        "pis":          pis,
        "piss":         piss,
        "relationship": rel,
        "notes":        notes,
    }
