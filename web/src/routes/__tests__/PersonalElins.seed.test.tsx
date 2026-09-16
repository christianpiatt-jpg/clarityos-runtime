/**
 * The char cap is gone (CT-1 2026-09-16, "delete the char cap on thread and
 * personal elins"): the seed counter counts, and warns about nothing; the
 * 6,000 mirror of the kernel's window no longer exists on this page.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    runEmotionalPhysics: vi.fn(() => new Promise(() => {})),
    runElinsV2: vi.fn(() => new Promise(() => {})),
  };
});

import * as page from "../PersonalElins";
import PersonalElins from "../PersonalElins";

afterEach(() => vi.clearAllMocks());

describe("the seed counter after the cap", () => {
  it("★ a 7,000-character seed counts and warns about nothing", () => {
    render(<MemoryRouter><PersonalElins /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Personal state — seed text"), { target: { value: "x".repeat(7000) } });
    expect(screen.getByTestId("seed-counter")).toHaveTextContent("7,000 characters");
    expect(screen.getByTestId("seed-counter").textContent).not.toMatch(/\//);
    expect(screen.queryByTestId("seed-overflow-warning")).toBeNull();
  });

  it("the 6,000 mirror is gone from the module", () => {
    expect("SEED_CHAR_LIMIT" in page).toBe(false);
  });
});
