/**
 * #171 -- the members table's cohort column reads citizen / admin / \u2014,
 * never "controller" / "founding" / "all", not even as hover text.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, founderMembersList: vi.fn() };
});

import * as api from "../../../lib/api";
import MembersTable from "../MembersTable";

const row = (email: string, extra: Record<string, unknown>) => ({
  email, cohort: "all", membership_status: null, membership_tier: null, created_at: 1, last_seen: null,
  balance_display: "$0.00", auth_method: "magic_link", member_number: null, citizen: false, controller: false,
  citz_id: null, ...extra,
});

afterEach(() => vi.clearAllMocks());

describe("MembersTable -- cohort words (#171)", () => {
  it("numbered -> citizen; controller -> admin; neither -> a dash", async () => {
    vi.mocked(api.founderMembersList).mockResolvedValue({
      ok: true, count: 3, limit: 50, offset: 0, has_more: false,
      members: [
        row("chris@example.com", { cohort: "controller", controller: true, member_number: 1, balance_display: "unlimited" }),
        row("ava@example.com", { cohort: "founding", member_number: 7 }),
        row("new@example.com", { cohort: "all" }),
      ],
    } as never);
    render(<MembersTable onSelect={() => {}} refreshKey={0} />);
    await waitFor(() => expect(screen.getAllByTestId("members-cohort")).toHaveLength(3));
    const words = screen.getAllByTestId("members-cohort").map((c) => c.textContent);
    expect(words).toEqual(["admin", "citizen", "\u2014"]);
    for (const c of screen.getAllByTestId("members-cohort")) {
      expect(c.getAttribute("title")).toBeNull();   // not even as hover text
    }
    const rows = screen.getAllByTestId("members-row").map((r) => r.textContent ?? "");
    expect(rows[0]).toContain("unlimited");
    expect(rows.join(" ")).not.toMatch(/\bcontroller\b|\bfounding\b|\ball\b/);
  });
});
