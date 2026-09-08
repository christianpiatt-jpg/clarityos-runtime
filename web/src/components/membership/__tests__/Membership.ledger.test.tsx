/**
 * #180b (1) -- /membership/state: the 21 keys that arrived and died.
 * Present -> rendered; absent -> "—"; a boolean false -> its word.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import MembershipStatusCard from "../MembershipStatusCard";
import RenewalStatusCard from "../RenewalStatusCard";
import GCreditsPanel from "../GCreditsPanel";
import type { MembershipStateView } from "../../../lib/api";

const DASH = "—";

const FULL = {
  user: "u",
  identity: { member_number: 17, citizen: true, controller: false, citz_id: "citz-000017ava", cohort: "founding" },
  membership: {
    tier: "founding_500", status: "active", price_locked: 50, started_ts: 1_781_536_458, cancelled_ts: null,
    next_price: 50, price_lock_forfeit: false, confirmed: true, confirmed_ts: 1_783_420_269,
  },
  billing: { state: "active", renewal_ts: 1_789_924_478, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 50 },
  cohort: { cohort: "founding_500", active_count: 5, cap: 500, remaining: 495, waitlist_count: 0, is_full: false },
  waitlist_position: null,
  g_credits: { balance: 15_000_000, balance_micro: 15_000_000, balance_display: "$15.00", unlimited: false, unit: "micro_dollars", history_tail: [] },
} as unknown as MembershipStateView;

const SPARSE = {
  user: "u",
  identity: { member_number: null, citizen: false, controller: false, citz_id: "citz-000099xyz", cohort: "all" },
  membership: { tier: null, status: null, price_locked: null, started_ts: null, cancelled_ts: null, next_price: 50, price_lock_forfeit: false },
  billing: { state: null, renewal_ts: null, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 50 },
  cohort: {},
  waitlist_position: null,
  g_credits: { balance: 0, history_tail: [] },
} as unknown as MembershipStateView;

describe("MembershipStatusCard (#180b 1)", () => {
  it("★ the seats line, the number, confirmed, the price lock as a word, the waitlist dash", () => {
    render(<MembershipStatusCard state={FULL} />);
    expect(screen.getByTestId("cohort-seated")).toHaveTextContent("founding_500 · 5 of 500 seated · 495 remaining · waitlist 0 · open");
    expect(screen.getByTestId("member-number")).toHaveTextContent("#17");
    expect(screen.getByTestId("citz-id")).toHaveTextContent("citz-000017ava · citizen");
    expect(screen.getByTestId("membership-confirmed")).toHaveTextContent("confirmed 2026-07-07");
    expect(screen.getByTestId("price-lock")).toHaveTextContent("not forfeited");
    expect(screen.getByTestId("waitlist-position")).toHaveTextContent(DASH);
    expect(screen.getByTitle("state.cohort.cohort · state.cohort.active_count · state.cohort.cap · state.cohort.remaining · state.cohort.waitlist_count · state.cohort.is_full")).toBeInTheDocument();
    expect(screen.getByTitle("state.identity.member_number")).toBeInTheDocument();
  });
  it("a full cohort reads full; a forfeited lock reads forfeited; a waitlist position reads its number", () => {
    const s = { ...FULL,
      cohort: { ...FULL.cohort, is_full: true, remaining: 0 },
      membership: { ...FULL.membership, price_lock_forfeit: true, confirmed: false },
      waitlist_position: 12,
    } as MembershipStateView;
    render(<MembershipStatusCard state={s} />);
    expect(screen.getByTestId("cohort-seated")).toHaveTextContent("0 remaining · waitlist 0 · full");
    expect(screen.getByTestId("price-lock")).toHaveTextContent("forfeited");
    expect(screen.getByTestId("membership-confirmed")).toHaveTextContent("not confirmed");
    expect(screen.getByTestId("waitlist-position")).toHaveTextContent("#12");
  });
  it("absent: dashes, never a zero invented", () => {
    render(<MembershipStatusCard state={SPARSE} />);
    expect(screen.getByTestId("cohort-seated")).toHaveTextContent(`${DASH} · ${DASH} of ${DASH} seated · ${DASH} remaining · waitlist ${DASH} · ${DASH}`);
    expect(screen.getByTestId("member-number")).toHaveTextContent(`#${DASH}`);
    expect(screen.getByTestId("membership-confirmed")).toHaveTextContent(DASH);
    expect(screen.getByTestId("price-lock")).toHaveTextContent("not forfeited");
  });
});

describe("RenewalStatusCard (#180b 1)", () => {
  it("★ next charge on a date, the state as a badge, no retry/grace rows when null", () => {
    render(<RenewalStatusCard state={FULL} />);
    expect(screen.getByTestId("next-charge")).toHaveTextContent("next charge $50.00 on 2026-09-20");
    expect(screen.getByTestId("billing-state")).toHaveTextContent("ACTIVE");
    // retry_count 0 is non-null: the row renders 0 / 3 (the rule says non-null)
    expect(screen.getByTestId("billing-retry")).toHaveTextContent("0 / 3");
    expect(screen.queryByTestId("billing-grace")).toBeNull();
    expect(screen.getByTitle("state.billing.next_amount · state.billing.renewal_ts")).toBeInTheDocument();
  });
  it("★ a member with no billing state still gets the card: dashes and the word", () => {
    render(<RenewalStatusCard state={SPARSE} />);
    expect(screen.getByTestId("renewal-card")).toBeInTheDocument();
    expect(screen.getByTestId("billing-state")).toHaveTextContent(DASH);
    expect(screen.getByTestId("next-charge")).toHaveTextContent(`next charge $50.00 on ${DASH}`);
    expect(screen.getByTestId("billing-none")).toBeInTheDocument();
  });
  it("grace renders when non-null, whatever the state", () => {
    const s = { ...FULL, billing: { ...FULL.billing, state: "past_due", renewal_retry_count: 2, renewal_grace_until_ts: 1_790_000_000 } } as MembershipStateView;
    render(<RenewalStatusCard state={s} />);
    expect(screen.getByTestId("billing-retry")).toHaveTextContent("2 / 3");
    expect(screen.getByTestId("billing-grace")).toHaveTextContent("2026-09-21");
    expect(screen.getByTestId("billing-state")).toHaveTextContent("PAST DUE");
  });
});

describe("GCreditsPanel (#180b 1)", () => {
  it("the unit and the metering as words beside the balance", () => {
    render(<GCreditsPanel state={FULL} onBuyPack20={() => {}} busy={null} />);
    expect(screen.getByTestId("g-ledger")).toHaveTextContent("micro_dollars · metered");
    expect(screen.getByTestId("g-balance")).toHaveTextContent("$15.00");
  });
  it("unlimited reads unlimited; absent reads dashes", () => {
    const s = { ...FULL, g_credits: { ...FULL.g_credits, unlimited: true, balance_display: "unlimited" } } as MembershipStateView;
    render(<GCreditsPanel state={s} onBuyPack20={() => {}} busy={null} />);
    expect(screen.getByTestId("g-ledger")).toHaveTextContent("micro_dollars · unlimited");
  });
  it("absent unit and flag read dashes", () => {
    render(<GCreditsPanel state={SPARSE} onBuyPack20={() => {}} busy={null} />);
    expect(screen.getByTestId("g-ledger")).toHaveTextContent(`${DASH} · ${DASH}`);
  });
});
