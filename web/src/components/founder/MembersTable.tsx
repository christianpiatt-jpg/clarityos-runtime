// components/founder/MembersTable.tsx — #150: every account, newest first,
// 50 per page. "Active 4" finally has a list of who. Click a row to select
// it for Manual ops. Rows are the server's projection: no hash, no salt, no
// operator id ever crosses the wire.

import { useCallback, useEffect, useState } from "react";
import { founderMembersList, type FounderMemberRow } from "../../lib/api";

interface Props {
  onSelect: (email: string) => void;
  /** bump to refetch (after a create) */
  refreshKey?: number;
  pageSize?: number;
}

function when(ts: number | null): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return Number.isNaN(d.getTime()) ? "—" : d.toISOString().slice(0, 10);
}

export default function MembersTable({ onSelect, refreshKey = 0, pageSize = 50 }: Props) {
  const [rows, setRows] = useState<FounderMemberRow[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (off: number) => {
    setError(null);
    try {
      const r = await founderMembersList({ limit: pageSize, offset: off });
      setRows(r.members);
      setHasMore(r.has_more);
      setOffset(off);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [pageSize]);

  useEffect(() => { void load(0); }, [load, refreshKey]);

  return (
    <section style={panelStyle} data-testid="members-table">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Members</h2>
        <span style={{ fontSize: 11, color: "#666" }}>
          {rows ? (rows.length ? `${offset + 1}–${offset + rows.length}` : "0") : "…"}
        </span>
      </div>
      {error && <div style={errorStyle}>{error}</div>}
      {rows && rows.length === 0 && (
        <div style={{ color: "#666", fontSize: 13 }} data-testid="members-empty">No accounts yet.</div>
      )}
      {rows && rows.length > 0 && (
        // capped: 50 rows must not push Manual ops (which a row-click feeds)
        // below the fold of the two-column grid
        <div style={{ maxHeight: 420, overflowY: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "#666" }}>
              <th style={th}>email</th><th style={th}>cohort</th><th style={th}>status</th>
              <th style={th}>tier</th><th style={th}>created</th><th style={th}>balance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr
                key={m.email}
                data-testid="members-row"
                onClick={() => onSelect(m.email)}
                style={{ cursor: "pointer" }}
                title="select for Manual ops"
              >
                <td style={td}><code>{m.email}</code></td>
                <td style={td}>{m.cohort ?? "—"}</td>
                <td style={td}>{m.membership_status ?? "—"}</td>
                <td style={td}>{m.membership_tier ?? "—"}</td>
                <td style={td}>{when(m.created_at)}</td>
                <td style={td}>{m.balance_display}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button type="button" disabled={offset === 0} onClick={() => void load(Math.max(0, offset - pageSize))}
                data-testid="members-prev">prev</button>
        <button type="button" disabled={!hasMore} onClick={() => void load(offset + pageSize)}
                data-testid="members-next">next</button>
      </div>
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd", borderRadius: 6, padding: 12, background: "#fff", marginBottom: 12,
};
const th: React.CSSProperties = { padding: "4px 6px", borderBottom: "1px solid #ddd", fontWeight: 600 };
const td: React.CSSProperties = { padding: "4px 6px", borderBottom: "1px solid #eee" };
const errorStyle: React.CSSProperties = {
  padding: 6, background: "#fee", border: "1px solid #f99", borderRadius: 4, fontSize: 12, marginBottom: 6,
};
