// v65 / Unit 69 — Provider health dashboard (desktop).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getProviderHealth,
  getUser,
  type ProviderHealthResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DISPLAY_ORDER: readonly string[] = [
  "mock", "anthropic", "openai", "gemini",
] as const;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function ProviderHealthShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [data, setData] = useState<ProviderHealthResponse | null>(null);
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

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getProviderHealth();
      setData(r);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void fetchHealth(); }, [fetchHealth]);

  const sortedKeys = (() => {
    if (!data) return [] as string[];
    const ordered: string[] = [];
    for (const k of DISPLAY_ORDER) {
      if (k in data) ordered.push(k);
    }
    for (const k of Object.keys(data).sort()) {
      if (!ordered.includes(k)) ordered.push(k);
    }
    return ordered;
  })();

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Provider Health"
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
            <h1 style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>PROVIDER HEALTH</h1>
            <p style={{ margin: "4px 0 12px", color: "var(--color-text-secondary)", fontSize: 13 }}>
              Lightweight reachability check for each LLM provider. Real
              providers issue a 1-token completion (3-second timeout);
              the <code>mock</code> entry is the always-available
              deterministic fallback.
            </p>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <div style={{ flex: 1, fontSize: 12, color: "var(--color-text-secondary)" }}>
                {lastChecked ? `last checked ${lastChecked}` : ""}
              </div>
              <button
                type="button"
                onClick={() => void fetchHealth()}
                disabled={loading}
                style={btnSecondary}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={{ background: "var(--color-bg-surface)", padding: 0 }}>
            {loading && !data ? (
              <div style={{ padding: 16 }}>Probing providers…</div>
            ) : !data ? (
              <div style={{ ...emptyStyle, padding: 16 }}>No data.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                    <th style={thStyle}>Provider</th>
                    <th style={thStyle}>Status</th>
                    <th style={thStyle}>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedKeys.map((name) => {
                    const entry = data[name];
                    return (
                      <tr
                        key={name}
                        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                      >
                        <td style={{ ...tdStyle, fontFamily: "monospace" }}>{name}</td>
                        <td style={tdStyle}>
                          <span
                            aria-label={entry.available ? "available" : "unavailable"}
                            style={{
                              display: "inline-block",
                              width: 10, height: 10, borderRadius: "50%",
                              marginRight: 8,
                              background: entry.available ? "#10b981" : "#ef4444",
                            }}
                          />
                          <span style={{ color: entry.available ? "#10b981" : "#ef4444" }}>
                            {entry.available ? "available" : "unavailable"}
                          </span>
                        </td>
                        <td style={{
                          ...tdStyle,
                          color: "var(--color-text-secondary)",
                          fontFamily: "monospace",
                          fontSize: 12,
                        }}>
                          {entry.error || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "10px 12px", fontWeight: 600,
  fontSize: 12, color: "var(--color-text-secondary)",
};
const tdStyle: React.CSSProperties = { padding: "10px 12px", verticalAlign: "middle" };
const btnSecondary: React.CSSProperties = {
  padding: "6px 12px", background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};
const emptyStyle: React.CSSProperties = { color: "var(--color-text-secondary)", fontStyle: "italic" };

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
