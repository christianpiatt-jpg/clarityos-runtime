// v73 / Unit 83 — OrgTimeline route tests.

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type {
  OrgTimelineEntry,
  OrgTimelineResponse,
  OrgTimelineWindow,
} from "../../lib/api";
import OrgTimeline, { summariseOrgEntry } from "../OrgTimeline";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api",
  );
  return {
    ...actual,
    getOrgTimeline: vi.fn(),
  };
});

import { getOrgTimeline } from "../../lib/api";
const mockOrg = vi.mocked(getOrgTimeline);

function makeEntry(
  overrides: Partial<OrgTimelineEntry> = {},
): OrgTimelineEntry {
  return {
    timestamp_ms:    1700000000000,
    operator_id:     "istian",   // masked tail
    event_type:      "record",
    payload_summary: { el: 5.0, ins: 5.0, tsi: 80 },
    ...overrides,
  };
}

function makeResponse(
  window: OrgTimelineWindow,
  entries: OrgTimelineEntry[] = [],
): OrgTimelineResponse {
  return { window, entries };
}

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/org/el_ins/timeline"]}>
      <OrgTimeline />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockOrg.mockReset(); });
afterEach(() => { try { localStorage.clear(); } catch { /* noop */ } });

describe("OrgTimeline route", () => {
  test("fires getOrgTimeline with 24h on mount", async () => {
    mockOrg.mockResolvedValueOnce(makeResponse("24h"));
    renderRoute();
    await waitFor(() => expect(mockOrg).toHaveBeenCalledTimes(1));
    expect(mockOrg).toHaveBeenCalledWith("24h");
  });

  test("switching tab fires new window fetch", async () => {
    const user = userEvent.setup();
    mockOrg.mockResolvedValue(makeResponse("24h"));
    renderRoute();
    await waitFor(() => expect(mockOrg).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-org-tab-7d"));
    await waitFor(() => expect(mockOrg).toHaveBeenCalledWith("7d"));
    await user.click(screen.getByTestId("el-ins-org-tab-30d"));
    await waitFor(() => expect(mockOrg).toHaveBeenCalledWith("30d"));
  });

  test("renders empty state when no entries", async () => {
    mockOrg.mockResolvedValueOnce(makeResponse("24h"));
    renderRoute();
    await screen.findByTestId("el-ins-org-empty");
  });

  test("renders entries with masked operator + type + summary", async () => {
    mockOrg.mockResolvedValueOnce(makeResponse("24h", [
      makeEntry({ operator_id: "istian", event_type: "record",
                  payload_summary: { el: 8.0, ins: 1.0, tsi: 90 } }),
      makeEntry({ operator_id: "thias_", event_type: "anomaly",
                  payload_summary: { severity: 4, rule: "tsi_spike" } }),
    ]));
    renderRoute();
    const table = await screen.findByTestId("el-ins-org-table");
    expect(table).toHaveTextContent("istian");
    expect(table).toHaveTextContent("thias_");
    expect(table).toHaveTextContent("tsi_spike");
  });

  test("403 from server surfaces in banner", async () => {
    // Caller is not in the founder cohort.
    const err = Object.assign(new Error("Founder cohort required"), {
      code: "http_error",
      status: 403,
    });
    mockOrg.mockRejectedValueOnce(err);
    renderRoute();
    await screen.findByTestId("el-ins-org-error");
  });

  test("REFRESH re-fires the helper", async () => {
    const user = userEvent.setup();
    mockOrg.mockResolvedValue(makeResponse("24h"));
    renderRoute();
    await waitFor(() => expect(mockOrg).toHaveBeenCalledTimes(1));
    await user.click(screen.getByTestId("el-ins-org-refresh"));
    await waitFor(() => expect(mockOrg).toHaveBeenCalledTimes(2));
  });
});

// ===========================================================================
// summariseOrgEntry — pure helper, 3 tests per spec
// ===========================================================================
describe("summariseOrgEntry", () => {
  test("record entry includes EL, INS, TSI", () => {
    const s = summariseOrgEntry({
      timestamp_ms: 0, operator_id: "istian", event_type: "record",
      payload_summary: { el: 8.0, ins: 1.0, tsi: 90 },
    });
    expect(s).toContain("EL 8.00");
    expect(s).toContain("INS 1.00");
    expect(s).toContain("TSI 90");
  });

  test("anomaly entry includes severity + rule", () => {
    const s = summariseOrgEntry({
      timestamp_ms: 0, operator_id: "istian", event_type: "anomaly",
      payload_summary: { severity: 5, rule: "quadrant_jump" },
    });
    expect(s).toContain("quadrant_jump");
    expect(s).toContain("severity 5");
  });

  test("rollup entry includes window + averages (no avg_tsi by spec)", () => {
    const s = summariseOrgEntry({
      timestamp_ms: 0, operator_id: "istian", event_type: "rollup",
      payload_summary: { window: "7d", avg_el: 3.5, avg_ins: 4.5 },
    });
    expect(s).toContain("7d");
    expect(s).toContain("EL 3.50");
    expect(s).toContain("INS 4.50");
  });
});
