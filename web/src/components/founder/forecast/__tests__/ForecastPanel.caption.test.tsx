/**
 * #119 — the founder's forecast chart says it is SAMPLE DATA.
 *
 * ★ WHAT THIS PINS. When ForecastPanel fetches /elins/forecast/example
 * itself (no block prop) the data is a fixture (app.py's example route),
 * and the panel now says so in one caption line under the chart. When a
 * block is PROVIDED (the ELINS inspector after a real run) there is no
 * caption -- that is a live run, and the caption would be the new lie.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  elinsForecastExample: vi.fn(),
}));

import { elinsForecastExample, type V34ForecastBlock } from "../../../../lib/api";
import ForecastPanel from "../ForecastPanel";

const mocked = vi.mocked(elinsForecastExample);

function block(): V34ForecastBlock {
  return {
    primitive_envelopes: { pressure: [0.5, 0.4, 0.3] },
    multi_envelope: [0.5, 0.4, 0.3],
    domain_envelopes: {},
    chain: null,
    chain_envelope: null,
    days: 2,
    version: "v34",
  };
}

const CAPTION = "fixture from /elins/forecast/example — not a live run";

describe("ForecastPanel — sample-data caption (#119)", () => {
  beforeEach(() => { mocked.mockReset(); });

  it("★ self-fetched example: the caption line is under the chart", async () => {
    mocked.mockResolvedValue({
      ok: true,
      example: { label: "example", inputs: { intensities: {}, edges: [], days: 2 }, forecast: block() },
    });
    render(<ForecastPanel title="Forecast engine (v34) — SAMPLE DATA" />);
    await waitFor(() => expect(screen.getByTestId("forecast-fixture-caption")).toBeInTheDocument());
    expect(screen.getByTestId("forecast-fixture-caption")).toHaveTextContent(CAPTION);
    expect(screen.getByText("Forecast engine (v34) — SAMPLE DATA")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledTimes(1);
  });

  it("a PROVIDED block (a real run) carries no caption", () => {
    render(<ForecastPanel block={block()} title="Forecast engine (v34)" />);
    expect(screen.queryByTestId("forecast-fixture-caption")).toBeNull();
    expect(mocked).not.toHaveBeenCalled();
  });
});
