// v70 / Unit 77 — OperatorElinsDashboard route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsOperatorSummaryResponse,
  ElInsRecentResponse,
  ElInsRecord,
} from "../../lib/api";
import OperatorElinsDashboard from "../OperatorElinsDashboard";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsOperatorSummary: vi.fn(),
    getElInsRecent: vi.fn(),
  };
});

import {
  getElInsOperatorSummary,
  getElInsRecent,
} from "../../lib/api";

const mockSummary = vi.mocked(getElInsOperatorSummary);
const mockRecent = vi.mocked(getElInsRecent);

function makeSummary(
  overrides: Partial<ElInsOperatorSummaryResponse> = {},
): ElInsOperatorSummaryResponse {
  return {
    recent_classification_distribution: {
      high_el: 5, high_ins: 3, balanced: 12,
    },
    avg_tsi:     78,
    trend:       "stable",
    sample_size: 20,
    ...overrides,
  };
}

function makeRecord(
  cls: "high_el" | "high_ins" | "balanced",
  ts: number,
  tsi: number | undefined = 80,
): ElInsRecord & { tsi?: number } {
  const rec: ElInsRecord & { tsi?: number } = {
    operator_id: "op_alice",
    thread_id:   "t1",
    timestamp:   ts,
    source:      "on_demand",
    result: {
      analysis: {
        el_components: [], ins_components: [],
        el_score: 5.0, ins_score: 3.0,
        ratio_classification: cls,
      },
      reasoning_mode:
        cls === "high_el" ? "stabilize" :
        cls === "high_ins" ? "expand" : "normal",
      regression_chain: {
        projection: null, drivers: [], precedents: [],
        principle_stack: [], invariant: null,
      },
      stability_notes: null,
    },
  };
  if (tsi !== undefined) rec.tsi = tsi;
  return rec;
}

function makeRecent(records: ElInsRecord[]): ElInsRecentResponse {
  return { operator_id: "op_alice", records };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/dashboard"]}>
      <OperatorElinsDashboard />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockSummary.mockReset();
  mockRecent.mockReset();
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("OperatorElinsDashboard route", () => {
  test("fires both summary + recent on mount", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    renderRoute();
    await waitFor(() => {
      expect(mockSummary).toHaveBeenCalledTimes(1);
      expect(mockRecent).toHaveBeenCalledTimes(1);
    });
  });

  test("renders the summary panel after fetch", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    renderRoute();
    await screen.findByTestId("el-ins-dashboard-summary");
  });

  test("renders trend label with correct text", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary({ trend: "improving" }));
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    renderRoute();
    const trend = await screen.findByTestId("el-ins-dashboard-trend");
    expect(trend).toHaveTextContent("IMPROVING");
  });

  test("renders empty state when no records", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary({ sample_size: 0 }));
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    renderRoute();
    await screen.findByText(/No EL\/INS records yet/i);
  });

  test("renders records table with TSI column", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord("balanced", 1700000000, 95),
      makeRecord("high_el",  1699999000, 72),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-dashboard-table");
    expect(table).toHaveTextContent("95");
    expect(table).toHaveTextContent("72");
    expect(table).toHaveTextContent("high_el");
    expect(table).toHaveTextContent("balanced");
  });

  test("REFRESH re-fires both endpoints", async () => {
    const user = userEvent.setup();
    mockSummary.mockResolvedValue(makeSummary());
    mockRecent.mockResolvedValue(makeRecent([]));
    renderRoute();
    await waitFor(() => expect(mockSummary).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-dashboard-refresh"));
    await waitFor(() => {
      expect(mockSummary).toHaveBeenCalledTimes(2);
      expect(mockRecent).toHaveBeenCalledTimes(2);
    });
  });

  test("renders pie chart SVG with classification slices", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    const { container } = renderRoute();
    await screen.findByTestId("el-ins-dashboard-summary");
    // First svg in the summary panel is the pie.
    const pie = container.querySelector(
      'svg[aria-label="classification distribution"]',
    );
    expect(pie).not.toBeNull();
    // 3 slices for 3 nonzero categories.
    expect(pie?.querySelectorAll("path").length).toBe(3);
  });

  test("renders empty pie when distribution is zero", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary({
      recent_classification_distribution: { high_el: 0, high_ins: 0, balanced: 0 },
      sample_size: 0,
    }));
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    const { container } = renderRoute();
    await screen.findByTestId("el-ins-dashboard-summary");
    const pie = container.querySelector('svg[aria-label="empty distribution"]');
    expect(pie).not.toBeNull();
  });

  test("renders line chart for TSI", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord("balanced", 1700000000, 95),
      makeRecord("balanced", 1700000001, 90),
      makeRecord("balanced", 1700000002, 85),
    ]));
    renderRoute();
    const line = await screen.findByTestId("el-ins-dashboard-tsi-chart");
    // 3 points → 3 circles + 1 polyline + 1 rect frame.
    expect(line.querySelectorAll("circle").length).toBe(3);
    expect(line.querySelector("polyline")).not.toBeNull();
  });

  test("error from any endpoint surfaces in banner", async () => {
    mockSummary.mockRejectedValueOnce(new Error("summary boom"));
    mockRecent.mockResolvedValueOnce(makeRecent([]));
    renderRoute();
    await screen.findByTestId("el-ins-dashboard-error");
  });

  test("no operator_id label appears anywhere", async () => {
    mockSummary.mockResolvedValueOnce(makeSummary());
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord("balanced", 1700000000, 95),
    ]));
    renderRoute();
    await screen.findByTestId("el-ins-dashboard-table");
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
