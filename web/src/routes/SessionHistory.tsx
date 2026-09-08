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
//
// #147: entries also carry {model_id, mock} (optional on the wire --
// absent on rows written before #147). The row names the model that
// answered; see modelLabel below.

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  ApiError,
  getSessionDetail,
  getProfile,
  listOperatorSessions,
  type LoginSession,
  type SessionDetailResponse,
  type SessionHistoryEntry,
  type SessionSummary,
} from "../lib/api";
import { getAuthSnapshot, subscribeAuth } from "../lib/auth";

export default function SessionHistory() {
  // v64 / Unit 66 — operator_id is determined by the server from the
  // authed session, not by user input. C1 (2026-08-21): the badge shows
  // the profile's operator_id (never the account email, which the
  // engine rejects as an operator id).
  // C1 (2026-08-21): operator_id from the hydrated profile only — never
  // the account email (the engine rejects it). Effect guards on empty.
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  const operatorId = auth.profile?.operator_id ?? "";
  // #191 -- the caption names the MEMBER NUMBER beside the operator id
  // (the op_… id is the "login code" a member never chose); a number not
  // minted yet says so in words, never a dash or a zero.
  const memberNumber = auth.profile?.member_number ?? null;
  const authedAs = !operatorId
    ? "loading profile…"
    : `${memberNumber == null ? "member number not minted" : `member #${memberNumber}`} · operator ${operatorId}`;
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  // #191 -- the durable login rows the server lists beside the runtime
  // sessions (process memory on the service: empty after a cold start).
  const [loginSessions, setLoginSessions] = useState<LoginSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetailResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---- list -----------------------------------------------------------
  useEffect(() => {
    if (!operatorId) return;  // C1: do not fire until profile hydrates
    let cancelled = false;
    (async () => {
      setLoadingList(true);
      setError(null);
      try {
        const r = await listOperatorSessions(operatorId);
        if (cancelled) return;
        setSessions(r.sessions);
        setLoginSessions(r.login_sessions ?? []);
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
    // C1: re-read at call time, not mount-time.
    const op = getProfile()?.operator_id ?? "";
    if (!op) {
      setError("Profile still loading — try again in a moment.");
      return;
    }
    setSessions(null);
    setLoadingList(true);
    void (async () => {
      try {
        const r = await listOperatorSessions(op);
        setSessions(r.sessions);
        setLoginSessions(r.login_sessions ?? []);
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
            <span data-testid="authed-as" style={{ fontFamily: "var(--font-mono)" }} title="profile.member_number · profile.operator_id">{authedAs}</span>
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
          <div style={{ padding: 12, borderBottom: "1px solid var(--os-border, rgba(20, 24, 28, 0.08))" }}>
            <h2 style={{ margin: 0 }}>SESSIONS</h2>
          </div>
          {loadingList && !sessions ? (
            <div style={{ padding: 12 }}>
              <span className="spinner" /> Loading…
            </div>
          ) : sessions && sessions.length === 0 && loginSessions.length === 0 ? (
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
                          ? "var(--os-bg-elev, rgba(20, 24, 28, 0.05))"
                          : "transparent",
                      border: "none",
                      borderBottom: "1px solid var(--os-border, rgba(20, 24, 28, 0.05))",
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
          {/* #191 -- the durable login rows: a session REF (never the id),
              the member number at login, the turn, the seal stamp. */}
          {loginSessions.length > 0 ? (
            <div data-testid="login-sessions" style={{ padding: 12, borderTop: "1px solid var(--os-border, rgba(20, 24, 28, 0.08))" }}>
              <h2 style={{ margin: "0 0 6px" }}>LOGINS</h2>
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {loginSessions.map((l) => (
                  <li
                    key={l.session_ref}
                    className="muted"
                    style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", padding: "3px 0" }}
                    title="login_sessions[].session_ref · .current · .member_number · .turn · .ts_sealed"
                  >
                    {l.session_ref}{l.current ? " (this login)" : ""} ·{" "}
                    {l.member_number == null ? "member number not minted" : `member #${l.member_number}`} ·{" "}
                    turn {l.turn} · {l.ts_sealed == null ? "—" : new Date(l.ts_sealed * 1000).toISOString()}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
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
                background: "var(--os-bg-elev, rgba(20, 24, 28, 0.03))",
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
                <span>{modelLabel(entry)}</span>
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

// #147 -- the record names the model that answered. `engine` is the
// dispatcher's routing label, chosen BEFORE the call; the vault
// preference can replace the model, and "copilot" names no provider at
// all. So the row leads with model_id and shows the engine only when the
// two disagree. Rows written before #147 carry no model_id: they keep
// the old engine= label.
const ENGINE_PROVIDER: Record<string, string> = {
  claude: "anthropic",
  gemini: "google",
  grok:   "xai",
  local:  "local",
};

export function modelLabel(
  entry: Pick<SessionHistoryEntry, "engine" | "model_id" | "mock">,
): string {
  const id = entry.model_id;
  if (!id) return `engine=${entry.engine}`;
  const provider = id.includes(":") ? id.slice(0, id.indexOf(":")) : id;
  const mock = entry.mock ? " \u00b7 mock" : "";
  if (ENGINE_PROVIDER[entry.engine] === provider) return `model=${id}${mock}`;
  return `engine ${entry.engine} \u2192 routed ${id}${mock}`;
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

