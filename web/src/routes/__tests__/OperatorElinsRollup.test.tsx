// v72 / Unit 81 — OperatorElinsRollup route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsRollupResult,
  ElInsRollupWindow,
} from "../../lib/api";
import OperatorElinsRollup from "../OperatorElinsRollup";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsRollup: vi.fn(),
  };
});

import { getElInsRollup } from "../../lib/api";
const mockRollup = vi.mocked(getElInsRollup);

function makeResult(
  overrides: Partial<ElInsRollupResult> = {},
): ElInsRollupResult {
  return {
    avg_el:       3.2,
    avg_ins:      4.1,
    avg_tsi:      75,
    reasoning_mode_distribution: {
      grounding: 2, analysis: 1, stabilization: 1,
    },
    record_count: 4,
    window_start: 1700000000,
    window_end:   1700086400,
    ...overrides,
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/rollup"]}>
      <OperatorElinsRollup />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockRollup.mockReset(); });
afterEach(() => { try { localStorage.clear(); } catch { /* noop */ } });

describe("OperatorElinsRollup route", () => {
  test("fires getElInsRollup three times on mount (24h/7d/30d)", async () => {
    mockRollup.mockResolvedValue(makeResult());
    renderRoute();
    await waitFor(() => expect(mockRollup).toHaveBeenCalledTimes(3));
    // Each call carries exactly one of the three windows.
    const args = mockRollup.mock.calls.map((c) => c[0] as ElInsRollupWindow);
    expect(args.sort()).toEqual(["24h", "30d", "7d"]);
  });

  test("renders three cards (24h, 7d, 30d)", async () => {
    mockRollup.mockResolvedValue(makeResult());
    renderRoute();
    await screen.findByTestId("el-ins-rollup-card-24h");
    expect(screen.getByTestId("el-ins-rollup-card-7d")).toBeInTheDocument();
    expect(screen.getByTestId("el-ins-rollup-card-30d")).toBeInTheDocument();
  });

  test("each card displays its stats", async () => {
    mockRollup.mockResolvedValue(makeResult({
      avg_el: 5.5, avg_ins: 2.5, avg_tsi: 60, record_count: 10,
    }));
    renderRoute();
    const card = await screen.findByTestId("el-ins-rollup-card-24h");
    expect(card).toHaveTextContent("5.50");      // avg_el
    expect(card).toHaveTextContent("2.50");      // avg_ins
    expect(card).toHaveTextContent("60/100");    // avg_tsi
    expect(card).toHaveTextContent("10");        // record_count
  });

  test("reasoning-mode pie includes labels from the distribution", async () => {
    mockRollup.mockResolvedValue(makeResult({
      reasoning_mode_distribution: { grounding: 3, analysis: 1 },
    }));
    renderRoute();
    const card = await screen.findByTestId("el-ins-rollup-card-24h");
    expect(card).toHaveTextContent("grounding: 3");
    expect(card).toHaveTextContent("analysis: 1");
  });

  test("empty distribution renders 'no records' placeholder", async () => {
    mockRollup.mockResolvedValue(makeResult({
      reasoning_mode_distribution: {}, record_count: 0,
    }));
    renderRoute();
    const card = await screen.findByTestId("el-ins-rollup-card-24h");
    expect(card).toHaveTextContent(/no records/i);
  });

  test("REFRESH re-fires all three", async () => {
    const user = userEvent.setup();
    mockRollup.mockResolvedValue(makeResult());
    renderRoute();
    await waitFor(() => expect(mockRollup).toHaveBeenCalledTimes(3));
    await user.click(screen.getByTestId("el-ins-rollup-refresh"));
    await waitFor(() => expect(mockRollup).toHaveBeenCalledTimes(6));
  });

  test("error from any window surfaces in banner", async () => {
    mockRollup.mockRejectedValueOnce(new Error("rollup boom"));
    renderRoute();
    await screen.findByTestId("el-ins-rollup-error");
  });
});
