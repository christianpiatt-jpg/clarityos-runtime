// components/settings/MemoryVaultPanel.tsx
// v46 — Memory Vault settings surface. Shows the global vault status
// (backend / encrypted / total keys) plus the caller's own vault
// counts, and lets the user manage their notes + embeddings inline.

import { useCallback, useEffect, useState } from "react";
import {
  meVaultEmbeddings, meVaultEmbeddingsDelete,
  meVaultNotes, meVaultNotesDelete, meVaultNotesPut,
  meVaultStatus,
  type V46VaultEmbedding, type V46VaultNote, type V46VaultStatusResponse,
} from "../../lib/api";

export default function MemoryVaultPanel() {
  const [status, setStatus] = useState<V46VaultStatusResponse | null>(null);
  const [notes, setNotes] = useState<V46VaultNote[]>([]);
  const [embeddings, setEmbeddings] = useState<V46VaultEmbedding[]>([]);
  const [draftKey, setDraftKey] = useState<string>("");
  const [draftText, setDraftText] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const [st, nn, ee] = await Promise.all([
        meVaultStatus(), meVaultNotes(), meVaultEmbeddings(),
      ]);
      setStatus(st);
      setNotes(nn.notes);
      setEmbeddings(ee.embeddings);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void loadAll(); }, [loadAll]);

  const saveNote = useCallback(async () => {
    const k = draftKey.trim();
    if (!k) { setError("Note key is required"); return; }
    setBusy("save"); setError(null);
    try {
      await meVaultNotesPut(k, draftText);
      setDraftKey("");
      setDraftText("");
      await loadAll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [draftKey, draftText, loadAll]);

  const editNote = useCallback((n: V46VaultNote) => {
    setDraftKey(n.key);
    setDraftText(n.text);
  }, []);

  const deleteNote = useCallback(async (key: string) => {
    setBusy("del-note"); setError(null);
    try {
      await meVaultNotesDelete(key);
      await loadAll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [loadAll]);

  const deleteEmbedding = useCallback(async (key: string) => {
    setBusy("del-emb"); setError(null);
    try {
      await meVaultEmbeddingsDelete(key);
      await loadAll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [loadAll]);

  return (
    <div style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Memory Vault</h2>
        <button
          type="button"
          onClick={() => void loadAll()}
          disabled={busy !== null}
          style={refreshStyle}
        >{busy === "load" ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {status && (
        <>
          <p style={helpStyle}>
            Encrypted local key/value store. Operator state, ELINS history,
            #G runs, notes, and embeddings live here. Backend:{" "}
            <code>{status.global.backend}</code> · scheme:{" "}
            <code>{status.global.scheme}</code>
            {status.global.encrypted ? " · encrypted" : " · plain (debug)"}
          </p>

          <div style={statRowStyle}>
            <Stat label="Total keys" value={String(status.user.vault_keys)} />
            <Stat label="Notes" value={String(status.user.notes_count)} />
            <Stat label="Embeddings" value={String(status.user.embeddings_count)} />
            <Stat label="ELINS history" value={String(status.user.elins_count)} />
            <Stat label="#G history" value={String(status.user.g_runs_count)} />
            <Stat label="Operator state" value={String(status.user.operator_state_count)} />
          </div>
        </>
      )}

      <h3 style={subHeader}>Notes</h3>
      <div style={composeStyle}>
        <input
          type="text"
          placeholder="key (e.g. team_brief)"
          value={draftKey}
          onChange={(e) => setDraftKey(e.target.value)}
          disabled={busy !== null}
          style={inputStyle}
        />
        <textarea
          placeholder="note text"
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
          disabled={busy !== null}
          rows={3}
          style={textareaStyle}
        />
        <button
          type="button"
          onClick={() => void saveNote()}
          disabled={busy !== null || !draftKey.trim()}
          style={ctaStyle}
        >{busy === "save" ? "Saving…" : "Save note"}</button>
      </div>

      <ul style={listStyle}>
        {notes.length === 0 && (
          <li style={mutedStyle}>No notes yet.</li>
        )}
        {notes.map((n) => (
          <li key={n.key} style={noteItemStyle}>
            <div style={{ flex: 1 }}>
              <code style={noteKeyStyle}>{n.key}</code>
              <div style={noteTextStyle}>{n.text}</div>
            </div>
            <div style={noteActionsStyle}>
              <button
                type="button"
                onClick={() => editNote(n)}
                disabled={busy !== null}
                style={actionStyle}
              >Edit</button>
              <button
                type="button"
                onClick={() => void deleteNote(n.key)}
                disabled={busy !== null}
                style={{ ...actionStyle, color: "#fca5a5" }}
              >Delete</button>
            </div>
          </li>
        ))}
      </ul>

      <h3 style={subHeader}>Embeddings</h3>
      <ul style={listStyle}>
        {embeddings.length === 0 && (
          <li style={mutedStyle}>No embeddings yet. (POST /me/vault/embeddings to add.)</li>
        )}
        {embeddings.map((e) => (
          <li key={e.key} style={noteItemStyle}>
            <div style={{ flex: 1 }}>
              <code style={noteKeyStyle}>{e.key}</code>
              <div style={mutedStyle}>dim: {e.dim}</div>
            </div>
            <div style={noteActionsStyle}>
              <button
                type="button"
                onClick={() => void deleteEmbedding(e.key)}
                disabled={busy !== null}
                style={{ ...actionStyle, color: "#fca5a5" }}
              >Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={statLabelStyle}>{label}</div>
      <code style={statValueStyle}>{value}</code>
    </div>
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
const helpStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-secondary, #A0A0A0)", margin: "0 0 10px 0",
};
const statRowStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
  gap: 8, marginBottom: 12,
};
const statLabelStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  textTransform: "uppercase", letterSpacing: 0.5,
};
const statValueStyle: React.CSSProperties = {
  fontSize: 14, color: "var(--os-text-primary, #fff)",
  fontFamily: "var(--font-mono, monospace)", display: "block", marginTop: 2,
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 14, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const composeStyle: React.CSSProperties = {
  display: "flex", flexDirection: "column", gap: 6, marginBottom: 8,
};
const inputStyle: React.CSSProperties = {
  width: "100%", padding: "6px 8px",
  background: "var(--os-deep, #0a0a0a)",
  color: "var(--os-text-primary, #fff)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-sm, 4px)", fontSize: 13,
  fontFamily: "var(--font-mono, monospace)", boxSizing: "border-box",
};
const textareaStyle: React.CSSProperties = {
  ...inputStyle, fontFamily: "inherit", resize: "vertical",
};
const ctaStyle: React.CSSProperties = {
  padding: "6px 12px",
  background: "var(--os-accent, #88f0d0)",
  color: "#04121b",
  border: "none",
  borderRadius: "var(--radius-pill, 999px)",
  fontSize: 12, fontWeight: 600, cursor: "pointer",
  alignSelf: "flex-start",
};
const listStyle: React.CSSProperties = {
  listStyle: "none", padding: 0, margin: 0,
};
const noteItemStyle: React.CSSProperties = {
  display: "flex", gap: 8, padding: "6px 0",
  borderBottom: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  alignItems: "flex-start",
};
const noteKeyStyle: React.CSSProperties = {
  fontSize: 11, fontFamily: "var(--font-mono, monospace)",
  color: "var(--os-accent, #88f0d0)",
};
const noteTextStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-primary, #fff)",
  marginTop: 2, whiteSpace: "pre-wrap",
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
};
const noteActionsStyle: React.CSSProperties = {
  display: "flex", flexDirection: "column", gap: 4,
};
const actionStyle: React.CSSProperties = {
  fontSize: 10, padding: "2px 8px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  borderRadius: "var(--radius-pill, 999px)", cursor: "pointer",
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
