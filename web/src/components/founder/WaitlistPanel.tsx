// components/founder/WaitlistPanel.tsx — founder-only waitlist console.
//
// Lists entries from /founder/waitlist with filter + search; a row click
// expands an inline editor for status / note / user_id (when converting).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  founderWaitlistList,
  founderWaitlistUpdate,
  type V32WaitlistEntry,
  type V32WaitlistStatus,
} from "../../lib/api";

const STATUS_FILTERS: ReadonlyArray<{ value: V32WaitlistStatus | ""; label: string }> = [
  { value: "", label: "All" },
  { value: "waiting", label: "Waiting" },
  { value: "contacted", label: "Contacted" },
  { value: "converted", label: "Converted" },
  { value: "dropped", label: "Dropped" },
];

const STATUS_COLORS: Record<V32WaitlistStatus, { bg: string; fg: string }> = {
  waiting:   { bg: "#eef", fg: "#447" },
  contacted: { bg: "#fff8e1", fg: "#a55" },
  converted: { bg: "#e6f5ec", fg: "#147" },
  dropped:   { bg: "#fde2e2", fg: "#922" },
};

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(Number(ts) * 1000).toISOString().slice(0, 16).replace("T", " "); }
  catch { return String(ts); }
}

export default function WaitlistPanel() {
  const [statusFilter, setStatusFilter] = useState<V32WaitlistStatus | "">("");
  const [search, setSearch] = useState("");
  const [entries, setEntries] = useState<V32WaitlistEntry[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await founderWaitlistList(
        statusFilter ? { status: statusFilter, limit: 500 } : { limit: 500 },
      );
      setEntries(r.entries);
      setCounts(r.counts);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void refresh(); }, [refresh]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) =>
      (e.email || "").toLowerCase().includes(q)
      || (e.name || "").toLowerCase().includes(q)
      || (e.note || "").toLowerCase().includes(q),
    );
  }, [entries, search]);

  return (
    <section
      style={{
        border: "1px solid #ddd",
        borderRadius: 6,
        padding: 16,
        background: "#fff",
      }}
    >
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 12,
      }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Waitlist</h2>
        <button onClick={() => void refresh()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <input
          type="search"
          placeholder="Search email / name / note"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, minWidth: 200, padding: "6px 8px", fontSize: 13 }}
          aria-label="Search waitlist"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as V32WaitlistStatus | "")}
          style={{ padding: "6px 8px", fontSize: 13 }}
          aria-label="Filter by status"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
              {f.value && counts[f.value] !== undefined ? ` (${counts[f.value]})` : ""}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div style={{
          padding: 8,
          background: "#fee",
          border: "1px solid #f99",
          borderRadius: 4,
          fontSize: 12,
          marginBottom: 8,
        }}>
          {error}
        </div>
      )}

      <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
        Showing {filtered.length} of {entries.length}
        {counts.total !== undefined ? ` (${counts.total} total)` : ""}
      </div>

      {filtered.length === 0 && !loading && (
        <div style={{ color: "#999", fontSize: 13 }}>No waitlist entries match this filter.</div>
      )}

      {filtered.map((entry) => (
        <Row key={entry.id} entry={entry} onChanged={refresh} />
      ))}
    </section>
  );
}

function Row({ entry, onChanged }: { entry: V32WaitlistEntry; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const sc = STATUS_COLORS[entry.status];
  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{
        border: "1px solid #eee",
        borderRadius: 4,
        marginBottom: 6,
        background: "#fafafa",
      }}
    >
      <summary
        style={{
          cursor: "pointer",
          padding: "8px 10px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
          gap: 8,
        }}
      >
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
          <strong>{entry.email}</strong>
          {entry.name ? <span style={{ color: "#666" }}> — {entry.name}</span> : null}
        </span>
        <span style={{
          padding: "1px 6px",
          background: sc.bg,
          color: sc.fg,
          borderRadius: 3,
          fontSize: 11,
        }}>
          {entry.status}
        </span>
        <span style={{ color: "#888", fontSize: 11, minWidth: 130, textAlign: "right" }}>
          {fmtTs(entry.created_ts)} · {entry.source}
        </span>
      </summary>
      {open && <Editor entry={entry} onChanged={onChanged} />}
    </details>
  );
}

function Editor({ entry, onChanged }: { entry: V32WaitlistEntry; onChanged: () => void }) {
  const [status, setStatus] = useState<V32WaitlistStatus>(entry.status);
  const [note, setNote] = useState<string>(entry.note ?? "");
  const [userId, setUserId] = useState<string>(entry.user_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: Parameters<typeof founderWaitlistUpdate>[0] = {
        id: entry.id,
        status,
      };
      if (note.trim() !== (entry.note ?? "")) payload.note = note.trim();
      if (status === "converted" && userId.trim()) payload.user_id = userId.trim();
      await founderWaitlistUpdate(payload);
      onChanged();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [entry.id, entry.note, status, note, userId, onChanged]);

  return (
    <div style={{ padding: "8px 10px 10px" }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr",
        gap: "4px 12px",
        fontSize: 12,
        marginBottom: 8,
      }}>
        <span style={{ color: "#666" }}>id</span>
        <code>{entry.id}</code>
        <span style={{ color: "#666" }}>email</span>
        <span>{entry.email}</span>
        <span style={{ color: "#666" }}>created</span>
        <span>{fmtTs(entry.created_ts)}</span>
        <span style={{ color: "#666" }}>updated</span>
        <span>{fmtTs(entry.updated_ts)}</span>
        {entry.contacted_ts && (
          <>
            <span style={{ color: "#666" }}>contacted</span>
            <span>{fmtTs(entry.contacted_ts)}</span>
          </>
        )}
        {entry.converted_ts && (
          <>
            <span style={{ color: "#666" }}>converted</span>
            <span>{fmtTs(entry.converted_ts)}</span>
          </>
        )}
      </div>

      <label style={{ display: "block", fontSize: 12, marginBottom: 6 }}>
        Status
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as V32WaitlistStatus)}
          style={{ marginLeft: 6, padding: "2px 6px", fontSize: 12 }}
          aria-label="Status"
        >
          <option value="waiting">waiting</option>
          <option value="contacted">contacted</option>
          <option value="converted">converted</option>
          <option value="dropped">dropped</option>
        </select>
      </label>

      {status === "converted" && (
        <label style={{ display: "block", fontSize: 12, marginBottom: 6 }}>
          User id <span style={{ color: "#888" }}>(required when converting)</span>
          <input
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            style={{
              display: "block",
              width: "100%",
              padding: "4px 6px",
              fontSize: 12,
              marginTop: 2,
              boxSizing: "border-box",
            }}
            aria-label="User id"
          />
        </label>
      )}

      <label style={{ display: "block", fontSize: 12, marginBottom: 6 }}>
        Note <span style={{ color: "#888" }}>(optional, 1000 chars)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          maxLength={1000}
          style={{
            display: "block",
            width: "100%",
            padding: "4px 6px",
            fontSize: 12,
            marginTop: 2,
            resize: "vertical",
            boxSizing: "border-box",
          }}
          aria-label="Note"
        />
      </label>

      {error && (
        <div style={{
          padding: 6,
          background: "#fee",
          border: "1px solid #f99",
          borderRadius: 3,
          fontSize: 11,
          marginBottom: 6,
        }}>
          {error}
        </div>
      )}

      <button onClick={() => void save()} disabled={busy}>
        {busy ? "Saving…" : "Save changes"}
      </button>
    </div>
  );
}
