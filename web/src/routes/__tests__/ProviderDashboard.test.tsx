// v68 / Unit 73 — ProviderDashboard route tests.
//
// Mocks all three API helpers (health, models, config) at module scope
// and verifies the dashboard joins them into a single table.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ProviderConfigResponse,
  ProviderHealthResponse,
  ProviderModelsResponse,
} from "../../lib/api";
import ProviderDashboard from "../ProviderDashboard";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getProviderHealth: vi.fn(),
    getProviderModels: vi.fn(),
    getProviderConfig: vi.fn(),
  };
});

import {
  getProviderConfig,
  getProviderHealth,
  getProviderModels,
} from "../../lib/api";

const mockHealth = vi.mocked(getProviderHealth);
const mockModels = vi.mocked(getProviderModels);
const mockConfig = vi.mocked(getProviderConfig);

function makeHealth(): ProviderHealthResponse {
  return {
    anthropic: { available: true,  error: null },
    openai:    { available: false, error: "401 unauthorized" },
    gemini:    { available: true,  error: null },
    mock:      { available: true,  error: null },
  };
}

function makeModels(): ProviderModelsResponse {
  return {
    registry: {
      anthropic: ["anthropic:claude-3.7"],
      openai:    ["openai:gpt-4.2"],
      google:    ["google:gemini-2.0"],
      xai:       ["xai:groq-llama"],
      local:     ["local:llama3.1"],
    },
    supported: [
      "openai:gpt-4.2",
      "anthropic:claude-3.7",
      "google:gemini-2.0",
      "xai:groq-llama",
      "local:llama3.1",
      "auto",
    ],
  };
}

function makeConfig(): ProviderConfigResponse {
  return {
    timeouts: {
      anthropic: { call: 30.0, health: 3.0 },
      openai:    { call: 30.0, health: 3.0 },
      gemini:    { call: 30.0, health: 3.0 },
      xai:       { call: 30.0, health: 3.0 },
      local:     { call: 30.0, health: 3.0 },
    },
    retries: {
      anthropic: 0, openai: 0, gemini: 0, xai: 0, local: 0,
    },
    defaults: { call_timeout: 30.0, health_timeout: 3.0, retries: 0 },
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/providers"]}>
      <ProviderDashboard />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockHealth.mockReset();
  mockModels.mockReset();
  mockConfig.mockReset();
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("ProviderDashboard route", () => {
  test("fires all three endpoints on mount", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await waitFor(() => {
      expect(mockHealth).toHaveBeenCalledTimes(1);
      expect(mockModels).toHaveBeenCalledTimes(1);
      expect(mockConfig).toHaveBeenCalledTimes(1);
    });
  });

  test("renders the dashboard table after fetch", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("provider-dashboard-table");
  });

  test("rows include providers from health, models, and config", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const table = await screen.findByTestId("provider-dashboard-table");
    expect(table).toHaveTextContent("anthropic");
    expect(table).toHaveTextContent("openai");
    expect(table).toHaveTextContent("gemini");
    expect(table).toHaveTextContent("mock");      // from health
    expect(table).toHaveTextContent("xai");        // from config + models
    expect(table).toHaveTextContent("local");      // from config + models
    expect(table).toHaveTextContent("google");     // from models registry
  });

  test("status column shows available + unavailable", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("provider-dashboard-table");
    expect(screen.getAllByText("available").length).toBeGreaterThan(0);
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/401 unauthorized/i)).toBeInTheDocument();
  });

  test("call and health timeout columns render the config values", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const table = await screen.findByTestId("provider-dashboard-table");
    // 5 providers × 1 row each = 5 cells of "30" plus 5 cells of "3"
    // plus defaults row (1 each).
    expect(table).toHaveTextContent("30");
    expect(table).toHaveTextContent("3");
  });

  test("models column renders registry model ids", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const table = await screen.findByTestId("provider-dashboard-table");
    expect(table).toHaveTextContent("anthropic:claude-3.7");
    expect(table).toHaveTextContent("openai:gpt-4.2");
  });

  test("supported list panel includes the auto sentinel", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    const heading = await screen.findByText("SUPPORTED MODEL IDS");
    // Scope to the panel that wraps the heading — "auto" might also
    // appear in body prose elsewhere; we only care about the list.
    const panel = heading.closest("div");
    expect(panel).not.toBeNull();
    const list = panel!.querySelector("ul");
    expect(list).not.toBeNull();
    expect(within(list!).getByText("auto")).toBeInTheDocument();
  });

  test("REFRESH button re-fires all three", async () => {
    const user = userEvent.setup();
    mockHealth.mockResolvedValue(makeHealth());
    mockModels.mockResolvedValue(makeModels());
    mockConfig.mockResolvedValue(makeConfig());
    renderRoute();
    await waitFor(() => expect(mockHealth).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("provider-dashboard-refresh"));
    await waitFor(() => {
      expect(mockHealth).toHaveBeenCalledTimes(2);
      expect(mockModels).toHaveBeenCalledTimes(2);
      expect(mockConfig).toHaveBeenCalledTimes(2);
    });
  });

  test("error from any endpoint surfaces in the banner", async () => {
    mockHealth.mockRejectedValueOnce(new Error("health boom"));
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("provider-dashboard-error");
  });

  test("defaults row renders below the per-provider rows", async () => {
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("provider-dashboard-table");
    expect(screen.getByText("(defaults)")).toBeInTheDocument();
  });

  test("no operator_id label appears anywhere in the dashboard", async () => {
    // Identity invariant: Units 70-71 removed operator_id surfacing across
    // operator screens. The Provider Dashboard is operator-scoped (auth-
    // gated) but must not re-introduce operator_id labels.
    mockHealth.mockResolvedValueOnce(makeHealth());
    mockModels.mockResolvedValueOnce(makeModels());
    mockConfig.mockResolvedValueOnce(makeConfig());
    renderRoute();
    await screen.findByTestId("provider-dashboard-table");
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
