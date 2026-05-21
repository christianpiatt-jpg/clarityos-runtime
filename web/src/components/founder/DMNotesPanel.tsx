// components/founder/DMNotesPanel.tsx — manual DM tracker.
//
// Lists DMs (filterable by channel + selected user), supports adding a
// new DM and appending notes to an existing one.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  founderDMAdd, founderDMList, founderDMNote,
  type V33DM, type V33DMChannel, type V33DMNote,
} from "../../lib/api";

const CHANNELS: ReadonlyArray<{ value: V33DMChannel | ""; label: string }> = [
  { value: "", label: "All channels" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "facebook", label: "Facebook" },
  { value: "email", label: "Email" },
  { value: "manual", label: "Manual" },
];

interface Props {
  scopeUser?: string;
}

export default function DMNotesPanel({ scopeUser }: Props) {
  const [channel, setChannel] = useState<V33DMChannel | "">("");
  const [dms, setDms] = useState<V33DM[]>([]);
  const [selectedDm, setSelectedDm] = useState<string | null>(null);
  const [notesByDm, setNotesByDm] = useState<Record<string, V33DMNote[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Add-DM form
  const [newChannel, setNewChannel] = useState<V33DMChannel>("manual");
  const [newSubject, setNewSubject] = useState("");
  const [newSnippet, setNewSnippet] = useState("");
  const [newUser, setNewUser] = useState("");

  // Add-note form
  const [noteBody, setNoteBody] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await founderDMList({
        ...(channel ? { channel } : {}),
        ...(scopeUser ? { user: scopeUser } : {}),
        limit: 200,
      });
      setDms(r.dms);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [channel, scopeUser]);

  useEffect(() => { void refresh(); }, [refresh]);

  const filtered = useMemo(() => dms, [dms]);

  const addDm = useCallback(async () => {
    setError(null);
    try {
      await founderDMAdd({
        channel: newChannel,
        user: newUser.trim() || undefined,
        subject: newSubject.trim() || undefined,
        snippet: newSnippet.trim() || undefined,
      });
      setNewSubject("");
      setNewSnippet("");
      setNewUser("");
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [newChannel, newUser, newSubject, newSnippet, refresh]);

  const addNote = useCallback(async () => {
    if (!selectedDm || !noteBody.trim()) return;
    setError(null);
    try {
      const r = await founderDMNote(selectedDm, noteBody.trim());
      setNotesByDm((m) => ({ ...m, [selectedDm]: r.notes }));
      setNoteBody("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [selectedDm, noteBody]);

  const select = useCallback(async (dm: V33DM) => {
    setSelectedDm(dm.id);
    if (notesByDm[dm.id]) return;
    try {
      // Fetch the existing notes for this DM. We don't have a list-only
      // endpoint, so trigger a no-op note add — the server returns the
      // current set. Skip on empty body so we don't create a stub.
      // Instead, just leave the notes empty and let the user add one.
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [notesByDm]);

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>DM inbox</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as V33DMChannel | "")}
            aria-label="Channel filter"
            style={{ fontSize: 12, padding: "4px 6px" }}
          >
            {CHANNELS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <button onClick={() => void refresh()} disabled={busy}>Refresh</button>
        </div>
      </div>

      {/* Add-DM form */}
      <details style={{ marginBottom: 8 }}>
        <summary style={{ cursor: "pointer", fontSize: 13 }}>Add a new DM</summary>
        <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
          <select
            value={newChannel}
            onChange={(e) => setNewChannel(e.target.value as V33DMChannel)}
            style={inputStyle}
            aria-label="New DM channel"
          >
            <option value="manual">manual</option>
            <option value="linkedin">linkedin</option>
            <option value="facebook">facebook</option>
            <option value="email">email</option>
          </select>
          <input
            type="text"
            value={newUser}
            onChange={(e) => setNewUser(e.target.value)}
            placeholder="ClarityOS username (optional)"
            style={inputStyle}
            aria-label="DM user"
          />
          <input
            type="text"
            value={newSubject}
            onChange={(e) => setNewSubject(e.target.value)}
            placeholder="Subject (optional)"
            style={inputStyle}
            aria-label="DM subject"
          />
          <textarea
            value={newSnippet}
            onChange={(e) => setNewSnippet(e.target.value)}
            placeholder="Snippet (≤ 500 chars)"
            rows={2}
            maxLength={500}
            style={{ ...inputStyle, resize: "vertical" }}
            aria-label="DM snippet"
          />
          <button onClick={() => void addDm()} disabled={busy}>Add DM</button>
        </div>
      </details>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {filtered.length === 0 && !busy && (
        <div style={mutedStyle}>No DMs match this filter.</div>
      )}
      {filtered.map((dm) => (
        <details
          key={dm.id}
          open={selectedDm === dm.id}
          onToggle={(e) => {
            const open = (e.target as HTMLDetailsElement).open;
            if (open) void select(dm);
            else if (selectedDm === dm.id) setSelectedDm(null);
          }}
          style={{
            marginBottom: 6,
            padding: "6px 10px",
            border: "1px solid #eee",
            borderRadius: 4,
            background: "#fafafa",
          }}
        >
          <summary style={{ cursor: "pointer", fontSize: 13, display: "flex", justifyContent: "space-between" }}>
            <span>
              <code>{dm.channel}</code>
              {" · "}
              <strong>{dm.subject || "(no subject)"}</strong>
              {dm.user ? <span style={{ color: "#666" }}> · {dm.user}</span> : null}
            </span>
            <span style={{ fontSize: 11, color: "#888" }}>
              {new Date(dm.ts * 1000).toISOString().slice(0, 16).replace("T", " ")}
            </span>
          </summary>
          {selectedDm === dm.id && (
            <div style={{ marginTop: 8 }}>
              {dm.snippet && <div style={{ fontSize: 12, color: "#444", marginBottom: 6 }}>{dm.snippet}</div>}
              <div style={{ fontSize: 12, marginBottom: 4, color: "#666" }}>
                Notes ({(notesByDm[dm.id] || []).length})
              </div>
              {(notesByDm[dm.id] || []).map((n) => (
                <div key={n.id} style={{ fontSize: 12, padding: "4px 0", borderTop: "1px dotted #ddd" }}>
                  <span style={{ color: "#888" }}>{new Date(n.ts * 1000).toISOString().slice(0, 16).replace("T", " ")}</span>
                  {" "}
                  {n.body}
                </div>
              ))}
              <textarea
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Append a note (≤ 4000 chars)"
                rows={2}
                maxLength={4000}
                style={{ ...inputStyle, marginTop: 6, resize: "vertical" }}
                aria-label="New note body"
              />
              <button onClick={() => void addNote()} disabled={!noteBody.trim()} style={{ marginTop: 4 }}>
                Add note
              </button>
            </div>
          )}
        </details>
      ))}
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 12,
  background: "#fff",
  marginBottom: 12,
};

const mutedStyle: React.CSSProperties = { color: "#666", fontSize: 13 };

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "6px 8px",
  fontSize: 13,
  border: "1px solid #ccc",
  borderRadius: 4,
  boxSizing: "border-box",
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "#fee",
  border: "1px solid #f99",
  borderRadius: 4,
  fontSize: 12,
  marginBottom: 6,
};
