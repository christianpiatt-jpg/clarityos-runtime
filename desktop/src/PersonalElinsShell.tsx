// ClarityOS desktop — Personal ELINS view.
//
// Renders inside the v1 ClarityOSSurface via DesktopShell. Two
// backend calls fired on mount + on "Re-run" click:
//   * /me/emotional_physics/analyze — required (primary)
//   * /elins/v2/run                  — optional ("deeper analysis")
//
// Path C: NO new backend, NO route library, NO new state machinery
// beyond plain useState. ``insights={null}`` so the v1 shell drops
// to a 2-column grid (sidebar + center, no insights pane).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getUser,
  runElinsV2,
  runEmotionalPhysics,
  type ElinsV2Envelope,
  type EmotionalPhysicsResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";

const DEFAULT_SEED = "Personal current state — open snapshot for analysis.";

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function PersonalElinsShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [seed, setSeed] = useState<string>(DEFAULT_SEED);
  const [ep, setEp] = useState<EmotionalPhysicsResponse | null>(null);
  const [elins, setElins] = useState<ElinsV2Envelope | null>(null);
  const [lastRunTs, setLastRunTs] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const run = useCallback(async (text: string) => {
    setLoading(true);
    setError(null);
    try {
      // EP is primary; ELINS v2 is optional (failure tolerated).
      const epRes = await runEmotionalPhysics(text);
      setEp(epRes);
      try {
        const elinsRes = await runElinsV2(text);
        setElins(elinsRes);
      } catch (e) {
        if (handleAuthError(e)) return;
        // ELINS v2 failure is non-fatal — leave the panel empty.
        setElins(null);
      }
      setLastRunTs(Date.now());
    } catch (e) {
      if (handleAuthError(e)) return;
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => {
    void run(DEFAULT_SEED);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onReRun = useCallback(() => {
    void run(seed);
  }, [run, seed]);

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Personal ELINS"
      sidebar={
        <div style={{
          marginTop: "auto",
          padding: 10,
          borderTop: "1px solid rgba(255,255,255,0.15)",
          display: "flex",
          justifyContent: "flex-end",
        }}>
          <button
            type="button"
            onClick={onSignOut}
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
// View
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
        <div style={{
          fontSize: 13,
          color: "var(--color-text-secondary)",
          marginTop: 4,
        }}>
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

// ---------------------------------------------------------------------------
// Sections — pure functions of (ep, elins)
// ---------------------------------------------------------------------------
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
          <div style={{ fontSize: 14, color: "var(--color-text-primary)" }}>
            <Tag tone="cyan">{elins.outputs.attractor}</Tag>
            <span style={{ marginLeft: 8, color: "var(--color-text-secondary)" }}>
              {attractorReading(elins.outputs.attractor)}
            </span>
          </div>
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
  // Per spec — render P0..P3 only for the v1 of this view.
  const slots: Array<"P0" | "P1" | "P2" | "P3"> = ["P0", "P1", "P2", "P3"];
  return (
    <section data-testid="section-collapse-risk">
      <SectionHeader>3. Collapse Risk (P0–P3)</SectionHeader>
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
              border: "1px solid rgba(255,255,255,0.15)",
              padding: 8,
              background: "var(--color-bg-surface)",
            }}>
              <div style={{ color: "var(--color-accent-cyan)", fontSize: 11 }}>{p}</div>
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
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
      border: "1px solid rgba(255,255,255,0.15)",
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
