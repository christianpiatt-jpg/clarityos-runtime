// v65 / Unit 69 — ProviderHealth route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ProviderHealthResponse } from "../../lib/api";
import ProviderHealth from "../ProviderHealth";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getProviderHealth: vi.fn(),
  };
});

import { getProviderHealth } from "../../lib/api";
const mockHealth = vi.mocked(getProviderHealth);

function makeAllUp(): ProviderHealthResponse {
  return {
    anthropic: { available: true,  error: null },
    openai:    { available: true,  error: null },
    gemini:    { available: true,  error: null },
    mock:      { available: true,  error: null },
  };
}

function makeMixed(): ProviderHealthResponse {
  return {
    anthropic: { available: true,  error: null },
    openai:    { available: false, error: "401 unauthorized" },
    gemini:    { available: false, error: "connection timeout" },
    mock:      { available: true,  error: null },
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/provider-health"]}>
      <ProviderHealth />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockHealth.mockReset();
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("ProviderHealth route", () => {
  test("calls getProviderHealth on mount", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    await waitFor(() => expect(mockHealth).toHaveBeenCalledTimes(1));
  });

  test("renders all 4 providers in the table", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    // Scope to the table — "mock" also appears in the description
    // prose above, which would trip a global getByText("mock").
    const table = await screen.findByRole("table");
    const t = within(table);
    expect(t.getByText("anthropic")).toBeInTheDocument();
    expect(t.getByText("openai")).toBeInTheDocument();
    expect(t.getByText("gemini")).toBeInTheDocument();
    expect(t.getByText("mock")).toBeInTheDocument();
  });

  test("shows available status when provider is up", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    // 4 providers all available — 4 "available" texts.
    const labels = await screen.findAllByText("available");
    expect(labels.length).toBe(4);
  });

  test("shows unavailable + error text when provider is down", async () => {
    mockHealth.mockResolvedValueOnce(makeMixed());
    renderRoute();
    await screen.findByText("401 unauthorized");
    expect(screen.getByText("connection timeout")).toBeInTheDocument();
    // 2 unavailable (openai + gemini).
    const labels = await screen.findAllByText("unavailable");
    expect(labels.length).toBe(2);
  });

  test("dash placeholder when no error", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    await screen.findByText("anthropic");
    // All providers have null error → renders "—" for each.
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(4);
  });

  test("REFRESH re-fetches", async () => {
    const user = userEvent.setup();
    mockHealth.mockResolvedValue(makeAllUp());
    renderRoute();
    await waitFor(() => expect(mockHealth).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "REFRESH" }));
    await waitFor(() => expect(mockHealth).toHaveBeenCalledTimes(2));
  });

  test("error from health endpoint surfaces in banner", async () => {
    mockHealth.mockRejectedValueOnce(new Error("backend unreachable"));
    renderRoute();
    await screen.findByText(/backend unreachable/i);
  });

  test("mock provider listed first per display order", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    const table = await screen.findByRole("table");
    const t = within(table);
    // Collect provider rows (table body only) in DOM order.
    const monoCells = t.getAllByText(/^(mock|anthropic|openai|gemini)$/);
    const orderedNames = monoCells.map((c) => c.textContent);
    expect(orderedNames).toEqual(["mock", "anthropic", "openai", "gemini"]);
  });

  test("last-checked timestamp appears after fetch", async () => {
    mockHealth.mockResolvedValueOnce(makeAllUp());
    renderRoute();
    await screen.findByText("anthropic");
    expect(screen.getByText(/last checked/i)).toBeInTheDocument();
  });
});
