// v64 / Unit 67 — ModelPreferences route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ModelPreferencesResponse } from "../../lib/api";
import ModelPreferences from "../ModelPreferences";

// C1: the badge reads operator_id from the auth snapshot (hydrated
// profile). Tests control it by assigning SNAP.profile before render.
const SNAP = vi.hoisted(() => ({
  session: "sid-test",
  user: "u",
  profile: null as null | { user: string; operator_id?: string | null },
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getModelPreferences: vi.fn(),
    setModelPreferences: vi.fn(),
  };
});

vi.mock("../../lib/auth", () => ({
  getAuthSnapshot: () => SNAP,
  subscribeAuth:   () => () => {},
}));

import {
  getModelPreferences,
  setModelPreferences,
} from "../../lib/api";

const mockGet = vi.mocked(getModelPreferences);
const mockSet = vi.mocked(setModelPreferences);

function makeResponse(
  overrides: Partial<ModelPreferencesResponse> = {},
): ModelPreferencesResponse {
  return {
    operator_id: "op_alice",
    provider:    "anthropic",
    model:       "claude-haiku-4-5-20251001",
    source:      "default",
    ...overrides,
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/model-preferences"]}>
      <ModelPreferences />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockGet.mockReset();
  mockSet.mockReset();
  SNAP.profile = { user: "u", operator_id: "op_alice" };
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("ModelPreferences route", () => {
  test("calls getModelPreferences on mount", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
  });

  test("renders current provider + model + source after load", async () => {
    mockGet.mockResolvedValueOnce(makeResponse({
      provider: "openai", model: "gpt-5.4", source: "vault",
    }));
    renderRoute();
    await screen.findByText("openai");
    expect(screen.getByText("gpt-5.4")).toBeInTheDocument();
    expect(screen.getByText("explicit (vault)")).toBeInTheDocument();
  });

  test("source label maps default → default (chain)", async () => {
    mockGet.mockResolvedValueOnce(makeResponse({ source: "default" }));
    renderRoute();
    await screen.findByText("default (chain)");
  });

  test("authed-as badge renders the profile operator_id", async () => {
    SNAP.profile = { user: "u", operator_id: "op_christian" };
    mockGet.mockResolvedValueOnce(makeResponse({ operator_id: "op_christian" }));
    renderRoute();
    await screen.findByText("op_christian");
  });

  test("changing provider snaps model to that provider's default", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await screen.findByText("anthropic");

    await user.selectOptions(
      screen.getByLabelText("Provider") as HTMLSelectElement,
      "openai",
    );
    const modelInput = screen.getByLabelText("Model") as HTMLInputElement;
    expect(modelInput.value).toBe("gpt-5.4");
  });

  test("SAVE posts the selected provider + model", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValueOnce(makeResponse());
    mockSet.mockResolvedValueOnce(makeResponse({
      provider: "openai", model: "gpt-5.4", source: "vault",
    }));
    renderRoute();
    await screen.findByText("anthropic");

    await user.selectOptions(
      screen.getByLabelText("Provider") as HTMLSelectElement,
      "openai",
    );
    await user.click(screen.getByRole("button", { name: "SAVE" }));

    await waitFor(() => expect(mockSet).toHaveBeenCalledTimes(1));
    expect(mockSet).toHaveBeenCalledWith("openai", "gpt-5.4");
  });

  test("error from setModelPreferences surfaces in banner", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValueOnce(makeResponse());
    mockSet.mockRejectedValueOnce(new Error("validation failed"));
    renderRoute();
    await screen.findByText("anthropic");

    await user.click(screen.getByRole("button", { name: "SAVE" }));
    await screen.findByText(/validation failed/i);
  });

  test("SAVE button is disabled when model is empty", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await screen.findByText("anthropic");

    const modelInput = screen.getByLabelText("Model") as HTMLInputElement;
    await user.clear(modelInput);
    expect(screen.getByRole("button", { name: "SAVE" })).toBeDisabled();
  });

  test("provider dropdown has all 5 providers", async () => {
    mockGet.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await screen.findByText("anthropic");

    const select = screen.getByLabelText("Provider") as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual([
      "anthropic", "openai", "gemini", "xai", "local",
    ]);
  });

  test("post-save success timestamp renders", async () => {
    const user = userEvent.setup();
    mockGet.mockResolvedValueOnce(makeResponse());
    mockSet.mockResolvedValueOnce(makeResponse({ source: "vault" }));
    renderRoute();
    await screen.findByText("anthropic");

    await user.click(screen.getByRole("button", { name: "SAVE" }));
    await screen.findByText(/saved at/i);
  });
});
