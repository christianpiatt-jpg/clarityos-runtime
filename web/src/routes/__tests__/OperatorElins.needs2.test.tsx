/**
 * F (CT-1 2026-09-16) -- EL/INS readers at n = 1: "1 read — needs 2" in
 * place of STABLE / 100 / a percentage on the Analyze badge, the Macro
 * percentages, the Dashboard average + trend and the Rollup average + pie;
 * the cockpit indicator reads ONE route (#290, the operator's default scope)
 * and names the mode as the provider mode it is.
 */
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getElInsRecent: vi.fn(), getElInsThread: vi.fn(), getElInsThreadStability: vi.fn(), postElInsAnalyze: vi.fn(),
    getElInsMacro: vi.fn(), getElInsOperatorSummary: vi.fn(), getElInsRollup: vi.fn(),
    getElInsReasoningMode: vi.fn(), getElInsAnomalies: vi.fn(), getTimeline: vi.fn(),
  };
});

import * as api from "../../lib/api";
import type { ElInsRecord } from "../../lib/api";
import OperatorElins from "../OperatorElins";
import OperatorElinsMacro from "../OperatorElinsMacro";
import OperatorElinsDashboard from "../OperatorElinsDashboard";
import OperatorElinsRollup from "../OperatorElinsRollup";
import ElInsIndicator from "../../components/cockpit/ElInsIndicator";
import { readsNeeded } from "../../lib/counts";

function rec(thread_id: string | null = "thread-001"): ElInsRecord {
  return {
    operator_id: "op_alice", thread_id, timestamp: 1700000000, source: "on_demand",
    result: {
      analysis: { el_components: [], ins_components: [], el_score: 5, ins_score: 3, ratio_classification: "balanced" },
      reasoning_mode: "normal",
      regression_chain: { projection: null, drivers: [], precedents: [], principle_stack: [], invariant: null },
      stability_notes: null,
    },
  };
}

beforeEach(() => {
  vi.mocked(api.getElInsAnomalies).mockResolvedValue({ operator_id: "op_alice", anomalies: [] });
  vi.mocked(api.getTimeline).mockResolvedValue({ operator_id: "op_alice", events: [] } as never);
});
afterEach(() => { vi.clearAllMocks(); try { localStorage.clear(); } catch { /* noop */ } });

test("readsNeeded", () => {
  expect(readsNeeded(1)).toBe("1 read — needs 2");
  expect(readsNeeded(0)).toBe("0 reads — needs 2");
});

test("★ Analyze: a one-read window shows no STABLE and no TSI", async () => {
  const user = userEvent.setup();
  vi.mocked(api.getElInsRecent).mockResolvedValue({ operator_id: "op_alice", records: [rec()] });
  vi.mocked(api.getElInsThread).mockResolvedValue({ operator_id: "op_alice", thread_id: "thread-001", records: [rec()] });
  vi.mocked(api.getElInsThreadStability).mockResolvedValue({ thread_id: "thread-001", stability: "stable", tsi: 100, window: 1 });
  render(<MemoryRouter initialEntries={["/operator/el_ins"]}><OperatorElins /></MemoryRouter>);
  await user.click(await screen.findByText("thread-001"));
  const badge = await screen.findByTestId("el-ins-stability-badge");
  expect(badge).toHaveTextContent("1 read — needs 2");
  expect(badge.textContent).not.toMatch(/STABLE|TSI|100/);
  expect(screen.getAllByText("Provider mode").length).toBeGreaterThanOrEqual(1);
});

test("★ Macro: one record shows no percentage", async () => {
  vi.mocked(api.getElInsMacro).mockResolvedValue({ operator_id: "op_alice", since: null, records: [rec()] });
  render(<MemoryRouter initialEntries={["/operator/el_ins/macro"]}><OperatorElinsMacro /></MemoryRouter>);
  const stats = await screen.findByTestId("el-ins-macro-stats");
  expect(screen.getByTestId("el-ins-macro-needs2")).toHaveTextContent("1 read — needs 2");
  expect(stats.textContent).not.toMatch(/%/);
  expect(stats).toHaveTextContent(/total records.*1/);
});

test("★ Dashboard: a sample of one shows no average and no trend", async () => {
  vi.mocked(api.getElInsOperatorSummary).mockResolvedValue({
    recent_classification_distribution: { high_el: 0, high_ins: 0, balanced: 1 }, avg_tsi: 100, trend: "stable", sample_size: 1,
  });
  vi.mocked(api.getElInsRecent).mockResolvedValue({ operator_id: "op_alice", records: [rec()] });
  render(<MemoryRouter initialEntries={["/operator/el_ins/dashboard"]}><OperatorElinsDashboard /></MemoryRouter>);
  const summary = await screen.findByTestId("el-ins-dashboard-summary");
  expect(screen.getByTestId("el-ins-dashboard-needs2")).toHaveTextContent("1 read — needs 2");
  expect(screen.queryByTestId("el-ins-dashboard-trend")).toBeNull();
  expect(summary.textContent).not.toMatch(/100\/100|STABLE/);
});

test("★ Rollup: one record shows no average TSI and no pie; the mode is the provider mode", async () => {
  vi.mocked(api.getElInsRollup).mockResolvedValue({
    avg_el: 5, avg_ins: 3, avg_tsi: 100, reasoning_mode_distribution: { normal: 1 }, record_count: 1,
    window_start: 1, window_end: 2,
  });
  render(<MemoryRouter initialEntries={["/operator/el_ins/rollup"]}><OperatorElinsRollup /></MemoryRouter>);
  const card = await screen.findByTestId("el-ins-rollup-card-24h");
  await waitFor(() => expect(api.getElInsRollup).toHaveBeenCalledTimes(3));
  expect(screen.getByTestId("el-ins-rollup-needs2-24h")).toHaveTextContent("1 read — needs 2");
  expect(card.textContent).not.toMatch(/100\/100/);
  expect(card).toHaveTextContent("PROVIDER MODE CHOSEN");
  expect(card.textContent).not.toMatch(/normal: 1/);
});

test("★ Indicator: one route, the operator's scope; the label is the provider mode", async () => {
  vi.mocked(api.getElInsReasoningMode).mockResolvedValue({
    operator_id: "op_alice", reasoning_mode: "grounding", el: 8, ins: 1, tsi: 75, timestamp: 1,
    ratio_classification: "high_el", source: "per_turn", thread_id: "t1",
  });
  render(<MemoryRouter><ElInsIndicator /></MemoryRouter>);
  const badge = await screen.findByTestId("el-ins-indicator");
  await waitFor(() => expect(badge).toHaveTextContent("Stability: High-EL"));
  expect(screen.getByTestId("el-ins-reasoning-mode-label")).toHaveTextContent("Provider mode: Grounding");
  expect(api.getElInsRecent).not.toHaveBeenCalled();
});
