// v74 / Unit 84 — SubscriptionGate tests.
//
// Covers:
//   * Default state renders BETA_NOTICE + children (Badge / AuthToggle / ActionControl).
//   * Successful confirm transitions to SUCCESS state (replaces gate region).
//   * subscription_inactive error surfaces inline error message.
//   * cohort_full error surfaces inline error message.
//   * Identity invariant: no operator_id text appears.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import SubscriptionGate from "../SubscriptionGate";
import { ApiError } from "../../../lib/api";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>(
    "../../../lib/api",
  );
  return {
    ...actual,
    confirmMembership: vi.fn(),
  };
});

import { confirmMembership } from "../../../lib/api";
const mockConfirm = vi.mocked(confirmMembership);

function makeSuccessResponse() {
  return {
    ok: true as const,
    state: {
      user: "alice",
      membership: {
        tier: "founding_500",
        status: "active",
        confirmed: true,
        confirmed_ts: 1700000000.0,
        next_price: 50.0,
      },
    },
  };
}

function renderGate() {
  return render(
    <MemoryRouter initialEntries={["/founding500/confirm"]}>
      <SubscriptionGate />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockConfirm.mockReset(); });
afterEach(() => { try { localStorage.clear(); } catch { /* noop */ } });

describe("SubscriptionGate", () => {
  test("default state renders BETA_NOTICE + badge + auth-toggle + action-control", () => {
    renderGate();
    expect(screen.getByTestId("subscription-gate")).toBeInTheDocument();
    expect(screen.getByTestId("subscription-gate-notice")).toBeInTheDocument();
    expect(screen.getByTestId("founding500-badge")).toBeInTheDocument();
    expect(screen.getByTestId("auth-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("action-control")).toBeInTheDocument();

    // Perplexity-canonical headers must be present.
    expect(screen.getByText(/founding 500 beta/i)).toBeInTheDocument();
    expect(screen.getByText(/clarityos is in beta\./i)).toBeInTheDocument();

    // No success or error region in default state.
    expect(screen.queryByTestId("subscription-gate-success")).not.toBeInTheDocument();
    expect(screen.queryByTestId("subscription-gate-error")).not.toBeInTheDocument();
  });

  test("on successful confirm, swaps to SUCCESS state", async () => {
    const user = userEvent.setup();
    mockConfirm.mockResolvedValueOnce(makeSuccessResponse());

    renderGate();
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("subscription-gate-success")).toBeInTheDocument();
    });
    expect(screen.getByText(/access confirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/founding 500 status is active\./i)).toBeInTheDocument();
    // Default-state regions are gone after success replaces the gate.
    expect(screen.queryByTestId("subscription-gate-notice")).not.toBeInTheDocument();
    expect(screen.queryByTestId("action-control")).not.toBeInTheDocument();
    expect(mockConfirm).toHaveBeenCalledTimes(1);
  });

  test("on subscription_inactive, shows inline error message", async () => {
    const user = userEvent.setup();
    mockConfirm.mockRejectedValueOnce(
      new ApiError("subscription_inactive", "No active subscription", 409, {
        error: "subscription_inactive",
      }),
    );

    renderGate();
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("subscription-gate-error")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/no active subscription detected/i),
    ).toBeInTheDocument();
    // Still in idle/error state — gate region present, not success.
    expect(screen.getByTestId("subscription-gate")).toBeInTheDocument();
    expect(screen.queryByTestId("subscription-gate-success")).not.toBeInTheDocument();
  });

  test("on cohort_full, shows the cohort-specific error", async () => {
    const user = userEvent.setup();
    mockConfirm.mockRejectedValueOnce(
      new ApiError("cohort_full", "Cohort full", 409, {
        error: "cohort_full",
      }),
    );

    renderGate();
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("subscription-gate-error")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/founding 500 cohort is at capacity/i),
    ).toBeInTheDocument();
  });

  test("identity invariant: no operator_id label in DOM", () => {
    renderGate();
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
    // No bare "op_" prefixed strings (used as operator id prefix in the codebase).
    const allText = document.body.textContent || "";
    expect(allText).not.toMatch(/\bop_[a-z0-9]+/i);
  });
});
