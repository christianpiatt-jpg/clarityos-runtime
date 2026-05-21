// v69 / Unit 74 — Per-operator EL/INS dashboard (desktop).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getElInsReasoningMode,
  getElInsRecent,
  getElInsThread,
  getElInsThreadStability,
  getUser,
  postElInsAnalyze,
  type ElInsProviderMode,
  type ElInsReasoningModeResponse,
  type ElInsRecord,
  type ElInsThreadStabilityResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const PROVIDER_MODES: readonly ElInsProviderMode[] = [
  "auto", "llm", "deterministic",
] as const;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorElinsShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<ElInsProviderMode>("auto");
  const [analyzeThreadId, setAnalyzeThreadId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);

  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [threadRecords, setThreadRecords] = useState<ElInsRecord[] | null>(null);
  const [stability, setStability] = useState<ElInsThreadStabilityResponse | null>(null);
  // v71 / Unit 79 — operator-level reasoning_mode for the header label.
  const [reasoningMode, setReasoningMode] = useState<ElInsReasoningModeResponse | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const fetchRecent = useCallback(async () => {
    setLoadingRecent(true);
    setRecentError(null);
    try {
      const [r, m] = await Promise.all([
        getElInsRecent(100),
        getElInsReasoningMode().catch(() => null),
      ]);
      setRecords(r.records);
      if (m) setReasoningMode(m);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setRecentError(formatError(e));
    } finally {
      setLoadingRecent(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void fetchRecent(); }, [fetchRecent]);

  const fetchThread = useCallback(async (tid: string) => {
    setSelectedThread(tid);
    setStability(null);
    try {
      const [detail, stab] = await Promise.all([
        getElInsThread(tid),
        getElInsThreadStability(tid),
      ]);
      setThreadRecords(detail.records);
      setStability(stab);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      // silent — surface in the "no records" empty state
      setThreadRecords([]);
    }
  }, [handleAuthError]);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      await postElInsAnalyze({
        text,
        provider_mode: mode,
        thread_id: analyzeThreadId.trim() || null,
      });
      setText("");
      await fetchRecent();
      if (analyzeThreadId.trim()) {
        await fetchThread(analyzeThreadId.trim());
      }
    } catch (err: unknown) {
      if (handleAuthError(err)) return;
      setAnalyzeError(formatError(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="EL/INS"
      sidebar={
        <div style={signOutContainerStyle}>
          <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>
            Sign out
          </button>
        </div>
      }
      center={
        <DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>EL/INS DASHBOARD</h1>
            <p style={mutedStyle}>
              Reasoning-stability diagnostic. Analyses are stored under the
              authed operator, keyed by thread_id when provided.
            </p>
            {userName ? (
              <div style={authedBadgeStyle}>
                Authed as <span style={authedBadgeNameStyle}>{userName}</span>
              </div>
            ) : null}
            {reasoningMode ? (
              <div style={{
                marginTop: 6, fontSize: 11, letterSpacing: "0.5px",
                color: "var(--color-text-secondary)", fontFamily: "monospace",
              }}>
                Reasoning Mode: <span style={{ color: "var(--color-text-primary)" }}>
                  {reasoningModeLabel(reasoningMode.reasoning_mode)}
                </span>
              </div>
            ) : null}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>ANALYZE</h2>
            <form onSubmit={handleAnalyze}>
              <label style={fieldLabel} htmlFor="el-text">Text</label>
              <textarea
                id="el-text"
                value={text}
                onChange={(ev) => setText(ev.target.value)}
                rows={4}
                disabled={analyzing}
                style={textareaStyle}
                placeholder="Paste or type the text to score…"
              />
              <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "flex-end" }}>
                <div style={{ flex: 0 }}>
                  <label style={fieldLabel} htmlFor="el-mode">Provider mode</label>
                  <select
                    id="el-mode"
                    value={mode}
                    onChange={(ev) => setMode(ev.target.value as ElInsProviderMode)}
                    disabled={analyzing}
                    style={inputStyle}
                  >
                    {PROVIDER_MODES.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={fieldLabel} htmlFor="el-thread">Thread id (optional)</label>
                  <input
                    id="el-thread"
                    type="text"
                    value={analyzeThreadId}
                    onChange={(ev) => setAnalyzeThreadId(ev.target.value)}
                    disabled={analyzing}
                    placeholder="(no thread)"
                    style={inputStyle}
                  />
                </div>
                <button
                  type="submit"
                  disabled={analyzing || !text.trim()}
                  style={btnPrimary}
                >
                  {analyzing ? "ANALYZING…" : "ANALYZE"}
                </button>
              </div>
            </form>
            {analyzeError ? <div style={bannerStyle}>{analyzeError}</div> : null}
          </div>

          <div style={panelStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <h2 style={{ ...h2Style, margin: 0 }}>RECENT</h2>
              <button
                type="button"
                onClick={() => void fetchRecent()}
                disabled={loadingRecent}
                style={btnSecondary}
              >REFRESH</button>
            </div>
            {loadingRecent && !records ? (
              <div>Loading…</div>
            ) : recentError ? (
              <div style={bannerStyle}>{recentError}</div>
            ) : !records || records.length === 0 ? (
              <div style={emptyStyle}>No EL/INS records yet for this operator.</div>
            ) : (
              <table style={tableStyle}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                    <th style={thStyle}>Timestamp</th>
                    <th style={thStyle}>Thread</th>
                    <th style={thStyle}>Classification</th>
                    <th style={thStyle}>EL</th>
                    <th style={thStyle}>INS</th>
                    <th style={thStyle}>Mode</th>
                    <th style={thStyle}>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec, i) => (
                    <tr key={`${rec.timestamp}-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(rec.timestamp)}
                      </td>
                      <td style={tdStyle}>
                        {rec.thread_id ? (
                          <button
                            type="button"
                            onClick={() => void fetchThread(rec.thread_id as string)}
                            style={linkBtnStyle}
                          >
                            {rec.thread_id}
                          </button>
                        ) : (
                          <span style={{ color: "var(--color-text-secondary)" }}>—</span>
                        )}
                      </td>
                      <td style={{ ...tdStyle, color: classColor(rec.result.analysis.ratio_classification) }}>
                        {rec.result.analysis.ratio_classification}
                      </td>
                      <td style={tdStyle}>{rec.result.analysis.el_score.toFixed(2)}</td>
                      <td style={tdStyle}>{rec.result.analysis.ins_score.toFixed(2)}</td>
                      <td style={tdStyle}>{rec.result.reasoning_mode}</td>
                      <td style={tdStyle}>{rec.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {selectedThread ? (
            <div style={panelStyle}>
              <h2 style={h2Style}>THREAD: {selectedThread}</h2>
              {stability ? (
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "4px 10px", marginBottom: 8,
                  border: `1px solid ${stabilityColor(stability.stability)}`,
                  fontSize: 11, letterSpacing: "0.5px",
                  fontFamily: "monospace",
                }}>
                  <span style={{
                    display: "inline-block", width: 8, height: 8, borderRadius: 4,
                    background: stabilityColor(stability.stability),
                  }} />
                  <span>{stabilityLabel(stability.stability)} · TSI {stability.tsi}/100</span>
                </div>
              ) : null}
              {!threadRecords || threadRecords.length === 0 ? (
                <div style={emptyStyle}>No records for this thread.</div>
              ) : (
                <ol style={{ paddingLeft: 16, margin: 0 }}>
                  {threadRecords.map((rec, i) => (
                    <li key={`${rec.timestamp}-${i}`} style={{ marginBottom: 8 }}>
                      <span style={{ fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(rec.timestamp)}
                      </span>
                      {" — "}
                      <span style={{ color: classColor(rec.result.analysis.ratio_classification) }}>
                        {rec.result.analysis.ratio_classification}
                      </span>
                      {" ("}
                      EL {rec.result.analysis.el_score.toFixed(2)}, INS{" "}
                      {rec.result.analysis.ins_score.toFixed(2)}
                      {")"}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ) : null}
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

// ---------- helpers ----------
function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return String(ts);
  }
}

function classColor(cls: string): string {
  if (cls === "high_el")  return "#ef4444";
  if (cls === "high_ins") return "#f59e0b";
  return "#10b981";
}

function stabilityColor(s: string): string {
  if (s === "stable") return "#10b981";
  if (s === "oscillating") return "#f59e0b";
  return "#ef4444";  // drifting_el | drifting_ins
}

function stabilityLabel(s: string): string {
  if (s === "stable")       return "STABLE";
  if (s === "oscillating")  return "OSCILLATING";
  if (s === "drifting_el")  return "DRIFTING EL";
  if (s === "drifting_ins") return "DRIFTING INS";
  return s.toUpperCase();
}

const _REASONING_LABELS: Record<string, string> = {
  grounding:              "Grounding",
  analysis:               "Analysis",
  structured_reflection:  "Structured Reflection",
  stabilization:          "Stabilization",
  extended_reasoning:     "Extended Reasoning",
  normal:                 "Normal",
};

function reasoningModeLabel(s: string): string {
  return _REASONING_LABELS[s] || s;
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---------- styles ----------
const containerStyle: React.CSSProperties = {
  flex: 1, padding: 24, overflowY: "auto",
  display: "flex", flexDirection: "column", gap: 16,
};
const panelStyle: React.CSSProperties = {
  background: "var(--color-bg-surface)", padding: 16,
};
const h1Style: React.CSSProperties = {
  margin: 0, fontSize: 18, color: "var(--color-text-primary)",
};
const h2Style: React.CSSProperties = {
  margin: "0 0 8px", fontSize: 14, color: "var(--color-text-primary)",
};
const mutedStyle: React.CSSProperties = {
  margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13,
};
const authedBadgeStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, letterSpacing: "0.5px",
};
const authedBadgeNameStyle: React.CSSProperties = {
  color: "var(--color-text-primary)", fontFamily: "var(--font-mono)",
};
const fieldLabel: React.CSSProperties = {
  display: "block", fontSize: 11, color: "var(--color-text-secondary)",
};
const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--color-bg-void)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text-primary)",
  padding: 6, fontFamily: "inherit",
};
const textareaStyle: React.CSSProperties = {
  ...inputStyle, fontFamily: "var(--font-mono)", resize: "vertical",
};
const btnPrimary: React.CSSProperties = {
  padding: "6px 16px", background: "var(--color-accent-cyan, #00f0ff)",
  border: "none", color: "#000", fontSize: 12, fontWeight: 700, cursor: "pointer",
};
const btnSecondary: React.CSSProperties = {
  padding: "6px 12px", background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer",
};
const tableStyle: React.CSSProperties = {
  width: "100%", borderCollapse: "collapse",
};
const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--color-text-secondary)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", verticalAlign: "middle", fontSize: 12,
  color: "var(--color-text-primary)",
};
const linkBtnStyle: React.CSSProperties = {
  background: "none", border: "none",
  color: "var(--color-accent-cyan, #00f0ff)",
  fontFamily: "monospace", fontSize: 11,
  cursor: "pointer", padding: 0, textDecoration: "underline",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};
const emptyStyle: React.CSSProperties = {
  color: "var(--color-text-secondary)", fontStyle: "italic",
};
const signOutContainerStyle: React.CSSProperties = {
  marginTop: "auto", padding: 10,
  borderTop: "1px solid rgba(255,255,255,0.15)",
  display: "flex", justifyContent: "flex-end",
};
const signOutBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)",
  padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0,
};
