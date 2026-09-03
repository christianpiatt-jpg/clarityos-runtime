/**
 * #150 — Members table: every account, newest first, 50 per page, click
 * selects for Manual ops.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  founderMembersList: vi.fn(),
}));

import { founderMembersList } from "../../../lib/api";
import MembersTable from "../MembersTable";

const mocked = vi.mocked(founderMembersList);
const row = (email: string, status: string | null = null) => ({
  email, cohort: "member", membership_status: status, membership_tier: status ? "founding_500" : null,
  created_at: 1_756_900_000, last_seen: null, balance_display: "$0.00", auth_method: "magic_link",
});
const page = (members: ReturnType<typeof row>[], has_more = false, offset = 0) => ({
  ok: true as const, members, count: members.length, limit: 50, offset, has_more,
});

describe("MembersTable (#150)", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("★ lists the rows the server sends and a click selects the email", async () => {
    mocked.mockResolvedValue(page([row("ruy@example.com", "active"), row("ana@example.com")]));
    const onSelect = vi.fn();
    render(<MembersTable onSelect={onSelect} />);
    await waitFor(() => expect(screen.getAllByTestId("members-row")).toHaveLength(2));
    expect(mocked).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    const rows = screen.getAllByTestId("members-row");
    expect(rows[0]).toHaveTextContent("ruy@example.com");
    expect(rows[0]).toHaveTextContent("active");
    expect(rows[1]).toHaveTextContent("ana@example.com");
    fireEvent.click(rows[1]);
    expect(onSelect).toHaveBeenCalledWith("ana@example.com");
  });

  it("pages: next asks for the next offset only when the server says there is more", async () => {
    mocked.mockResolvedValueOnce(page([row("a@example.com")], true, 0));
    mocked.mockResolvedValueOnce(page([row("b@example.com")], false, 50));
    render(<MembersTable onSelect={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("members-next")).toBeEnabled());
    expect(screen.getByTestId("members-prev")).toBeDisabled();
    fireEvent.click(screen.getByTestId("members-next"));
    await waitFor(() => expect(mocked).toHaveBeenLastCalledWith({ limit: 50, offset: 50 }));
    await waitFor(() => expect(screen.getByTestId("members-next")).toBeDisabled());
    expect(screen.getByTestId("members-prev")).toBeEnabled();
  });

  it("no accounts yet is said, not an empty table", async () => {
    mocked.mockResolvedValue(page([]));
    render(<MembersTable onSelect={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("members-empty")).toBeInTheDocument());
  });

  it("a refreshKey bump refetches", async () => {
    mocked.mockResolvedValue(page([row("a@example.com")]));
    const { rerender } = render(<MembersTable onSelect={() => {}} refreshKey={0} />);
    await waitFor(() => expect(mocked).toHaveBeenCalledTimes(1));
    rerender(<MembersTable onSelect={() => {}} refreshKey={1} />);
    await waitFor(() => expect(mocked).toHaveBeenCalledTimes(2));
  });
});
