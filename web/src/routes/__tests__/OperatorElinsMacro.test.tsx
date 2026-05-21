// v69 / Unit 74 — OperatorElinsMacro route smoke tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ElInsMacroResponse, ElInsRecord } from "../../lib/api";
import OperatorElinsMacro from "../OperatorElinsMacro";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getElInsMacro: vi.fn(),
  };
});

import { getElInsMacro } from "../../lib/api";
const mockMacro = vi.mocked(getElInsMacro);

function makeRecord(
  cls: "high_el" | "high_ins" | "balanced",
  el: number,
  ins: number,
  ts: number,
): ElInsRecord {
  return {
    operator_id: "op_alice",
    thread_id:   "t1",
    timestamp:   ts,
    source:      "on_demand",
    result: {
      analysis: {
        el_components: [], ins_components: [],
        el_score: el, ins_score: ins,
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
}

function makeMacroResponse(recs: ElInsRecord[]): ElInsMacroResponse {
  return { operator_id: "op_alice", since: null, records: recs };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/macro"]}>
      <OperatorElinsMacro />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockMacro.mockReset(); });

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("OperatorElinsMacro route", () => {
  test("fires getElInsMacro on mount", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([]));
    renderRoute();
    await waitFor(() => expect(mockMacro).toHaveBeenCalledTimes(1));
  });

  test("renders zero stats when no records", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([]));
    renderRoute();
    const stats = await screen.findByTestId("el-ins-macro-stats");
    expect(stats).toHaveTextContent(/total records.*0/i);
    expect(stats).toHaveTextContent(/avg EL score.*0\.00/i);
  });

  test("computes classification percentages correctly", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([
      makeRecord("balanced", 2, 2, 1700000000),
      makeRecord("balanced", 2, 2, 1700000001),
      makeRecord("high_el",  8, 1, 1700000002),
      makeRecord("high_ins", 1, 8, 1700000003),
    ]));
    renderRoute();
    const stats = await screen.findByTestId("el-ins-macro-stats");
    // 2/4 = 50% balanced, 1/4 = 25% high_el, 1/4 = 25% high_ins
    expect(stats).toHaveTextContent(/% balanced.*50\.0%/i);
    expect(stats).toHaveTextContent(/% high_el.*25\.0%/i);
    expect(stats).toHaveTextContent(/% high_ins.*25\.0%/i);
  });

  test("computes avg el/ins scores", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([
      makeRecord("balanced", 2, 4, 1700000000),
      makeRecord("balanced", 4, 6, 1700000001),
    ]));
    renderRoute();
    const stats = await screen.findByTestId("el-ins-macro-stats");
    // avg EL = (2+4)/2 = 3.00; avg INS = (4+6)/2 = 5.00
    expect(stats).toHaveTextContent(/avg EL score.*3\.00/i);
    expect(stats).toHaveTextContent(/avg INS score.*5\.00/i);
  });

  test("window selector changes the since parameter", async () => {
    const user = userEvent.setup();
    mockMacro.mockResolvedValue(makeMacroResponse([]));
    renderRoute();
    await waitFor(() => expect(mockMacro).toHaveBeenCalledTimes(1));
    // Default window is index 2 (30d). Switch to "All time" (index 3).
    await user.selectOptions(screen.getByTestId("el-ins-macro-window"), "3");
    await waitFor(() => expect(mockMacro).toHaveBeenCalledTimes(2));
    // Second call's argument should be null (all time).
    expect(mockMacro.mock.calls[1][0]).toBeNull();
  });

  test("REFRESH re-fetches", async () => {
    const user = userEvent.setup();
    mockMacro.mockResolvedValue(makeMacroResponse([]));
    renderRoute();
    await waitFor(() => expect(mockMacro).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-macro-refresh"));
    await waitFor(() => expect(mockMacro).toHaveBeenCalledTimes(2));
  });

  test("records table renders rows", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([
      makeRecord("high_el", 8, 1, 1700000000),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-macro-table");
    expect(table).toHaveTextContent("high_el");
    expect(table).toHaveTextContent("t1");
  });

  test("error surfaces in banner", async () => {
    mockMacro.mockRejectedValueOnce(new Error("macro boom"));
    renderRoute();
    await screen.findByTestId("el-ins-macro-error");
  });

  test("no operator_id label appears in the dashboard", async () => {
    mockMacro.mockResolvedValueOnce(makeMacroResponse([
      makeRecord("balanced", 2, 2, 1700000000),
    ]));
    renderRoute();
    await screen.findByTestId("el-ins-macro-table");
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});
