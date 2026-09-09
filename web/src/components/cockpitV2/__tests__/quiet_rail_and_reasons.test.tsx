/**
 * #218 · #219 (CT-1 2026-09-09, from a member session on index-CWICu6Bz.js)
 *
 * #218 THE RAIL GETS QUIET. VaultStatus used to render about twenty lines off
 * the continuity snapshot. For a new member every one was empty: five counts
 * at 0, five flags at "—", eight store names with no stamp, and a last
 * episode reading "— · weight —". It was noisiest exactly when it had nothing
 * to say. It is now ONE LINK, with ONE line above it only when that line is
 * true: "vault · N items". The rows moved to /vault with their provenance
 * titles (VaultSnapshotRows.ledger.test.tsx pins them there).
 *
 * #219 ABSENCE NAMES ITS REASON. "No Markov state for this session <id>" told
 * a member nothing they could act on, and carried an id. The panel now says
 * which absence it is, from what it already has; and a summary with no turn
 * stamp says why instead of showing a dash.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return {
    ...actual,
    markovEnvelopeLatest: vi.fn(),
    listThreads: vi.fn(), getThread: vi.fn(), createThread: vi.fn(),
    postThreadMessage: vi.fn(), continuitySnapshot: vi.fn(),
  };
});

import * as api from "../../../lib/api";
import { ApiError } from "../../../lib/api";
import VaultStatus, { itemTotal } from "../../cockpit/VaultStatus";
import EnvelopeViewerPanel, {
  absenceReason, NO_TURN_YET, NO_TURN_SINCE_WRITER, NO_STATE_UNKNOWN_WHY,
} from "../EnvelopeViewerPanel";
import { turnCaption, UNSTAMPED_CAPTION } from "../../../lib/summaryCurrency";
import { cockpit } from "../../../state/cockpitStore";

// ===========================================================================
// #218 -- the rail
// ===========================================================================

/** The eight store names that used to sit on the rail. */
const STORE_NAMES = [
  "envelope", "events_decay", "identity", "trajectory",
  "elins", "universal_physics", "coherence", "memory_context",
];

const EMPTY_SNAP = {
  user: "u",
  now_ts: 1_788_553_349,
  counts: { events: 0, episodes: 0, narratives: 0, story_arcs: 0, elins_briefs: 0 },
  coherence_flags: {},
  last_updated_ts: {},
  memory_context: {},
};
const FULL_SNAP = {
  ...EMPTY_SNAP,
  counts: { events: 31, episodes: 12, narratives: 12, story_arcs: 0, elins_briefs: 0 },
};

function mountRail(snapshot: unknown) {
  return render(<MemoryRouter><VaultStatus snapshot={snapshot as never} /></MemoryRouter>);
}

describe("#218 -- the vault rail at N = 0 is ONE link and nothing else", () => {
  it("a new member's empty vault: the link, no count line, no rows", () => {
    mountRail(EMPTY_SNAP);
    expect(screen.getByTestId("vault-open")).toHaveTextContent("Open Vault");
    expect(screen.queryByTestId("vault-total")).toBeNull();
    // not a "0", not a dash, not an empty row
    const rail = screen.getByTestId("vault-open").closest("div")!;
    expect(rail.textContent).toBe("Open Vault →");
  });

  it("none of the eight store names, five flags or the last episode survive on the rail", () => {
    mountRail(EMPTY_SNAP);
    for (const name of STORE_NAMES) expect(screen.queryByTestId(`store-${name}`)).toBeNull();
    for (const f of ["identity_ok", "elins_ok", "trajectory_ok", "cross_scale_ok", "universal_ok"]) {
      expect(screen.queryByTestId(`flag-${f}`)).toBeNull();
    }
    expect(screen.queryByTestId("vault-episode")).toBeNull();
    expect(screen.queryByTestId("vault-flags")).toBeNull();
    expect(screen.queryByTestId("vault-stores")).toBeNull();
    expect(screen.queryByText("No counts available.")).toBeNull();
  });

  it("a null snapshot is the same one link -- an absence is not a reading", () => {
    mountRail(null);
    expect(screen.getByTestId("vault-open")).toBeInTheDocument();
    expect(screen.queryByTestId("vault-total")).toBeNull();
  });
});

describe("#218 -- at N > 0 the rail adds ONE true line", () => {
  it("the count line is the sum of the counts, and keeps its provenance title", () => {
    mountRail(FULL_SNAP);
    expect(screen.getByTestId("vault-total")).toHaveTextContent("continuity · 55 items");
    expect(screen.getByTestId("vault-total")).toHaveAttribute("title", "snapshot.counts (sum)");
    expect(screen.getByTestId("vault-open")).toBeInTheDocument();
  });

  it("★ the line names what it COUNTS -- these are not vault items", () => {
    // A refuter caught this before it shipped. snapshot.counts is the
    // continuity envelope (events · episodes · narratives · story_arcs ·
    // elins_briefs), which grows on every TURN; /vault lists hand-saved
    // notes. CT-1's own captured snapshot reads 55 here and 0 there, so a
    // line saying "vault · 55 items" directly above a link to a page
    // reading "0 items · Nothing saved yet" would be the very defect this
    // order exists to remove.
    mountRail(FULL_SNAP);
    expect(screen.getByTestId("vault-total")).not.toHaveTextContent(/^vault ·/);
  });

  it("one item reads 'item', not 'items'", () => {
    mountRail({ ...EMPTY_SNAP, counts: { events: 1 } });
    expect(screen.getByTestId("vault-total")).toHaveTextContent("continuity · 1 item");
  });

  it("itemTotal never returns NaN and ignores what is not a count", () => {
    expect(itemTotal(null)).toBe(0);
    expect(itemTotal({ counts: {} } as never)).toBe(0);
    expect(itemTotal({ counts: { a: 2, b: "x", c: -4, d: NaN, e: 3 } } as never)).toBe(5);
  });
});

// ===========================================================================
// #219 -- the three envelope reasons
// ===========================================================================

describe("#219 -- absence names its reason, and never repeats the server's line", () => {
  it("no turns on the thread yet", () => {
    expect(absenceReason("no_state", "No Markov state for session t_1", 0)).toBe(NO_TURN_YET);
    expect(NO_TURN_YET).toBe("no turn on this thread yet");
  });

  it("turns exist, but they predate the writer", () => {
    expect(absenceReason("no_state", "No Markov state for session t_1", 14)).toBe(NO_TURN_SINCE_WRITER);
    expect(NO_TURN_SINCE_WRITER).toBe("no turn on this thread since the state writer shipped");
  });

  it("any other failure reads the reason the wire sent", () => {
    expect(absenceReason("rate_limited", "Too many requests", 3)).toBe("Too many requests");
    expect(absenceReason(null, "Failed to fetch", 3)).toBe("Failed to fetch");
  });

  it("neither sentence carries an id or the words 'Markov state'", () => {
    for (const s of [NO_TURN_YET, NO_TURN_SINCE_WRITER]) {
      expect(s).not.toMatch(/Markov/i);
      expect(s).not.toMatch(/t_|sess_|[0-9a-f]{8}/);
    }
  });

  it("an unknown turn count states the fact and claims NO cause -- and never the id", () => {
    // The order banned a bare "No Markov state for session <id>" outright.
    // With no turn count we cannot say WHY, but we can refuse to hand a
    // member an id.
    const line = absenceReason("no_state", "No Markov state for session t_1", null);
    expect(line).toBe(NO_STATE_UNKNOWN_WHY);
    expect(line).toBe("no state for this thread yet");
    expect(line).not.toMatch(/Markov|t_1/);
  });

  it("no branch of absenceReason can emit the banned string", () => {
    for (const count of [0, 1, 14, null]) {
      const line = absenceReason("no_state", "No Markov state for session t_1", count);
      expect(line).not.toMatch(/No Markov state/i);
      expect(line).not.toMatch(/t_1/);
    }
  });
});

describe("#219 -- the panel renders the sentence, not the server's line", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); act(() => { cockpit.session.actions.select(null); }); });

  /** Drive the real store: thread.init() loads the thread AND selects its id
   *  as the session id (cockpitStore), which is what makes the envelope
   *  panel fetch. Same path the cockpit takes on mount. */
  async function mountPanel(messageCount: number) {
    const m = {
      thread_id: "t_1", title: "T", created_at: 1, updated_at: 2,
      message_count: messageCount, archived: false, summary: null,
      summary_ts_ms: null, summary_commit_sha: null, summary_turn: null,
      project_id: null,
    };
    vi.mocked(api.listThreads).mockResolvedValue([m] as never);
    vi.mocked(api.getThread).mockResolvedValue({ meta: m, messages: [] } as never);
    (api.markovEnvelopeLatest as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiError("no_state", "No Markov state for session t_1", 404),
    );
    render(<EnvelopeViewerPanel />);
    await act(async () => { await cockpit.thread.actions.init(); });
  }

  it("a fresh thread reads the no-turn sentence, not 'No Markov state'", async () => {
    await mountPanel(0);
    const line = screen.getByTestId("envelope-absence");
    expect(line).toHaveTextContent(NO_TURN_YET);
    expect(line).not.toHaveTextContent(/Markov/i);
  });

  it("an old thread reads the since-the-writer sentence", async () => {
    await mountPanel(14);
    expect(screen.getByTestId("envelope-absence")).toHaveTextContent(NO_TURN_SINCE_WRITER);
  });
});

// ===========================================================================
// #219 -- the unstamped summary caption
// ===========================================================================

describe("#219 -- a summary with no turn stamp says why", () => {
  it("no made_turn reads one sentence, no dash, no jargon, no id", () => {
    expect(turnCaption({ made_turn: undefined, now_turn: 3 })).toBe(UNSTAMPED_CAPTION);
    expect(turnCaption({ made_turn: null, now_turn: 3 })).toBe(UNSTAMPED_CAPTION);
    expect(turnCaption(null)).toBe(UNSTAMPED_CAPTION);
    expect(UNSTAMPED_CAPTION).toBe("not stamped — summarized before the stamp shipped");
    // no jargon, no id: no sha, no snake_case key, no hex run
    expect(UNSTAMPED_CAPTION).not.toMatch(/sha|_id|[0-9a-f]{7}/i);
  });

  it("a stamped summary is unchanged", () => {
    expect(turnCaption({ made_turn: 3, now_turn: 3 })).toBe("made turn 3 · now turn 3");
    expect(turnCaption({ made_turn: 3, now_turn: 4 })).toBe("made turn 3 · now turn 4");
    expect(turnCaption({ made_turn: 3, now_turn: null })).toBe("made turn 3 · now turn —");
  });
});

// ===========================================================================
// #228 -- the write worked; the panel could not see it
// ===========================================================================

describe("#228 -- a turn reloads the envelope, so the sentence cannot go stale", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); act(() => { cockpit.session.actions.select(null); }); });

  it("★ send() reloads the envelope; without it the panel says the OPPOSITE of the truth", async () => {
    const before = { thread_id: "t_9", title: "T", created_at: 1, updated_at: 2,
      message_count: 0, archived: false, summary: null, summary_ts_ms: null,
      summary_commit_sha: null, summary_turn: null, project_id: null };
    const after = { ...before, message_count: 1 };
    vi.mocked(api.listThreads).mockResolvedValue([before] as never);
    vi.mocked(api.getThread).mockResolvedValue({ meta: before, messages: [] } as never);
    vi.mocked(api.postThreadMessage).mockResolvedValue({
      meta: after,
      user_message: { role: "user", content: "hi", ts_ms: 1 },
      assistant_message: { role: "assistant", content: "ok", ts_ms: 2 },
    } as never);

    // the state does not exist before the turn, and DOES after it -- which is
    // what the backend actually does on this request (#140 B).
    const envelope = vi.mocked(api.markovEnvelopeLatest);
    envelope.mockRejectedValueOnce(new ApiError("no_state", "No Markov state for session t_9", 404));
    envelope.mockResolvedValueOnce({
      ok: true, state_index: 0, state_vector: [0.1], predictive_vector: [0.1],
      qc_envelope: {}, envelope_metrics: {},
    } as never);

    render(<EnvelopeViewerPanel />);
    await act(async () => { await cockpit.thread.actions.init(); });
    expect(screen.getByTestId("envelope-absence")).toHaveTextContent(NO_TURN_YET);

    await act(async () => { await cockpit.thread.actions.send("hi"); });

    // the envelope was re-read on the turn, not left at its 404
    expect(envelope).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId("envelope-absence")).toBeNull();
    // and the sentence that WOULD have appeared is the false one
    expect(screen.queryByText(NO_TURN_SINCE_WRITER)).toBeNull();
  });
});

// ===========================================================================
// #218 -- the link is never gated behind the snapshot
// ===========================================================================

describe("#218 -- the rail's link survives a failed snapshot", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); });

  it("at first paint (status idle, nothing fetched yet) the link is already there", async () => {
    const VaultStatusPanel = (await import("../VaultStatusPanel")).default;
    // no load() call at all: the slice is still idle, which used to match
    // none of the three branches and render an EMPTY body.
    render(<MemoryRouter><VaultStatusPanel /></MemoryRouter>);
    expect(screen.getByTestId("vault-open")).toBeInTheDocument();
    expect(screen.queryByTestId("vault-snapshot-error")).toBeNull();
  });

  it("a failed /continuity/snapshot still leaves a way into the vault", async () => {
    const VaultStatusPanel = (await import("../VaultStatusPanel")).default;
    vi.mocked(api.continuitySnapshot).mockRejectedValue(new ApiError("net", "Network unreachable", 0));
    render(<MemoryRouter><VaultStatusPanel /></MemoryRouter>);
    await act(async () => { await cockpit.vault.actions.load(); });
    expect(screen.getByTestId("vault-open")).toBeInTheDocument();
    expect(screen.getByTestId("vault-snapshot-error")).toHaveTextContent("counts unread");
  });

});
