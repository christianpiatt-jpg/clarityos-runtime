// v73 / Unit 82 — OperatorTimeline route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  TimelineEvent,
  TimelineListResponse,
} from "../../lib/api";
import OperatorTimeline, { summariseEvent } from "../OperatorTimeline";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getTimeline: vi.fn(),
  };
});

import { getTimeline } from "../../lib/api";
const mockTimeline = vi.mocked(getTimeline);

function makeEvent(
  overrides: Partial<TimelineEvent> = {},
): TimelineEvent {
  return {
    id:           "ev-001",
    timestamp_ms: 1700000000000,
    event_type:   "record",
    payload: {
      el: 8.0, ins: 1.0, tsi: 90,
      reasoning_mode: "grounding",
      thread_id: "t1",
    },
    operator_id: "op_alice",
    ...overrides,
  };
}

function makeResponse(events: TimelineEvent[] = []): TimelineListResponse {
  return { operator_id: "op_alice", events };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/timeline"]}>
      <OperatorTimeline />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockTimeline.mockReset(); });
afterEach(() => { try { localStorage.clear(); } catch { /* noop */ } });

describe("OperatorTimeline route", () => {
  test("fires getTimeline on mount", async () => {
    mockTimeline.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await waitFor(() => expect(mockTimeline).toHaveBeenCalledTimes(1));
  });

  test("renders empty state when no events", async () => {
    mockTimeline.mockResolvedValueOnce(makeResponse());
    renderRoute();
    await screen.findByTestId("el-ins-timeline-empty");
  });

  test("renders rows per event with type colour-coded", async () => {
    mockTimeline.mockResolvedValueOnce(makeResponse([
      makeEvent(),
      makeEvent({ id: "ev-002", event_type: "anomaly",
                  payload: { type: "high_el", severity: 3, message: "m", anomaly_id: "x" }}),
      makeEvent({ id: "ev-003", event_type: "rollup",
                  payload: { window: "24h", avg_el: 3.0, avg_ins: 4.0, avg_tsi: 80, record_count: 10 }}),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-timeline-table");
    expect(table).toHaveTextContent("record");
    expect(table).toHaveTextContent("anomaly");
    expect(table).toHaveTextContent("rollup");
  });

  test("REFRESH re-fires the helper", async () => {
    const user = userEvent.setup();
    mockTimeline.mockResolvedValue(makeResponse([makeEvent()]));
    renderRoute();
    await waitFor(() => expect(mockTimeline).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-timeline-refresh"));
    await waitFor(() => expect(mockTimeline).toHaveBeenCalledTimes(2));
  });

  test("clicking a row opens the JSON modal", async () => {
    const user = userEvent.setup();
    mockTimeline.mockResolvedValueOnce(makeResponse([makeEvent()]));
    renderRoute();
    const row = await screen.findByTestId("el-ins-timeline-row-ev-001");
    await user.click(row);
    await screen.findByTestId("el-ins-timeline-modal");
    const payload = screen.getByTestId("el-ins-timeline-modal-payload");
    expect(payload).toHaveTextContent('"grounding"');
  });

  test("modal CLOSE button hides the modal", async () => {
    const user = userEvent.setup();
    mockTimeline.mockResolvedValueOnce(makeResponse([makeEvent()]));
    renderRoute();
    await user.click(await screen.findByTestId("el-ins-timeline-row-ev-001"));
    await screen.findByTestId("el-ins-timeline-modal");
    await user.click(screen.getByTestId("el-ins-timeline-modal-close"));
    expect(screen.queryByTestId("el-ins-timeline-modal")).not.toBeInTheDocument();
  });

  test("error from fetch surfaces in banner", async () => {
    mockTimeline.mockRejectedValueOnce(new Error("boom"));
    renderRoute();
    await screen.findByTestId("el-ins-timeline-error");
  });

  test("no operator_id label appears in the rendered surface", async () => {
    mockTimeline.mockResolvedValueOnce(makeResponse([makeEvent()]));
    renderRoute();
    await screen.findByTestId("el-ins-timeline-table");
    expect(screen.queryByText(/operator_id/i)).not.toBeInTheDocument();
  });
});

// ===========================================================================
// summariseEvent — pure helper. 4 tests per spec.
// ===========================================================================
describe("summariseEvent", () => {
  test("record event includes EL, INS, TSI, mode", () => {
    const s = summariseEvent({
      id: "x", timestamp_ms: 0, operator_id: "op",
      event_type: "record",
      payload: { el: 8.0, ins: 1.0, tsi: 90, reasoning_mode: "grounding" },
    });
    expect(s).toContain("EL 8.00");
    expect(s).toContain("INS 1.00");
    expect(s).toContain("TSI 90");
    expect(s).toContain("grounding");
  });

  test("anomaly event includes type + severity", () => {
    const s = summariseEvent({
      id: "x", timestamp_ms: 0, operator_id: "op",
      event_type: "anomaly",
      payload: { type: "high_el", severity: 3 },
    });
    expect(s).toContain("high_el");
    expect(s).toContain("severity 3");
  });

  test("rollup event includes window + averages", () => {
    const s = summariseEvent({
      id: "x", timestamp_ms: 0, operator_id: "op",
      event_type: "rollup",
      payload: { window: "24h", avg_el: 3.5, avg_ins: 4.5, avg_tsi: 80 },
    });
    expect(s).toContain("24h");
    expect(s).toContain("EL 3.50");
    expect(s).toContain("INS 4.50");
    expect(s).toContain("TSI 80");
  });

  test("system event has a default summary", () => {
    const s = summariseEvent({
      id: "x", timestamp_ms: 0, operator_id: "op",
      event_type: "system",
      payload: {},
    });
    expect(s).toBe("system event");
  });
});
