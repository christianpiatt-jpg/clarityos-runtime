// v80 — Regression-First packet runner (desktop).
//
// Operator pastes a cognitive packet, hits RUN, and gets back a
// persisted chain. The chain is seeded with one "unknown" layer
// (the last entry in the packet's regression_chain skeleton);
// timeline events are emitted server-side. The shell stays read-only
// after the run — operators continue to walk the chain via the v76
// /step / /tag endpoints when those surfaces land.

import { useCallback, useState } from "react";
import {
  ApiError,
  clearSession,
  getUser,
  postRegressionFirstPacket,
  replayRegressionFirstChain,
  type RegressionFirstChain,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

const EXAMPLE_PACKET = `{
  "EL": 2,
  "INS": 3,
  "ratio": "0.67",
  "el_signals": ["something is wrong"],
  "ins_signals": ["page", "scaffold"],
  "classification": "structure-dominant",
  "operator_intent": "Identify root cause of rendering failure.",
  "regression_required": true,
  "regression_chain": [
    {
      "layer": 1,
      "name": "Domain & Routing",
      "question": "Which page is set as homepage?",
      "location": "Settings → Reading → Homepage",
      "goal": "Correct page selected"
    }
  ],
  "recommended_system_action": "Pause and request operator verification."
}`;

export default function RegressionFirstShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [packetText, setPacketText] = useState<string>(EXAMPLE_PACKET);
  const [busy, setBusy] = useState(false);
  const [chain, setChain] = useState<RegressionFirstChain | null>(null);
  const [source, setSource] = useState<"packet" | "replay" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  const onRun = useCallback(async () => {
    setBusy(true); setError(null); setChain(null); setSource(null);
    let parsed: Record<string, unknown>;
    try {
      const raw = JSON.parse(packetText);
      if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
        throw new Error("packet must be a JSON object");
      }
      parsed = raw as Record<string, unknown>;
    } catch (e) {
      setError(`invalid_json: ${e instanceof Error ? e.message : String(e)}`);
      setBusy(false);
      return;
    }
    try {
      const result = await postRegressionFirstPacket(parsed);
      setChain(result);
      setSource("packet");
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      if (e instanceof ApiError) {
        setError(`${e.code}: ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }, [packetText, handleAuthError]);

  const onRerun = useCallback(async () => {
    if (!chain) return;
    const id = chain.chain_id;
    setBusy(true); setError(null);
    try {
      const result = await replayRegressionFirstChain(id);
      setChain(result);
      setSource("replay");
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      if (e instanceof ApiError) {
        setError(`${e.code}: ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  }, [chain, handleAuthError]);

  const seeded = chain && chain.layers.length > 0
    ? chain.layers[chain.layers.length - 1]
    : null;

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Regression First"
      insights={null}
      sidebar={<div style={signOutContainerStyle}>
        <button
          type="button"
          onClick={handleSignOut}
          style={signOutBtnStyle}
          data-testid="regression-first-signout"
        >
          Sign out
        </button>
      </div>}
      center={<DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>REGRESSION FIRST</h1>
            <p style={mutedStyle}>
              v80 packet runner. Drop a unified cognitive packet
              (EL/INS + regression_chain skeleton) and the kernel
              persists a chain with one seeded layer, emitting timeline
              events.
            </p>
            {userName && (
              <div style={authedBadgeStyle}>
                Authed as <span style={authedBadgeNameStyle}>{userName}</span>
              </div>
            )}
          </div>

          <div style={panelStyle}>
            <label htmlFor="rf-packet-editor" style={labelStyle}>
              Cognitive packet (JSON)
            </label>
            <textarea
              id="rf-packet-editor"
              data-testid="regression-first-packet-editor"
              value={packetText}
              onChange={(e) => setPacketText(e.target.value)}
              spellCheck={false}
              rows={16}
              style={editorStyle}
            />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button
                type="button"
                data-testid="regression-first-run"
                onClick={() => void onRun()}
                disabled={busy}
                style={busy ? btnPrimaryDisabled : btnPrimary}
              >
                {busy ? "Running…" : "RUN REGRESSION FIRST"}
              </button>
            </div>
            {error && (
              <div style={errorBannerStyle} data-testid="regression-first-error">
                {error}
              </div>
            )}
          </div>

          {chain && (
            <div style={panelStyle} data-testid="regression-first-summary">
              <h2 style={h2Style}>
                CHAIN {source === "replay" && (
                  <span style={replayBadgeStyle}>REPLAY</span>
                )}
              </h2>
              <div style={kvRowStyle}>
                <span style={kStyle}>Title</span>
                <span style={vStyle}>{chain.title}</span>
              </div>
              <div style={kvRowStyle}>
                <span style={kStyle}>Chain id</span>
                <code style={codeStyle}>{chain.chain_id}</code>
              </div>
              <div style={kvRowStyle}>
                <span style={kStyle}>State</span>
                <span style={vStyle}>
                  {chain.closed_at ? "closed" : "open"} · layers ={" "}
                  {chain.layers.length} · tags ={" "}
                  {Object.keys(chain.tags).length}
                </span>
              </div>
              {seeded && (
                <div style={kvRowStyle}>
                  <span style={kStyle}>Seeded layer</span>
                  <span style={vStyle}>
                    index {seeded.layer_index} · status{" "}
                    <code style={codeStyle}>{seeded.status}</code>
                  </span>
                </div>
              )}
              <button
                type="button"
                data-testid="regression-first-rerun"
                onClick={() => void onRerun()}
                disabled={busy}
                style={busy ? btnSecondaryDisabled : btnSecondary}
              >
                {busy ? "Running…" : "RERUN REGRESSION"}
              </button>
            </div>
          )}
        </div>
      </DesktopAuthGate>}
    />
  );
}

// ---------- styles (mirror OperatorTimelineShell conventions) ----------
const containerStyle: React.CSSProperties = {
  display: "flex", flexDirection: "column", gap: 16, padding: 16,
};
const panelStyle: React.CSSProperties = {
  border: "1px solid #333", padding: 16,
  background: "var(--os-deep, #0a0a0a)",
};
const h1Style: React.CSSProperties = {
  margin: 0, fontSize: 18, letterSpacing: 2, fontFamily: "ui-monospace, monospace",
};
const h2Style: React.CSSProperties = {
  margin: "0 0 12px", fontSize: 14, letterSpacing: 1.5,
  fontFamily: "ui-monospace, monospace",
};
const mutedStyle: React.CSSProperties = {
  marginTop: 8, color: "#999", fontSize: 13,
};
const labelStyle: React.CSSProperties = {
  display: "block", color: "#aaa", fontSize: 12, marginBottom: 6,
  letterSpacing: 1, textTransform: "uppercase",
};
const editorStyle: React.CSSProperties = {
  width: "100%",
  fontFamily: "ui-monospace, monospace",
  fontSize: 12,
  padding: 8,
  background: "#000",
  color: "#ddd",
  border: "1px solid #444",
  resize: "vertical",
  boxSizing: "border-box",
};
const btnPrimary: React.CSSProperties = {
  padding: "8px 16px",
  background: "var(--os-accent, #00F0FF)",
  color: "#000",
  border: "none",
  cursor: "pointer",
  fontWeight: 600,
  letterSpacing: 1.2,
  fontFamily: "ui-monospace, monospace",
};
const btnPrimaryDisabled: React.CSSProperties = {
  ...btnPrimary, opacity: 0.4, cursor: "wait",
};
const btnSecondary: React.CSSProperties = {
  padding: "6px 12px",
  background: "transparent",
  color: "var(--os-accent, #00F0FF)",
  border: "1px solid var(--os-accent, #00F0FF)",
  cursor: "pointer",
  fontFamily: "ui-monospace, monospace",
  fontSize: 11,
  letterSpacing: 1.2,
  marginTop: 12,
};
const btnSecondaryDisabled: React.CSSProperties = {
  ...btnSecondary, opacity: 0.4, cursor: "wait",
};
const replayBadgeStyle: React.CSSProperties = {
  marginLeft: 8,
  padding: "1px 6px",
  fontSize: 10,
  letterSpacing: 1.5,
  background: "var(--os-accent, #00F0FF)",
  color: "#000",
};
const errorBannerStyle: React.CSSProperties = {
  marginTop: 12, padding: 8,
  border: "1px solid var(--os-boundary, #E02020)",
  color: "var(--os-boundary, #E02020)",
  fontSize: 12, fontFamily: "ui-monospace, monospace",
};
const authedBadgeStyle: React.CSSProperties = {
  marginTop: 12, fontSize: 11, color: "#666",
  fontFamily: "ui-monospace, monospace",
};
const authedBadgeNameStyle: React.CSSProperties = {
  color: "var(--os-accent, #00F0FF)",
};
const kvRowStyle: React.CSSProperties = {
  display: "flex", gap: 12, marginBottom: 8, alignItems: "baseline",
};
const kStyle: React.CSSProperties = {
  color: "#888", fontSize: 11, letterSpacing: 1,
  textTransform: "uppercase", minWidth: 120,
};
const vStyle: React.CSSProperties = {
  color: "#ddd", fontSize: 13,
};
const codeStyle: React.CSSProperties = {
  fontFamily: "ui-monospace, monospace", color: "#ddd", fontSize: 12,
};
const signOutContainerStyle: React.CSSProperties = {
  padding: 16, borderTop: "1px solid #222",
};
const signOutBtnStyle: React.CSSProperties = {
  padding: "8px 12px",
  background: "transparent",
  color: "#ddd",
  border: "1px solid #444",
  cursor: "pointer",
  fontFamily: "ui-monospace, monospace",
  fontSize: 12, letterSpacing: 1,
};
