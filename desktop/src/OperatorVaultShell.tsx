// ClarityOS desktop — Operator vault inspector (v63 / Unit 48).
//
// Mirrors web/src/routes/OperatorVault.tsx. Single-pane widescreen
// layout: operator-id input + REFRESH + JSON tree viewer.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getOperatorVault,
  getUser,
  type VaultInspectorResponse,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorVaultShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  // v68/Unit 72 — operator_id state removed; backend ignores it and
  // uses the authed identity (since v64/Unit 66).
  const operatorId = userName || "";
  const [data, setData] = useState<VaultInspectorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const r = await getOperatorVault(operatorId);
      setData(r);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [operatorId, handleAuthError]);

  useEffect(() => {
    void fetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operatorId]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Operator Vault"
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
            <h1 style={{ margin: 0, fontSize: 18, color: "var(--color-text-primary)" }}>OPERATOR VAULT</h1>
            <p style={{ margin: "4px 0 12px", color: "var(--color-text-secondary)", fontSize: 13 }}>
              Read-only snapshot of the runtime vault. Distinct from
              the legacy storage-layer vault — this is the ELINS
              long-arc state that session_loop persists between steps.
            </p>
            {userName ? (
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 8, letterSpacing: "0.5px" }}>
                Authed as <span style={{ color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" }}>{userName}</span>
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
              <button
                type="button"
                onClick={() => void fetch()}
                disabled={loading}
                style={btnSecondaryStyle}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={{ background: "var(--color-bg-surface)", padding: 16, flex: 1, overflowY: "auto", minHeight: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <h2 style={panelHeadingStyle}>VAULT</h2>
              <span style={{ color: "var(--color-text-secondary)", fontFamily: "monospace", fontSize: 11 }}>
                {data?.last_updated ? `updated ${data.last_updated}` : "never updated"}
              </span>
            </div>
            {loading ? (
              <div>Loading…</div>
            ) : !data || data.vault === null ? (
              <div style={emptyStyle}>
                No vault recorded for this operator yet. Run a /session
                step to populate.
              </div>
            ) : (
              <JsonTree value={data.vault} depth={0} />
            )}
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
  );
}

// ---- Recursive collapsible JSON viewer ----
interface JsonTreeProps {
  value:  unknown;
  depth:  number;
  label?: string;
}

function JsonTree({ value, depth, label }: JsonTreeProps) {
  const pad = depth * 16;
  const labelEl = label !== undefined ? (
    <span style={{ color: "var(--color-text-secondary)" }}>{label}: </span>
  ) : null;

  if (value === null) {
    return <div style={{ marginLeft: pad, fontFamily: "monospace" }}>{labelEl}<span style={{ color: "#f59e0b" }}>null</span></div>;
  }
  if (typeof value === "string") {
    return <div style={{ marginLeft: pad, fontFamily: "monospace" }}>{labelEl}<span style={{ color: "#10b981" }}>"{value}"</span></div>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <div style={{ marginLeft: pad, fontFamily: "monospace" }}>{labelEl}<span style={{ color: "#00f0ff" }}>{String(value)}</span></div>;
  }
  if (Array.isArray(value)) return <ArrayNode value={value} depth={depth} label={label} />;
  if (typeof value === "object") return <ObjectNode value={value as Record<string, unknown>} depth={depth} label={label} />;
  return <div style={{ marginLeft: pad }}>{labelEl}<span>{String(value)}</span></div>;
}

function ObjectNode({ value, depth, label }: { value: Record<string, unknown>; depth: number; label?: string }) {
  const [open, setOpen] = useState<boolean>(depth < 1);
  const keys = Object.keys(value);
  const pad = depth * 16;
  return (
    <div style={{ marginLeft: pad, fontFamily: "monospace" }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", padding: 0, font: "inherit" }}
        aria-expanded={open}
      >
        <span style={{ color: "var(--color-text-secondary)" }}>{open ? "▾" : "▸"} </span>
        {label !== undefined ? <span style={{ color: "var(--color-text-secondary)" }}>{label}: </span> : null}
        <span>{`{ ${keys.length} key${keys.length === 1 ? "" : "s"} }`}</span>
      </button>
      {open ? (
        <div>
          {keys.map(k => <JsonTree key={k} value={value[k]} depth={depth + 1} label={k} />)}
        </div>
      ) : null}
    </div>
  );
}

function ArrayNode({ value, depth, label }: { value: unknown[]; depth: number; label?: string }) {
  const [open, setOpen] = useState<boolean>(depth < 1);
  const pad = depth * 16;
  return (
    <div style={{ marginLeft: pad, fontFamily: "monospace" }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", padding: 0, font: "inherit" }}
        aria-expanded={open}
      >
        <span style={{ color: "var(--color-text-secondary)" }}>{open ? "▾" : "▸"} </span>
        {label !== undefined ? <span style={{ color: "var(--color-text-secondary)" }}>{label}: </span> : null}
        <span>{`[ ${value.length} item${value.length === 1 ? "" : "s"} ]`}</span>
      </button>
      {open ? (
        <div>
          {value.map((v, i) => <JsonTree key={i} value={v} depth={depth + 1} label={String(i)} />)}
        </div>
      ) : null}
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
const panelHeadingStyle: React.CSSProperties = { margin: 0, fontSize: 14, color: "var(--color-text-primary)" };
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
