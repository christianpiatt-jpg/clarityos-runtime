"""
runtime_http_config.py — Unit 71 / v66.

Leaf configuration module for per-provider HTTP behaviour. Houses the
two timeout maps (call-path vs health-check) and the retry-count map
so production code, tests, and future tuning all consult the same
source.

DESIGN
------
Two timeout flavours are kept distinct because they answer different
questions:

    PROVIDER_CALL_TIMEOUTS     — generous (30s) for real operator
                                 inference calls; a 1-token completion
                                 across the public internet can easily
                                 take >10s when providers are warming
                                 cold instances.

    PROVIDER_HEALTH_TIMEOUTS   — tight (3s) for the /runtime/providers/
                                 health probe; the goal is "is the
                                 provider reachable", not "do I get a
                                 useful reply". 3s catches outages
                                 fast without inflating the UI spinner.

Pre-Unit-71 both values existed but were scattered:
    * model_router._PROVIDER_HTTP_TIMEOUT = 30.0    (call path)
    * runtime_http._PROVIDER_HEALTH_TIMEOUT = 3.0   (health-check
      override, monkey-patched onto model_router)

Unit 71 keeps the same default values; the behaviour change is purely
that both are now sourced from one place and addressable per provider.

NO TOP-OF-FILE IMPORTS FROM model_router / runtime_http
--------------------------------------------------------
This module is a **leaf**. Both ``model_router`` and ``runtime_http``
import it. If this module imported either of those back, the system
would deadlock on initial import. Tests verify the no-back-import
invariant.

PUBLIC SURFACE
--------------
    PROVIDER_CALL_TIMEOUTS    : dict[str, float]
    PROVIDER_HEALTH_TIMEOUTS  : dict[str, float]
    PROVIDER_RETRIES          : dict[str, int]
    DEFAULT_CALL_TIMEOUT      : float
    DEFAULT_HEALTH_TIMEOUT    : float
    DEFAULT_RETRIES           : int

    get_call_timeout(provider)   -> float
    get_health_timeout(provider) -> float
    get_retry_count(provider)    -> int

The getter functions accept either a known provider name, an unknown
provider name, or ``None``. In every case they return a finite number
— the corresponding ``DEFAULT_*`` value — so callers never need to
guard against missing keys.
"""
from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Defaults
#
# These match the pre-Unit-71 in-line constants exactly. Behaviour is
# preserved; only the addressing changes.
# ---------------------------------------------------------------------------
DEFAULT_CALL_TIMEOUT: float = 30.0
DEFAULT_HEALTH_TIMEOUT: float = 3.0
DEFAULT_RETRIES: int = 0


# ---------------------------------------------------------------------------
# Per-provider maps
#
# Keys match the provider strings used throughout model_router /
# runtime_http (``anthropic``, ``openai``, ``gemini``, ``xai``,
# ``local``). The synthetic ``mock`` provider doesn't appear here —
# it never makes an HTTP request.
# ---------------------------------------------------------------------------
PROVIDER_CALL_TIMEOUTS: dict[str, float] = {
    "anthropic": 30.0,
    "openai":    30.0,
    "gemini":    30.0,
    "xai":       30.0,
    "local":     30.0,
}

PROVIDER_HEALTH_TIMEOUTS: dict[str, float] = {
    "anthropic": 3.0,
    "openai":    3.0,
    "gemini":    3.0,
    "xai":       3.0,
    "local":     3.0,
}

PROVIDER_RETRIES: dict[str, int] = {
    "anthropic": 0,
    "openai":    0,
    "gemini":    0,
    "xai":       0,
    "local":     0,
}


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------
def get_call_timeout(provider: Optional[str]) -> float:
    """Return the per-provider call-path timeout in seconds.

    Unknown / ``None`` providers receive ``DEFAULT_CALL_TIMEOUT`` so
    callers never need to guard against missing keys.
    """
    if provider is None:
        return DEFAULT_CALL_TIMEOUT
    return PROVIDER_CALL_TIMEOUTS.get(provider, DEFAULT_CALL_TIMEOUT)


def get_health_timeout(provider: Optional[str]) -> float:
    """Return the per-provider health-check timeout in seconds.

    Unknown / ``None`` providers receive ``DEFAULT_HEALTH_TIMEOUT``.
    """
    if provider is None:
        return DEFAULT_HEALTH_TIMEOUT
    return PROVIDER_HEALTH_TIMEOUTS.get(provider, DEFAULT_HEALTH_TIMEOUT)


def get_retry_count(provider: Optional[str]) -> int:
    """Return the per-provider retry budget. Currently 0 across the
    board; the knob exists so the policy can be tuned without touching
    every call site.
    """
    if provider is None:
        return DEFAULT_RETRIES
    return PROVIDER_RETRIES.get(provider, DEFAULT_RETRIES)
