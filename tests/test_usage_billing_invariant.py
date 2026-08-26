"""
v56 usage billing — the invariant and the three leaks, as regression tests.

★★★ GATE 0 lives here. ``purchase value = use value x 1.20``, where use
value is the TOTAL cost of service (vendor tokens + service cost). It is
asserted as an exact integer identity -- ``debited * 5 == cost * 6`` -- and
never as a float comparison against 1.2, because "about 1.20" is precisely
the claim CT-1 refused to publish.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import pytest  # noqa: E402

import compute_meter  # noqa: E402
import usage_billing  # noqa: E402
import usage_rates  # noqa: E402
import users_store  # noqa: E402

M = "openai:gpt-5.4"


def _u(**kw):
    return usage_billing.Usage(model_id=M, provider="openai", **kw)


# --------------------------------------------------------------------------
# GATE 0 — the invariant
# --------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(),                                              # zero-token / vendorless
    dict(prompt=13, completion=4),                       # tiny
    dict(prompt=1587, completion=92),                    # uncached
    dict(prompt=204, cached=2816, completion=4),         # cached (live shape)
    dict(prompt=4727, completion=202),                   # large
    dict(prompt=3168, completion=308),                   # #cite retry, folded
    dict(prompt=100000, completion=4000),                # very large
])
def test_invariant_is_exactly_120(kw):
    cost, debited, holds = usage_billing.check_invariant(_u(**kw))
    assert holds, f"ratio drifted off 1.20: cost={cost} debited={debited}"
    assert debited * usage_rates.MARKUP_DEN == cost * usage_rates.MARKUP_NUM


def test_service_cost_is_inside_the_markup_not_added_after():
    """The first draft added the service fee AFTER the multiply, which makes
    the ratio 1.20 + fee/vendor and therefore never exactly 1.20."""
    u = _u(prompt=1000, completion=100)
    cost = usage_billing.cost_micro(u)
    vendor = usage_billing.vendor_cost_pico(u) // usage_billing.PICO_PER_MICRO
    assert cost > vendor, "service cost must be part of the denominator"
    assert usage_billing.debit_for(u) * 5 == cost * 6


def test_no_floats_in_the_ledger():
    for kw in (dict(prompt=7, completion=3), dict(prompt=99999, cached=12345, completion=17)):
        for v in (usage_billing.cost_micro(_u(**kw)),
                  usage_billing.debit_for(_u(**kw)),
                  usage_billing.cost_pico(_u(**kw))):
            assert isinstance(v, int)


# --------------------------------------------------------------------------
# GATE 5 — cached tokens bill at the cached rate
# --------------------------------------------------------------------------
def test_cached_tokens_bill_at_the_cached_rate():
    warm = _u(prompt=204, cached=2816, completion=4)
    cold = _u(prompt=3020, cached=0, completion=4)
    assert usage_billing.debit_for(warm) < usage_billing.debit_for(cold)
    items = usage_billing.describe(warm)["line_items_micro"]
    assert items["cached"] > 0 and items["input"] > 0, "both line items must be visible"
    r = usage_rates.rate_for(M)
    assert items["cached"] == warm.cached * r["cached"] // usage_billing.PICO_PER_MICRO


def test_openai_usage_parser_does_not_double_count_the_cache():
    """OpenAI's prompt_tokens INCLUDES cached tokens; Anthropic's does not.
    Getting this backwards double-bills one vendor's cache."""
    parsed = usage_billing.extract_usage(
        {"usage": {"prompt_tokens": 3020, "completion_tokens": 4,
                   "prompt_tokens_details": {"cached_tokens": 2816}}},
        "openai", M)
    assert parsed.prompt == 204 and parsed.cached == 2816
    assert parsed.prompt + parsed.cached == 3020


def test_anthropic_usage_parser_does_not_subtract_the_cache():
    parsed = usage_billing.extract_usage(
        {"usage": {"input_tokens": 204, "output_tokens": 4,
                   "cache_read_input_tokens": 2816}},
        "anthropic", "anthropic:claude-haiku-4-5-20251001")
    assert parsed.prompt == 204 and parsed.cached == 2816


# --------------------------------------------------------------------------
# GATE 6 — the retry leak
# --------------------------------------------------------------------------
def test_retry_settles_on_the_turns_total_tokens():
    one = _u(prompt=3100, completion=800)
    folded = one + one
    assert folded.prompt == 6200 and folded.completion == 1600
    # Billing a single call during a two-call turn recovers ~60% of cost,
    # i.e. cost - 40%, exactly where the quality path fires.
    cost_two = usage_billing.cost_micro(folded)
    assert usage_billing.debit_for(one) * 100 // cost_two < 70


# --------------------------------------------------------------------------
# GATE 7 — the refund rule
# --------------------------------------------------------------------------
def test_refund_our_errors_but_never_a_vendor_billed_call():
    m = compute_meter.ComputeMeter(user="u", request_id="r", endpoint="/t")
    assert m.should_refund(), "a failure before dispatch must refund"
    m.add_vendor_usage({"model_id": M, "provider": "openai", "mock": False,
                        "usage": {"prompt_tokens": 10, "completion_tokens": 2,
                                  "cached_tokens": 0}})
    assert not m.should_refund(), "a vendor-billed call must NOT refund"


def test_a_mock_result_does_not_suppress_the_refund():
    m = compute_meter.ComputeMeter(user="u", request_id="r2", endpoint="/t")
    m.add_vendor_usage({"model_id": M, "provider": "openai", "mock": True, "usage": None})
    assert m.should_refund(), "a mock consumed no vendor tokens"


# --------------------------------------------------------------------------
# Reserve — must cover the output ceiling, or it under-reserves
# --------------------------------------------------------------------------
def test_reserve_covers_the_output_ceiling():
    """Input-only reserves under-cover: output is priced 8x higher, so a
    short prompt with a long completion settles well above an input-only
    reserve and the affordability check stops meaning anything."""
    prompt_tokens = 402
    input_only = usage_billing.reserve_for(M, prompt_tokens, 0)
    with_ceiling = usage_billing.reserve_for(M, prompt_tokens, 4096)
    settled = usage_billing.debit_for(_u(prompt=402, completion=96))
    assert input_only < settled, "input-only reserve under-covers a real call"
    assert with_ceiling > settled, "reserve must over-cover, so delta refunds"


def test_reserve_estimate_is_biased_high():
    text = "word " * 1000
    assert compute_meter.estimate_input_tokens(text) > len(text) / 4.0


# --------------------------------------------------------------------------
# GATE 3 — no conversion code anywhere in the billing path
# --------------------------------------------------------------------------
def test_no_balance_conversion_code_exists():
    """The retired cent field must never be read, and no module in the
    billing path may multiply a balance into the new unit."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for mod in ("users_store.py", "usage_billing.py", "usage_rates.py",
                "compute_meter.py", "usage_records.py"):
        src = open(os.path.join(root, mod), encoding="utf-8").read()
        for line in src.splitlines():
            code = line.split("#", 1)[0]
            assert 'get("g_credits")' not in code, f"{mod}: reads the frozen field"
            assert '"g_credits":' not in code, f"{mod}: writes the frozen field"
            if "10_000" in code or "10000" in code:
                assert "*" not in code, f"{mod}: balance multiply -- {line.strip()}"


# --------------------------------------------------------------------------
# GATE 4 — signup grant is idempotent
# --------------------------------------------------------------------------
def test_signup_grant_is_idempotent(reset_stores):
    users_store.create_user(username="g1", password_hash=b"x", salt="",
                            tier="free", created_at=0.0)
    first = users_store.grant_signup_credits("g1")
    assert first == users_store.SIGNUP_GRANT_MICRO
    assert users_store.grant_signup_credits("g1") == first
    assert users_store.grant_signup_credits("g1") == first
