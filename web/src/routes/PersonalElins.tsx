// ClarityOS web — Personal ELINS route.
//
// Rendered as a full-viewport v1 ClarityOSSurface via WebShell. The
// /personal-elins route is registered OUTSIDE the Layout wrapper in
// App.tsx so the cockpit chrome doesn't nest under the v1 surface.
//
// Two backend calls fire on mount + on "Re-run" click:
//   * /me/emotional_physics/analyze — required (primary)
//   * /elins/v2/run                  — optional ("deeper analysis")
//
// ``insights={null}`` drops the v1 grid to 2 columns (no insights pane).

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  runElinsV2,
  runEmotionalPhysics,
  type ElinsV2Envelope,
  type EmotionalPhysicsResponse,
  type RelationalPrimitives,
} from "../lib/api";
import { useCockpit } from "../state/cockpitStore";
import { bearingRows, stopMark } from "../lib/bearings";
// #238 -- the ONE reading of "a layer above declined".
import { sectionRefusal, physicsRefusal, type Refusal } from "../lib/refusal";
import { labelFor, hasLabel } from "../lib/labels";
import {
  getAuthSnapshot,
  signOut,
  subscribeAuth,
} from "../lib/auth";
import { useSyncExternalStore } from "react";
import WebShell from "../components/WebShell";
import {
  attractorVerdict,
  INDETERMINATE_LABEL,
  indeterminateDetail,
} from "../lib/attractor";

const DEFAULT_SEED = "Personal current state — open snapshot for analysis.";

function useAuth() {
  return useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
}

export default function PersonalElins() {
  const auth = useAuth();
  const navigate = useNavigate();

  const [seed, setSeed] = useState<string>(DEFAULT_SEED);
  const [ep, setEp] = useState<EmotionalPhysicsResponse | null>(null);
  const [elins, setElins] = useState<ElinsV2Envelope | null>(null);
  const [lastRunTs, setLastRunTs] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // #162 (c) -- ONE KEY, TWO DOORS. The cockpit's personal view sent the
  // relationship id (cockpitStore personal.run); this door did not, so a
  // run from here could never accumulate under the relationship the
  // member had selected. The store is the app's one selection; read it.
  const relationshipId = useCockpit((s) => s.relationships.activeId);

  const run = useCallback(async (text: string, rel: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const epRes = await runEmotionalPhysics(text, rel);
      setEp(epRes);
      try {
        const elinsRes = await runElinsV2(text, null, rel);
        setElins(elinsRes);
      } catch {
        // ELINS v2 failure is non-fatal — leave panel empty.
        setElins(null);
      }
      setLastRunTs(Date.now());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // The mount run is the DEFAULT seed -- boilerplate, not the member's
    // text about anyone -- so it is never recorded against a relationship.
    // Re-run carries the selected relationship: a run on it saves a turn.
    void run(DEFAULT_SEED, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onReRun = useCallback(() => {
    void run(seed, relationshipId);
  }, [run, seed, relationshipId]);

  const onNavigate = useCallback((label: string) => {
    // ★ THE MISSING EDGE. /threads and /personal-elins each own the full
    // viewport, and until now the only handled nav labels were those two --
    // so a member inside a thread could not reach the cockpit without
    // typing the URL.
    //
    // ★★ "Home" is the cockpit destination. OperatorSidebar renders SEVEN
    // static NAV_ITEMS (Home, Threads, Projects, Emotional Physics,
    // Personal ELINS, Library, Settings) and there is no "Cockpit" entry;
    // adding one would edit a shared v1 component the harness and
    // ClarityOSSurface also render. Home is the natural destination for the
    // member product and needs no shared-component change.
    //
    // ★ Projects / Emotional Physics / Settings remain DEAD CLICKS -- they
    // render, they are clickable, and nothing happens. Reported, not fixed
    // here: out of scope for this order.
    if (label === "Home") navigate("/cockpit");
    if (label === "Threads") navigate("/threads");
    if (label === "Personal ELINS") navigate("/personal-elins");
  }, [navigate]);

  return (
    <WebShell
      userName={auth.user}
      onNavigate={onNavigate}
      activeNav="Personal ELINS"
      sidebar={
        <div style={{
          marginTop: "auto",
          padding: 10,
          borderTop: "1px solid rgba(20, 24, 28, 0.12)",
          display: "flex",
          justifyContent: "flex-end",
        }}>
          <button
            type="button"
            onClick={signOut}
            title="Clear the local session"
            style={{
              background: "transparent",
              border: "1px solid var(--color-text-secondary)",
              color: "var(--color-text-secondary)",
              padding: "4px 10px",
              fontSize: 11,
              cursor: "pointer",
              borderRadius: 0,
            }}
          >Sign out</button>
        </div>
      }
      center={
        <PersonalElinsView
          seed={seed}
          onSeedChange={setSeed}
          onReRun={onReRun}
          lastRunTs={lastRunTs}
          loading={loading}
          error={error}
          ep={ep}
          elins={elins}
          relationshipId={relationshipId}
        />
      }
      insights={null}
    />
  );
}

// ---------------------------------------------------------------------------
// View — pure presentational. Mirror of desktop PersonalElinsView.
// ---------------------------------------------------------------------------
interface ViewProps {
  seed: string;
  onSeedChange: (s: string) => void;
  onReRun: () => void;
  lastRunTs: number | null;
  loading: boolean;
  error: string | null;
  ep: EmotionalPhysicsResponse | null;
  elins: ElinsV2Envelope | null;
  /** #162 (c) -- the relationship a Re-run saves a turn under. */
  relationshipId?: string | null;
}

function PersonalElinsView({
  seed, onSeedChange, onReRun, lastRunTs, loading, error, ep, elins, relationshipId,
}: ViewProps) {
  return (
    <div
      data-testid="personal-elins-view"
      style={{
        flex: 1,
        overflowY: "auto",
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      <header>
        <h1 style={{ margin: 0, fontSize: 22, color: "var(--color-text-primary)" }}>
          Personal ELINS
        </h1>
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginTop: 4 }}>
          Your personal macro snapshot
        </div>
        <div style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--color-text-secondary)",
          marginTop: 8,
        }}>
          {loading
            ? "running…"
            : lastRunTs
            ? `updated ${relativeTime(lastRunTs)}`
            : "not yet run"}
        </div>
        {relationshipId ? (
          <div
            data-testid="personal-relationship"
            style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-secondary)", marginTop: 4 }}
          >
            re-runs save a turn under relationship {relationshipId}
          </div>
        ) : null}
      </header>

      {error ? (
        <div style={{
          background: "rgba(224, 32, 32, 0.1)",
          border: "1px solid var(--color-accent-red)",
          color: "var(--color-text-primary)",
          padding: 10,
          fontSize: 12,
        }}>
          {error}
        </div>
      ) : null}

      <SeedComposer
        seed={seed}
        onSeedChange={onSeedChange}
        onReRun={onReRun}
        loading={loading}
      />

      <SectionEmotionalPhysics ep={ep} />
      <SectionAttractor elins={elins} />
      <SectionCollapseRisk elins={elins} ep={ep} />
      <SectionFieldWeather elins={elins} ep={ep} />
    </div>
  );
}

/** The seed textarea + character counter + [Re-run] button.
 *
 *  ★ ONE DEFINITION. Extracted verbatim from PersonalElinsView so the
 *  cockpit view renders the SAME control rather than a second copy --
 *  a second copy is the vocabulary drift this build exists to stop. */
export function SeedComposer({
  seed, onSeedChange, onReRun, loading,
}: {
  seed: string;
  onSeedChange: (s: string) => void;
  onReRun: () => void;
  loading: boolean;
}) {
  return (
    <div>
      <label
        htmlFor="seed-input"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          display: "block",
          marginBottom: 4,
        }}
      >Personal state — seed text</label>
      <textarea
        id="seed-input"
        value={seed}
        onChange={(e) => onSeedChange(e.target.value)}
        rows={2}
        aria-describedby="seed-counter"
        style={{
          width: "100%",
          background: "var(--color-bg-surface-alt)",
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          border: "1px solid var(--color-text-secondary)",
          borderRadius: "var(--radius-small)",
          padding: 8,
          outline: "none",
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />
      {/* ★★★ THE CLIFF AT 6,000 CHARACTERS -- now a TAIL cut (#139).
          intelligence_kernel.cut_window keeps the LAST 6,000 characters
          on the personal surface (WINDOW_CHARS["personal"]) and returns
          the window it read in _meta. Before #139 it was a silent HEAD
          slice that kept the beginning and dropped the end -- the current
          state -- which is what this counter was born to warn about. The
          count and the warning stay; the words now say which end is kept. */}
      <div
        id="seed-counter"
        data-testid="seed-counter"
        style={{
          marginTop: 4,
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.03em",
          color: seed.length > SEED_CHAR_LIMIT
            ? "var(--color-accent-red, #E74C3C)"
            : "var(--color-text-secondary)",
        }}
      >
        {seed.length.toLocaleString()} / {SEED_CHAR_LIMIT.toLocaleString()} characters
        {seed.length > SEED_CHAR_LIMIT ? (
          <span data-testid="seed-overflow-warning" style={{ display: "block", marginTop: 2 }}>
            ⚠ {(seed.length - SEED_CHAR_LIMIT).toLocaleString()} characters past the
            limit will NOT be read. The engine keeps the last{" "}
            {SEED_CHAR_LIMIT.toLocaleString()} — the end of a seed, usually the
            current state — and drops the opening. If the opening matters, trim
            from the top yourself so it fits.
          </span>
        ) : null}
      </div>
      <div style={{ marginTop: 8 }}>
        <button
          type="button"
          onClick={onReRun}
          disabled={loading || !seed.trim()}
          data-testid="personal-elins-rerun"
          style={{
            background: "transparent",
            border: "1px solid var(--color-accent-cyan)",
            color: "var(--color-accent-cyan)",
            padding: "6px 14px",
            fontSize: 12,
            cursor: loading || !seed.trim() ? "not-allowed" : "pointer",
            opacity: loading || !seed.trim() ? 0.5 : 1,
            borderRadius: 0,
            fontFamily: "var(--font-sans)",
            letterSpacing: "0.04em",
          }}
        >{loading ? "Running…" : "Re-run Personal ELINS"}</button>
      </div>
    </div>
  );
}

export function SectionEmotionalPhysics({ ep }: { ep: EmotionalPhysicsResponse | null }) {
  // #162 (b) / #196 -- ONLY a reply the ONE backend vocabulary classed
  // as "cut"; "normal" and "unknown" both render nothing.
  const stopped = stopMark(ep?._meta?.stop_reason, ep?._meta?.stop_class);
  return (
    <section data-testid="section-emotional-physics">
      <SectionHeader>1. Emotional Physics</SectionHeader>
      {stopped ? (
        <div
          role="status"
          data-testid="stop-mark"
          style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-accent-red, #E74C3C)", marginBottom: 6 }}
        >
          stopped early: {stopped}
        </div>
      ) : null}
      {!ep ? (
        <Muted>Awaiting first run…</Muted>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <LayerCard label="Field curvature" body={ep.field_curvature} hideUnnamed />
          <LayerCard label="Edge pressure" body={ep.edge_pressure} hideUnnamed />
          {/* #162 (a) -- five NAMED bearings; LayerCard's first-four slice
              used to drop the fifth. */}
          <BearingsCard rp={ep.relational_primitives} />
          {/* #237 (1) -- under a decline this card carries the refusal,
              not guidance. The other three cards are readings of the
              input and stay as they are. */}
          <LayerCard
            label="External expression"
            body={ep.external_expression}
            refusal={physicsRefusal(ep)}
            hideUnnamed
          />
        </div>
      )}
    </section>
  );
}

/** #162 (a) -- layer 3 as five named rows. Missing key -> an em dash;
 *  "unclear" -> the word; the internal key in a title attribute; notes
 *  stays prose. Same reading logic as the v1 physics view (lib/bearings). */
function BearingsCard({ rp }: { rp: RelationalPrimitives | undefined }) {
  const rows = bearingRows(rp);
  const notes = typeof rp?.notes === "string" && rp.notes.trim() ? rp.notes.trim() : null;
  return (
    <div
      data-testid="bearings-card"
      style={{
        border: "1px solid rgba(20, 24, 28, 0.12)",
        background: "var(--color-bg-surface)",
        padding: 10,
      }}
    >
      <div
        title="relational_primitives"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          marginBottom: 6,
        }}
      >
        Relational primitives · {labelFor("relational_primitives").instrument}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {rows.map((r) => (
          <Tag key={r.key} tone="muted">
            <span title={r.key}>{r.label}</span>: <span data-testid={`bearing-${r.key}`}>{r.value}</span>
          </Tag>
        ))}
      </div>
      {notes ? (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-primary)", lineHeight: 1.4 }}>
          {notes}
        </div>
      ) : null}
    </div>
  );
}

export function SectionAttractor({ elins }: { elins: ElinsV2Envelope | null }) {
  return (
    <section data-testid="section-attractor">
      <SectionHeader><span title="attractor">2. {labelFor("attractor").word}</span></SectionHeader>
      {!elins ? (
        <Muted>ELINS v2 unavailable.</Muted>
      ) : (
        <div>
          {(() => {
            const v = attractorVerdict(
              elins.outputs.state_distribution as Record<string, number>,
              elins.outputs.attractor,
            );
            if (!v.determinate) {
              return (
                <div
                  style={{ fontSize: 14, color: "var(--color-text-primary)" }}
                  data-testid="attractor-indeterminate"
                >
                  <Tag tone="cyan">—</Tag>
                  <span style={{ marginLeft: 8, color: "var(--color-text-secondary)" }}>
                    {INDETERMINATE_LABEL}
                  </span>
                  <div style={{
                    marginTop: 4,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--color-text-secondary)",
                  }}>
                    {indeterminateDetail(v.leaders)}
                  </div>
                </div>
              );
            }
            return (
              <div
                style={{ fontSize: 14, color: "var(--color-text-primary)" }}
                data-testid="attractor-determinate"
              >
                <Tag tone="cyan">{v.state}</Tag>
                <span style={{ marginLeft: 8, color: "var(--color-text-secondary)" }}>
                  {attractorReading(v.state)}
                </span>
              </div>
            );
          })()}
          <div style={{
            display: "flex",
            gap: 12,
            marginTop: 10,
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: "var(--color-text-secondary)",
          }}>
            {(["S1", "S2", "S3", "S4"] as const).map((s) => (
              <span key={s}>{s}: {fmtPct(elins.outputs.state_distribution?.[s])}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function SectionCollapseRisk(
  { elins, ep }: { elins: ElinsV2Envelope | null; ep?: EmotionalPhysicsResponse | null },
) {
  const slots: Array<"P0" | "P1" | "P2" | "P3"> = ["P0", "P1", "P2", "P3"];
  // #238 -- a refusal does not get a forecast. When the layer above said
  // it could not assess, NO risk percentage is produced here: not a 33%,
  // not a 0%, not a "balanced". The panel still renders, carrying the
  // reason in that layer's own words, so a member sees that it exists
  // and why it is quiet.
  const refusal = sectionRefusal(ep, elins);
  return (
    <section data-testid="section-collapse-risk">
      {/* #185 -- CT-1's word, the instrument key in the title */}
      <SectionHeader><span title="collapse_state">3. {labelFor("collapse_state").word} (P0–P3)</span></SectionHeader>
      {/* ★ These are INDEPENDENT probabilities, not shares of a whole.
          Measured live: 33/0/0/22 = 55%, and 10/21/1/15 = 47%. Neither sums
          to 100 because neither should. Rendering them as adjacent cells of
          equal width invites the reader to total them, so the framing says
          outright that there is no total. The numbers were never wrong. */}
      {/* ★ #238 -- THE CAPTION IS PART OF THE FORECAST. It used to render
          outside the gate, so a silenced panel still carried "These do not
          sum to 100%" -- a sentence about risk cells that were never
          produced, and a percentage on glass under a refusal. It explains
          the cells; with no cells there is nothing for it to explain. */}
      {!refusal.refused ? (
        <div
          data-testid="collapse-risk-caption"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--color-text-secondary)",
            marginBottom: 6,
            letterSpacing: "0.03em",
          }}
        >
          Independent risks — each is its own probability. These do not sum to 100%.
        </div>
      ) : null}
      {refusal.refused ? (
        <RefusalLine refusal={refusal} testId="collapse-risk-refusal" />
      ) : !elins ? (
        <Muted>ELINS v2 unavailable.</Muted>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 8,
          fontFamily: "var(--font-mono)",
          fontSize: 12,
        }}>
          {slots.map((p) => (
            <div key={p} style={{
              border: "1px solid rgba(20, 24, 28, 0.12)",
              padding: 8,
              background: "var(--color-bg-surface)",
            }}>
              <div style={{ color: "var(--color-accent-cyan)", fontSize: 11 }}>
                {p} risk
              </div>
              <div style={{ color: "var(--color-text-primary)", marginTop: 2 }} data-testid={`risk-${p}`}>
                {/* #185 -- a missing risk is "—", never a manufactured 0% */}
                {fmtPct(elins.outputs.P0_P8?.[p])}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function SectionFieldWeather(
  { elins, ep }: { elins: ElinsV2Envelope | null; ep?: EmotionalPhysicsResponse | null },
) {
  // #238 -- THE PHRASE BANK MUST NOT ASSEMBLE FROM AN EMPTY ENVELOPE.
  // "Soft pressure rising. Watch the edge for fragmentation." is a
  // directional sentence; it was printed over an input the layer above
  // had just declined to assess. On a refusal nothing is composed at all.
  const refusal = sectionRefusal(ep, elins);
  return (
    <section data-testid="section-field-weather">
      <SectionHeader>4. Field Weather</SectionHeader>
      {refusal.refused ? (
        <RefusalLine refusal={refusal} testId="field-weather-refusal" />
      ) : (
        <div style={{
          fontSize: 13,
          color: "var(--color-text-primary)",
          lineHeight: 1.5,
        }}>
          {deriveFieldWeather(elins)}
        </div>
      )}
    </section>
  );
}

/** #238 -- the one sentence a silenced panel carries. The reason is the
 *  declining layer's own words; the layer NAME rides in a title, never in
 *  the prose, because a member should not have to know our layer names. */
function RefusalLine({ refusal, testId }: { refusal: Refusal; testId: string }) {
  return (
    <div
      role="status"
      data-testid={testId}
      title={refusal.source ? `refused by: ${refusal.source}` : undefined}
      style={{
        fontSize: 13,
        color: "var(--color-text-secondary)",
        lineHeight: 1.5,
      }}
    >
      {refusal.reason}
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: "var(--color-accent-cyan)",
      textTransform: "uppercase",
      letterSpacing: "0.05em",
      marginBottom: 8,
      paddingBottom: 4,
      borderBottom: "1px solid var(--os-line)",
    }}>{children}</div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: 8 }}>
      {children}
    </div>
  );
}

function Tag({ tone, children }: { tone: "cyan" | "red" | "muted"; children: React.ReactNode }) {
  const color =
    tone === "cyan"
      ? "var(--color-accent-cyan)"
      : tone === "red"
      ? "var(--color-accent-red)"
      : "var(--color-text-secondary)";
  return (
    <span style={{
      display: "inline-block",
      border: `1px solid ${color}`,
      color,
      padding: "2px 6px",
      fontSize: 11,
      fontFamily: "var(--font-mono)",
      letterSpacing: "0.04em",
    }}>{children}</span>
  );
}

/** #237 -- the external-expression card, and the three other layer cards.
 *
 *  (1) INSTRUCTIONS TO THE MEMBER MUST NEVER LAND IN "what to say", which
 *      means what to say TO ANOTHER PERSON. CT-1 read
 *      `what to say: "Provide a specific situation, interaction, or
 *      relational dynamic to analyze, Include context: who is involved"`
 *      under a section that had just refused. When the layer above
 *      declined, this card carries the refusal AS a refusal and renders no
 *      guidance at all.
 *  (2) NO INTERNAL KEY ON GLASS. labelFor falls back to the raw key, so
 *      `risk_if_unchanged` and `ext_step` -- neither of which is in the
 *      #201 dictionary -- were printed to a member verbatim. A key with no
 *      word of CT-1's is NOT rendered; the card says how many readings it
 *      is holding back, and the keys are reported to CT-1 to name. No
 *      wording is invented here. */
function LayerCard(
  { label, body, refusal, hideUnnamed }: {
    label: string;
    body: Record<string, unknown>;
    refusal?: Refusal;
    /** #237 (2) -- suppress keys CT-1 has not named.
     *
     *  ★ THIS WAS FIRST SET ONLY ON THE EXTERNAL-EXPRESSION CARD, on the
     *  belief that the other cards ship real readings whose keys have no
     *  dictionary word. A refuter proved that FALSE: `stable` and
     *  `reads_as_distant` exist nowhere but a test fixture, and EVERY key
     *  the physics schema actually defines already has one of CT-1's
     *  words. Hiding unnamed keys everywhere is therefore a no-op on real
     *  output and makes "no internal key is on glass" a PROPERTY of the
     *  surface instead of a spot fix on one card -- which matters because
     *  this leg exists precisely because the model drifts from the schema. */
    hideUnnamed?: boolean;
  },
) {
  const allEntries = Object.entries(body || {});
  const unnamed = hideUnnamed
    ? allEntries.filter(([k]) => k !== "notes" && !hasLabel(k))
    : [];
  const entries = hideUnnamed
    ? allEntries.filter(([k]) => k === "notes" || hasLabel(k))
    : allEntries;
  const notes = typeof (body as Record<string, unknown>).notes === "string"
    ? (body as Record<string, unknown>).notes as string
    : null;
  return (
    <div style={{
      border: "1px solid rgba(20, 24, 28, 0.12)",
      background: "var(--color-bg-surface)",
      padding: 10,
    }}>
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color: "var(--color-text-secondary)",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        marginBottom: 6,
      }}>{label}</div>
      {refusal?.refused ? (
        /* (1) -- the refusal, as a refusal. No guidance under a decline. */
        <div
          role="status"
          data-testid="layer-refusal"
          style={{ fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.4 }}
        >
          {refusal.reason}
        </div>
      ) : entries.filter(([k]) => k !== "notes").length === 0 ? (
        <Muted>—</Muted>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {/* #162 -- every reading. The first-four slice dropped layer 2's
              fifth key (risk_of_misread) and, when notes landed early, two. */}
          {entries.map(([k, v]) => {
            if (k === "notes") return null;
            // #237 (4) -- A LIST RENDERS AS A LIST. The old renderer joined
            // items with ", " and printed them as one sentence, so CT-1 read
            // "...dynamic to analyze, Include context: who is involved" as a
            // single run-on line. A multi-item reading gets its own stacked
            // block; a single value keeps the chip.
            if (Array.isArray(v) && v.length > 1) {
              return (
                <div key={k} style={{ flexBasis: "100%", marginTop: 2 }}>
                  <div style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--color-text-secondary)",
                    letterSpacing: "0.04em",
                  }}>
                    <span title={k}>{labelFor(k).word}</span>
                  </div>
                  <ul
                    data-testid={`layer-${k}`}
                    style={{ margin: "2px 0 0", paddingLeft: 16, fontSize: 12, lineHeight: 1.4 }}
                  >
                    {v.map((item, i) => (
                      <li key={i} style={{ color: "var(--color-text-primary)" }}>{String(item)}</li>
                    ))}
                  </ul>
                </div>
              );
            }
            // #185 -- CT-1's word for the sub-key (labels.ts), the raw key in
            // the title; a false reads its WORD, a missing value "—".
            return (
              <Tag key={k} tone="muted">
                <span title={k}>{labelFor(k).word}</span>: <span data-testid={`layer-${k}`}>{renderValue(v)}</span>
              </Tag>
            );
          })}
        </div>
      )}
      {/* (2) -- a held-back reading is declared, never silently dropped,
          and never by its internal name. */}
      {!refusal?.refused && unnamed.length > 0 ? (
        <div
          data-testid={`layer-unnamed-${label.toLowerCase().replace(/\s+/g, "-")}`}
          title={unnamed.map(([k]) => k).join(" · ")}
          style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-secondary)" }}
        >
          {unnamed.length} {unnamed.length === 1 ? "reading" : "readings"} not yet named
        </div>
      ) : null}
      {notes && !refusal?.refused ? (
        <div style={{
          marginTop: 8,
          fontSize: 12,
          color: "var(--color-text-primary)",
          lineHeight: 1.4,
        }}>{notes}</div>
      ) : null}
    </div>
  );
}

/** #237 (3) + (4) -- WHAT THIS USED TO DO, AND WHY IT WAS WRONG.
 *
 *   `String(v).slice(0, 40)`  cut prose mid-word with no ellipsis and no
 *     declaration. CT-1 read "Resubmit with a specific interpersonal o"
 *     on his own session -- exactly 40 characters. #139: a cut declares
 *     itself. The cut is RAISED (a card has room to wrap) and, if a value
 *     ever does exceed the new ceiling, it declares itself with an
 *     ellipsis instead of stopping mid-syllable.
 *   `v.slice(0, 3).join(", ")`  printed a list of instructions as ONE
 *     comma-joined sentence ("...to analyze, Include context: who is
 *     involved") AND silently dropped the fourth item. A list renders as
 *     a list; nothing is dropped.
 *
 *  renderValue keeps its string contract for the scalar callers; arrays
 *  now go through renderList, which returns nodes. */
export const VALUE_CHAR_LIMIT = 400;

/** Test hook: the value rule itself, so the "a false reads its WORD" pin
 *  (#185) survives independently of which card renders which key (#237). */
export function renderValueForTest(v: unknown): string { return renderValue(v); }

function renderValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";   // #185 -- a false is a word, never blank
  if (Array.isArray(v)) return v.map(String).join(" · ") || "—";
  if (typeof v === "object") return "…";
  const s = String(v);
  // #139 -- a cut declares itself.
  return s.length > VALUE_CHAR_LIMIT ? s.slice(0, VALUE_CHAR_LIMIT) + "\u2026" : s;
}

// ★ The tie-break moved to lib/attractor.ts so ElinsV2View could import the
// SAME implementation. It shipped here in cdae4ba and missed that consumer,
// which kept rendering the raw backend value. Re-exported so existing
// importers (and the test suite) keep working unchanged.
// Mirrors intelligence_kernel.WINDOW_CHARS["personal"] (6_000, a TAIL window
// since #139). Kept as a literal because web/ and the runtime share no code;
// if the backend table moves, this must move with it.
export const SEED_CHAR_LIMIT = 6000;

export {
  attractorVerdict,
  ATTRACTOR_TIE_EPSILON,
  type AttractorVerdict,
} from "../lib/attractor";

function attractorReading(a: "S1" | "S2" | "S3" | "S4"): string {
  switch (a) {
    case "S1": return "stable coherence";
    case "S2": return "pressured coherence";
    case "S3": return "pressured incoherence";
    case "S4": return "collapse trajectory";
  }
}

function deriveFieldWeather(elins: ElinsV2Envelope | null): string {
  if (!elins) return "Awaiting deeper analysis…";
  const { attractor, collapse_state, multiplier } = elins.outputs;
  // ★ The same tie applies here. "Field is calm" on a level distribution is
  // the same false reassurance as the S1 label, in prose.
  const verdict = attractorVerdict(
    elins.outputs.state_distribution as Record<string, number>, attractor,
  );
  if (!verdict.determinate && collapse_state !== "hard" && collapse_state !== "soft") {
    return "No attractor leads. The field is level rather than settled — "
      + "read the pressure and collapse figures directly.";
  }
  if (collapse_state === "hard") {
    return "Hard collapse trajectory. Field is unstable; intervention warranted.";
  }
  if (collapse_state === "soft") {
    return "Soft pressure rising. Watch the edge for fragmentation.";
  }
  switch (attractor) {
    case "S1": return "Stable coherence. Field is calm.";
    case "S2": return "Pressured coherence. Strain bearable; structure intact.";
    case "S3": return "Pressured incoherence. Field is fragmenting at the edges.";
    case "S4":
      return `Collapse trajectory forming (multiplier ${multiplier.toFixed(2)}).`;
  }
}

function fmtPct(x: unknown): string {
  // #185 -- only a number is a reading; anything else is "—", never 0%
  if (typeof x !== "number" || !Number.isFinite(x)) return "\u2014";
  if (!Number.isFinite(x)) return "—";
  return `${Math.round(x * 100)}%`;
}

function relativeTime(ts_ms: number): string {
  if (!ts_ms) return "—";
  const diff = Date.now() - ts_ms;
  if (diff < 0) return new Date(ts_ms).toLocaleTimeString();
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts_ms).toLocaleDateString();
}
