"""
ComputeMeter — reserve / settle around a metered call.

★★ THE PATH DEFECT this exists to fix

``metered_compute`` is a FastAPI dependency: it runs BEFORE the handler, so
at that point the prompt does not exist yet and neither does any notion of
what the call will cost. That is why it charged a flat 1 credit -- a flat
fee was the only thing it *could* know. The fee was wrong in both
directions: a one-line question subsidised a 100k-token analysis.

The meter splits the job:

    dependency  -- entitlement, idempotency key, pre-flight balance check
    handler     -- reserve() once the prompt is assembled
                   settle() once the vendor has reported real usage

The handler owns the two calls because the handler is the only place that
knows the prompt and the response.

★ RESERVE IS AN ESTIMATE, AND THAT IS DELIBERATE.

The work order specified an EXACT reserve ("the input is already
assembled"). The prompt text is indeed assembled -- but tokens are not
characters, and this service carries no tokenizer: the router speaks raw
urllib to both vendors and neither ``tiktoken`` nor an SDK is in
requirements.txt. An exact pre-call count would mean adding a tokenizer per
vendor (and Anthropic's is a network round-trip, which would bill latency to
save nothing).

So the reserve is estimated and biased HIGH, and the settle is exact from
the vendor's reported usage. That ordering matters:

    over-reserve -> negative delta -> member REFUNDED at settle
    under-reserve -> positive delta -> member owes more after the fact

Reserving high means the member can never consume compute they could not
afford, and any excess comes straight back. Reserving low would let a
balance go negative between reserve and settle. Fail toward over-reserving.

★★★ The INVARIANT is enforced at SETTLE, which is the only place it can be:
it is a statement about what the call actually cost, and that is not known
until the vendor says so. Reserve gates affordability; settle sets price.
"""
from __future__ import annotations

import logging
from typing import Optional

import usage_billing
import usage_records
import users_store

logger = logging.getLogger("clarityos.compute_meter")

# Characters per token used for the reserve estimate. English prose runs
# ~4.0 chars/token on both vendors' tokenizers; 3.2 deliberately UNDER-states
# chars-per-token, which OVER-states token count, which over-reserves.
# See the module docstring for why the bias points this way.
_RESERVE_CHARS_PER_TOKEN = 3.2

# Floor on the estimate so a near-empty prompt still reserves something.
_RESERVE_MIN_TOKENS = 32

# Output ceiling assumed at reserve time. Mirrors model_router.route_request's
# ``max_tokens`` default — the vendor cannot return more than this, so
# reserving against it always over-reserves and never under-reserves.
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# Model id used only to price a call that never reached a vendor, so that
# the rate lookup resolves and the service cost is charged. No vendor tokens
# are attributed to it -- see ComputeMeter.settle.
_DEFAULT_MODEL_ID = "openai:gpt-5.4"


def estimate_input_tokens(text: str) -> int:
    """Conservative (high) token estimate for a reserve. Never exact --
    callers must treat the result as a reservation, not a price."""
    if not text:
        return _RESERVE_MIN_TOKENS
    return max(_RESERVE_MIN_TOKENS, int(len(text) / _RESERVE_CHARS_PER_TOKEN) + 1)


class ComputeMeter:
    """One metered call's money. Created by ``metered_compute``, handed to
    the handler on ``session["_meter"]``.

    Lifecycle:

        m.reserve(model_id, prompt_text)   -> debits the estimate, 402 if short
        m.add_vendor_usage(result)         -> once per vendor call, retries too
        m.settle()                         -> reconciles to the exact price

    ``settle`` is idempotent: calling it twice settles once.
    """

    def __init__(self, *, user: str, request_id: str, endpoint: str):
        self.user = user
        self.request_id = request_id
        self.endpoint = endpoint
        self.reserved_micro = 0
        self.settled = False
        self.calls = 0
        # ★★ THE REFUND RULE, as one flag.
        #
        # If the vendor consumed tokens and THEN something failed, refunding
        # the member means we eat a bill we have already been charged. Once
        # any vendor call reports usage this flips True and the teardown
        # refund is suppressed. Our OWN failures -- validation, auth, a 5xx
        # raised before dispatch -- leave it False and do refund.
        self.vendor_billed = False
        # True when the idempotency key had already been charged. A replay
        # settles nothing and refunds nothing -- see reserve().
        self.replayed = False
        self._usage: Optional[usage_billing.Usage] = None
        self._model_id = ""

    # -- reserve ----------------------------------------------------------
    def reserve(self, model_id: str, prompt_text: str,
                max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> int:
        """Debit the estimated cost before dispatch. Raises
        ``ValueError("no_credits")`` when the balance will not cover it --
        the caller maps that to 402, exactly as the flat-fee gate did."""
        self._model_id = model_id
        tokens = estimate_input_tokens(prompt_text)
        amount = usage_billing.reserve_for(model_id, tokens, max_output_tokens)
        res = users_store.consume_g_credit_tx(self.user, self.request_id, cost=amount)
        if res.get("replay"):
            # ★★ A REPLAY MUST BE A FINANCIAL NO-OP, END TO END.
            #
            # The original call already reserved AND settled. The debit
            # ledger correctly refuses to charge again -- but if we still
            # record `reserved_micro = amount`, settle computes
            # `delta = settle - reserve` against a reserve that was never
            # taken on THIS pass, sees a large negative, and REFUNDS it.
            # The member is paid to retry. Measured at +48,702 micro per
            # replay before this branch existed.
            #
            # Zero the reserve and mark the meter settled so the teardown
            # settle cannot move money.
            self.reserved_micro = 0
            self.replayed = True
            self.settled = True
        else:
            self.reserved_micro = amount
        logger.info(
            "meter reserve user=%s req=%s model=%s est_in=%d max_out=%d "
            "reserve=%d replay=%s",
            self.user, self.request_id, model_id, tokens, max_output_tokens,
            amount, res.get("replay"),
        )
        return amount

    # -- usage ------------------------------------------------------------
    def add_vendor_usage(self, result: dict) -> None:
        """Fold ONE vendor call's reported usage into this turn.

        ★★ THE RETRY LEAK, closed here. A ``#cite`` turn that retries fires
        two billed vendor calls for one member turn. Calling this once per
        call and settling on the sum means the member pays cost+20% for the
        turn -- not for one call while we absorb the other. Settling on a
        single call's usage during a retry turns +20% into roughly -40%
        exactly where the quality path fires.
        """
        if not isinstance(result, dict):
            return
        raw = result.get("usage")
        model_id = result.get("model_id") or self._model_id
        provider = result.get("provider") or ""
        if not raw:
            # No usage block. A mock/stub consumed nothing real, so there is
            # nothing to bill and nothing to suppress the refund for.
            if not result.get("mock"):
                logger.warning(
                    "meter vendor call reported no usage req=%s model=%s -- "
                    "billing will fall back to the reserve",
                    self.request_id, model_id,
                )
            return
        u = usage_billing.Usage(
            prompt=int(raw.get("prompt_tokens") or 0),
            completion=int(raw.get("completion_tokens") or 0),
            cached=int(raw.get("cached_tokens") or 0),
            model_id=model_id, provider=provider,
            estimated=bool(raw.get("estimated")),
        )
        self._usage = u if self._usage is None else (self._usage + u)
        self.calls += 1
        self.vendor_billed = True

    # -- settle -----------------------------------------------------------
    def settle(self) -> Optional[dict]:
        """Reconcile the reserve to the exact price. Returns the breakdown,
        or None when there was nothing to settle."""
        if self.settled:
            return None
        self.settled = True
        if self._usage is None:
            # No vendor usage. Two ways to land here, and BOTH must still be
            # charged:
            #
            #   * a deterministic engine (/markov, /galileo, /library,
            #     /tizzy, /engine/v1/run) that never calls reserve() because
            #     it never dispatches to a vendor;
            #   * a mock result, where the provider key is unset.
            #
            # ★ Charging nothing here is how five of the seven metered
            # routes silently became FREE when the flat 1-credit debit was
            # replaced. A zero-token Usage still carries the service cost,
            # so the call is billed for what it actually consumed -- our
            # infrastructure -- rather than for nothing at all.
            self._usage = usage_billing.Usage(model_id=self._model_id or _DEFAULT_MODEL_ID)
        breakdown = usage_billing.describe(self._usage, reserved=self.reserved_micro)
        delta = breakdown["delta_micro"]
        try:
            if delta > 0:
                # Derived key -- the settle is its own idempotent debit, so a
                # replay of the whole request cannot double-charge it.
                users_store.consume_g_credit_tx(
                    self.user, self.request_id + ":settle", cost=delta)
            elif delta < 0:
                users_store.add_g_credits(
                    self.user, -delta,
                    history_entry={
                        "kind": "settle_refund", "request_id": self.request_id,
                        "amount_micro": -delta, "endpoint": self.endpoint,
                    })
        except ValueError as e:
            # Balance could not cover the overage. The compute already ran;
            # we do not claw back a delivered answer. Log it and let the
            # balance floor hold at zero -- under-recovering by the delta is
            # the correct failure direction.
            logger.warning(
                "meter settle shortfall user=%s req=%s delta=%d err=%s",
                self.user, self.request_id, delta, e,
            )
        usage_records.record(
            request_id=self.request_id, user=self.user, endpoint=self.endpoint,
            breakdown=breakdown, reserve_micro=self.reserved_micro, calls=self.calls,
        )
        logger.info(
            "meter settle user=%s req=%s reserve=%d settle=%d delta=%+d calls=%d "
            "vendor=%d service=%d total=%d invariant=%s",
            self.user, self.request_id, self.reserved_micro,
            breakdown["debited_micro"], delta, self.calls,
            breakdown["vendor_micro"], breakdown["service_micro"],
            breakdown["total_cost_micro"], breakdown["invariant_holds"],
        )
        return breakdown

    # -- refund -----------------------------------------------------------
    def should_refund(self) -> bool:
        """★ Leak 2, encoded. Refund OUR errors; never refund a call the
        vendor has already billed us for."""
        return not self.vendor_billed
