/**
 * #145 / #141 -- the account lives on /membership: the terms (#162's copy,
 * carried from /plans), a password, the model preference, sign-out. The
 * account block is not behind the membership_ui_enabled flag.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../hooks/useFlags", () => ({ useFlags: vi.fn() }));
vi.mock("../../hooks/useMembership", () => ({ useMembership: vi.fn() }));
vi.mock("../../components/settings/SetPasswordPanel", () => ({
  default: () => <div data-testid="set-password-panel">PASSWORD</div>,
}));
vi.mock("../../components/settings/ModelPreferences", () => ({
  default: () => <div data-testid="model-preferences">MODEL</div>,
}));
vi.mock("../../components/settings/LocalModelPanel", () => ({
  default: () => <div data-testid="local-model-panel">LOCAL MODEL</div>,
}));
vi.mock("../../components/settings/MemoryVaultPanel", () => ({
  default: () => <div data-testid="memory-vault-panel">MEMORY VAULT</div>,
}));
vi.mock("../../components/membership/BillingHistoryPanel", () => ({
  default: () => <div data-testid="billing-history">HISTORY</div>,
}));
vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return { ...actual, signOut: vi.fn() };
});

import * as auth from "../../lib/auth";
import { useFlags } from "../../hooks/useFlags";
import { useMembership } from "../../hooks/useMembership";
import type { MembershipStateView } from "../../lib/api";
import MembershipPage from "../MembershipPage";

const STATE = {
  user: "u",
  identity: { member_number: 17, citizen: true, controller: false, citz_id: "citz-000017ava", cohort: "founding" },
  membership: { tier: "founding_500", status: "active", price_locked: 50, started_ts: 1, cancelled_ts: null, next_price: 50, price_lock_forfeit: false },
  billing: { state: "active", renewal_ts: null, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 50 },
  cohort: { cohort: "founding_500", active_count: 4, cap: 500, remaining: 496, waitlist_count: 0, is_full: false },
  waitlist_position: null,
  g_credits: { balance: 0, history_tail: [] },
} as unknown as MembershipStateView;

function arm(uiEnabled: boolean) {
  vi.mocked(useFlags).mockReturnValue({
    flags: { membership_ui_enabled: uiEnabled, g_credits_enabled: false, founder_tier_enabled: false },
    loading: false,
  } as never);
  vi.mocked(useMembership).mockReturnValue({
    state: STATE, loading: false, error: null,
    refresh: vi.fn(), activate: vi.fn(), cancel: vi.fn(),
    buySingle: vi.fn(), buyPack20: vi.fn(), confirmIntent: vi.fn(),
  } as never);
}

beforeEach(() => vi.clearAllMocks());

describe("MembershipPage — the account (#141)", () => {
  it("★ the terms, a password, the model preference and sign-out are here", () => {
    arm(true);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    expect(screen.getByTestId("plans-terms")).toHaveTextContent("recurring until you cancel");
    expect(screen.queryByText(/one-time/i)).toBeNull();
    expect(screen.queryByText(/expires permanently/i)).toBeNull();
    expect(screen.getByTestId("set-password-panel")).toBeInTheDocument();
    expect(screen.getByTestId("model-preferences")).toBeInTheDocument();
    // the member's own notes and local-model panels: their only surface
    expect(screen.getByTestId("memory-vault-panel")).toBeInTheDocument();
    expect(screen.getByTestId("local-model-panel")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("membership-signout"));
    expect(vi.mocked(auth.signOut)).toHaveBeenCalledTimes(1);
  });

  it("the membership body still renders above it", () => {
    arm(true);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    expect(screen.getByTestId("citz-id")).toHaveTextContent("citz-000017ava · citizen");
    expect(screen.getByTestId("billing-history")).toBeInTheDocument();
  });

  it("★ the account block is not behind the membership flag", () => {
    arm(false);
    render(<MemoryRouter><MembershipPage /></MemoryRouter>);
    expect(screen.getByTestId("membership-disabled")).toBeInTheDocument();
    expect(screen.getByTestId("set-password-panel")).toBeInTheDocument();
    expect(screen.getByTestId("membership-signout")).toBeInTheDocument();
    expect(screen.getByTestId("plans-terms")).toBeInTheDocument();
  });
});
