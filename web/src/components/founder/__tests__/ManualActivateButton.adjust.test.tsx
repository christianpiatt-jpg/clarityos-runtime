/**
 * #142 -- Adjust in DOLLARS at $0.01: 15.00 typed -> 15_000_000 on the wire;
 * the response's dollars are said back; a bad amount never reaches the wire.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, founderMembershipCredits: vi.fn(), founderMembershipActivate: vi.fn(), founderMembershipCancel: vi.fn() };
});

import * as api from "../../../lib/api";
import ManualActivateButton from "../ManualActivateButton";

afterEach(() => vi.clearAllMocks());

describe("ManualActivateButton -- Adjust in dollars", () => {
  it("15.00 -> 15_000_000 micro on the wire; the dollars are said back", async () => {
    vi.mocked(api.founderMembershipCredits).mockResolvedValue({
      ok: true, user: "ava@example.com", balance: 15_000_000, balance_micro: 15_000_000,
      balance_display: "$15.00", delta: 15_000_000, delta_micro: 15_000_000, delta_display: "+$15.00",
    } as never);
    render(<ManualActivateButton user="ava@example.com" />);
    const input = screen.getByLabelText("Dollars") as HTMLInputElement;
    expect(input.value).toBe("15.00");
    fireEvent.click(screen.getByTestId("adjust-submit"));
    await waitFor(() => expect(api.founderMembershipCredits).toHaveBeenCalledWith("ava@example.com", 15_000_000, undefined));
    expect(await screen.findByText(/\+\$15\.00 \u2192 balance \$15\.00/)).toBeInTheDocument();
  });
  it("-2.50 -> -2_500_000; 1.005 never reaches the wire", async () => {
    vi.mocked(api.founderMembershipCredits).mockResolvedValue({ ok: true } as never);
    render(<ManualActivateButton user="x@example.com" />);
    const input = screen.getByLabelText("Dollars");
    fireEvent.change(input, { target: { value: "-2.50" } });
    fireEvent.click(screen.getByTestId("adjust-submit"));
    await waitFor(() => expect(api.founderMembershipCredits).toHaveBeenCalledWith("x@example.com", -2_500_000, undefined));
    fireEvent.change(input, { target: { value: "1.005" } });
    fireEvent.click(screen.getByTestId("adjust-submit"));
    expect(await screen.findByText(/Enter a dollar amount/)).toBeInTheDocument();
    expect(api.founderMembershipCredits).toHaveBeenCalledTimes(1);
  });
});
