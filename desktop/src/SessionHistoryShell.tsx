// ClarityOS desktop — Session history viewer (v63 / Unit 47).
//
// Mirrors web/src/routes/SessionHistory.tsx and
// phone/app/operator_session_history.tsx against the same
// /operator/sessions + /operator/session/{id} GETs. Widescreen
// 2-column grid: sessions list left, selected detail right.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getSessionDetail,
  getUser,
  listOperatorSessions,
  type SessionDetailResponse,
  type SessionSummary,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function SessionHistoryShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  // v68/Unit 72 — operator_id state removed; server uses authed identity
  // (since v64/Unit 66). We still hand a string to listOperatorSessions
  // for client-side logging clarity, but the backend ignores it.
  const operatorId = userName || "";
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetailResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const fetchList = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const r = await listOperatorSessions(operatorId);
      setSessions(r.sessions);
      if (r.sessions.length > 0 && selectedId === null) {
        setSelectedId(r.sessions[0].session_id);
      }
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoadingList(false);
    }
  }, [operatorId, selectedId, handleAuthError]);

  useEffect(() => {
    void fetchList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operatorId]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    (async () => {
      setLoadingDetail(true);
      try {
        const r = await getSessionDetail(selectedId);
        if (!cancelled) setDetail(r);
      } catch (e: unknown) {
        if (cancelled) return;
        if (handleAuthError(e)) return;
        setError(formatError(e));
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedId, handleAuthError]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="History"
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
            onClick={handleSignOut}
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
        <DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={{ flex: 1, padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
          <div style={{ padding: 16, background: "var(--color-bg-surface)" }}>
            <h1 style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>SESSION HISTORY</h1>
            <p style={{ margin: "4px 0 12px", color: "var(--color-text-secondary)", fontSize: 13 }}>
              Read-only inspector over past operator sessions.
            </p>
            {userName ? (
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 8, letterSpacing: "0.5px" }}>
                Authed as <span style={{ color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" }}>{userName}</span>
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
              <button
                type="button"
                onClick={() => void fetchList()}
                disabled={loadingList}
                style={btnSecondaryStyle}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 320px) 1fr", gap: 16, flex: 1, minHeight: 0 }}>
            {/* LIST */}
            <div style={{ background: "var(--color-bg-surface)", padding: 16, overflowY: "auto" }}>
              <h2 style={panelHeadingStyle}>SESSIONS</h2>
              {loadingList && !sessions ? (
                <div style={{ color: "var(--color-text-secondary)" }}>Loading…</div>
              ) : sessions && sessions.length === 0 ? (
                <div style={emptyStyle}>No sessions for this operator.</div>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {(sessions || []).map((s) => (
                    <li key={s.session_id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(s.session_id)}
                        style={{
                          display: "block",
                          width: "100%",
                          textAlign: "left",
                          padding: "8px 10px",
                          background: selectedId === s.session_id
                            ? "rgba(255,255,255,0.06)"
                            : "transparent",
                          border: "none",
                          borderBottom: "1px solid rgba(255,255,255,0.05)",
                          color: "var(--color-text-primary)",
                          cursor: "pointer",
                        }}
                      >
                        <div style={{ fontFamily: "monospace", fontSize: 12 }}>{s.session_id}</div>
                        <div style={{ color: "var(--color-text-secondary)", fontSize: 11, marginTop: 2 }}>
                          {s.history_len} step(s) · {s.timestamp || "no activity"}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* DETAIL */}
            <div style={{ background: "var(--color-bg-surface)", padding: 16, overflowY: "auto" }}>
              {!selectedId ? (
                <div style={emptyStyle}>Select a session on the left.</div>
              ) : loadingDetail ? (
                <div>Loading detail…</div>
              ) : !detail ? (
                <div style={emptyStyle}>No detail available.</div>
              ) : (
                <DetailView detail={detail} />
              )}
            </div>
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

function DetailView({ detail }: { detail: SessionDetailResponse }) {
  const state = detail.session_state;
  return (
    <div>
      <div style={{ marginBottom: 12, fontSize: 12 }}>
        <div><span style={{ color: "var(--color-text-secondary)" }}>session_id: </span><span style={{ fontFamily: "monospace" }}>{state.session_id}</span></div>
        <div><span style={{ color: "var(--color-text-secondary)" }}>history: </span>{state.history.length} step(s)</div>
      </div>
      <h2 style={panelHeadingStyle}>STEPS</h2>
      {state.history.length === 0 ? (
        <div style={emptyStyle}>No steps in this session yet.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {state.history.map((entry, i) => (
            <div
              key={`${entry.timestamp}-${i}`}
              style={{
                padding: 10,
                borderLeft: `3px solid ${decisionColor(entry.runtime_decision)}`,
                background: "rgba(255,255,255,0.03)",
              }}
            >
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontFamily: "monospace", fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>
                <span>#{i + 1}</span>
                <span>{entry.timestamp}</span>
                <span>intent={entry.intent_type}</span>
                <span>engine={entry.engine}</span>
                <span style={{ color: decisionColor(entry.runtime_decision) }}>
                  {entry.runtime_decision.toUpperCase()}
                </span>
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{entry.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const btnSecondaryStyle: React.CSSProperties = {
  padding: "6px 12px",
  background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)",
  fontSize: 12,
  cursor: "pointer",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8,
  padding: 8,
  background: "rgba(239,68,68,0.12)",
  color: "#ef4444",
  fontSize: 12,
};
const panelHeadingStyle: React.CSSProperties = { margin: "0 0 8px", fontSize: 14, color: "var(--color-text-primary)" };
const emptyStyle: React.CSSProperties = { color: "var(--color-text-secondary)", fontStyle: "italic" };

function decisionColor(decision: string): string {
  if (decision === "block") return "#ef4444";
  if (decision === "warn")  return "#f59e0b";
  return "#10b981";
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
