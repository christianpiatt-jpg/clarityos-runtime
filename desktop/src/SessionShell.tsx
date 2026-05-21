// ClarityOS desktop — Operator session view (v62 / Unit 45).
//
// Mirrors web/src/routes/Session.tsx and phone/app/operator_session.tsx
// against the same /operator/session/{start,step} backend. Widescreen
// 2-column layout per the spec:
//
//   left column  — STATE + COMPOSE
//   right column — RUNTIME RESPONSE + MODEL RESPONSE
//
// Renders inside the v1 ClarityOSSurface via DesktopShell, matching
// the PersonalElinsShell / LibraryShell discipline (insights={null}
// so the v1 grid drops to two columns; sidebar only carries the
// Sign-out cap).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  clearSession,
  getUser,
  startSession,
  stepSession,
  type SessionIntentType,
  type SessionState,
  type SessionStepResult,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const RESUME_KEY = "clarityos_session_resume_id";
const INTENT_OPTIONS: SessionIntentType[] = [
  "query",
  "action",
  "plan",
  "diagnostic",
];

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function SessionShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [state, setState] = useState<SessionState | null>(null);
  const [lastStep, setLastStep] = useState<SessionStepResult | null>(null);
  const [text, setText] = useState("");
  const [intent, setIntent] = useState<SessionIntentType>("query");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operatorIdRef = useRef<string>("op_anon");

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const readResumeId = (): string | null => {
    try { return localStorage.getItem(RESUME_KEY); } catch { return null; }
  };
  const writeResumeId = (id: string | null): void => {
    try {
      if (id) localStorage.setItem(RESUME_KEY, id);
      else localStorage.removeItem(RESUME_KEY);
    } catch { /* noop */ }
  };

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError(null);
    const opId = userName || "op_anon";
    operatorIdRef.current = opId;
    try {
      const storedId = readResumeId();
      const r = storedId
        ? await startSession(opId, { resume: true, sessionId: storedId })
        : await startSession(opId);
      setState(r.session_state);
      writeResumeId(r.session_state.session_id);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [userName, handleAuthError]);

  useEffect(() => {
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSend = useCallback(async () => {
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
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setSending(false);
    }
  }, [state, text, intent, handleAuthError]);

  const handleNewSession = useCallback(async () => {
    writeResumeId(null);
    setState(null);
    setLastStep(null);
    setText("");
    setError(null);
    setLoading(true);
    try {
      const r = await startSession(operatorIdRef.current);
      setState(r.session_state);
      writeResumeId(r.session_state.session_id);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  const ui = lastStep?.runtime?.ui_response;
  const modelText = lastStep?.model?.response?.text;
  const severity = ui?.severity ?? null;

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Session"
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
            onClick={() => { clearSession(); onSignOut(); }}
            title="Clear the local session"
            style={signOutBtnStyle}
          >Sign out</button>
        </div>
      }
      center={
        <DesktopAuthGate onRequestSignIn={() => { clearSession(); onSignOut(); }}>
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          minWidth: 0,
        }}>
          {userName ? (
            <div style={authedBadgeStyle}>
              Authed as <span style={authedBadgeNameStyle}>{userName}</span>
            </div>
          ) : null}
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(320px, 1fr) minmax(320px, 1fr)",
            gap: 20,
            minWidth: 0,
          }}>
          {/* LEFT COLUMN */}
          <div style={colStyle}>
            <Panel title="STATE" action={
              <button
                type="button"
                onClick={() => void handleNewSession()}
                disabled={loading || sending}
                style={smallBtnStyle}
              >NEW SESSION</button>
            }>
              {loading && !state ? (
                <div style={mutedStyle}>Starting…</div>
              ) : state ? (
                <KvList rows={[
                  ["session_id", state.session_id, true],
                  ["history", `${state.history.length} step(s)`, false],
                ]} />
              ) : null}
              {error ? <div style={errBoxStyle}>{error}</div> : null}
            </Panel>

            <Panel title="COMPOSE">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. what should the operator do next?"
                rows={6}
                disabled={!state || sending}
                style={textareaStyle}
              />
              <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                {INTENT_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setIntent(opt)}
                    disabled={!state || sending}
                    style={opt === intent ? intentChipActiveStyle : intentChipStyle}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!state || sending || !text.trim()}
                style={primaryBtnStyle}
              >{sending ? "SENDING…" : "SEND"}</button>
            </Panel>
          </div>

          {/* RIGHT COLUMN */}
          <div style={colStyle}>
            <Panel title="RUNTIME RESPONSE">
              {!lastStep ? (
                <div style={mutedStyle}>No step taken yet.</div>
              ) : ui ? (
                <div style={{
                  borderLeft: `3px solid ${severityToColor(severity)}`,
                  paddingLeft: 12,
                  paddingTop: 6, paddingBottom: 6,
                }}>
                  <div style={{
                    color: severityToColor(severity),
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    marginBottom: 4,
                  }}>{ui.severity.toUpperCase()}</div>
                  <div style={{ fontWeight: 600 }}>{ui.headline}</div>
                  <div style={{ ...mutedStyle, marginTop: 4 }}>{ui.body}</div>
                  {ui.tags.length > 0 ? (
                    <div style={{
                      display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8,
                    }}>
                      {ui.tags.map((t) => (
                        <span key={t} style={tagStyle}>{t}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </Panel>

            <Panel title="MODEL RESPONSE">
              {!lastStep ? (
                <div style={mutedStyle}>No step taken yet.</div>
              ) : (
                <>
                  <KvList rows={[
                    ["model", lastStep.model.request.model_id, true],
                    ["provider", lastStep.model.metadata.provider, false],
                    ["mock", String(lastStep.model.metadata.mock), false],
                  ]} />
                  <pre style={preStyle}>{modelText || "(empty)"}</pre>
                </>
              )}
            </Panel>
          </div>
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

// ---------- helpers ----------
function severityToColor(severity: string | null): string {
  if (severity === "critical") return "#ef4444";
  if (severity === "warning")  return "#f59e0b";
  return "#10b981";
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in e.body) {
      const detail = (e.body as Record<string, unknown>).detail;
      if (typeof detail === "string") return detail;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---------- small layout primitives ----------
function Panel({
  title, action, children,
}: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={panelStyle}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 8,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.5px" }}>
          {title}
        </div>
        {action ?? null}
      </div>
      {children}
    </div>
  );
}

function KvList({ rows }: { rows: ReadonlyArray<readonly [string, string, boolean]> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", rowGap: 4, columnGap: 12 }}>
      {rows.map(([k, v, mono]) => (
        <>
          <div key={`k-${k}`} style={{ color: "var(--color-text-secondary, #888)", fontSize: 12 }}>{k}</div>
          <div
            key={`v-${k}`}
            style={{
              fontSize: 12,
              fontFamily: mono ? "var(--font-mono)" : undefined,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}
          >{v}</div>
        </>
      ))}
    </div>
  );
}

// ---------- inline styles (kept local; matches PersonalElinsShell pattern) ----------
const colStyle: React.CSSProperties = {
  display: "flex", flexDirection: "column", gap: 16, minWidth: 0,
};
const panelStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 4,
  padding: 16,
};
const mutedStyle: React.CSSProperties = {
  color: "var(--color-text-secondary, #888)",
  fontSize: 12,
};
const errBoxStyle: React.CSSProperties = {
  marginTop: 8,
  padding: 8,
  background: "#3a1414",
  border: "1px solid #5e1f1f",
  color: "#ff8a8a",
  fontSize: 12,
  borderRadius: 2,
};
const textareaStyle: React.CSSProperties = {
  width: "100%",
  background: "rgba(0,0,0,0.4)",
  color: "var(--color-text-primary, #fff)",
  border: "1px solid rgba(255,255,255,0.15)",
  padding: 8,
  fontFamily: "inherit",
  fontSize: 13,
  borderRadius: 2,
  resize: "vertical",
};
const intentChipStyle: React.CSSProperties = {
  background: "transparent",
  color: "var(--color-text-secondary, #888)",
  border: "1px solid rgba(255,255,255,0.15)",
  padding: "4px 10px",
  fontSize: 11,
  cursor: "pointer",
  borderRadius: 0,
};
const intentChipActiveStyle: React.CSSProperties = {
  ...intentChipStyle,
  background: "rgba(255,255,255,0.06)",
  color: "var(--color-text-primary, #fff)",
  borderColor: "var(--color-accent-cyan, #00F0FF)",
};
const primaryBtnStyle: React.CSSProperties = {
  marginTop: 10,
  width: "100%",
  background: "var(--color-accent-cyan, #00F0FF)",
  color: "#04121b",
  border: "none",
  padding: "8px 12px",
  fontWeight: 700,
  letterSpacing: "0.5px",
  cursor: "pointer",
  borderRadius: 2,
};
const smallBtnStyle: React.CSSProperties = {
  background: "transparent",
  color: "var(--color-text-secondary, #888)",
  border: "1px solid rgba(255,255,255,0.15)",
  padding: "4px 10px",
  fontSize: 11,
  cursor: "pointer",
  borderRadius: 0,
};
const signOutBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-text-secondary, #888)",
  color: "var(--color-text-secondary, #888)",
  padding: "4px 10px",
  fontSize: 11,
  cursor: "pointer",
  borderRadius: 0,
};
const tagStyle: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 10,
  padding: "2px 6px",
  background: "rgba(255,255,255,0.06)",
  color: "var(--color-text-secondary, #888)",
  borderRadius: 2,
};
const preStyle: React.CSSProperties = {
  margin: 0,
  marginTop: 8,
  padding: 12,
  background: "rgba(0,0,0,0.4)",
  whiteSpace: "pre-wrap",
  fontFamily: "var(--font-mono)",
  fontSize: 12,
  color: "var(--color-text-primary, #fff)",
  borderRadius: 2,
};
const authedBadgeStyle: React.CSSProperties = {
  color: "var(--color-text-secondary, #888)",
  fontSize: 11,
  letterSpacing: "0.5px",
};
const authedBadgeNameStyle: React.CSSProperties = {
  color: "var(--color-text-primary, #fff)",
  fontFamily: "var(--font-mono)",
};
