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
} from "../lib/api";
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

  const run = useCallback(async (text: string) => {
    setLoading(true);
    setError(null);
    try {
      const epRes = await runEmotionalPhysics(text);
      setEp(epRes);
      try {
        const elinsRes = await runElinsV2(text);
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
    void run(DEFAULT_SEED);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onReRun = useCallback(() => {
    void run(seed);
  }, [run, seed]);

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
}

function PersonalElinsView({
  seed, onSeedChange, onReRun, lastRunTs, loading, error, ep, elins,
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
        {/* ★★★ THE SILENT CLIFF AT 6,000 CHARACTERS.
            intelligence_kernel.py:1845 does `cleaned = cleaned[:6000]` and
            its own docstring says "Truncation is silent — the call still
            succeeds." It is a HEAD slice: it keeps the beginning and drops
            the end. In a narrative seed the current state is at the END, so
            a long paste returns a confident read of its oldest half with
            nothing anywhere signalling that the rest was never seen.
            This is the frontend half — count and warn before sending. The
            _meta half is backend and waits on the blocked deploy. */}
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
              limit will NOT be read. The engine keeps the first{" "}
              {SEED_CHAR_LIMIT.toLocaleString()} and silently drops the rest — and the
              end of a seed is usually the current state. Trim from the top, not
              the bottom.
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

      <SectionEmotionalPhysics ep={ep} />
      <SectionAttractor elins={elins} />
      <SectionCollapseRisk elins={elins} />
      <SectionFieldWeather elins={elins} />
    </div>
  );
}

function SectionEmotionalPhysics({ ep }: { ep: EmotionalPhysicsResponse | null }) {
  return (
    <section data-testid="section-emotional-physics">
      <SectionHeader>1. Emotional Physics</SectionHeader>
      {!ep ? (
        <Muted>Awaiting first run…</Muted>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <LayerCard label="Field curvature" body={ep.field_curvature} />
          <LayerCard label="Edge pressure" body={ep.edge_pressure} />
          <LayerCard label="Relational primitives" body={ep.relational_primitives} />
          <LayerCard label="External expression" body={ep.external_expression} />
        </div>
      )}
    </section>
  );
}

function SectionAttractor({ elins }: { elins: ElinsV2Envelope | null }) {
  return (
    <section data-testid="section-attractor">
      <SectionHeader>2. Attractor State</SectionHeader>
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
              <span key={s}>{s}: {fmtPct(elins.outputs.state_distribution[s])}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function SectionCollapseRisk({ elins }: { elins: ElinsV2Envelope | null }) {
  const slots: Array<"P0" | "P1" | "P2" | "P3"> = ["P0", "P1", "P2", "P3"];
  return (
    <section data-testid="section-collapse-risk">
      <SectionHeader>3. Collapse Risk (P0–P3)</SectionHeader>
      {/* ★ These are INDEPENDENT probabilities, not shares of a whole.
          Measured live: 33/0/0/22 = 55%, and 10/21/1/15 = 47%. Neither sums
          to 100 because neither should. Rendering them as adjacent cells of
          equal width invites the reader to total them, so the framing says
          outright that there is no total. The numbers were never wrong. */}
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
      {!elins ? (
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
              <div style={{ color: "var(--color-text-primary)", marginTop: 2 }}>
                {fmtPct(elins.outputs.P0_P8[p] ?? 0)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SectionFieldWeather({ elins }: { elins: ElinsV2Envelope | null }) {
  return (
    <section data-testid="section-field-weather">
      <SectionHeader>4. Field Weather</SectionHeader>
      <div style={{
        fontSize: 13,
        color: "var(--color-text-primary)",
        lineHeight: 1.5,
      }}>
        {deriveFieldWeather(elins)}
      </div>
    </section>
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
      borderBottom: "1px solid rgba(0, 240, 255, 0.15)",
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

function LayerCard({ label, body }: { label: string; body: Record<string, unknown> }) {
  const entries = Object.entries(body || {});
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
      {entries.length === 0 ? (
        <Muted>—</Muted>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {entries.slice(0, 4).map(([k, v]) => {
            if (k === "notes") return null;
            return (
              <Tag key={k} tone="muted">
                {k}: {renderValue(v)}
              </Tag>
            );
          })}
        </div>
      )}
      {notes ? (
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

function renderValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.slice(0, 3).map(String).join(", ") || "—";
  if (typeof v === "object") return "…";
  return String(v).slice(0, 40);
}

// ★ The tie-break moved to lib/attractor.ts so ElinsV2View could import the
// SAME implementation. It shipped here in cdae4ba and missed that consumer,
// which kept rendering the raw backend value. Re-exported so existing
// importers (and the test suite) keep working unchanged.
// Mirrors intelligence_kernel.EMOTIONAL_PHYSICS_INPUT_CHAR_CAP (6_000). Kept
// as a literal because web/ and the runtime share no code; if the backend cap
// moves, this must move with it.
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

function fmtPct(x: number): string {
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
