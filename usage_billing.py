"""
Usage billing arithmetic — reserve / settle, in micro-dollars.

★★★ THE INVARIANT (CT-1, 2026-08-26)

        purchase value = use value x 1.20

    where "use value" is the TOTAL cost of service: vendor tokens PLUS the
    service cost of running the call. The service cost sits INSIDE the
    multiply, not after it. Adding it afterwards is what made the ratio
    drift off 1.20 in the first draft:

        WRONG   debited = vendor x 1.20 + service   ->  ratio never 1.20
        RIGHT   debited = (vendor + service) x 1.20 ->  ratio exactly 1.20

    ``debit_for`` is the single function that implements it, and
    ``check_invariant`` is the assertion the acceptance gate runs.

NO FLOATS. Ever. The whole path is integer arithmetic:

    pico-dollars (1e-6 µ$)  — the working unit. tokens x micro_per_million
                              lands here exactly, with no division.
    micro-dollars (µ$)      — the ledger unit. Reached by exactly ONE
                              rounding step, in ``_quantize_cost``.

★★ ROUND ONCE. The retired draft rounded up at reserve AND at settle; that
   double-round is what broke the invariant. Reserve is computed on the same
   scale and is reconciled by the settle delta, so it never needs its own
   rounding decision to be "safe" — being slightly off is exactly what the
   delta exists to fix.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import usage_rates

logger = logging.getLogger("clarityos.usage_billing")

PICO_PER_MICRO = 1_000_000


# ===========================================================================
# Usage — what the vendor says it actually consumed.
# ===========================================================================
class Usage:
    """One vendor call's reported token usage.

    ``cached`` is prompt tokens served from the vendor's prompt cache; they
    bill at the cached rate. ``prompt`` is the UNCACHED remainder — callers
    must not include cached tokens in it, and ``from_vendor`` guarantees
    that for every provider it knows.
    """

    __slots__ = ("prompt", "completion", "cached", "model_id", "provider", "estimated")

    def __init__(self, *, prompt: int = 0, completion: int = 0, cached: int = 0,
                 model_id: str = "", provider: str = "", estimated: bool = False):
        self.prompt = max(0, int(prompt))
        self.completion = max(0, int(completion))
        self.cached = max(0, int(cached))
        self.model_id = model_id
        self.provider = provider
        # True when these numbers came from our own estimate rather than the
        # vendor's response. Recorded so a later audit can tell measured
        # usage from guessed usage.
        self.estimated = bool(estimated)

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt,
            "completion_tokens": self.completion,
            "cached_tokens": self.cached,
            "model_id": self.model_id,
            "provider": self.provider,
            "estimated": self.estimated,
        }

    def __add__(self, other: "Usage") -> "Usage":
        """Sum two calls' usage. ★ This is how the retry leak is closed:
        a #cite turn that fired twice adds both calls before settling, so
        the member is billed for one turn at cost+20%, not for two."""
        return Usage(
            prompt=self.prompt + other.prompt,
            completion=self.completion + other.completion,
            cached=self.cached + other.cached,
            model_id=self.model_id or other.model_id,
            provider=self.provider or other.provider,
            estimated=self.estimated or other.estimated,
        )

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return (f"Usage(prompt={self.prompt}, completion={self.completion}, "
                f"cached={self.cached}, model_id={self.model_id!r}, "
                f"estimated={self.estimated})")


def extract_usage(raw: Any, provider: str, model_id: str) -> Optional[Usage]:
    """Pull the vendor's own usage block out of a raw provider response.

    ★ Read from the VENDOR's numbers, never from our estimate. Returns None
    when the response carries no usage block, which is the honest answer for
    a mock/stub result — the caller then decides whether to fall back to an
    estimate and marks it ``estimated=True``.

    OpenAI chat-completions:
        usage.prompt_tokens              (INCLUDES cached)
        usage.completion_tokens
        usage.prompt_tokens_details.cached_tokens

    Anthropic messages:
        usage.input_tokens               (EXCLUDES cache reads)
        usage.output_tokens
        usage.cache_read_input_tokens
        usage.cache_creation_input_tokens

    ★★ The two vendors disagree on whether the prompt count includes the
    cached tokens. OpenAI's does; Anthropic's does not. Getting this
    backwards double-bills the cache on one provider and under-bills it on
    the other, so each is handled explicitly rather than generically.

    ★ ANTHROPIC PARSING IS UNVERIFIED against a live response — there is no
    Anthropic key in the build environment. The shape below is from the
    published API; it has not been confirmed against a real call.
    """
    if not isinstance(raw, dict):
        return None
    u = raw.get("usage")
    if not isinstance(u, dict):
        return None

    if provider == "openai":
        total_prompt = int(u.get("prompt_tokens") or 0)
        details = u.get("prompt_tokens_details")
        cached = int((details or {}).get("cached_tokens") or 0) if isinstance(details, dict) else 0
        # OpenAI's prompt_tokens INCLUDES cached tokens; subtract so the two
        # line items don't overlap. Clamp in case the vendor ever reports
        # cached > prompt.
        cached = min(cached, total_prompt)
        return Usage(prompt=total_prompt - cached, completion=int(u.get("completion_tokens") or 0),
                     cached=cached, model_id=model_id, provider=provider)

    if provider == "anthropic":
        # Anthropic's input_tokens EXCLUDES cache reads — do not subtract.
        # Cache *creation* tokens bill at a premium on Anthropic; we treat
        # them as ordinary input, which over-recovers slightly rather than
        # under-recovering. Fail toward charging.
        cache_read = int(u.get("cache_read_input_tokens") or 0)
        cache_create = int(u.get("cache_creation_input_tokens") or 0)
        return Usage(prompt=int(u.get("input_tokens") or 0) + cache_create,
                     completion=int(u.get("output_tokens") or 0),
                     cached=cache_read, model_id=model_id, provider=provider)

    logger.warning("usage_billing no usage parser for provider=%r", provider)
    return None


# ===========================================================================
# The arithmetic.
# ===========================================================================
def cost_pico(usage: Usage) -> int:
    """Exact cost of service in pico-dollars: vendor tokens + service cost.

    This is the denominator of the invariant. Integer throughout — each
    ``tokens x micro_per_million`` term is already in pico-dollars, so
    nothing is divided and nothing is rounded here.
    """
    r = usage_rates.rate_for(usage.model_id)
    vendor = (usage.prompt * r["input"]
              + usage.cached * r["cached"]
              + usage.completion * r["output"])
    service = usage_rates.service_micro_per_call() * PICO_PER_MICRO
    return vendor + service


def vendor_cost_pico(usage: Usage) -> int:
    """Vendor tokens only, no service cost. Reported alongside the total in
    the gate-0 table so the arithmetic is auditable."""
    r = usage_rates.rate_for(usage.model_id)
    return (usage.prompt * r["input"]
            + usage.cached * r["cached"]
            + usage.completion * r["output"])


def _quantize_cost(pico: int) -> int:
    """The ONE rounding step: pico-dollars -> micro-dollars.

    ★ Quantized to a multiple of MARKUP_DEN (5 µ$) so that applying the 6/5
    markup is an EXACT integer operation and the ratio is exactly 1.20 by
    construction, not 1.2000077 after a stray remainder. CT-1's gate says
    "not about" — this is what makes that literally true rather than true
    to two decimal places.

    The quantum is 5 µ$ = $0.000005. On a typical ~10,100 µ$ turn that is a
    5e-4 relative error, an order of magnitude below the cent resolution the
    unit change was adopted to escape. Rounds half-up, and never below zero.
    """
    den = usage_rates.MARKUP_DEN
    quantum = den * PICO_PER_MICRO
    # Round half-up to the nearest whole quantum, then express in µ$.
    quanta = (pico + quantum // 2) // quantum
    return max(0, quanta * den)


def debit_for(usage: Usage) -> int:
    """★★★ The invariant, in one place. Cost of service, marked up 20%.

    Returns µ$ to debit. Exactly ``cost x 6 / 5`` with no remainder,
    because ``_quantize_cost`` guarantees the cost is a multiple of 5.
    """
    cost_micro = _quantize_cost(cost_pico(usage))
    assert cost_micro % usage_rates.MARKUP_DEN == 0, "quantize invariant broken"
    return cost_micro // usage_rates.MARKUP_DEN * usage_rates.MARKUP_NUM


def cost_micro(usage: Usage) -> int:
    """The quantized cost of service in µ$ — the invariant's denominator."""
    return _quantize_cost(cost_pico(usage))


def check_invariant(usage: Usage) -> tuple[int, int, bool]:
    """Return ``(cost_micro, debited_micro, holds)``.

    ``holds`` is True iff ``debited * 5 == cost * 6`` — an exact integer
    identity, not a float comparison against 1.2. This is the assertion the
    acceptance gate runs on every row.
    """
    c = cost_micro(usage)
    d = debit_for(usage)
    return c, d, (d * usage_rates.MARKUP_DEN == c * usage_rates.MARKUP_NUM)


# ===========================================================================
# Reserve / settle.
# ===========================================================================
def reserve_for(model_id: str, input_tokens: int, max_output_tokens: int = 0) -> int:
    """Reserve, in µ$, computed BEFORE the call from the assembled prompt
    and the output ceiling.

    ★★ THE ORDER SPECIFIED INPUT ONLY, AND THAT UNDER-RESERVES.
    ``reserve = in_tokens x in_rate x 1.20`` looks right because input is
    most of the TOKENS — but output is priced 8x higher ($10/M vs $1.25/M
    on gpt-5.4), so it is usually most of the COST. Measured: a 402-token
    prompt with a 96-token completion reserved 948 µ$ and settled at
    1,878 µ$ — the reserve covered barely half the bill, and the whole
    point of reserving is that the member cannot start compute they cannot
    afford.

    ``max_output_tokens`` IS knowable before dispatch (the router passes
    max_tokens on every call), so it is included at the output rate. Actual
    output is always <= the ceiling, so this over-reserves and the excess
    comes back as a negative delta at settle. Reserve high, settle true.

    Input is charged at the UNCACHED rate for the same reason: at reserve
    time we do not know what the vendor will serve from cache, and
    reserving at the cached rate would under-reserve every cache miss.
    """
    return debit_for(Usage(
        prompt=max(0, int(input_tokens)),
        completion=max(0, int(max_output_tokens)),
        model_id=model_id,
    ))


def settle_delta(model_id: str, usage: Usage, reserved: int) -> int:
    """``settle - reserve`` in µ$.

    Positive means the member owes more (debit the difference under a
    derived idempotency key); negative means we over-reserved (refund the
    difference). Zero means the reserve was exact and nothing moves.
    """
    return debit_for(usage) - int(reserved)


def describe(usage: Usage, reserved: Optional[int] = None) -> dict:
    """A full, auditable breakdown of one settle. Used by the usage record,
    the founder view, and the acceptance table."""
    r = usage_rates.rate_for(usage.model_id)
    v_pico = vendor_cost_pico(usage)
    c = cost_micro(usage)
    d = debit_for(usage)
    out = {
        "model_id": usage.model_id,
        "provider": usage.provider,
        "rates_micro_per_million": dict(r),
        "prompt_tokens": usage.prompt,
        "cached_tokens": usage.cached,
        "completion_tokens": usage.completion,
        "estimated": usage.estimated,
        # Line items, in µ$, so a cached call visibly shows the discount.
        "line_items_micro": {
            "input":  usage.prompt * r["input"] // PICO_PER_MICRO,
            "cached": usage.cached * r["cached"] // PICO_PER_MICRO,
            "output": usage.completion * r["output"] // PICO_PER_MICRO,
        },
        "vendor_micro": v_pico // PICO_PER_MICRO,
        "service_micro": usage_rates.service_micro_per_call(),
        "total_cost_micro": c,
        "debited_micro": d,
        "markup": f"{usage_rates.MARKUP_NUM}/{usage_rates.MARKUP_DEN}",
        "invariant_holds": d * usage_rates.MARKUP_DEN == c * usage_rates.MARKUP_NUM,
    }
    if reserved is not None:
        out["reserved_micro"] = int(reserved)
        out["delta_micro"] = d - int(reserved)
    return out


# ===========================================================================
# Display.
# ===========================================================================
def micro_to_dollars(micro: int) -> str:
    """Format µ$ as a dollar string. ★ The ledger is µ$; the member sees
    dollars. "One credit is one penny paid" is unchanged — a penny is
    exactly 10,000 units."""
    # #142 -- floored to the cent; a sub-cent figure reads $0.00 with NO
    # sign (a sign on nothing asserts a direction the cent cannot show).
    cents = abs(int(micro)) // 10_000
    sign = "-" if (micro < 0 and cents > 0) else ""
    return f"{sign}${cents // 100}.{cents % 100:02d}"
