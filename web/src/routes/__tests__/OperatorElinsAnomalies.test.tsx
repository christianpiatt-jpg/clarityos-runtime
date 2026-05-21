// v72 / Unit 80 — OperatorElinsAnomalies route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsAnomaliesResponse,
  ElInsAnomaly,
} from "../../lib/api";
import OperatorElinsAnomalies from "../OperatorElinsAnomalies";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsAnomalies: vi.fn(),
  };
});

import { getElInsAnomalies } from "../../lib/api";
const mockList = vi.mocked(getElInsAnomalies);

function makeAnomaly(
  overrides: Partial<ElInsAnomaly> = {},
): ElInsAnomaly {
  return {
    id:          "anom-001",
    timestamp:   1700000000,
    type:        "high_el",
    severity:    3,
    message:     "EL score 8.50 exceeds threshold 7.5",
    record_id:   "thread-1:1700000000000",
    operator_id: "op_alice",
    thread_id:   "thread-1",
    ...overrides,
  };
}

function makeResponse(rows: ElInsAnomaly[] = []): ElInsAnomaliesResponse {
  return { operator_id: "op_alice", anomalies: rows };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/anomalies"]}>
      <OperatorElinsAnomalies />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockList.mockReset(); });
afterEach(() => { try { localStorage.clear(); } catch { /* noop */ } });

describe("OperatorElinsAnomalies route", () => {
  test("fires getElInsAnomalies on mount", async () => {
    mockList.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
  });

  test("renders empty state when no anomalies", async () => {
    mockList.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await screen.findByTestId("el-ins-anomalies-empty");
  });

  test("renders rows for each anomaly", async () => {
    mockList.mockResolvedValueOnce(makeResponse([
      makeAnomaly(),
      makeAnomaly({ id: "anom-002", type: "tsi_spike", severity: 4, message: "TSI 90/100 exceeds spike threshold 85" }),
      makeAnomaly({ id: "anom-003", type: "quadrant_jump", severity: 5, message: "Quadrant jump Q4→Q3" }),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-anomalies-table");
    expect(table).toHaveTextContent("high_el");
    expect(table).toHaveTextContent("tsi_spike");
    expect(table).toHaveTextContent("quadrant_jump");
  });

  test("severity chip text matches anomaly severity", async () => {
    mockList.mockResolvedValueOnce(makeResponse([
      makeAnomaly({ severity: 5 }),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-anomalies-table");
    expect(table).toHaveTextContent("5");
  });

  test("REFRESH re-fires the helper", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValue(makeResponse([makeAnomaly()]));
    renderRoute();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-anomalies-refresh"));
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  test("error from fetch surfaces in banner", async () => {
    mockList.mockRejectedValueOnce(new Error("anomalies boom"));
    renderRoute();
    await screen.findByTestId("el-ins-anomalies-error");
  });

  test("no operator_id label appears in the rendered table", async () => {
    mockList.mockResolvedValueOnce(makeResponse([makeAnomaly()]));
    renderRoute();
    await screen.findByTestId("el-ins-anomalies-table");
    // Identity invariant from v67/v68 still holds — operator_id is the
    // payload field but the UI must not surface that literal label.
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
