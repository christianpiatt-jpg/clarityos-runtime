/**
 * #374 -- the dashboard with UNMAPPED records in the summary.
 * (The export page has its own file: OperatorElinsExport.unmapped.374.test.tsx.
 * An earlier draft of this header claimed to cover both while covering one --
 * a refuter caught the claim, not a test.)
 *
 * ★ THE MEASURED DEFECT. With the operator's recent records = [balanced,
 * UNMAPPED], the backend now returns sample_size 2 / mapped_sample_size 1.
 * The dashboard's reads-needed gate was on sample_size, so 2 passed it and
 * the page drew a PieChart of ONE balanced read -- a single 100% green wedge
 * -- plus "avg TSI: 100/100 · trend: stable" over one mapped read. That is
 * the F violation ("a percentage of one read is that read") the same change
 * set had already corrected on the macro page. With [UNMAPPED x3] the pie
 * said "no data" but the gate still let an average and a trend render, and
 * nothing on the page said three records carried no reading.
 *
 * Every test names the mutation that breaks it.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type {
  ElInsOperatorSummaryResponse,
  ElInsRecentResponse,
} from "../../lib/api";
import OperatorElinsDashboard from "../OperatorElinsDashboard";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getElInsOperatorSummary: vi.fn(), getElInsRecent: vi.fn() };
});

import { getElInsOperatorSummary, getElInsRecent } from "../../lib/api";
const mockSummary = vi.mocked(getElInsOperatorSummary);
const mockRecent = vi.mocked(getElInsRecent);

function summary(
  d: { high_el: number; high_ins: number; balanced: number; unmapped: number },
  avg_tsi = 100,
): ElInsOperatorSummaryResponse {
  const total = d.high_el + d.high_ins + d.balanced + d.unmapped;
  return {
    recent_classification_distribution: d,
    avg_tsi,
    trend: "stable",
    sample_size: total,
    mapped_sample_size: total - d.unmapped,
  };
}

const noRecent: ElInsRecentResponse = { operator_id: "op_alice", records: [] } as ElInsRecentResponse;

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/dashboard"]}>
      <OperatorElinsDashboard />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockSummary.mockReset(); mockRecent.mockReset(); mockRecent.mockResolvedValue(noRecent); });
afterEach(() => { vi.clearAllMocks(); });

describe("OperatorElinsDashboard -- UNMAPPED in the summary (#374)", () => {
  test("★ [balanced, UNMAPPED]: sample 2, mapped 1 -> the reads-needed gate, not an average over one read", async () => {
    // MUTATION: gate on `summary.sample_size < 2` as before. sample_size is
    // 2, so the old gate passed and "avg TSI: 100/100" rendered over ONE
    // mapped read.
    mockSummary.mockResolvedValue(summary({ high_el: 0, high_ins: 0, balanced: 1, unmapped: 1 }));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-dashboard-needs2")).toBeInTheDocument());
    expect(document.body.textContent).not.toContain("avg TSI");
    expect(screen.getByTestId("el-ins-dashboard-unmapped")).toHaveTextContent("1 of 2");
  });

  test("★ [UNMAPPED x3]: mapped 0 -> named, gated, no average", async () => {
    // MUTATION: drop the unmapped line, or gate on total. Three records, zero
    // readings: the page must say so and must not average nothing.
    mockSummary.mockResolvedValue(summary({ high_el: 0, high_ins: 0, balanced: 0, unmapped: 3 }, 0));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-dashboard-unmapped")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-dashboard-unmapped")).toHaveTextContent("3 of 3");
    expect(screen.getByTestId("el-ins-dashboard-needs2")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("avg TSI");
  });

  test("two mapped reads and one unmapped -> the average renders AND the absence is named", async () => {
    // MUTATION: render the unmapped line only inside the gated branch, so it
    // disappears exactly when there is enough data to show the rest.
    mockSummary.mockResolvedValue(summary({ high_el: 1, high_ins: 0, balanced: 1, unmapped: 1 }, 72));
    renderRoute();
    await waitFor(() => expect(document.body.textContent).toContain("avg TSI"));
    expect(screen.queryByTestId("el-ins-dashboard-needs2")).toBeNull();
    expect(screen.getByTestId("el-ins-dashboard-unmapped")).toHaveTextContent("1 of 3");
    expect(document.body.textContent).toContain("72/100");
  });

  test("no unmapped records -> no unmapped line, page exactly as before", async () => {
    // MUTATION: render the line unconditionally. Absence of an absence is not
    // a thing to announce.
    mockSummary.mockResolvedValue(summary({ high_el: 2, high_ins: 1, balanced: 3, unmapped: 0 }, 80));
    renderRoute();
    await waitFor(() => expect(document.body.textContent).toContain("avg TSI"));
    expect(screen.queryByTestId("el-ins-dashboard-unmapped")).toBeNull();
  });
});
