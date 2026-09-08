/**
 * #124 — the founder is /me.controller; the citizen id shows on /membership.
 *
 * ★ WHAT THESE PIN. RequireAdmin's predicate admits a profile with
 * controller=true whatever its cohort label, and admits NOTHING else (#157:
 * the derived label "controller" without the flag, and every legacy string,
 * are refused -- the server's shim is deleted and the surface follows). The
 * membership card renders the citz id beside the title when the state
 * carries one, and nothing when it does not.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { isController } from "../RequireAdmin";
import MembershipStatusCard from "../membership/MembershipStatusCard";
import type { MembershipStateView } from "../../lib/api";

function state(identity?: MembershipStateView["identity"]): MembershipStateView {
  return {
    user: "u",
    identity,
    membership: { tier: "founding_500", status: "active", price_locked: 50, started_ts: 1, cancelled_ts: null, next_price: 50, price_lock_forfeit: false },
    billing: { state: "active", renewal_ts: null, renewal_retry_count: 0, renewal_grace_until_ts: null, next_amount: 50 },
    cohort: { cohort: "founding_500", active_count: 4, cap: 500, remaining: 496, waitlist_count: 0, is_full: false },
    waitlist_position: null,
    g_credits: { balance: 0, history_tail: [] },
  } as unknown as MembershipStateView;
}

describe("RequireAdmin.isController (#124)", () => {
  it("admits controller=true whatever the label", () => {
    expect(isController({ controller: true, cohort: "all" })).toBe(true);
    expect(isController({ controller: true, cohort: "controller" })).toBe(true);
    expect(isController({ controller: true })).toBe(true);
  });

  it("#157 -- refuses the label without the flag, every legacy string, a citizen, a member, a null profile", () => {
    expect(isController({ controller: false, cohort: "controller" })).toBe(false);
    expect(isController({ cohort: "controller" })).toBe(false);
    expect(isController({ cohort: "founder" })).toBe(false);
    expect(isController({ cohort: "founder_exception" })).toBe(false);
    expect(isController({ cohort: "admin" })).toBe(false);
    expect(isController({ controller: false, cohort: "founding" })).toBe(false);
    expect(isController({ cohort: "all" })).toBe(false);
    expect(isController({ cohort: "member" })).toBe(false);
    expect(isController(null)).toBe(false);
    expect(isController(undefined)).toBe(false);
  });
});

describe("MembershipStatusCard — the citizen id (#124)", () => {
  it("★ renders citz-000001chr · admin beside the title (#171: the word is admin)", () => {
    render(<MembershipStatusCard state={state({ member_number: 1, paid: false, controller: true, citz_id: "citz-000001chr", cohort: "controller" })} />);
    expect(screen.getByTestId("citz-id")).toHaveTextContent("citz-000001chr · admin");
  });

  it("a paid citizen reads · citizen; an unnumbered state shows nothing", () => {
    render(<MembershipStatusCard state={state({ member_number: 7, paid: true, controller: false, citz_id: "citz-000007ch0", cohort: "founding" })} />);
    expect(screen.getByTestId("citz-id")).toHaveTextContent("citz-000007ch0 · citizen");
  });

  it("no identity, no id", () => {
    render(<MembershipStatusCard state={state(undefined)} />);
    expect(screen.queryByTestId("citz-id")).toBeNull();
  });
});
