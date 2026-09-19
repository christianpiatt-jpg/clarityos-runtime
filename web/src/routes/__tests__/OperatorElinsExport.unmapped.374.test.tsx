/**
 * #374-W -- the export preview with UNMAPPED records in the summary.
 *
 * ★ WHY THIS FILE EXISTS. #374 added two rows to this page -- "no reading
 * (0/0)" and "mapped sample size" -- and shipped them with no test: deleting
 * both rows left all ten existing tests green, and rendering the WRONG number
 * in either row (sample_size where mapped_sample_size belongs) was equally
 * invisible. A refuter found that, not a test. The page also printed
 * "avg TSI 0/100 · trend stable" directly under "mapped sample size 0" -- an
 * average of nothing -- where the Dashboard and Macro pages already gated on
 * mapped reads. Fixed in the same leg.
 *
 * Every test names the mutation that breaks it, and every fixture is built so
 * that sample_size != mapped_sample_size: a row that quietly rendered the
 * wrong one cannot pass.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { ConfigResponse, ElInsOperatorSummaryResponse } from "../../lib/api";
import OperatorElinsExport from "../OperatorElinsExport";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getElInsOperatorSummary: vi.fn(), config: vi.fn() };
});

import { config, getElInsOperatorSummary } from "../../lib/api";
const mockSummary = vi.mocked(getElInsOperatorSummary);
const mockConfig = vi.mocked(config);

function summary(
  d: { high_el: number; high_ins: number; balanced: number; unmapped: number },
  avg_tsi: number,
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

const cfg: ConfigResponse = { ok: true, data: { backend: "memory", version: "4.14" } } as ConfigResponse;

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/operator/el_ins/export"]}>
      <OperatorElinsExport />
    </MemoryRouter>,
  );
}

beforeEach(() => { mockSummary.mockReset(); mockConfig.mockReset(); mockConfig.mockResolvedValue(cfg); });
afterEach(() => { vi.clearAllMocks(); });

describe("OperatorElinsExport -- UNMAPPED in the summary (#374-W)", () => {
  test("★ [UNMAPPED x3]: the two rows read 3 and 0, and NO average or trend is printed", async () => {
    // MUTATION: delete either row; or print avg TSI/trend unconditionally
    // (the shipped defect: "avg TSI 0/100 · trend stable" under "mapped
    // sample size 0"). sample_size is 3 and mapped is 0 -- they differ, so a
    // row that renders the wrong one fails here.
    mockSummary.mockResolvedValue(summary({ high_el: 0, high_ins: 0, balanced: 0, unmapped: 3 }, 0));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-export-unmapped")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-export-unmapped")).toHaveTextContent(/^3$/);
    expect(screen.getByTestId("el-ins-export-mapped")).toHaveTextContent(/^0$/);
    expect(screen.getByTestId("el-ins-export-needs2")).toHaveTextContent("0 reads — needs 2");
    // the gated branch's own label reads "avg TSI / trend", so the value is
    // what must be absent -- the "/100" suffix only an average carries
    expect(document.body.textContent).not.toContain("/100");
    expect(document.body.textContent).not.toMatch(/trend\s*stable/);
  });

  test("★ one mapped read among three: mapped reads 1, and one read is not averaged", async () => {
    // MUTATION: gate on sample_size (3 -> passes) instead of mapped (1 ->
    // gated). This is exactly the F violation the Dashboard fixed and this
    // page had not.
    mockSummary.mockResolvedValue(summary({ high_el: 0, high_ins: 0, balanced: 1, unmapped: 2 }, 100));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-export-mapped")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-export-unmapped")).toHaveTextContent(/^2$/);
    expect(screen.getByTestId("el-ins-export-mapped")).toHaveTextContent(/^1$/);
    expect(screen.getByTestId("el-ins-export-needs2")).toHaveTextContent("1 read — needs 2");
    expect(document.body.textContent).not.toContain("100/100");
  });

  test("two mapped reads and one unmapped: the rows AND the average both render", async () => {
    // MUTATION: gate on `<= 2`, or hide the rows inside the gated branch so
    // they vanish exactly when there is enough data to show the rest.
    mockSummary.mockResolvedValue(summary({ high_el: 1, high_ins: 0, balanced: 1, unmapped: 1 }, 72));
    renderRoute();
    await waitFor(() => expect(document.body.textContent).toContain("72/100"));
    expect(screen.queryByTestId("el-ins-export-needs2")).toBeNull();
    expect(screen.getByTestId("el-ins-export-unmapped")).toHaveTextContent(/^1$/);
    expect(screen.getByTestId("el-ins-export-mapped")).toHaveTextContent(/^2$/);
    expect(document.body.textContent).toContain("stable");
  });

  test("★ the mapped row is mapped_sample_size, not sample_size", async () => {
    // MUTATION: render summary.sample_size in the "mapped sample size" row.
    // 20 total, 8 unmapped, 12 mapped -- three distinct numbers on purpose.
    mockSummary.mockResolvedValue(summary({ high_el: 4, high_ins: 3, balanced: 5, unmapped: 8 }, 66));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-export-mapped")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-export-mapped")).toHaveTextContent(/^12$/);
    expect(screen.getByTestId("el-ins-export-unmapped")).toHaveTextContent(/^8$/);
    // and sample size still says 20, unchanged in name, type and meaning
    expect(document.body.textContent).toMatch(/sample size\s*20/);
  });
});
