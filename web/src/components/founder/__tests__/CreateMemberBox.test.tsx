/**
 * #150 — Create member: the founder types an email, the account exists.
 *
 * ★ WHAT THESE PIN. CREATE is disabled until the text is an email; the
 * post carries the two flags; the result line reads "created · activated ·
 * link sent" or "already existed · link resent"; a throttled link is said;
 * a failure is shown; a prefill (from a search miss) lands in the box.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  founderMembersCreate: vi.fn(),
}));

import { founderMembersCreate } from "../../../lib/api";
import CreateMemberBox, { resultLine } from "../CreateMemberBox";

const mocked = vi.mocked(founderMembersCreate);
const ok = (over: Partial<Parameters<typeof resultLine>[0]> = {}) => ({
  ok: true as const, created: true, activated: false, activate_error: null, sent: true, link_throttled: false, email_hash: "h", ...over,
});

describe("CreateMemberBox (#150)", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("CREATE is disabled until the text is an email", () => {
    render(<CreateMemberBox />);
    expect(screen.getByTestId("create-member-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "not an email" } });
    expect(screen.getByTestId("create-member-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "ruy@example.com" } });
    expect(screen.getByTestId("create-member-submit")).toBeEnabled();
  });

  it("★ posts the email with both flags and reads 'created · activated · link sent'", async () => {
    mocked.mockResolvedValue(ok({ activated: true }));
    const onCreated = vi.fn();
    render(<CreateMemberBox onCreated={onCreated} />);
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "Ruy@Example.com" } });
    fireEvent.click(screen.getByTestId("create-member-activate"));
    fireEvent.click(screen.getByTestId("create-member-submit"));
    await waitFor(() => expect(screen.getByTestId("create-member-result")).toBeInTheDocument());
    expect(mocked).toHaveBeenCalledWith({ email: "Ruy@Example.com", activate: true, send_link: true });
    expect(screen.getByTestId("create-member-result")).toHaveTextContent("created · activated · link sent");
    expect(onCreated).toHaveBeenCalledWith("ruy@example.com", expect.objectContaining({ created: true }));
  });

  it("an existing account reads 'already existed · link resent'", async () => {
    mocked.mockResolvedValue(ok({ created: false }));
    render(<CreateMemberBox />);
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "again@example.com" } });
    fireEvent.click(screen.getByTestId("create-member-submit"));
    await waitFor(() => expect(screen.getByTestId("create-member-result")).toHaveTextContent("already existed · link resent"));
  });

  it("send link unticked: no 'link sent' claim", async () => {
    mocked.mockResolvedValue(ok({ sent: false }));
    render(<CreateMemberBox />);
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "quiet@example.com" } });
    fireEvent.click(screen.getByTestId("create-member-sendlink"));
    fireEvent.click(screen.getByTestId("create-member-submit"));
    await waitFor(() => expect(screen.getByTestId("create-member-result")).toBeInTheDocument());
    expect(mocked).toHaveBeenCalledWith({ email: "quiet@example.com", activate: false, send_link: false });
    expect(screen.getByTestId("create-member-result")).toHaveTextContent("created");
    expect(screen.getByTestId("create-member-result").textContent).not.toMatch(/link/);
  });

  it("a refused activation is said: the doc exists, the seat did not happen", () => {
    expect(resultLine(ok({ activated: false, activate_error: "cohort_error" })))
      .toBe("created · link sent · activate failed: cohort_error");
  });

  it("a throttled link is said, not hidden", () => {
    expect(resultLine(ok({ created: false, sent: false, link_throttled: true })))
      .toBe("already existed · link throttled — try again in a few minutes");
  });

  it("a failed post is shown", async () => {
    mocked.mockRejectedValue(new Error("Founder cohort required"));
    render(<CreateMemberBox />);
    fireEvent.change(screen.getByTestId("create-member-email"), { target: { value: "x@example.com" } });
    fireEvent.click(screen.getByTestId("create-member-submit"));
    await waitFor(() => expect(screen.getByTestId("create-member-error")).toHaveTextContent("Founder cohort required"));
  });

  it("a prefill lands in the box", () => {
    render(<CreateMemberBox prefill="miss@example.com" />);
    expect(screen.getByTestId("create-member-email")).toHaveValue("miss@example.com");
    expect(screen.getByTestId("create-member-submit")).toBeEnabled();
  });
});
