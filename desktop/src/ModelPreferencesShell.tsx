// v64 / Unit 67 — Model preferences (desktop).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getModelPreferences,
  getUser,
  setModelPreferences,
  type ModelPreferencesResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const PROVIDERS: readonly string[] = [
  "anthropic", "openai", "gemini", "xai", "local",
] as const;

const DEFAULT_MODELS: Record<string, string> = {
  anthropic: "claude-3.7",
  openai:    "gpt-4.2",
  gemini:    "gemini-2.0",
  xai:       "groq-llama",
  local:     "llama3.1",
};

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function ModelPreferencesShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState(DEFAULT_MODELS.anthropic);
  const [current, setCurrent] = useState<ModelPreferencesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getModelPreferences();
      setCurrent(r);
      setProvider(r.provider);
      setModel(r.model);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void fetch(); }, [fetch]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSavedAt(null);
    try {
      const r = await setModelPreferences(provider, model);
      setCurrent(r);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setSaving(false);
    }
  }

  function pickProvider(next: string) {
    setProvider(next);
    setModel(DEFAULT_MODELS[next] || "");
  }

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Model"
      sidebar={
        <div style={{
          marginTop: "auto", padding: 10,
          borderTop: "1px solid rgba(255,255,255,0.15)",
          display: "flex", justifyContent: "flex-end",
        }}>
          <button
            type="button" onClick={handleSignOut}
            style={{
              background: "transparent",
              border: "1px solid var(--color-text-secondary)",
              color: "var(--color-text-secondary)",
              padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0,
            }}
          >Sign out</button>
        </div>
      }
      center={
        <DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={{ flex: 1, padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ padding: 16, background: "var(--color-bg-surface)" }}>
            <h1 style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>
              MODEL PREFERENCES
            </h1>
            <p style={{ margin: "4px 0 12px", color: "var(--color-text-secondary)", fontSize: 13 }}>
              Per-operator (provider, model) used by the runtime loop. Stored in the vault.
            </p>
            {userName ? (
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", letterSpacing: "0.5px" }}>
                Authed as <span style={{ color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" }}>{userName}</span>
              </div>
            ) : null}
          </div>

          <div style={{ background: "var(--color-bg-surface)", padding: 16 }}>
            <h2 style={panelHeading}>CURRENT</h2>
            {loading ? (
              <div>Loading…</div>
            ) : current ? (
              <div style={{ fontSize: 13 }}>
                <div><span style={kvLabel}>provider: </span>{current.provider}</div>
                <div><span style={kvLabel}>model: </span><span style={{ fontFamily: "monospace" }}>{current.model}</span></div>
                <div><span style={kvLabel}>source: </span>
                  {current.source === "vault" ? "explicit (vault)" : "default (chain)"}</div>
              </div>
            ) : (
              <div style={emptyStyle}>No preference loaded.</div>
            )}
          </div>

          <div style={{ background: "var(--color-bg-surface)", padding: 16 }}>
            <h2 style={panelHeading}>UPDATE</h2>
            <form onSubmit={save}>
              <label style={fieldLabel} htmlFor="pref-provider">Provider</label>
              <select
                id="pref-provider"
                value={provider}
                onChange={(e) => pickProvider(e.target.value)}
                disabled={saving}
                style={inputStyle}
              >
                {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>

              <label style={{ ...fieldLabel, marginTop: 8 }} htmlFor="pref-model">Model</label>
              <input
                id="pref-model"
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={saving}
                style={{ ...inputStyle, fontFamily: "monospace" }}
              />

              <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  type="submit"
                  disabled={saving || !model.trim()}
                  style={btnPrimary}
                >
                  {saving ? "SAVING…" : "SAVE"}
                </button>
                {savedAt ? (
                  <span style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>
                    saved at {savedAt}
                  </span>
                ) : null}
              </div>
            </form>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

const panelHeading: React.CSSProperties = { margin: "0 0 8px", fontSize: 14, color: "var(--color-text-primary)" };
const kvLabel: React.CSSProperties = { color: "var(--color-text-secondary)" };
const emptyStyle: React.CSSProperties = { color: "var(--color-text-secondary)", fontStyle: "italic" };
const fieldLabel: React.CSSProperties = { display: "block", fontSize: 11, color: "var(--color-text-secondary)" };
const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "var(--color-bg-void)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text-primary)",
  padding: 6,
};
const btnPrimary: React.CSSProperties = {
  padding: "6px 16px",
  background: "var(--color-accent-cyan, #00f0ff)",
  border: "none",
  color: "#000",
  fontSize: 12,
  fontWeight: 700,
  cursor: "pointer",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 12, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};

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
