/**
 * #192 -- "$1,000" is the ADJUST CAP per call, not a price; the caption
 * says both so neither reads as the other.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, founderMembershipCredits: vi.fn(), founderMembershipActivate: vi.fn(), founderMembershipCancel: vi.fn() };
});

import ManualActivateButton from "../ManualActivateButton";

describe("ManualActivateButton -- the cap is a cap (#192)", () => {
  it("★ the caption names the max per call and the price of a run", () => {
    render(<ManualActivateButton user="ava@example.com" />);
    expect(screen.getByTestId("adjust-cap-caption"))
      .toHaveTextContent("adjust ±$1,000.00 max per call · a #G run costs $1.00");
    expect(screen.queryByText(/\(\±\$1,000 per call\)/)).toBeNull();
  });
});
