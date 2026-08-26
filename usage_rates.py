"""
Vendor rate table + service-cost config for usage billing.

★ Rates are CONFIG, never hardcoded at a call site. They changed twice this
year; a rate change must be a config edit, not a code edit.

UNITS — everything is an integer. There are no floats in this module and
none in the ledger.

    1 unit = 1 micro-dollar (µ$) = $0.000001
    1,000,000 µ$ = $1.00        10,000 µ$ = 1 cent

Vendor rates are published per MILLION tokens, so we store them exactly that
way: ``micro_per_million`` is the µ$ charged for 1,000,000 tokens. That makes
``tokens x micro_per_million`` an exact integer in PICO-dollars (1e-6 µ$),
which is the working unit inside usage_billing. No division, no float, no
precision loss until the single rounding step at settle.

    $1.25 / M tokens  ->  micro_per_million = 1_250_000

Every rate is overridable from the environment so a price change can ship
without a deploy:

    CLARITYOS_RATE__OPENAI_GPT_5_4__INPUT   = 1250000
    CLARITYOS_RATE__OPENAI_GPT_5_4__CACHED  = 125000
    CLARITYOS_RATE__OPENAI_GPT_5_4__OUTPUT  = 10000000
    CLARITYOS_SERVICE_MICRO_PER_CALL        = 100
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.usage_rates")

# --------------------------------------------------------------------------
# Markup — CT-1's invariant, as an exact rational. Never a float.
#
#     purchase value = use value x 1.20   ==   x 6/5
#
# Kept as a numerator/denominator pair so the multiplication stays in
# integer arithmetic end to end.
# --------------------------------------------------------------------------
MARKUP_NUM = 6
MARKUP_DEN = 5

# --------------------------------------------------------------------------
# Service cost — our cost to serve one call, in µ$, INSIDE the markup.
#
# CT-1 correction 2026-08-26: this is a cost of service (Firestore reads and
# writes, Cloud Run CPU-seconds, amortized Stripe fees), not an add-on fee.
# It goes in the denominator with the vendor tokens, then the whole sum is
# marked up. Adding it after the multiply is what made the ratio drift off
# 1.20 in the first draft.
#
# 100 µ$ = $0.0001 per call. Deliberately conservative: a Firestore write
# is ~$0.0000018 and a Cloud Run CPU-second is ~$0.000024, so this covers a
# double-digit multiple of the real per-call infra draw.
# --------------------------------------------------------------------------
_DEFAULT_SERVICE_MICRO_PER_CALL = 100


def _env_int(name: str) -> Optional[int]:
    """Read an integer override. A malformed value is ignored with a warning
    rather than crashing the billing path — a bad env var must not take the
    meter offline."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        logger.warning("usage_rates ignoring non-integer override %s=%r", name, raw)
        return None


def service_micro_per_call() -> int:
    v = _env_int("CLARITYOS_SERVICE_MICRO_PER_CALL")
    if v is None:
        return _DEFAULT_SERVICE_MICRO_PER_CALL
    return max(0, v)


# --------------------------------------------------------------------------
# Rate table. Keys are full model ids as the router emits them
# ("<provider>:<wire_model>"). Values are µ$ per 1,000,000 tokens.
#
#   input   — uncached prompt tokens
#   cached  — prompt tokens served from the vendor's prompt cache
#   output  — completion tokens
#
# ★ cached MUST be billed at the cached rate. The transcript is the same
#   prefix every turn, so cache hits are the normal case, not the exception.
#   Charging full price for cached input bills members for a discount they
#   never received.
# --------------------------------------------------------------------------
_RATES: dict[str, dict[str, int]] = {
    # OpenAI gpt-5.4 — cached input is 10% of input.
    "openai:gpt-5.4": {
        "input":   1_250_000,     # $1.25 / M
        "cached":    125_000,     # $0.125 / M  (10%)
        "output":  10_000_000,    # $10.00 / M
    },
    "openai:gpt-5.4-mini": {
        "input":     250_000,     # $0.25 / M
        "cached":     25_000,     # $0.025 / M
        "output":  2_000_000,     # $2.00 / M
    },
    # Anthropic Haiku 4.5 — cache read is 10% of input (a 90% discount).
    # ★ These rates are configured but the PARSING of Anthropic's usage
    #   block is UNVERIFIED against a live response — no Anthropic key in
    #   the build environment. See usage_billing.extract_usage.
    "anthropic:claude-haiku-4-5-20251001": {
        "input":   1_000_000,     # $1.00 / M
        "cached":    100_000,     # $0.10 / M   (10%)
        "output":  5_000_000,     # $5.00 / M
    },
}

# Charged when a model id is not in the table. Deliberately the most
# expensive row we carry, so an unpriced model over-recovers rather than
# silently serving compute for free. Fail toward charging, never toward
# a free lunch on an unknown model.
_UNKNOWN_MODEL_RATE = {
    "input":   1_250_000,
    "cached":    125_000,
    "output":  10_000_000,
}


def rate_for(model_id: str) -> dict[str, int]:
    """Return {input, cached, output} in µ$ per million tokens.

    Env overrides win over the table. The override name is derived from the
    model id: non-alphanumerics become underscores and the whole thing is
    upper-cased, e.g.

        openai:gpt-5.4 input -> CLARITYOS_RATE__OPENAI_GPT_5_4__INPUT
    """
    base = _RATES.get(model_id)
    if base is None:
        logger.warning("usage_rates no rate for model_id=%r; using fallback", model_id)
        base = _UNKNOWN_MODEL_RATE
    slug = "".join(c if c.isalnum() else "_" for c in model_id).upper()
    out: dict[str, int] = {}
    for kind, default in base.items():
        override = _env_int(f"CLARITYOS_RATE__{slug}__{kind.upper()}")
        out[kind] = default if override is None else max(0, override)
    return out


def known_models() -> tuple[str, ...]:
    """Model ids carried in the table. Used by the founder rate view."""
    return tuple(sorted(_RATES))
