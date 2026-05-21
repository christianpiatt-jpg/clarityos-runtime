// v69 / Unit 74 — OperatorElins route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsAnalyzeResponse,
  ElInsRecentResponse,
  ElInsRecord,
  ElInsThreadResponse,
  ElInsThreadStabilityResponse,
} from "../../lib/api";
import OperatorElins from "../OperatorElins";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsRecent: vi.fn(),
    getElInsThread: vi.fn(),
    getElInsThreadStability: vi.fn(),
    postElInsAnalyze: vi.fn(),
  };
});

import {
  getElInsRecent,
  getElInsThread,
  getElInsThreadStability,
  postElInsAnalyze,
} from "../../lib/api";

const mockRecent = vi.mocked(getElInsRecent);
const mockThread = vi.mocked(getElInsThread);
const mockStability = vi.mocked(getElInsThreadStability);
const mockAnalyze = vi.mocked(postElInsAnalyze);

function makeStability(
  stability: "stable" | "drifting_el" | "drifting_ins" | "oscillating" = "stable",
  tsi: number = 90,
): ElInsThreadStabilityResponse {
  return { thread_id: "thread-001", stability, tsi, window: 6 };
}

function makeRecord(
  overrides: Partial<ElInsRecord> = {},
  cls: "high_el" | "high_ins" | "balanced" = "balanced",
): ElInsRecord {
  return {
    operator_id: "op_alice",
    thread_id:   "thread-001",
    timestamp:   1700000000.0,
    source:      "on_demand",
    result: {
      analysis: {
        el_components: [],
        ins_components: [],
        el_score: 2.5,
        ins_score: 2.0,
        ratio_classification: cls,
      },
      reasoning_mode: cls === "high_el" ? "stabilize" : cls === "high_ins" ? "expand" : "normal",
      regression_chain: {
        projection: null, drivers: [], precedents: [],
        principle_stack: [], invariant: null,
      },
      stability_notes: null,
    },
    ...overrides,
  };
}

function makeRecent(recs: ElInsRecord[] = []): ElInsRecentResponse {
  return { operator_id: "op_alice", records: recs };
}

function makeThread(recs: ElInsRecord[] = []): ElInsThreadResponse {
  return { operator_id: "op_alice", thread_id: "thread-001", records: recs };
}

function makeAnalyzeResponse(): ElInsAnalyzeResponse {
  return {
    result: makeRecord({}, "high_el").result,
    stored: true,
    thread_id: "thread-001",
    timestamp: 1700000001.0,
  };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins"]}>
      <OperatorElins />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockRecent.mockReset();
  mockThread.mockReset();
  mockStability.mockReset();
  mockAnalyze.mockReset();
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("OperatorElins route", () => {
  test("fires getElInsRecent on mount", async () => {
    mockRecent.mockResolvedValueOnce(makeRecent());
    renderRoute();
    await waitFor(() => expect(mockRecent).toHaveBeenCalledTimes(1));
  });

  test("renders empty state when no records exist", async () => {
    mockRecent.mockResolvedValueOnce(makeRecent());
    renderRoute();
    await screen.findByText(/no EL\/INS records yet/i);
  });

  test("renders the recent table with records", async () => {
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord({ timestamp: 1700000000.0 }, "high_el"),
      makeRecord({ timestamp: 1699999000.0, source: "per_turn" }, "balanced"),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-recent-table");
    expect(table).toHaveTextContent("high_el");
    expect(table).toHaveTextContent("balanced");
    expect(table).toHaveTextContent("per_turn");
  });

  test("ANALYZE submits text + provider_mode + thread_id", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValue(makeRecent());
    mockAnalyze.mockResolvedValueOnce(makeAnalyzeResponse());
    renderRoute();
    await waitFor(() => expect(mockRecent).toHaveBeenCalled());

    await user.type(screen.getByTestId("el-ins-text"), "catastrophic doom");
    await user.type(screen.getByTestId("el-ins-thread-id"), "thread-001");
    await user.click(screen.getByTestId("el-ins-analyze"));

    await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
    const arg = mockAnalyze.mock.calls[0][0];
    expect(arg.text).toBe("catastrophic doom");
    expect(arg.thread_id).toBe("thread-001");
  });

  test("ANALYZE button is disabled until text is typed", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValueOnce(makeRecent());
    renderRoute();
    await waitFor(() => expect(mockRecent).toHaveBeenCalled());
    const btn = screen.getByTestId("el-ins-analyze") as HTMLButtonElement;
    expect(btn).toBeDisabled();
    await user.type(screen.getByTestId("el-ins-text"), "hi");
    expect(btn).not.toBeDisabled();
  });

  test("clicking a thread cell loads the per-thread drill-down", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord({ thread_id: "thread-001" }, "high_el"),
    ]));
    mockThread.mockResolvedValueOnce(makeThread([
      makeRecord({ timestamp: 1700000000.0 }, "high_el"),
    ]));
    mockStability.mockResolvedValueOnce(makeStability("drifting_el", 60));
    renderRoute();
    const cell = await screen.findByText("thread-001");
    await user.click(cell);
    await waitFor(() => expect(mockThread).toHaveBeenCalledWith("thread-001"));
    await screen.findByTestId("el-ins-thread-list");
  });

  test("stability badge renders on thread drill-down with classification + TSI", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord({ thread_id: "thread-001" }, "high_el"),
    ]));
    mockThread.mockResolvedValueOnce(makeThread([
      makeRecord({}, "high_el"),
    ]));
    mockStability.mockResolvedValueOnce(makeStability("drifting_el", 60));
    renderRoute();
    const cell = await screen.findByText("thread-001");
    await user.click(cell);
    const badge = await screen.findByTestId("el-ins-stability-badge");
    expect(badge).toHaveTextContent(/DRIFTING EL/i);
    expect(badge).toHaveTextContent(/TSI 60\/100/);
  });

  test("stability badge color reflects classification", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValueOnce(makeRecent([
      makeRecord({ thread_id: "thread-001" }, "balanced"),
    ]));
    mockThread.mockResolvedValueOnce(makeThread([
      makeRecord({}, "balanced"),
    ]));
    mockStability.mockResolvedValueOnce(makeStability("stable", 95));
    renderRoute();
    const cell = await screen.findByText("thread-001");
    await user.click(cell);
    const badge = await screen.findByTestId("el-ins-stability-badge");
    expect(badge).toHaveTextContent(/STABLE/i);
    expect(badge).toHaveTextContent(/TSI 95\/100/);
  });

  test("REFRESH re-fetches recent", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValue(makeRecent());
    renderRoute();
    await waitFor(() => expect(mockRecent).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-refresh"));
    await waitFor(() => expect(mockRecent).toHaveBeenCalledTimes(2));
  });

  test("error from recent surfaces in banner", async () => {
    mockRecent.mockRejectedValueOnce(new Error("recent boom"));
    renderRoute();
    await screen.findByTestId("el-ins-recent-error");
  });

  test("error from analyze surfaces in banner", async () => {
    const user = userEvent.setup();
    mockRecent.mockResolvedValue(makeRecent());
    mockAnalyze.mockRejectedValueOnce(new Error("analyze boom"));
    renderRoute();
    await waitFor(() => expect(mockRecent).toHaveBeenCalled());
    await user.type(screen.getByTestId("el-ins-text"), "hi");
    await user.click(screen.getByTestId("el-ins-analyze"));
    await screen.findByTestId("el-ins-analyze-error");
  });

  test("no operator_id label appears anywhere in the dashboard", async () => {
    // Identity invariant — v67/v68 stripped operator_id surfaces.
    mockRecent.mockResolvedValueOnce(makeRecent([makeRecord()]));
    renderRoute();
    await screen.findByTestId("el-ins-recent-table");
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
