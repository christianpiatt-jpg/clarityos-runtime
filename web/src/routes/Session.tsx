// Session — minimal operator UI surface.
//
// Calls /operator/session/start on mount and /operator/session/step
// on submit. Renders the runtime UI response (headline / body /
// severity / tags) plus the model response text. No persistence in
// the browser — the server-side runtime_persistence layer (Unit 42)
// handles state across requests. On reload, the route mints a new
// session unless a session_id is found in localStorage from a prior
// visit, in which case it tries to resume.

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getUser,
  startSession,
  stepSession,
  type SessionIntentType,
  type SessionState,
  type SessionStepResult,
} from "../lib/api";

const RESUME_KEY = "clarityos_session_resume_id";

const INTENT_OPTIONS: SessionIntentType[] = [
  "query",
  "action",
  "plan",
  "diagnostic",
];

export default function Session() {
  const [state, setState] = useState<SessionState | null>(null);
  const [lastStep, setLastStep] = useState<SessionStepResult | null>(null);
  const [text, setText] = useState("");
  const [intent, setIntent] = useState<SessionIntentType>("query");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operatorIdRef = useRef<string>("op_anon");

  // ---- Bootstrap ------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      const operatorId = getUser() || "op_anon";
      operatorIdRef.current = operatorId;
      try {
        let storedId: string | null = null;
        try {
          storedId = localStorage.getItem(RESUME_KEY);
        } catch {
          /* storage disabled */
        }
        const r = storedId
          ? await startSession(operatorId, {
              resume:    true,
              sessionId: storedId,
            })
          : await startSession(operatorId);
        if (cancelled) return;
        setState(r.session_state);
        try {
          localStorage.setItem(RESUME_KEY, r.session_state.session_id);
        } catch {
          /* noop */
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setError(formatError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ---- Submit one step -----------------------------------------------
  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!state) return;
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const r = await stepSession(state, text, intent);
      setState(r.session_state);
      setLastStep(r.step_result);
      setText("");
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setSending(false);
    }
  }

  function handleNewSession() {
    try {
      localStorage.removeItem(RESUME_KEY);
    } catch {
      /* noop */
    }
    setState(null);
    setLastStep(null);
    setText("");
    setError(null);
    setLoading(true);
    (async () => {
      try {
        const r = await startSession(operatorIdRef.current);
        setState(r.session_state);
        try {
          localStorage.setItem(RESUME_KEY, r.session_state.session_id);
        } catch {
          /* noop */
        }
      } catch (e: unknown) {
        setError(formatError(e));
      } finally {
        setLoading(false);
      }
    })();
  }

  // ---- Render ---------------------------------------------------------
  const ui = lastStep?.runtime?.ui_response;
  const modelText = lastStep?.model?.response?.text;
  const severityColor = ui ? severityToColor(ui.severity) : null;

  return (
    <div>
      <div className="panel">
        <h1>SESSION</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Operator runtime — one step per submit. Server holds vault +
          history; this page just renders the response. Reload resumes
          the most recent session from server-side storage.
        </p>
      </div>

      {/* Session metadata */}
      <div className="panel">
        <div className="row row-between" style={{ marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>STATE</h2>
          <button
            className="btn btn-sm btn-secondary"
            onClick={handleNewSession}
            disabled={loading || sending}
          >
            NEW SESSION
          </button>
        </div>
        {loading && !state ? (
          <div><span className="spinner" /> Starting…</div>
        ) : state ? (
          <div className="kv">
            <div className="k">session_id</div>
            <div className="v" style={{ fontFamily: "var(--font-mono)" }}>
              {state.session_id}
            </div>
            <div className="k">operator_id</div>
            <div className="v">{state.operator_id}</div>
            <div className="k">history</div>
            <div className="v">{state.history.length} step(s)</div>
          </div>
        ) : null}
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }}>{error}</div>
        ) : null}
      </div>

      {/* Compose */}
      <div className="panel">
        <h2>COMPOSE</h2>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="session-text">Text</label>
            <textarea
              id="session-text"
              className="input"
              rows={3}
              placeholder="e.g. what should the operator do next?"
              value={text}
              onChange={(ev) => setText(ev.target.value)}
              disabled={sending || !state}
            />
          </div>
          <div className="row" style={{ marginTop: 8, gap: 8 }}>
            <div className="field" style={{ flex: 0 }}>
              <label htmlFor="session-intent">Intent</label>
              <select
                id="session-intent"
                className="input"
                value={intent}
                onChange={(ev) =>
                  setIntent(ev.target.value as SessionIntentType)
                }
                disabled={sending || !state}
              >
                {INTENT_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1 }} />
            <button
              type="submit"
              className="btn"
              disabled={sending || !state || !text.trim()}
            >
              {sending ? "SENDING…" : "SEND"}
            </button>
          </div>
        </form>
      </div>

      {/* Runtime UI response */}
      <div className="panel">
        <h2>RUNTIME RESPONSE</h2>
        {!lastStep ? (
          <div className="empty">No step taken yet.</div>
        ) : ui ? (
          <>
            <div
              style={{
                padding: "8px 12px",
                marginBottom: 12,
                borderLeft: `3px solid ${severityColor}`,
                background: "var(--os-bg-elev, rgba(255,255,255,0.04))",
              }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.75rem",
                  color: severityColor || undefined,
                  marginBottom: 4,
                }}
              >
                {ui.severity.toUpperCase()}
              </div>
              <div style={{ fontWeight: 600 }}>{ui.headline}</div>
              <div style={{ marginTop: 4 }} className="muted">{ui.body}</div>
              {ui.tags.length > 0 ? (
                <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {ui.tags.map((tag) => (
                    <span
                      key={tag}
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.7rem",
                        padding: "2px 6px",
                        background: "rgba(255,255,255,0.08)",
                        borderRadius: 2,
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </div>

      {/* Model response */}
      <div className="panel">
        <h2>MODEL RESPONSE</h2>
        {!lastStep ? (
          <div className="empty">No step taken yet.</div>
        ) : (
          <>
            <div className="kv" style={{ marginBottom: 8 }}>
              <div className="k">model</div>
              <div className="v" style={{ fontFamily: "var(--font-mono)" }}>
                {lastStep.model.request.model_id}
              </div>
              <div className="k">provider</div>
              <div className="v">{lastStep.model.metadata.provider}</div>
              <div className="k">mock</div>
              <div className="v">{String(lastStep.model.metadata.mock)}</div>
            </div>
            <pre
              style={{
                margin: 0,
                padding: 12,
                background: "var(--os-bg-elev, rgba(255,255,255,0.04))",
                whiteSpace: "pre-wrap",
                fontFamily: "var(--font-mono)",
                fontSize: "0.85rem",
              }}
            >{modelText || "(empty)"}</pre>
          </>
        )}
      </div>
    </div>
  );
}

function severityToColor(severity: string): string {
  if (severity === "critical") return "var(--os-err, #ef4444)";
  if (severity === "warning")  return "var(--os-warn, #f59e0b)";
  return "var(--os-ok, #10b981)";
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const detail = (e.body as Record<string, unknown>).detail;
      if (typeof detail === "string") return detail;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
