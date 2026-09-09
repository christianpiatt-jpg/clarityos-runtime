/**
 * #180b (2) -- the continuity snapshot's rows render what it carries: five
 * flags as WORDS, eight stores each with its last update in the title, the
 * last episode as one line. Absent -> "—". now_ts is C.
 *
 * #218 (CT-1 2026-09-09) -- these rows MOVED off the cockpit rail to /vault.
 * The assertions came with them, unchanged, including every provenance title:
 * the rail is quiet now, but the ledger contract is not weaker for it. The
 * rail's own (new) contract is pinned in cockpitV2/__tests__/
 * quiet_rail_and_reasons.test.tsx.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import VaultSnapshotRows from "../VaultSnapshotRows";

const DASH = "—";
const TS = 1_788_546_523;

const SNAP = {
  user: "u",
  now_ts: 1_788_553_349,
  counts: { events: 31, episodes: 12, narratives: 12, story_arcs: 0, elins_briefs: 0 },
  last_updated_ts: {
    envelope: TS, events_decay: TS, identity: TS, trajectory: TS, elins: null,
    universal_physics: TS, coherence: TS, memory_context: TS,
  },
  memory_context: {
    stable_intents: [], dominant_topics: ["governance"], trajectory_themes: [],
    last_episode: { sentiment: "neutral", episode_id: "ep_mYQOIREEh_hClZMR", weight: 0.5 },
    last_updated_ts: TS, fading_intents: [], identity_themes: [],
  },
  coherence_flags: { identity_ok: false, elins_ok: false, trajectory_ok: true, cross_scale_ok: true, universal_ok: true },
};

function mount(snapshot: unknown) {
  return render(<VaultSnapshotRows snapshot={snapshot as never} />);
}

describe("VaultSnapshotRows (#180b 2, moved by #218)", () => {
  it("★ five words, never a number; false reads not ok", () => {
    mount(SNAP);
    expect(screen.getByTestId("flag-identity_ok")).toHaveTextContent("identity not ok");
    expect(screen.getByTestId("flag-elins_ok")).toHaveTextContent("elins not ok");
    expect(screen.getByTestId("flag-trajectory_ok")).toHaveTextContent("trajectory ok");
    expect(screen.getByTestId("flag-cross_scale_ok")).toHaveTextContent("cross_scale ok");
    expect(screen.getByTestId("flag-universal_ok")).toHaveTextContent("universal ok");
    expect(screen.getByTestId("vault-flags")).not.toHaveTextContent(/[0-9]/);
    expect(screen.getByTitle("snapshot.coherence_flags.identity_ok")).toBeInTheDocument();
  });
  it("★ eight stores, each with its last update in the title; a null stamp reads a dash there", () => {
    mount(SNAP);
    const stores = screen.getByTestId("vault-stores");
    expect(stores).toHaveTextContent("envelope");
    expect(stores).toHaveTextContent("memory_context");
    expect(screen.getByTestId("store-envelope")).toHaveAttribute("title", "snapshot.last_updated_ts.envelope · last updated 2026-09-04 18:28Z");
    expect(screen.getByTestId("store-elins")).toHaveAttribute("title", `snapshot.last_updated_ts.elins · last updated ${DASH}`);
  });
  it("the last episode as one line, its id and stamp in the title", () => {
    mount(SNAP);
    expect(screen.getByTestId("vault-episode")).toHaveTextContent("last episode neutral · weight 0.5");
    expect(screen.getByTestId("vault-episode")).toHaveAttribute("title", "snapshot.memory_context.last_episode.episode_id ep_mYQOIREEh_hClZMR · snapshot.memory_context.last_updated_ts 2026-09-04 18:28Z");
    expect(screen.getByTestId("vault-episode")).not.toHaveTextContent("1788553349");   // now_ts is C
  });
  it("counts still render, each titled", () => {
    mount(SNAP);
    expect(screen.getByTitle("snapshot.counts.events")).toHaveTextContent("events31");
  });
  it("absent: the five names with dashes, the eight stores dashed in their titles, the episode dashed", () => {
    mount({ user: "u", counts: {} });
    for (const f of ["identity_ok", "elins_ok", "trajectory_ok", "cross_scale_ok", "universal_ok"]) {
      expect(screen.getByTestId(`flag-${f}`)).toHaveTextContent(DASH);
    }
    expect(screen.getByTestId("store-coherence")).toHaveAttribute("title", `snapshot.last_updated_ts.coherence · last updated ${DASH}`);
    expect(screen.getByTestId("vault-episode")).toHaveTextContent(`last episode ${DASH} · weight ${DASH}`);
    expect(screen.getByText("No counts available.")).toBeInTheDocument();
  });
  it("a null snapshot renders the rows, dashed", () => {
    mount(null);
    expect(screen.getByTestId("flag-universal_ok")).toHaveTextContent(DASH);
    expect(screen.getByTestId("vault-snapshot-rows")).toBeInTheDocument();
  });
});
