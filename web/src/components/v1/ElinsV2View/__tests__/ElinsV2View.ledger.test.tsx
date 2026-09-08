/**
 * #180a -- the drop ledger, leg A: the ELINS rail renders what it carries.
 *
 * Per block: present -> rendered; absent -> an em dash; no_signal:true ->
 * one line and nothing else; every caption carries its wire path in a
 * title attribute and its instrument in the text; the old literals are
 * gone.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

import ElinsV2View from "../ElinsV2View";

const DASH = "—";
const six = (a: number) => [a, a - 0.1, a - 0.2, a - 0.3, a - 0.4, a - 0.5];
const etf = (a: number) => ({ "365": a, "3650": a / 2, "18250": a / 10 });

const FULL = {
  elins_version: "elins.v2.0",
  region: "US",
  input: { raw_text: "x" },
  pipeline: {
    L1_ingest: { scenario_id: "sc_abc002d25684e636", char_count: 6000, word_count: 876, domain_hint: null },
    L2_normalize: { normalized: true, note: "a code comment" },
    L3_domain: {
      scores: { geopolitical: 1, institutional: 2, personal: 5, social: 3, technological: 0.5 },
      top: "personal", hint: null, effective_top: "personal",
    },
    L4_narrative: { edge_count: 3, threshold: 0.05 },
    L5_pressure: { primitive: "pressure", intensity: 0.412, edge_count: 3 },
    L6_drift: { primitive: "drift", intensity: 0.05, edge_count: 1 },
    L7_basin: { region: "US", available: true },
    L8_temporal: {
      forecast_5day: {
        days: [
          { day: 1, phase: "balanced", projected_net: 0.1 },
          { day: 2, phase: "rising", projected_net: 0.3 },
          { day: 3, phase: "rising", projected_net: 0.5 },
          { day: 4, phase: "balanced", projected_net: 0.4 },
          { day: 5, phase: "easing", projected_net: 0.2 },
        ],
        starting_net: 0.1, ending_net: 0.2, trend: "rising",
      },
      forecast_engine: {
        primitive_envelopes: {
          pressure: six(1), tension: six(0.9), trust: six(0.8), drift: six(0.7),
          contradiction: six(0.6), alignment: six(0.5),
        },
        multi_envelope: six(0.95),
        domain_envelopes: {
          Economic_Markets: six(1), Geopolitical: six(0.9), Social_Cultural: six(0.8),
          Security_Military: six(0.7), Legal_Justice: six(0.6), Science_Technology: six(0.5),
          Environmental: six(0.55),
        },
        chain: null, chain_envelope: null, days: 5, version: "forecast.v34.1",
      },
      etf_table: {
        pressure: etf(0.9), tension: etf(0.8), trust: etf(0.7), drift: etf(0.6),
        contradiction: etf(0.5), alignment: etf(0.4),
      },
      etf_agg: { n_365: 0.8, n_3650: 0.4, n_18250: 0.05 },
    },
    L9_alignment: { primitive: "alignment", intensity: 0, edge_count: 0 },
    L10_signature: {
      scenario_id: "sc_abc002d25684e636",
      summary: {
        top_primitive: "pressure", top_primitive_intensity: 0.412, domain: "personal",
        signal: "stress", trend: "rising", stress_score: 0.61, relief_score: 0.12, no_signal: false,
      },
      ts: 1, version: "elins.v34.1",
    },
  },
  outputs: {
    collapse_state: "soft",
    attractor: "S1",
    state_distribution: { S1: 0.7, S2: 0.1, S3: 0.1, S4: 0.1 },
    P0_P8: { P0: 0.33, P1: 0, P2: 0, P3: 0.22, P4: 0, P5: 0, P6: 0.44, P7: 0, P8: 0 },
    geography_tier: "T2",
    timeline: { short_term_days: 365, mid_term_days: 3650, long_term_days: 18250 },
    multiplier: 1.225,
  },
  meta: { engine: "clarity_elins_v2", view_kind: "path_c_adapter", warnings: [], notes: [] },
};

/** The shape the older tests send: every layer present but empty. */
const SPARSE = {
  elins_version: "v2",
  region: null,
  input: { raw_text: "x" },
  pipeline: {
    L1_ingest: {}, L2_normalize: {}, L3_domain: {}, L4_narrative: {},
    L5_pressure: { primitive: "pressure", intensity: 0, edge_count: 0 },
    L6_drift: { primitive: "drift", intensity: 0, edge_count: 0 },
    L7_basin: { region: null, available: false },
    L8_temporal: { forecast_5day: {}, forecast_engine: {}, etf_table: {}, etf_agg: {} },
    L9_alignment: { primitive: "alignment", intensity: 0, edge_count: 0 },
    L10_signature: {},
  },
  outputs: {
    collapse_state: "none", attractor: "S1",
    state_distribution: { S1: 0.25, S2: 0.25, S3: 0.25, S4: 0.25 },
    P0_P8: {}, geography_tier: null, timeline: {}, multiplier: 1,
  },
  meta: { engine: "clarity_elins_v2", view_kind: "v2" },
};

function full() { return render(<ElinsV2View envelope={FULL as never} />); }
function sparse() { return render(<ElinsV2View envelope={SPARSE as never} />); }

describe("#180a (a) domain row", () => {
  it("five bars, the top in bold, the values as they came", () => {
    full();
    const row = screen.getByTestId("domain-row");
    expect(within(row).getByTitle("pipeline.L3_domain.scores")).toHaveTextContent("domain · elins-lexicon");
    for (const d of ["geopolitical", "institutional", "personal", "social", "technological"]) {
      expect(screen.getByTestId(`domain-${d}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("domain-personal")).toHaveAttribute("data-top", "true");
    expect(screen.getByTestId("domain-personal")).toHaveTextContent("5");
    expect(screen.getByTestId("domain-technological")).toHaveTextContent("0.50");
    expect(screen.getByTestId("domain-social")).not.toHaveAttribute("data-top");
    expect(screen.queryByTestId("domain-effective")).toBeNull();
  });
  it("absent scores: five names, five dashes, nothing bold", () => {
    sparse();
    for (const d of ["geopolitical", "institutional", "personal", "social", "technological"]) {
      expect(screen.getByTestId(`domain-${d}`)).toHaveTextContent(DASH);
      expect(screen.getByTestId(`domain-${d}`)).not.toHaveAttribute("data-top");
    }
  });
  it("an effective top that moved is named beside the raw top", () => {
    const env = { ...FULL, pipeline: { ...FULL.pipeline, L3_domain: { ...FULL.pipeline.L3_domain, effective_top: "social" } } };
    render(<ElinsV2View envelope={env as never} />);
    expect(screen.getByTestId("domain-social")).toHaveAttribute("data-top", "true");
    expect(screen.getByTestId("domain-effective")).toHaveTextContent("top personal → effective social");
  });
});

describe("#180a (b) signature line", () => {
  it("signal · trend · stress · relief · top (intensity) · domain, the instrument from the wire", () => {
    full();
    expect(screen.getByTitle("pipeline.L10_signature.summary")).toHaveTextContent("signature · elins v34.1");
    expect(screen.getByTestId("sig-signal")).toHaveTextContent("signal stress");
    expect(screen.getByTestId("sig-trend")).toHaveTextContent("trend rising");
    expect(screen.getByTestId("sig-stress_score")).toHaveTextContent("stress 0.610");
    expect(screen.getByTestId("sig-relief_score")).toHaveTextContent("relief 0.120");
    expect(screen.getByTestId("sig-top_primitive")).toHaveTextContent("top pressure (0.412)");
    expect(screen.getByTestId("sig-domain")).toHaveTextContent("domain personal");
  });
  it("absent: every token is a dash", () => {
    sparse();
    for (const k of ["signal", "trend", "stress_score", "relief_score", "top_primitive", "domain"]) {
      expect(screen.getByTestId(`sig-${k}`)).toHaveTextContent(DASH);
    }
  });
  it("★ no_signal:true -- the whole rail is one line, no readings, the actions stay", () => {
    const env = { ...FULL, pipeline: { ...FULL.pipeline, L10_signature: { ...FULL.pipeline.L10_signature, summary: { ...FULL.pipeline.L10_signature.summary, no_signal: true } } } };
    render(<ElinsV2View envelope={env as never} runOn={{ rawText: "x" }} />);
    expect(screen.getByTestId("elins-no-signal")).toHaveTextContent("no signal — elins v34.1");
    expect(screen.queryByTestId("domain-row")).toBeNull();
    expect(screen.queryByTestId("elins-signature")).toBeNull();
    expect(screen.queryByTestId("survival-table")).toBeNull();
    expect(screen.queryByTestId("math-rail")).toBeNull();
    expect(screen.queryByTestId("forecast-row")).toBeNull();
    expect(screen.queryByTestId("elins-provenance")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByLabelText("Re-run ELINS v2")).toBeInTheDocument();
  });
});

describe("#180a (c) survival table", () => {
  it("six primitives × three horizons, then the aggregate; the instrument from the wire", () => {
    full();
    expect(screen.getByTitle("pipeline.L8_temporal.etf_table")).toHaveTextContent("survival · elins forecast v34.1");
    // a cell is a projected INTENSITY (ep0 * exp(-lambda * n)), shown as such;
    // only the aggregate row is a fraction and reads as a percent
    const pressure = screen.getByTestId("survival-pressure");
    expect(within(pressure).getByTitle("pipeline.L8_temporal.etf_table.pressure.365")).toHaveTextContent("0.900");
    expect(within(pressure).getByTitle("pipeline.L8_temporal.etf_table.pressure.3650")).toHaveTextContent("0.450");
    expect(within(pressure).getByTitle("pipeline.L8_temporal.etf_table.pressure.18250")).toHaveTextContent("0.090");
    expect(within(pressure).queryByText(/%/)).toBeNull();
    for (const p of ["pressure", "tension", "trust", "drift", "contradiction", "alignment"]) {
      expect(screen.getByTestId(`survival-${p}`)).toHaveTextContent(p);
    }
    const all = screen.getByTestId("survival-all");
    expect(within(all).getByTitle("pipeline.L8_temporal.etf_agg.n_365")).toHaveTextContent("80%");
    expect(within(all).getByTitle("pipeline.L8_temporal.etf_agg.n_18250")).toHaveTextContent("5%");
    expect(screen.getByText("365d")).toBeInTheDocument();
    expect(screen.getByText("18250d")).toBeInTheDocument();
  });
  it("absent: eighteen dashes and three more, no percent invented", () => {
    sparse();
    const table = screen.getByTestId("survival-table");
    expect(within(table).queryAllByText(/%/)).toHaveLength(0);
    expect(within(table).getAllByText(DASH)).toHaveLength(21);
  });
  it("the old literal is gone", () => {
    full();
    expect(screen.queryByText("ETF · survival")).toBeNull();
  });
});

describe("#180a (d) forecast row + folded envelopes", () => {
  it("a sparkline, start → end · trend, the phases, the envelopes under a fold", () => {
    full();
    expect(screen.getByTitle("pipeline.L8_temporal.forecast_5day")).toHaveTextContent("forecast · elins forecast v34.1");
    expect(screen.getByTestId("forecast-spark")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-nets")).toHaveTextContent("start 0.100 → end 0.200 · trend rising");
    expect(screen.getByTestId("forecast-phases")).toHaveTextContent("d1 balanced 0.10");
    expect(screen.getByTestId("forecast-phases")).toHaveTextContent("d5 easing 0.20");
    const fold = screen.getByTestId("forecast-envelopes");
    expect(within(fold).getByTitle("pipeline.L8_temporal.forecast_engine")).toHaveTextContent("envelopes · elins forecast v34.1 · 5 days");
    expect(within(fold).getByTestId("env-pressure")).toHaveTextContent("1.00 0.90 0.80 0.70 0.60 0.50");
    expect(within(fold).getByTestId("env-Environmental")).toHaveTextContent("0.55 0.45");
    expect(within(fold).getByTestId("env-chain")).toHaveTextContent(DASH);
    expect(within(fold).getByTitle("pipeline.L8_temporal.forecast_engine.domain_envelopes.Legal_Justice")).toBeInTheDocument();
  });
  it("absent: no sparkline, dashes, the seven domain rows still named", () => {
    sparse();
    expect(screen.queryByTestId("forecast-spark")).toBeNull();
    expect(screen.getByTestId("forecast-spark-absent")).toHaveTextContent(DASH);
    expect(screen.getByTestId("forecast-nets")).toHaveTextContent(`start ${DASH} → end ${DASH} · trend ${DASH}`);
    expect(screen.getByTestId("forecast-phases")).toHaveTextContent(DASH);
    expect(screen.getByTestId("env-Geopolitical")).toHaveTextContent(DASH);
    expect(screen.getByTestId("env-multi")).toHaveTextContent(DASH);
  });
});

describe("#180a (e) the P-grid columns carry the timeline", () => {
  it("near 365d · mid 3650d · far 18250d, the section names its instrument", () => {
    full();
    expect(screen.getByTitle("outputs.P0_P8")).toHaveTextContent("P0–P8 · resolution × timescale · elins v2 · outputs");
    expect(screen.getByTestId("pgrid-near-days").parentElement).toHaveTextContent("near · 365d");
    expect(screen.getByTestId("pgrid-mid-days").parentElement).toHaveTextContent("mid · 3650d");
    expect(screen.getByTestId("pgrid-far-days").parentElement).toHaveTextContent("far · 18250d");
  });
  it("absent timeline: the captions carry no days", () => {
    sparse();
    expect(screen.queryByTestId("pgrid-near-days")).toBeNull();
    expect(screen.queryByTestId("pgrid-mid-days")).toBeNull();
    expect(screen.queryByTestId("pgrid-far-days")).toBeNull();
  });
});

describe("#180a (f) provenance footer", () => {
  it("scenario · versions · size · view · edges · basin · region · normalized", () => {
    full();
    const f = screen.getByTestId("elins-provenance");
    expect(f).toHaveTextContent("scenario sc_abc002d25684e636 · elins.v2.0 · elins v34.1 · forecast v34.1 · 6,000 chars / 876 words · view path_c_adapter · edges 3 · threshold 0.050 · basin US · region US · normalized");
    expect(within(f).getByTitle("pipeline.L10_signature.scenario_id · pipeline.L1_ingest.scenario_id")).toBeInTheDocument();
    expect(within(f).getByTitle("pipeline.L1_ingest.char_count · pipeline.L1_ingest.word_count")).toBeInTheDocument();
    expect(within(f).getByTitle("pipeline.L4_narrative.edge_count · pipeline.L4_narrative.threshold")).toBeInTheDocument();
    expect(within(f).getByTitle("pipeline.L7_basin.available · pipeline.L7_basin.region")).toBeInTheDocument();
    expect(within(f).getByTitle("meta.view_kind")).toBeInTheDocument();
    expect(within(f).getByTitle("elins_version")).toBeInTheDocument();
    expect(within(f).getByTitle("region")).toBeInTheDocument();
    expect(within(f).getByTitle("pipeline.L2_normalize.normalized")).toBeInTheDocument();
  });
  it("absent: dashes, never a number; available:false is a value and reads unavailable", () => {
    sparse();
    expect(screen.getByTestId("prov-scenario")).toHaveTextContent(`scenario ${DASH}`);
    expect(screen.getByTestId("prov-size")).toHaveTextContent(`${DASH} chars / ${DASH} words`);
    expect(screen.getByTestId("prov-edges")).toHaveTextContent(`edges ${DASH} · threshold ${DASH}`);
    expect(screen.getByTestId("prov-basin")).toHaveTextContent("basin unavailable");
    expect(screen.getByTestId("prov-normalized")).toHaveTextContent(DASH);
    expect(screen.getByTestId("prov-forecast-version")).toHaveTextContent(DASH);
  });
  it("an unavailable basin reads unavailable even when a region string rides along; a missing flag reads a dash", () => {
    const env = { ...FULL, pipeline: { ...FULL.pipeline, L7_basin: { region: "EU", available: false } } };
    const { unmount } = render(<ElinsV2View envelope={env as never} />);
    expect(screen.getByTestId("prov-basin")).toHaveTextContent("basin unavailable");
    unmount();
    const none = { ...FULL, pipeline: { ...FULL.pipeline, L7_basin: {} } };
    render(<ElinsV2View envelope={none as never} />);
    expect(screen.getByTestId("prov-basin")).toHaveTextContent(`basin ${DASH}`);
  });
});

describe("#180a (g) geography tier + multiplier", () => {
  it("the key in the title, the instrument in the caption; the old literals gone", () => {
    full();
    expect(screen.getByTitle("outputs.geography_tier")).toHaveTextContent("geography tier · elins v2 · outputs");
    expect(screen.getByTitle("outputs.multiplier")).toHaveTextContent("multiplier · elins v2 · outputs");
    expect(screen.queryByText("Geography tier")).toBeNull();
    expect(screen.queryByText("Multiplier")).toBeNull();
    expect(screen.getByText("T2")).toBeInTheDocument();
    expect(screen.getByTestId("multiplier-value")).toHaveTextContent("1.23×");
  });
  it("an absent multiplier is a dash, not 1.00×", () => {
    const env = { ...FULL, outputs: { ...FULL.outputs, multiplier: undefined } };
    render(<ElinsV2View envelope={env as never} />);
    expect(screen.getByTestId("multiplier-value")).toHaveTextContent(DASH);
    expect(screen.queryByText("1.00×")).toBeNull();
  });
  it("a forecast day without a number reads a dash, not an invented ordinal", () => {
    const env = {
      ...FULL,
      pipeline: { ...FULL.pipeline, L8_temporal: { ...FULL.pipeline.L8_temporal, forecast_5day: {
        days: [{ phase: "balanced", projected_net: 0.1 }, { day: 2, phase: "rising", projected_net: 0.3 }],
      } } },
    };
    render(<ElinsV2View envelope={env as never} />);
    expect(screen.getByTestId("forecast-phases")).toHaveTextContent(`${DASH} balanced 0.10`);
    expect(screen.getByTestId("forecast-phases")).toHaveTextContent("d2 rising 0.30");
    expect(screen.getByTestId("forecast-phases")).not.toHaveTextContent("d1");
  });
});

describe("#180a the instruments fall back to the dictionary when the wire carries no version", () => {
  it("survival and signature still name an instrument", () => {
    sparse();
    expect(screen.getByTitle("pipeline.L8_temporal.etf_table")).toHaveTextContent("survival · elins forecast v34.1");
    expect(screen.getByTitle("pipeline.L10_signature.summary")).toHaveTextContent("signature · elins v34.1");
  });
});
