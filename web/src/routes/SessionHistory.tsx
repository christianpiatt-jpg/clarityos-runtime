// SessionHistory — read-only viewer over /operator/sessions +
// /operator/session/{id}.
//
// Left column: list of past sessions for the current operator
// (id + last-step timestamp + history length).
// Right column: detail view of the selected session, including every
// history entry with its intent / text / decision / engine /
// timestamp. No mutation.
//
// v59-locked history field names: {timestamp, intent_type, text,
// runtime_decision, engine} — the spec called for {input, intent,
// runtime_response, model_response} but those would require breaking
// the v59 lock that 7 versions of tests depend on. The UI labels map
// the v59 names to operator-friendly text instead.

import { useEffect, useState } from "react";
import {
  ApiError,
  getSessionDetail,
  getUser,
  listOperatorSessions,
  type SessionDetailResponse,
  type SessionSummary,
} from "../lib/api";

export default function SessionHistory() {
  // v64 / Unit 66 — operator_id is determined by the server from the
  // authed session, not by user input. We still show getUser() as a
  // read-only "authed as" badge so the user can see whose history
  // they're inspecting.
  const operatorId = getUser() || "(not signed in)";
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetailResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---- list -----------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingList(true);
      setError(null);
      try {
        const r = await listOperatorSessions(operatorId);
        if (cancelled) return;
        setSessions(r.sessions);
        // Auto-select first (newest) if none selected.
        if (r.sessions.length > 0 && selectedId === null) {
          setSelectedId(r.sessions[0].session_id);
        } else if (r.sessions.length === 0) {
          setSelectedId(null);
          setDetail(null);
        }
      } catch (e: unknown) {
        if (!cancelled) setError(formatError(e));
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    })();
    return () => { cancelled = true; };
  }, [operatorId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- detail ---------------------------------------------------------
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoadingDetail(true);
      setError(null);
      try {
        const r = await getSessionDetail(selectedId);
        if (!cancelled) setDetail(r);
      } catch (e: unknown) {
        if (!cancelled) setError(formatError(e));
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedId]);

  function refresh() {
    setSessions(null);
    setLoadingList(true);
    void (async () => {
      try {
        const r = await listOperatorSessions(operatorId);
        setSessions(r.sessions);
      } catch (e: unknown) {
        setError(formatError(e));
      } finally {
        setLoadingList(false);
      }
    })();
  }

  return (
    <div>
      <div className="panel">
        <h1>SESSION HISTORY</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Read-only inspector over past operator sessions. The server
          holds vault + history; this view paginates through them.
        </p>
        <div className="row" style={{ marginTop: 12, gap: 8, alignItems: "center" }}>
          <div style={{ flex: 1, fontSize: "0.85rem" }}>
            <span className="muted">authed as </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>{operatorId}</span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={refresh}
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }}>{error}</div>
        ) : null}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(240px, 320px) 1fr",
          gap: 12,
          alignItems: "start",
        }}
      >
        {/* LIST */}
        <div className="panel" style={{ padding: 0 }}>
          <div style={{ padding: 12, borderBottom: "1px solid var(--os-border, rgba(255,255,255,0.1))" }}>
            <h2 style={{ margin: 0 }}>SESSIONS</h2>
          </div>
          {loadingList && !sessions ? (
            <div style={{ padding: 12 }}>
              <span className="spinner" /> Loading…
            </div>
          ) : sessions && sessions.length === 0 ? (
            <div className="empty" style={{ padding: 12 }}>
              No sessions for this operator.
            </div>
          ) : (
            <ul
              style={{
                listStyle: "none",
                margin: 0,
                padding: 0,
                maxHeight: "70vh",
                overflowY: "auto",
              }}
            >
              {(sessions || []).map((s) => (
                <li key={s.session_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(s.session_id)}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      padding: "10px 12px",
                      background:
                        selectedId === s.session_id
                          ? "var(--os-bg-elev, rgba(255,255,255,0.06))"
                          : "transparent",
                      border: "none",
                      borderBottom: "1px solid var(--os-border, rgba(255,255,255,0.05))",
                      color: "inherit",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                      {s.session_id}
                    </div>
                    <div className="muted" style={{ marginTop: 2, fontSize: "0.75rem" }}>
                      {s.history_len} step(s) · {s.timestamp || "no activity"}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* DETAIL */}
        <div className="panel">
          {!selectedId ? (
            <div className="empty">Select a session on the left.</div>
          ) : loadingDetail ? (
            <div><span className="spinner" /> Loading detail…</div>
          ) : !detail ? (
            <div className="empty">No detail available.</div>
          ) : (
            <SessionDetailPanel detail={detail} />
          )}
        </div>
      </div>
    </div>
  );
}

function SessionDetailPanel({ detail }: { detail: SessionDetailResponse }) {
  const state = detail.session_state;
  return (
    <div>
      <div className="kv" style={{ marginBottom: 12 }}>
        <div className="k">session_id</div>
        <div className="v" style={{ fontFamily: "var(--font-mono)" }}>
          {state.session_id}
        </div>
        <div className="k">operator_id</div>
        <div className="v">{state.operator_id}</div>
        <div className="k">history</div>
        <div className="v">{state.history.length} step(s)</div>
      </div>

      <h2 style={{ margin: "12px 0 8px" }}>STEPS</h2>
      {state.history.length === 0 ? (
        <div className="empty">No steps in this session yet.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {state.history.map((entry, i) => (
            <div
              key={`${entry.timestamp}-${i}`}
              style={{
                padding: 10,
                borderLeft: `3px solid ${decisionColor(entry.runtime_decision)}`,
                background: "var(--os-bg-elev, rgba(255,255,255,0.03))",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  flexWrap: "wrap",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.75rem",
                  color: "var(--os-text-secondary, #888)",
                  marginBottom: 6,
                }}
              >
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

function decisionColor(decision: string): string {
  if (decision === "block") return "var(--os-err, #ef4444)";
  if (decision === "warn")  return "var(--os-warn, #f59e0b)";
  return "var(--os-ok, #10b981)";
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

