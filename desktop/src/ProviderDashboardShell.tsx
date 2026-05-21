// v68 / Unit 73 — Provider Dashboard (desktop).
//
// Unified view that joins /runtime/providers/{health, models, config}
// per the web mirror. Wrapped in DesktopAuthGate so mid-session 401s
// land the user on the inline CTA instead of bouncing to the full
// SignIn screen.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getProviderConfig,
  getProviderHealth,
  getProviderModels,
  getUser,
  type ProviderConfigResponse,
  type ProviderHealthResponse,
  type ProviderModelsResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DISPLAY_ORDER: readonly string[] = [
  "mock", "anthropic", "openai", "gemini", "xai", "local", "google",
] as const;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function ProviderDashboardShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [health, setHealth] = useState<ProviderHealthResponse | null>(null);
  const [models, setModels] = useState<ProviderModelsResponse | null>(null);
  const [config, setConfig] = useState<ProviderConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, m, c] = await Promise.all([
        getProviderHealth(),
        getProviderModels(),
        getProviderConfig(),
      ]);
      setHealth(h);
      setModels(m);
      setConfig(c);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const providers = (() => {
    const seen = new Set<string>();
    if (health) for (const k of Object.keys(health)) seen.add(k);
    if (models) for (const k of Object.keys(models.registry)) seen.add(k);
    if (config) for (const k of Object.keys(config.timeouts)) seen.add(k);
    const ordered: string[] = [];
    for (const k of DISPLAY_ORDER) if (seen.has(k)) ordered.push(k);
    for (const k of [...seen].sort()) if (!ordered.includes(k)) ordered.push(k);
    return ordered;
  })();

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Providers"
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
            <h1 style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>PROVIDER DASHBOARD</h1>
            <p style={{ margin: "4px 0 12px", color: "var(--color-text-secondary)", fontSize: 13 }}>
              Per-provider availability, model registry, and HTTP
              timeout configuration in one place.
            </p>
            {userName ? (
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 8, letterSpacing: "0.5px" }}>
                Authed as <span style={{ color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" }}>{userName}</span>
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <div style={{ flex: 1, fontSize: 12, color: "var(--color-text-secondary)" }}>
                {lastChecked ? `last checked ${lastChecked}` : ""}
              </div>
              <button
                type="button"
                onClick={() => void fetchAll()}
                disabled={loading}
                style={btnSecondary}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={{ background: "var(--color-bg-surface)", padding: 0 }}>
            {loading && !health ? (
              <div style={{ padding: 16 }}>Loading providers…</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                    <th style={thStyle}>Provider</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Call (s)</th>
                    <th style={thStyle}>Health (s)</th>
                    <th style={thStyle}>Retries</th>
                    <th style={thStyle}>Models</th>
                  </tr>
                </thead>
                <tbody>
                  {providers.map((name) => {
                    const h = health?.[name];
                    const t = config?.timeouts[name];
                    const r = config?.retries[name];
                    const m = models?.registry[name];
                    return (
                      <tr key={name} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                        <td style={{ ...tdStyle, fontFamily: "monospace" }}>{name}</td>
                        <td style={tdStyle}>
                          {h ? (
                            <span style={{ color: h.available ? "#10b981" : "#ef4444" }}>
                              {h.available ? "available" : "unavailable"}
                              {h.error ? (
                                <span style={mutedInline}> · {h.error}</span>
                              ) : null}
                            </span>
                          ) : (
                            <span style={{ color: "var(--color-text-secondary)" }}>—</span>
                          )}
                        </td>
                        <td style={tdStyle}>{t ? t.call : <span style={{ color: "var(--color-text-secondary)" }}>—</span>}</td>
                        <td style={tdStyle}>{t ? t.health : <span style={{ color: "var(--color-text-secondary)" }}>—</span>}</td>
                        <td style={tdStyle}>{r !== undefined ? r : <span style={{ color: "var(--color-text-secondary)" }}>—</span>}</td>
                        <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                          {m && m.length > 0 ? m.join(", ") : <span style={{ color: "var(--color-text-secondary)" }}>—</span>}
                        </td>
                      </tr>
                    );
                  })}
                  {config ? (
                    <tr style={{ borderTop: "2px solid rgba(255,255,255,0.15)" }}>
                      <td style={{ ...tdStyle, color: "var(--color-text-secondary)", fontStyle: "italic" }}>
                        (defaults)
                      </td>
                      <td style={{ ...tdStyle, color: "var(--color-text-secondary)" }}>—</td>
                      <td style={tdStyle}>{config.defaults.call_timeout}</td>
                      <td style={tdStyle}>{config.defaults.health_timeout}</td>
                      <td style={tdStyle}>{config.defaults.retries}</td>
                      <td style={{ ...tdStyle, color: "var(--color-text-secondary)" }}>—</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            )}
          </div>

          {models ? (
            <div style={{ background: "var(--color-bg-surface)", padding: 16 }}>
              <h2 style={{ margin: 0, marginBottom: 8, fontSize: 14, color: "var(--color-text-primary)" }}>
                SUPPORTED MODEL IDS
              </h2>
              <p style={{ margin: "0 0 8px", color: "var(--color-text-secondary)", fontSize: 12 }}>
                Flat allowlist consumed by <code>is_valid_model</code>.
                Includes the <code>auto</code> routing sentinel.
              </p>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {models.supported.map((m) => (
                  <li
                    key={m}
                    style={{
                      fontFamily: "monospace",
                      fontSize: 12,
                      padding: "3px 0",
                      color: "var(--color-text-primary)",
                    }}
                  >
                    {m}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "10px 12px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--color-text-secondary)",
};
const tdStyle: React.CSSProperties = {
  padding: "10px 12px", verticalAlign: "middle", fontSize: 12,
  color: "var(--color-text-primary)",
};
const btnSecondary: React.CSSProperties = {
  padding: "6px 12px", background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};
const mutedInline: React.CSSProperties = {
  color: "var(--color-text-secondary)",
  fontSize: 11,
  marginLeft: 6,
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
