// v63 / Unit 48 — OperatorVault route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { VaultInspectorResponse } from "../../lib/api";
import OperatorVault from "../OperatorVault";

// C1: operator_id comes from the auth snapshot (hydrated profile);
// refresh() re-reads getProfile(). Tests assign SNAP.profile pre-render.
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
    getOperatorVault: vi.fn(),
    getProfile:       vi.fn(() => SNAP.profile),
  };
});

vi.mock("../../lib/auth", () => ({
  getAuthSnapshot: () => SNAP,
  subscribeAuth:   () => () => {},
}));

import { getOperatorVault } from "../../lib/api";

const mockVault = vi.mocked(getOperatorVault);

// --------------------------------------------------------------------
// Fixtures
// --------------------------------------------------------------------
function makeColdResponse(operatorId: string = "op_anon"): VaultInspectorResponse {
  return {
    operator_id:  operatorId,
    vault:        null,
    last_updated: "",
  };
}

function makeWarmResponse(operatorId: string = "op_anon"): VaultInspectorResponse {
  return {
    operator_id:  operatorId,
    vault: {
      elins: {
        last_fusion:    { regime: "stable" },
        last_long_arc:  { decision: "allow" },
        fusion_history: [{ step: 1 }, { step: 2 }],
      },
    },
    last_updated: "2026-05-12T10:00:05+00:00",
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator-vault"]}>
      <OperatorVault />
    </MemoryRouter>,
  );
}

// --------------------------------------------------------------------
// Setup / teardown
// --------------------------------------------------------------------
beforeEach(() => {
  mockVault.mockReset();
  SNAP.profile = { user: "u", operator_id: "op_alice" };
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

// --------------------------------------------------------------------
// Tests
// --------------------------------------------------------------------
describe("OperatorVault route", () => {
  test("calls getOperatorVault on mount (server uses authed id)", async () => {
    // v64 / Unit 66 — argument is decorative under auth wall.
    mockVault.mockResolvedValueOnce(makeColdResponse());
    renderRoute();
    await waitFor(() => expect(mockVault).toHaveBeenCalledTimes(1));
  });

  test("passes profile operator_id when hydrated", async () => {
    SNAP.profile = { user: "u", operator_id: "op_christian" };
    mockVault.mockResolvedValueOnce(makeColdResponse("op_christian"));
    renderRoute();
    await waitFor(() => expect(mockVault).toHaveBeenCalledWith("op_christian"));
  });

  test("renders empty state when vault is null", async () => {
    mockVault.mockResolvedValueOnce(makeColdResponse());
    renderRoute();
    await screen.findByText(/No vault recorded/i);
  });

  test("renders last_updated stamp when present", async () => {
    mockVault.mockResolvedValueOnce(makeWarmResponse());
    renderRoute();
    await screen.findByText(/updated 2026-05-12T10:00:05/);
  });

  test('renders "never updated" when last_updated empty', async () => {
    mockVault.mockResolvedValueOnce(makeColdResponse());
    renderRoute();
    await screen.findByText(/never updated/i);
  });

  test("renders nested JSON keys after warm load", async () => {
    mockVault.mockResolvedValueOnce(makeWarmResponse());
    renderRoute();
    // Top-level "elins" key visible.
    await screen.findByText("elins:");
  });

  test("REFRESH re-fetches the vault", async () => {
    const user = userEvent.setup();
    mockVault.mockResolvedValue(makeColdResponse());
    renderRoute();
    await waitFor(() => expect(mockVault).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "REFRESH" }));
    await waitFor(() => expect(mockVault).toHaveBeenCalledTimes(2));
  });

  test("error from vault call surfaces in the banner", async () => {
    mockVault.mockRejectedValueOnce(new Error("server unreachable"));
    renderRoute();
    await screen.findByText(/server unreachable/i);
  });

  test("renders collapsed nested object count label", async () => {
    mockVault.mockResolvedValueOnce(makeWarmResponse());
    renderRoute();
    // Root vault is auto-expanded at depth 0 but the `elins` child
    // at depth 1 stays collapsed and renders its key-count label.
    // The warm fixture has 3 keys under elins.
    await screen.findByText(/3 keys/);
  });

  test("authed-as badge renders the profile operator_id", async () => {
    // C1 (2026-08-21) — the badge shows the hydrated profile's
    // operator_id (never the account email, which the engine rejects).
    SNAP.profile = { user: "u", operator_id: "op_christian" };
    mockVault.mockResolvedValueOnce(makeColdResponse("op_christian"));
    renderRoute();
    await waitFor(() => expect(mockVault).toHaveBeenCalledTimes(1));
    expect(screen.getByText("op_christian")).toBeInTheDocument();
  });
});
