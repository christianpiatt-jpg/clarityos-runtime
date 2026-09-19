/**
 * #374 -- the macro distribution with UNMAPPED records in it.
 *
 * ★ WHY THIS FILE EXISTS. The existing macro test cannot construct an
 * UNMAPPED record (its makeRecord type is closed at three classes), so every
 * branch #374 added to computeStats and the stats panel was reachable from
 * the wire and unexercised. Before #374, `counts[cls] += 1` on an UNMAPPED
 * record indexed a key that did not exist: undefined + 1 wrote NaN to a
 * phantom entry, the record left the distribution, and `total` still counted
 * it -- so three percentages divided by a denominator none of them
 * represented, and summed to well under 100 with nothing on the page saying
 * why.
 *
 * Every test names the mutation that breaks it.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { ElInsMacroResponse, ElInsRatioClassification, ElInsRecord } from "../../lib/api";
import OperatorElinsMacro from "../OperatorElinsMacro";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getElInsMacro: vi.fn() };
});

import { getElInsMacro } from "../../lib/api";
const mockMacro = vi.mocked(getElInsMacro);

function rec(cls: ElInsRatioClassification | string, el: number, ins: number, ts: number): ElInsRecord {
  return {
    operator_id: "op_alice", thread_id: "t1", timestamp: ts, source: "per_turn",
    result: {
      analysis: {
        el_components: [], ins_components: [],
        el_score: el, ins_score: ins,
        // the cast is the point: the wire can carry a value the union has
        // not heard of, and the page must not vanish it
        ratio_classification: cls as ElInsRatioClassification,
      },
      reasoning_mode: cls === "UNMAPPED" ? "UNMAPPED" : "normal",
      regression_chain: { projection: null, drivers: [], precedents: [], principle_stack: [], invariant: null },
      stability_notes: null,
    },
  };
}

function resp(recs: ElInsRecord[]): ElInsMacroResponse {
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
afterEach(() => { vi.clearAllMocks(); });

describe("OperatorElinsMacro -- UNMAPPED in the distribution (#374)", () => {
  test("★ the no-reading row is named, and the percentages divide by the MAPPED count", async () => {
    // MUTATION: divide by `n` (total) instead of `mapped`, or drop the
    // UNMAPPED key from `counts`. Three mapped reads: 2 balanced, 1 high_el.
    // Over mapped that is 66.7 / 33.3 / 0; over total it would be 50 / 25 / 0
    // -- summing to 75 with nothing saying where the last quarter went.
    mockMacro.mockResolvedValue(resp([
      rec("balanced", 4, 3, 1000), rec("balanced", 4, 3, 1001),
      rec("high_el", 9, 1, 1002), rec("UNMAPPED", 0, 0, 1003),
    ]));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-macro-stats")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-macro-unmapped")).toHaveTextContent("1 of 4");
    const stats = screen.getByTestId("el-ins-macro-stats").textContent ?? "";
    expect(stats).toContain("66.7%");
    expect(stats).toContain("33.3%");
    expect(stats).not.toContain("50.0%");
  });

  test("★ every record UNMAPPED -> '3 of 3', the reads-needed gate, no percentages, no NaN", async () => {
    // MUTATION: gate on `total < 2` instead of `mapped < 2`, or remove the
    // `mapped || 1` guard (0/0 -> NaN%). Three records, zero readings: there
    // is no split to show however many there are.
    mockMacro.mockResolvedValue(resp([
      rec("UNMAPPED", 0, 0, 1000), rec("UNMAPPED", 0, 0, 1001), rec("UNMAPPED", 0, 0, 1002),
    ]));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-macro-stats")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-macro-unmapped")).toHaveTextContent("3 of 3");
    expect(screen.getByTestId("el-ins-macro-needs2")).toBeInTheDocument();
    const stats = screen.getByTestId("el-ins-macro-stats").textContent ?? "";
    expect(stats).not.toMatch(/\d+\.\d%/);
    expect(stats).not.toContain("NaN");
  });

  test("no UNMAPPED records -> the row reads 'none' and the split is unchanged", async () => {
    // MUTATION: render the row only when unmapped > 0 without the "none"
    // arm -- the reader then cannot tell "no unmapped" from "not counted".
    mockMacro.mockResolvedValue(resp([rec("balanced", 4, 3, 1000), rec("high_ins", 1, 9, 1001)]));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-macro-stats")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-macro-unmapped")).toHaveTextContent("none");
    expect(screen.getByTestId("el-ins-macro-stats").textContent).toContain("50.0%");
  });

  test("★ a value the union has never heard of counts as unmapped rather than vanishing", async () => {
    // MUTATION: `counts[cls] += 1` unguarded -- a fifth wire state would
    // write NaN to a phantom key and leave the page silently, exactly as
    // UNMAPPED did before #374.
    mockMacro.mockResolvedValue(resp([
      rec("balanced", 4, 3, 1000), rec("balanced", 4, 3, 1001), rec("a_future_state", 2, 2, 1002),
    ]));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-macro-stats")).toBeInTheDocument());
    expect(screen.getByTestId("el-ins-macro-unmapped")).toHaveTextContent("1 of 3");
    const stats = screen.getByTestId("el-ins-macro-stats").textContent ?? "";
    expect(stats).toContain("100.0%");
    expect(stats).not.toContain("NaN");
  });

  test("an UNMAPPED record renders an em dash in the table, in the muted colour", async () => {
    // MUTATION: render the raw key, or fall through to the OK green.
    mockMacro.mockResolvedValue(resp([rec("balanced", 4, 3, 1000), rec("UNMAPPED", 0, 0, 1001)]));
    renderRoute();
    await waitFor(() => expect(screen.getByTestId("el-ins-macro-stats")).toBeInTheDocument());
    const cells = Array.from(document.querySelectorAll("td")).filter(td => td.textContent === "—");
    expect(cells.length).toBeGreaterThan(0);
    const dashCell = cells.find(td => (td.getAttribute("style") ?? "").includes("--os-text-muted"));
    expect(dashCell).toBeDefined();
    expect(document.body.textContent).not.toContain("UNMAPPED");
  });
});
