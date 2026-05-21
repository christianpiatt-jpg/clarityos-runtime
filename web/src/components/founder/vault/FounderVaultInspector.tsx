// components/founder/vault/FounderVaultInspector.tsx
// v46 — Founder vault inspector. Lists every user with vault rows,
// drills into per-user keys grouped by namespace, and reads individual
// item values on demand.

import { useCallback, useEffect, useState } from "react";
import {
  founderVaultItem, founderVaultKeys, founderVaultUsers,
} from "../../../lib/api";

type VaultUser = { user_id: string; keys: number };

interface KeyDoc {
  user_id: string;
  count: number;
  keys: string[];
  by_namespace: Record<string, { count: number; keys: string[] }>;
}

interface ItemDoc {
  ok: boolean;
  user_id: string;
  key: string;
  value: unknown;
  namespace?: string;
  error?: string;
}

export default function FounderVaultInspector() {
  const [users, setUsers] = useState<VaultUser[]>([]);
  const [activeUser, setActiveUser] = useState<string | null>(null);
  const [keys, setKeys] = useState<KeyDoc | null>(null);
  const [item, setItem] = useState<ItemDoc | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    setBusy("users"); setError(null);
    try {
      const r = await founderVaultUsers();
      setUsers(r.users);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void loadUsers(); }, [loadUsers]);

  const openUser = useCallback(async (uid: string) => {
    setBusy("keys"); setError(null); setItem(null);
    setActiveUser(uid);
    try {
      const r = await founderVaultKeys(uid);
      setKeys(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setKeys(null);
    } finally { setBusy(null); }
  }, []);

  const openItem = useCallback(async (uid: string, key: string) => {
    setBusy("item"); setError(null);
    try {
      const r = await founderVaultItem(uid, key);
      setItem(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setItem(null);
    } finally { setBusy(null); }
  }, []);

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Vault Inspector</h2>
        <button
          type="button"
          onClick={() => void loadUsers()}
          disabled={busy !== null}
          style={refreshStyle}
        >{busy === "users" ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <div style={gridStyle}>
        <div>
          <h3 style={subHeader}>Users ({users.length})</h3>
          <ul style={listStyle}>
            {users.length === 0 && (
              <li style={mutedStyle}>No vaults yet.</li>
            )}
            {users.map((u) => {
              const on = u.user_id === activeUser;
              return (
                <li
                  key={u.user_id}
                  onClick={() => void openUser(u.user_id)}
                  style={{ ...rowStyle, ...(on ? rowOnStyle : {}) }}
                >
                  <code style={{ fontSize: 11 }}>{u.user_id}</code>
                  <span style={mutedStyle}>{u.keys} keys</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <h3 style={subHeader}>
            Keys{activeUser ? ` — ${activeUser}` : ""}
          </h3>
          {!activeUser && <p style={mutedStyle}>Pick a user to inspect.</p>}
          {keys && (
            <>
              {Object.entries(keys.by_namespace).map(([ns, info]) => (
                <div key={ns} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "var(--os-accent, #88f0d0)", marginBottom: 4 }}>
                    {ns} ({info.count})
                  </div>
                  <ul style={listStyle}>
                    {info.keys.map((k) => (
                      <li
                        key={k}
                        onClick={() => activeUser && void openItem(activeUser, k)}
                        style={rowStyle}
                      >
                        <code style={{ fontSize: 10, wordBreak: "break-all" }}>{k}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </>
          )}
        </div>

        <div>
          <h3 style={subHeader}>Item</h3>
          {!item && <p style={mutedStyle}>Click a key to view.</p>}
          {item && (
            <div style={itemBoxStyle}>
              <div style={mutedStyle}>{item.namespace}</div>
              <code style={{ fontSize: 10, wordBreak: "break-all" }}>{item.key}</code>
              <pre style={preStyle}>
                {item.error
                  ? `error: ${item.error}`
                  : JSON.stringify(item.value, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-md, 8px)",
  padding: 12,
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  marginBottom: 12,
};
const headerStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8,
};
const refreshStyle: React.CSSProperties = {
  fontSize: 11, padding: "3px 10px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  borderRadius: "var(--radius-pill, 999px)",
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 0, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const gridStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1.2fr 1.5fr", gap: 12,
};
const listStyle: React.CSSProperties = {
  listStyle: "none", padding: 0, margin: 0,
};
const rowStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "4px 6px",
  borderBottom: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  cursor: "pointer", gap: 6,
};
const rowOnStyle: React.CSSProperties = {
  background: "var(--os-deep, #0a0a0a)",
  borderLeft: "2px solid var(--os-accent, #88f0d0)",
};
const mutedStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
};
const itemBoxStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 8, background: "var(--os-deep, #0a0a0a)",
};
const preStyle: React.CSSProperties = {
  marginTop: 6, fontSize: 10,
  fontFamily: "var(--font-mono, monospace)",
  color: "var(--os-text-primary, #fff)",
  whiteSpace: "pre-wrap", wordBreak: "break-all",
  maxHeight: 320, overflow: "auto",
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
