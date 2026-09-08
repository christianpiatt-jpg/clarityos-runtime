/**
 * #187 -- the #G words render for every member; the flag disables the buy
 * action only ("not enabled"). #183 -- the homeless panels have a home:
 * the envelope kv, the one tier card, the billing + cap panel. A missing
 * value reads "—"; a false reads its word.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../hooks/useFlags", () => ({ useFlags: vi.fn() }));
vi.mock("../../hooks/useMembership", () => ({ useMembership: vi.fn() }));
vi.mock("../../components/settings/SetPasswordPanel", () => ({ default: () => <div data-testid="set-password-panel" /> }));
vi.mock("../../components/settings/ModelPreferences", () => ({ default: () => <div data-testid="model-preferences" /> }));
vi.mock("../../components/settings/LocalModelPanel", () => ({ default: () => <div data-testid="local-model-panel" /> }));
vi.mock("../../components/settings/KernelFacts", () => ({ default: () => <div data-testid="kernel-facts" /> }));
vi.mock("../../components/settings/MemoryVaultPanel", () => ({ default: () => <div data-testid="memory-vault-panel" /> }));
vi.mock("../../components/membership/BillingHistoryPanel", () => ({ default: () => <div data-testid="billing-history" /> }));
const AUTH = vi.hoisted(() => ({
  session: "sess", user: "ava@example.com",
  profile: null as null | Record<string, unknown>,
}));
vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return { ...actual, signOut: vi.fn(), getAuthSnapshot: () => AUTH, subscribeAuth: () => () => {} };
});

import { useFlags } from "../../hooks/useFlags";
import { useMembership } from "../../hooks/useMembership";
import type { MembershipStateView } from "../../lib/api";
import MembershipPage from "../MembershipPage";

const STATE = {
  user: "ava@example.com",
  identity: { member_number: 17, paid: true, controller: false, citz_id: "citz-000017ava", cohort: "founding" },
  membership: { tier: "founding_500", status: "active", price_locked: 50, started_ts: 1, cancelled_ts: null, next_price: 50, price_lock_forfeit: false },
  billing: { state: "active", renewal_ts: 1_788_900_000, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 50 },
  cohort: { cohort: "founding_500", active_count: 4, cap: 500, remaining: 496, waitlist_count: 0, is_full: false },
  waitlist_position: null,
  g_credits: { balance: 0, unit: "micro-dollars", unlimited: false, balance_display: "$0.00", history_tail: [] },
} as unknown as MembershipStateView;

function arm(gCredits: boolean) {
  vi.mocked(useFlags).mockReturnValue({
    flags: { membership_ui_enabled: true, g_credits_enabled: gCredits, founder_tier_enabled: false },
    loading: false,
  } as never);
  vi.mocked(useMembership).mockReturnValue({
    state: STATE, loading: false, error: null,
    refresh: vi.fn(), activate: vi.fn(), cancel: vi.fn(),
    buySingle: vi.fn(), buyPack20: vi.fn(), confirmIntent: vi.fn(),
  } as never);
}

beforeEach(() => { vi.clearAllMocks(); AUTH.profile = null; });

describe("MembershipPage — #187 the words render; the flag gates the buy only", () => {
  it("★ flag OFF: the #G words render and the buy reads not enabled, disabled", () => {
    arm(false);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    expect(screen.getByTestId("g-ledger")).toHaveTextContent("micro-dollars · metered");
    expect(screen.getByTestId("g-balance")).toHaveTextContent("$0.00");
    const buy = screen.getByTestId("g-buy-pack20") as HTMLButtonElement;
    expect(buy.disabled).toBe(true);
    expect(buy).toHaveTextContent("not enabled");
  });
  it("flag ON: the buy is live", () => {
    arm(true);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    const buy = screen.getByTestId("g-buy-pack20") as HTMLButtonElement;
    expect(buy.disabled).toBe(false);
    expect(buy).toHaveTextContent("Buy 20-pack ($20.00)");
  });
});

describe("MembershipPage — #183 the homeless panels, housed", () => {
  it("★ envelope · tier · billing+cap render from the state; a false reads its word", () => {
    arm(true);
    AUTH.profile = { user: "ava@example.com", member_number: 17, controller: false, operator_id: "op_ava", billing_expires_at: 1_790_000_000 };
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    const env = screen.getByTestId("membership-envelope");
    expect(env).toHaveTextContent("ava@example.com");
    expect(env).toHaveTextContent("citizen");
    expect(env).toHaveTextContent("op_ava");
    expect(env).toHaveTextContent("2026-09-");  // billing expires, a day, from seconds
    const tier = screen.getByTestId("membership-tier");
    expect(tier).toHaveTextContent("founding_500");
    expect(tier).toHaveTextContent("$50.00");
    expect(tier).toHaveTextContent("false");   // price_lock_forfeit: the word, never blank
    const bc = screen.getByTestId("membership-billing-cap");
    expect(bc).toHaveTextContent("active");
    expect(bc).toHaveTextContent("4 of 500 seated · 496 remaining · 0 waiting · open");
    expect(bc).toHaveTextContent("2026-09-");  // renewal day
  });
  it("no profile (the load window) -> dashes, never a crash", () => {
    arm(true);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    const env = screen.getByTestId("membership-envelope");
    expect(env).toHaveTextContent("user—");
    expect(env).toHaveTextContent("operator—");
  });
});
