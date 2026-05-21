// v71 / Unit 79 — ElInsIndicator reasoning-mode label tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsRecentResponse,
  ElInsRecord,
  ElInsReasoningModeResponse,
} from "../../../lib/api";
import ElInsIndicator from "../ElInsIndicator";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>(
    "../../../lib/api",
  );
  return {
    ...actual,
    getElInsRecent:         vi.fn(),
    getElInsReasoningMode:  vi.fn(),
    getElInsAnomalies:      vi.fn(),
    getTimeline:            vi.fn(),
  };
});

import {
  getElInsAnomalies,
  getElInsRecent,
  getElInsReasoningMode,
  getTimeline,
} from "../../../lib/api";

const mockRecent = vi.mocked(getElInsRecent);
const mockMode = vi.mocked(getElInsReasoningMode);
const mockAnomalies = vi.mocked(getElInsAnomalies);
const mockTimeline = vi.mocked(getTimeline);

function makeRecord(
  cls: "high_el" | "high_ins" | "balanced",
): ElInsRecord {
  return {
    operator_id: "op_alice",
    thread_id:   "t1",
    timestamp:   1700000000.0,
    source:      "on_demand",
    result: {
      analysis: {
        el_components: [], ins_components: [],
        el_score: 5.0, ins_score: 3.0,
        ratio_classification: cls,
      },
      reasoning_mode: cls === "high_el" ? "stabilize" : "normal",
      regression_chain: {
        projection: null, drivers: [], precedents: [],
        principle_stack: [], invariant: null,
      },
      stability_notes: null,
    },
  };
}

function makeReasoning(
  mode: ElInsReasoningModeResponse["reasoning_mode"] = "grounding",
): ElInsReasoningModeResponse {
  return {
    operator_id:    "op_alice",
    reasoning_mode: mode,
    el:             8.0,
    ins:            1.0,
    tsi:            75,
    timestamp:      1700000000.0,
  };
}

function renderComponent() {
  return render(
    <MemoryRouter>
      <ElInsIndicator />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockRecent.mockReset();
  mockMode.mockReset();
  mockAnomalies.mockReset();
  mockTimeline.mockReset();
  // Defaults for tests that don't care about the red/timeline dots.
  mockAnomalies.mockResolvedValue({ operator_id: "op_alice", anomalies: [] });
  mockTimeline.mockResolvedValue({ operator_id: "op_alice", events: [] });
});

afterEach(() => {
  try { localStorage.clear(); } catch { /* noop */ }
});

describe("ElInsIndicator reasoning-mode label", () => {
  test("renders Reasoning Mode label below stability when present", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice",
      records: [makeRecord("high_el")],
    } as ElInsRecentResponse);
    mockMode.mockResolvedValueOnce(makeReasoning("grounding"));
    renderComponent();
    const label = await screen.findByTestId("el-ins-reasoning-mode-label");
    expect(label).toHaveTextContent("Grounding");
  });

  test("maps each reasoning_mode value to a display label", async () => {
    const cases: Array<[ElInsReasoningModeResponse["reasoning_mode"], RegExp]> = [
      ["grounding",              /Grounding/i],
      ["analysis",               /Analysis/i],
      ["structured_reflection",  /Structured Reflection/i],
      ["stabilization",          /Stabilization/i],
      ["extended_reasoning",     /Extended Reasoning/i],
      ["normal",                 /Normal/i],
    ];
    for (const [mode, pattern] of cases) {
      mockRecent.mockResolvedValueOnce({
        operator_id: "op_alice",
        records: [makeRecord("balanced")],
      } as ElInsRecentResponse);
      mockMode.mockResolvedValueOnce(makeReasoning(mode));
      const { unmount } = renderComponent();
      const label = await screen.findByTestId("el-ins-reasoning-mode-label");
      expect(label).toHaveTextContent(pattern);
      unmount();
    }
  });

  test("does not render reasoning-mode label when fetch fails", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice",
      records: [makeRecord("balanced")],
    } as ElInsRecentResponse);
    mockMode.mockRejectedValueOnce(new Error("boom"));
    renderComponent();
    // Stability label appears even when reasoning-mode call fails.
    await screen.findByTestId("el-ins-indicator");
    expect(screen.queryByTestId("el-ins-reasoning-mode-label")).not.toBeInTheDocument();
  });

  test("does not render reasoning-mode label when no records exist", async () => {
    mockRecent.mockResolvedValueOnce({ operator_id: "op_alice", records: [] });
    mockMode.mockResolvedValueOnce({
      operator_id: "op_alice",
      reasoning_mode: "normal",
      el: null, ins: null, tsi: null, timestamp: null,
    });
    renderComponent();
    await screen.findByTestId("el-ins-indicator");
    // The empty-history endpoint returns "normal" — we DO render the
    // label in that case, so users see a default reading. Only the
    // *fetch failure* case suppresses the label.
    const label = await screen.findByTestId("el-ins-reasoning-mode-label");
    expect(label).toHaveTextContent(/Normal/i);
  });

  test("renders red-dot badge when anomalies in last 24h", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice", records: [makeRecord("balanced")],
    });
    mockMode.mockResolvedValueOnce(makeReasoning("normal"));
    mockAnomalies.mockResolvedValueOnce({
      operator_id: "op_alice",
      anomalies: [{
        id: "x", timestamp: Date.now() / 1000 - 60,
        type: "high_el", severity: 3, message: "test",
        record_id: "t1:0", operator_id: "op_alice", thread_id: "t1",
      }],
    });
    renderComponent();
    await screen.findByTestId("el-ins-anomaly-dot");
  });

  test("does NOT render red-dot when only old anomalies", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice", records: [makeRecord("balanced")],
    });
    mockMode.mockResolvedValueOnce(makeReasoning("normal"));
    mockAnomalies.mockResolvedValueOnce({
      operator_id: "op_alice",
      anomalies: [{
        id: "x", timestamp: Date.now() / 1000 - (60 * 60 * 48),  // 48h ago
        type: "high_el", severity: 3, message: "test",
        record_id: "t1:0", operator_id: "op_alice", thread_id: "t1",
      }],
    });
    renderComponent();
    await screen.findByTestId("el-ins-indicator");
    expect(screen.queryByTestId("el-ins-anomaly-dot")).not.toBeInTheDocument();
  });

  test("renders timeline accent dot when fresh timeline event exists", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice", records: [makeRecord("balanced")],
    });
    mockMode.mockResolvedValueOnce(makeReasoning("normal"));
    mockTimeline.mockResolvedValueOnce({
      operator_id: "op_alice",
      events: [{
        id: "ev-1", timestamp_ms: Date.now() - 60_000,   // 1 min ago
        event_type: "record", payload: {}, operator_id: "op_alice",
      }],
    });
    renderComponent();
    await screen.findByTestId("el-ins-timeline-dot");
  });

  test("does NOT render timeline dot when timeline empty", async () => {
    mockRecent.mockResolvedValueOnce({
      operator_id: "op_alice", records: [makeRecord("balanced")],
    });
    mockMode.mockResolvedValueOnce(makeReasoning("normal"));
    mockTimeline.mockResolvedValueOnce({ operator_id: "op_alice", events: [] });
    renderComponent();
    await screen.findByTestId("el-ins-indicator");
    expect(screen.queryByTestId("el-ins-timeline-dot")).not.toBeInTheDocument();
  });
});
