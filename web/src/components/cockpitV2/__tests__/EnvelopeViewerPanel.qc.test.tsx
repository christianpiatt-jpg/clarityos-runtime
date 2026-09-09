/**
 * #203 (CT-1 2026-09-09) -- the QC envelope stops rendering.
 *
 * The Markov state written on every thread turn carries a CONSTANT envelope:
 * _write_thread_markov_state copies the prior forward and starts from the
 * identity one, so qc_predictive 1.0000 · qc_stability 1.0000 ·
 * qc_drift 0.0000 · qc_pressure 0.0000 and three 0.0000 trends were on
 * screen on every turn of every thread, forever. A constant printed to four
 * decimals reads as a measurement. CT-1 measured it on screen 09-09.
 *
 * These pin: the panel renders the rows it EARNS (state vector dims,
 * predictive dims, state index) and nothing computed by no one. The wire
 * still carries the fields -- the backend write did not move.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, markovEnvelopeLatest: vi.fn() };
});

import * as api from "../../../lib/api";
import EnvelopeViewerPanel from "../EnvelopeViewerPanel";
import { cockpit } from "../../../state/cockpitStore";

/** Exactly what the thread path produces today. */
const CONSTANT_ENVELOPE = {
  ok: true as const,
  state_index: 4,
  state_vector: new Array(768).fill(0.01),
  predictive_vector: new Array(768).fill(0.01),
  qc_envelope: {
    qc_stability: 1.0,
    qc_drift: 0.0,
    qc_predictive: 1.0,
    qc_pressure: 0.0,
  },
  envelope_metrics: {
    stability_trend: 0.0,
    drift_trend: 0.0,
    pressure_trend: 0.0,
  },
};

async function mount(envelope: unknown) {
  (api.markovEnvelopeLatest as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(envelope);
  await act(async () => { cockpit.session.actions.select("s1"); });
  render(<EnvelopeViewerPanel />);
}

beforeEach(() => { vi.clearAllMocks(); });
afterEach(() => { cleanup(); act(() => { cockpit.session.actions.select(null); }); });

describe("EnvelopeViewerPanel -- #203 the panel renders the rows it earns", () => {
  it("no qc row and no trend row, even though the wire sends all seven", async () => {
    await mount(CONSTANT_ENVELOPE);
    for (const k of ["qc_stability", "qc_drift", "qc_predictive", "qc_pressure",
                     "stability_trend", "drift_trend", "pressure_trend"]) {
      expect(screen.queryByText(k)).toBeNull();
    }
  });

  it("no 1.0000 and no 0.0000 anywhere on the panel", async () => {
    await mount(CONSTANT_ENVELOPE);
    const text = screen.getByText("Envelope").closest("section")!.textContent ?? "";
    expect(text).not.toContain("1.0000");
    expect(text).not.toContain("0.0000");
  });

  it("the rows it earns: two dimension counts and the state index somebody computed", async () => {
    await mount(CONSTANT_ENVELOPE);
    expect(screen.getByText("state vector")).toBeInTheDocument();
    expect(screen.getByText("predictive vector")).toBeInTheDocument();
    expect(screen.getByText("state index")).toBeInTheDocument();
    expect(screen.getAllByText("768 dims")).toHaveLength(2);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("an absent state_index is an em dash, never a 0", async () => {
    await mount({ ...CONSTANT_ENVELOPE, state_index: null });
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0")).toBeNull();
  });

  it("a state_index of 0 is a reading and renders as 0", async () => {
    await mount({ ...CONSTANT_ENVELOPE, state_index: 0 });
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});

/** The other half of CT-1's rule. "Until something computes them" is not
 *  "never again": /markov/chat writes a REAL envelope to the same store this
 *  panel reads (qc_stability from a similarity, qc_drift from it,
 *  qc_predictive from an exponential, qc_pressure from curvatures, and real
 *  trends). A measured envelope must still render, or the panel would be
 *  hiding a reading somebody DID compute. */
const MEASURED_ENVELOPE = {
  ...CONSTANT_ENVELOPE,
  qc_envelope: {
    qc_stability: 0.8123,
    qc_drift: 0.1877,
    qc_predictive: 0.5701,
    qc_pressure: 0.0442,
  },
  envelope_metrics: {
    stability_trend: -0.0311,
    drift_trend: 0.0311,
    pressure_trend: 0.0044,
  },
};

describe("EnvelopeViewerPanel -- a MEASURED envelope still renders", () => {
  it("the qc rows come back when the values are not the identity constant", async () => {
    await mount(MEASURED_ENVELOPE);
    expect(screen.getByText("qc_stability")).toBeInTheDocument();
    expect(screen.getByText("0.8123")).toBeInTheDocument();
    expect(screen.getByText("qc_pressure")).toBeInTheDocument();
    expect(screen.getByText("0.0442")).toBeInTheDocument();
  });

  it("the trend rows come back when a trend is not zero", async () => {
    await mount(MEASURED_ENVELOPE);
    expect(screen.getByText("stability_trend")).toBeInTheDocument();
    expect(screen.getByText("-0.0311")).toBeInTheDocument();
  });

  it("one changed value is enough: the rest of the identity envelope still shows", async () => {
    await mount({
      ...CONSTANT_ENVELOPE,
      qc_envelope: { ...CONSTANT_ENVELOPE.qc_envelope, qc_drift: 0.25 },
    });
    expect(screen.getByText("qc_drift")).toBeInTheDocument();
    expect(screen.getByText("0.2500")).toBeInTheDocument();
    expect(screen.getByText("qc_stability")).toBeInTheDocument();
  });

  it("the identity envelope with a measured TREND renders the trend only", async () => {
    await mount({
      ...CONSTANT_ENVELOPE,
      envelope_metrics: { stability_trend: 0.0, drift_trend: 0.4, pressure_trend: 0.0 },
    });
    expect(screen.queryByText("qc_stability")).toBeNull();
    expect(screen.getByText("drift_trend")).toBeInTheDocument();
    expect(screen.getByText("0.4000")).toBeInTheDocument();
  });

  it("an empty envelope renders neither block", async () => {
    await mount({ ...CONSTANT_ENVELOPE, qc_envelope: {}, envelope_metrics: {} });
    expect(screen.queryByText("qc_stability")).toBeNull();
    expect(screen.queryByText("stability_trend")).toBeNull();
    expect(screen.getByText("state index")).toBeInTheDocument();
  });
});
