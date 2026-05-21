// v74 / Unit 84 — ActionControl tests.
//
// Covers:
//   * Button disabled until checkbox checked.
//   * Clicking submit calls confirmMembership() once.
//   * onSuccess fires on resolved promise.
//   * onError fires with the correct classified code on ApiError.
//   * Generic error path: non-ApiError throws map to "generic".

import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ActionControl from "../ActionControl";
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

function makeResp() {
  return {
    ok: true as const,
    state: {
      user: "alice",
      membership: { tier: "founding_500", status: "active", confirmed: true },
    },
  };
}

beforeEach(() => { mockConfirm.mockReset(); });

describe("ActionControl", () => {
  test("button disabled until checkbox checked", async () => {
    const user = userEvent.setup();
    render(<ActionControl onSuccess={() => {}} onError={() => {}} />);

    const button = screen.getByTestId("action-control-submit");
    expect(button).toBeDisabled();

    await user.click(screen.getByTestId("action-control-checkbox"));
    expect(button).toBeEnabled();
  });

  test("on submit, calls confirmMembership and fires onSuccess", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    const onError = vi.fn();
    mockConfirm.mockResolvedValueOnce(makeResp());

    render(<ActionControl onSuccess={onSuccess} onError={onError} />);
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(mockConfirm).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  test("subscription_inactive ApiError maps to subscription_inactive code", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    const onError = vi.fn();
    mockConfirm.mockRejectedValueOnce(
      new ApiError("subscription_inactive", "x", 409, { error: "subscription_inactive" }),
    );

    render(<ActionControl onSuccess={onSuccess} onError={onError} />);
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    expect(onError).toHaveBeenCalledWith("subscription_inactive");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  test("cohort_full ApiError maps to cohort_full code", async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    mockConfirm.mockRejectedValueOnce(
      new ApiError("cohort_full", "x", 409, { error: "cohort_full" }),
    );

    render(<ActionControl onSuccess={() => {}} onError={onError} />);
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => expect(onError).toHaveBeenCalledWith("cohort_full"));
  });

  test("non-ApiError throws map to generic", async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    mockConfirm.mockRejectedValueOnce(new Error("network blip"));

    render(<ActionControl onSuccess={() => {}} onError={onError} />);
    await user.click(screen.getByTestId("action-control-checkbox"));
    await user.click(screen.getByTestId("action-control-submit"));

    await waitFor(() => expect(onError).toHaveBeenCalledWith("generic"));
  });
});
