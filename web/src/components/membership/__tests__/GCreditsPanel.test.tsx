/**
 * #142 / #155 -- the panel shows DOLLARS: the big number is balance_display
 * ("unlimited" for the controller), the history deltas are dollars at $0.01
 * read from credits_delta (or the meter's amount_micro) even when the row
 * carries no `amount` (the signup grant).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GCreditsPanel from "../GCreditsPanel";

function state(g: Record<string, unknown>) {
  return {
    user: "u", membership: { tier: null, status: null, price_locked: null, started_ts: null,
      cancelled_ts: null, next_price: 50, price_lock_forfeit: false },
    billing: { state: "none", renewal_ts: null, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 0 },
    cohort: { cohort: "founding_500", active_count: 1, cap: 500, remaining: 499, waitlist_count: 0, is_full: false },
    waitlist_position: null,
    g_credits: g,
  } as never;
}
const noop = () => {};

describe("GCreditsPanel -- dollars on the surface", () => {
  it("661054 micro reads $0.66, never the raw figure", () => {
    render(<GCreditsPanel state={state({ balance: 661054, balance_micro: 661054, balance_display: "$0.66", history_tail: [] })} onBuySingle={noop} onBuyPack20={noop} />);
    expect(screen.getByTestId("g-balance")).toHaveTextContent("$0.66");
    expect(screen.queryByText("661054")).toBeNull();
    expect(screen.getByText("#G balance")).toBeInTheDocument();
    expect(screen.getByText(/\$1\.00 buys one #G run\. Metered from this balance\. Never expires\./)).toBeInTheDocument();
  });
  it("a controller reads unlimited", () => {
    render(<GCreditsPanel state={state({ balance: 0, balance_micro: 0, balance_display: "unlimited", unlimited: true, history_tail: [] })} onBuySingle={noop} onBuyPack20={noop} />);
    expect(screen.getByTestId("g-balance")).toHaveTextContent("unlimited");
  });
  it("a state without balance_display falls back to the client formatter", () => {
    render(<GCreditsPanel state={state({ balance: 15_000_000, history_tail: [] })} onBuySingle={noop} onBuyPack20={noop} />);
    expect(screen.getByTestId("g-balance")).toHaveTextContent("$15.00");
  });
  it("history rows: the signup grant (no amount) reads +$15.00; sub-cent reads $0.00; a debit reads -$1.00", () => {
    render(<GCreditsPanel state={state({ balance: 0, balance_display: "$0.00", history_tail: [
      { type: "signup_grant", credits_delta: 15_000_000, source: "account_creation", ts: 1 },
      { type: "adjust", credits_delta: 15_000_000, amount: 0.0, ts: 2 },
      { type: "g_consume", credits_delta: -1_000_000, amount: 0.0, ts: 3 },
      { kind: "settle_refund", amount_micro: 900, request_id: "r", endpoint: "/markov" },
      { type: "g_credit_pack", credits_delta: 20_000_000, amount: 20.0, ts: 5 },
    ] })} onBuySingle={noop} onBuyPack20={noop} />);
    const deltas = screen.getAllByTestId("g-history-delta").map((d) => d.textContent);
    // newest first (the panel reverses the tail)
    expect(deltas).toEqual(["+$20.00", "$0.00", "-$1.00", "+$15.00", "+$15.00"]);
    const rows = screen.getAllByTestId("g-history-row").map((r) => r.textContent ?? "");
    expect(rows[0]).toContain("$20.00");          // paid
    expect(rows[1]).toContain("settle_refund");   // the meter's row names its kind
    expect(rows[4]).toContain("signup_grant");
  });
});
