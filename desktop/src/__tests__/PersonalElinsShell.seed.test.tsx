/**
 * The char cap is gone (CT-1 2026-09-16, "delete the char cap on thread and
 * personal elins"): the desktop seed counter counts, and warns about
 * nothing; the 6,000 mirror of the kernel's cap no longer exists.
 */
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("../DesktopShell", () => ({
  default: ({ center }: { center: ReactNode }) => center,
}));
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    runEmotionalPhysics: vi.fn(() => new Promise(() => {})),
    runElinsV2: vi.fn(() => new Promise(() => {})),
  };
});

import * as shell from "../PersonalElinsShell";
import PersonalElinsShell from "../PersonalElinsShell";

afterEach(() => vi.clearAllMocks());

describe("the desktop seed counter after the cap", () => {
  it("★ a 7,000-character seed counts and warns about nothing", () => {
    render(<PersonalElinsShell onSignOut={vi.fn()} onNavigate={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Personal state — seed text"), { target: { value: "x".repeat(7000) } });
    expect(screen.getByTestId("seed-counter").textContent).toContain("7,000 characters");
    expect(screen.getByTestId("seed-counter").textContent).not.toMatch(/\//);
    expect(screen.queryByTestId("seed-overflow-warning")).toBeNull();
  });

  it("the 6,000 mirror is gone from the module", () => {
    expect("SEED_CHAR_LIMIT" in shell).toBe(false);
  });
});
