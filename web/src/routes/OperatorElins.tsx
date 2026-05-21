// v69 / Unit 74 — Per-operator EL/INS dashboard.
//
// Three panels:
//   1. ANALYZE — quick textarea + provider_mode picker + analyze button.
//      Optional thread_id field; when set, the result is stored.
//   2. RECENT — last 100 records for the authed operator, newest-first.
//      Columns: timestamp, thread_id, classification, EL, INS, mode.
//   3. SELECTED THREAD — when a record's thread is clicked, shows the
//      full history for that thread (single-thread drill-down).
//
// Auth-gated via RequireAuth at the App.tsx route layer.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getElInsRecent,
  getElInsThread,
  getElInsThreadStability,
  postElInsAnalyze,
  type ElInsProviderMode,
  type ElInsRecord,
  type ElInsThreadStabilityResponse,
} from "../lib/api";

const PROVIDER_MODES: readonly ElInsProviderMode[] = [
  "auto", "llm", "deterministic",
] as const;

export default function OperatorElins() {
  // Analyze panel state
  const [text, setText] = useState("");
  const [mode, setMode] = useState<ElInsProviderMode>("auto");
  const [analyzeThreadId, setAnalyzeThreadId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  // Recent list state
  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);

  // Selected-thread drill-down state
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [threadRecords, setThreadRecords] = useState<ElInsRecord[] | null>(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [threadError, setThreadError] = useState<string | null>(null);
  // v70 / Unit 76 — stability badge for the selected thread
  const [stability, setStability] = useState<ElInsThreadStabilityResponse | null>(null);

  const fetchRecent = useCallback(async () => {
    setLoadingRecent(true);
    setRecentError(null);
    try {
      const r = await getElInsRecent(100);
      setRecords(r.records);
    } catch (e: unknown) {
      setRecentError(formatError(e));
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  useEffect(() => { void fetchRecent(); }, [fetchRecent]);

  const fetchThread = useCallback(async (tid: string) => {
    setLoadingThread(true);
    setThreadError(null);
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
      setThreadError(formatError(e));
    } finally {
      setLoadingThread(false);
    }
  }, []);

  async function handleAnalyze(e: React.FormEvent) {
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
      setAnalyzeError(formatError(err));
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <h1>EL/INS DASHBOARD</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Reasoning-stability diagnostic. Analyses are stored under the
          authed operator, keyed by thread_id when provided. The cockpit
          indicator reads the most recent record for the operator.
        </p>
      </div>

      {/* Analyze */}
      <div className="panel">
        <h2>ANALYZE</h2>
        <form onSubmit={handleAnalyze}>
          <div className="field">
            <label htmlFor="el-text">Text</label>
            <textarea
              id="el-text"
              className="input"
              rows={4}
              placeholder="Paste or type the text to score…"
              value={text}
              onChange={(ev) => setText(ev.target.value)}
              disabled={analyzing}
              data-testid="el-ins-text"
            />
          </div>
          <div className="row" style={{ marginTop: 8, gap: 12, alignItems: "flex-end" }}>
            <div className="field" style={{ flex: 0 }}>
              <label htmlFor="el-mode">Provider mode</label>
              <select
                id="el-mode"
                className="input"
                value={mode}
                onChange={(ev) => setMode(ev.target.value as ElInsProviderMode)}
                disabled={analyzing}
              >
                {PROVIDER_MODES.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="el-thread">Thread id (optional — to persist)</label>
              <input
                id="el-thread"
                className="input"
                placeholder="(no thread)"
                value={analyzeThreadId}
                onChange={(ev) => setAnalyzeThreadId(ev.target.value)}
                disabled={analyzing}
                data-testid="el-ins-thread-id"
              />
            </div>
            <button
              type="submit"
              className="btn"
              disabled={analyzing || !text.trim()}
              data-testid="el-ins-analyze"
            >
              {analyzing ? "ANALYZING…" : "ANALYZE"}
            </button>
          </div>
        </form>
        {analyzeError ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-analyze-error">
            {analyzeError}
          </div>
        ) : null}
      </div>

      {/* Recent records */}
      <div className="panel">
        <div className="row row-between" style={{ marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>RECENT</h2>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void fetchRecent()}
            disabled={loadingRecent}
            data-testid="el-ins-refresh"
          >
            REFRESH
          </button>
        </div>
        {loadingRecent && !records ? (
          <div><span className="spinner" /> Loading…</div>
        ) : recentError ? (
          <div className="banner err" data-testid="el-ins-recent-error">{recentError}</div>
        ) : !records || records.length === 0 ? (
          <div className="empty">No EL/INS records yet for this operator.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-recent-table">
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
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(rec.timestamp)}
                  </td>
                  <td style={tdStyle}>
                    {rec.thread_id ? (
                      <button
                        type="button"
                        className="link"
                        onClick={() => void fetchThread(rec.thread_id as string)}
                        style={{
                          background: "none", border: "none",
                          color: "var(--os-accent, #00f0ff)",
                          fontFamily: "var(--font-mono)", fontSize: 11,
                          cursor: "pointer", padding: 0,
                        }}
                      >
                        {rec.thread_id}
                      </button>
                    ) : (
                      <span className="muted">—</span>
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

      {/* Per-thread drill-down */}
      {selectedThread ? (
        <div className="panel">
          <h2>THREAD: {selectedThread}</h2>
          {stability ? (
            <div
              data-testid="el-ins-stability-badge"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 10px",
                marginBottom: 8,
                border: `1px solid ${stabilityColor(stability.stability)}`,
                borderRadius: 2,
                fontSize: 11,
                letterSpacing: "0.5px",
              }}
              title={`window: ${stability.window} sample(s)`}
            >
              <span style={{
                display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                background: stabilityColor(stability.stability),
              }} />
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {stabilityLabel(stability.stability)} · TSI {stability.tsi}/100
              </span>
            </div>
          ) : null}
          {loadingThread ? (
            <div><span className="spinner" /> Loading thread…</div>
          ) : threadError ? (
            <div className="banner err" data-testid="el-ins-thread-error">{threadError}</div>
          ) : !threadRecords || threadRecords.length === 0 ? (
            <div className="empty">No records for this thread.</div>
          ) : (
            <ol data-testid="el-ins-thread-list" style={{ paddingLeft: 16, margin: 0 }}>
              {threadRecords.map((rec, i) => (
                <li key={`${rec.timestamp}-${i}`} style={{ marginBottom: 8 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
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
                  {rec.result.stability_notes ? (
                    <div className="muted" style={{ fontSize: 11 }}>{rec.result.stability_notes}</div>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </div>
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
  if (cls === "high_el")  return "var(--os-err, #ef4444)";
  if (cls === "high_ins") return "var(--os-warn, #f59e0b)";
  return "var(--os-ok, #10b981)";
}

function stabilityColor(s: string): string {
  if (s === "stable") return "var(--os-ok, #10b981)";
  if (s === "oscillating") return "var(--os-warn, #f59e0b)";
  return "var(--os-err, #ef4444)";  // drifting_el | drifting_ins
}

function stabilityLabel(s: string): string {
  if (s === "stable")       return "STABLE";
  if (s === "oscillating")  return "OSCILLATING";
  if (s === "drifting_el")  return "DRIFTING EL";
  if (s === "drifting_ins") return "DRIFTING INS";
  return s.toUpperCase();
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

const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--os-text-muted, #888)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", verticalAlign: "middle", fontSize: 12,
};
