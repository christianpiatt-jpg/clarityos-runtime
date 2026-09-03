/**
 * #150 — Member search miss: "No account yet for X — create one?"
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  founderMembersList: vi.fn(),
}));

import { founderMembersList } from "../../../lib/api";
import MemberDetailPanel from "../MemberDetailPanel";

const mocked = vi.mocked(founderMembersList);

function mount(selected: string, onCreateRequest = vi.fn()) {
  render(
    <MemoryRouter>
      <MemberDetailPanel selected={selected} onSelect={() => {}} onCreateRequest={onCreateRequest} />
    </MemoryRouter>,
  );
  return onCreateRequest;
}

describe("MemberDetailPanel — search miss (#150)", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("★ a selected address with no doc offers to create one, and the button hands the email up", async () => {
    mocked.mockResolvedValue({ ok: true, members: [], count: 0, limit: 50, offset: 0, has_more: false });
    const onCreateRequest = mount("ruy@example.com");
    await waitFor(() => expect(screen.getByTestId("member-miss")).toBeInTheDocument());
    expect(mocked).toHaveBeenCalledWith({ email: "ruy@example.com" });
    expect(screen.getByTestId("member-miss")).toHaveTextContent("No account yet for ruy@example.com — create one?");
    fireEvent.click(screen.getByTestId("member-miss-create"));
    expect(onCreateRequest).toHaveBeenCalledWith("ruy@example.com");
  });

  it("an existing address shows no miss copy", async () => {
    mocked.mockResolvedValue({
      ok: true, count: 1, limit: 50, offset: 0, has_more: false,
      members: [{ email: "ana@example.com", cohort: "member", membership_status: "active", membership_tier: "founding_500",
                  created_at: 1, last_seen: null, balance_display: "$0.00", auth_method: "magic_link" }],
    });
    mount("ana@example.com");
    await waitFor(() => expect(mocked).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("member-miss")).toBeNull();
  });

  it("a failed lookup says nothing (never a false 'no account')", async () => {
    mocked.mockRejectedValue(new Error("403"));
    mount("who@example.com");
    await waitFor(() => expect(mocked).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("member-miss")).toBeNull();
  });

  it("a non-email selection that misses shows no create offer (Create member cannot make it)", async () => {
    mocked.mockResolvedValue({ ok: true, members: [], count: 0, limit: 50, offset: 0, has_more: false });
    mount("Legacy.User");
    await waitFor(() => expect(mocked).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("member-miss")).toBeNull();
  });

  it("nothing selected: no lookup", () => {
    mount("");
    expect(mocked).not.toHaveBeenCalled();
  });
});
