/**
 * #162 (f) -- CT-1 ruled 09-04: $50 recurring until cancelled; no one-time
 * path exists. The page sells none, and the billing line reflects the
 * config flag without the "free invites only" fiction.
 */
import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    config: vi.fn(async () => ({ ok: true, data: { terrace_1_cap: 500, terrace_1_redeemed: 4, billing_configured: false } })),
    getProfile: vi.fn(() => null),
  };
});
vi.mock("../../lib/auth", async () => {
  const actual = await vi.importActual<typeof import("../../lib/auth")>("../../lib/auth");
  return { ...actual, syncProfile: vi.fn(async () => null) };
});

import * as api from "../../lib/api";
import Plans from "../Plans";

describe("Plans -- no one-time membership is offered", () => {
  test("the copy sells $50 recurring until cancelled and nothing one-time", async () => {
    render(<MemoryRouter><Plans /></MemoryRouter>);
    expect(await screen.findByTestId("plans-terms")).toHaveTextContent("recurring until you cancel");
    expect(screen.queryByText(/one-time/i)).toBeNull();
    expect(screen.queryByText(/expires permanently/i)).toBeNull();
    expect(screen.queryByText(/Compute meters/i)).toBeNull();
    expect(screen.getByText("$50 a month, recurring until you cancel")).toBeInTheDocument();
  });
  test("the billing line says offline, not \"free invites only\"", async () => {
    render(<MemoryRouter><Plans /></MemoryRouter>);
    expect(await screen.findByText("offline")).toBeInTheDocument();
    expect(screen.queryByText(/free invites/i)).toBeNull();
  });
});

describe("Plans -- the billing line reads the flag", () => {
  test("billing_configured true reads online", async () => {
    vi.mocked(api.config).mockResolvedValueOnce({ ok: true, data: { billing_configured: true } } as never);
    render(<MemoryRouter><Plans /></MemoryRouter>);
    expect(await screen.findByText("online")).toBeInTheDocument();
  });
});
