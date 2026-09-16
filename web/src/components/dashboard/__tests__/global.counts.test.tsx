/**
 * #305 C5 C6 -- the founder inspector and the /dashboard Global card:
 * no_signal:true reads "—", never 0 / "balanced"; and the Global card names
 * no top primitive on a tie (#284's rule, the 5-point epsilon).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GlobalPanel, { topPrimitiveWord } from "../GlobalPanel";
import { synthesisView } from "../../founder/ELINSInspector";

const BASE = {
  scenario_id: "sc_1", ep_mean: 0.0, domains: {}, forecast: [], has_eso: false, available: true,
  top_primitives: [{ key: "alignment", intensity: 0 }, { key: "contradiction", intensity: 0 }],
};

describe("#305 C5 -- no signal is a dash", () => {
  it("★ the Global card: EP mean and the top primitive read '—', the bars are one dash", () => {
    render(<GlobalPanel section={{ ...BASE, no_signal: true } as never} />);
    // the Stat's title rides on its label; the value is the next element
    expect(screen.getByTitle("snapshot.global.ep_mean").nextElementSibling).toHaveTextContent("—");
    expect(screen.getByTitle("snapshot.global.top_primitives[0].key").nextElementSibling).toHaveTextContent("—");
    expect(screen.getByTestId("global-no-signal")).toHaveTextContent("—");
    expect(screen.queryByText("alignment")).toBeNull();
    expect(screen.queryByText("0.000")).toBeNull();
  });

  it("the inspector's synthesis: the six reading fields read '—'; other keys ride through", () => {
    const syn = { top_primitive: "alignment", top_primitive_intensity: 0, domain: "personal", signal: "balanced",
      trend: "flat", stress_score: 0, relief_score: 0, no_signal: true };
    expect(synthesisView(syn)).toEqual({ top_primitive: "—", top_primitive_intensity: "—", domain: "personal",
      signal: "—", trend: "—", stress_score: "—", relief_score: "—", no_signal: true });
    const real = { ...syn, no_signal: false };
    expect(synthesisView(real)).toBe(real);
  });
});

describe("#305 C6 -- a tie names no top primitive", () => {
  it("★ within 5 points: '—'; a clear lead: the key", () => {
    expect(topPrimitiveWord({ ...BASE, top_primitives: [{ key: "pressure", intensity: 0.30 }, { key: "tension", intensity: 0.27 }] } as never)).toBe("—");
    expect(topPrimitiveWord({ ...BASE, top_primitives: [{ key: "pressure", intensity: 0.30 }, { key: "tension", intensity: 0.20 }] } as never)).toBe("pressure");
    expect(topPrimitiveWord({ ...BASE, top_primitives: [{ key: "pressure", intensity: 0.30 }] } as never)).toBe("pressure");
    expect(topPrimitiveWord({ ...BASE, top_primitives: [] } as never)).toBe("—");
  });
  it("on the card", () => {
    render(<GlobalPanel section={{ ...BASE, ep_mean: 0.2, top_primitives: [{ key: "pressure", intensity: 0.30 }, { key: "tension", intensity: 0.27 }] } as never} />);
    expect(screen.getByTitle("snapshot.global.top_primitives[0].key").nextElementSibling).toHaveTextContent("—");
    expect(screen.getByTitle("snapshot.global.ep_mean").nextElementSibling).toHaveTextContent("0.200");
  });
});
